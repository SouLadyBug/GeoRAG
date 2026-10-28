"""Run GeoRAG-Bench: retrieval ablations, end-to-end answers, and Analyze tasks.

Results go to ``results/*.json``; :mod:`georag.eval.report` turns them into charts and the
paper-style ``results/REPORT.md``. Nothing on the website is typed by hand: every number there
is read from these files.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np

from georag.eval.metrics import (
    all_at_k,
    answer_recall,
    bootstrap_ci,
    mean,
    mrr,
    ndcg_at_k,
    recall_at_k,
    token_f1,
)
from georag.index.rerank import Scorer
from georag.schemas import RetrievalToggles

log = logging.getLogger("georag.eval")

CONFIGS: dict[str, RetrievalToggles] = {
    "BM25": RetrievalToggles(bm25=True, dense=False, graph=False, rerank=False),
    "Dense": RetrievalToggles(bm25=False, dense=True, graph=False, rerank=False),
    "Hybrid (RRF)": RetrievalToggles(bm25=True, dense=True, graph=False, rerank=False),
    "Hybrid + graph": RetrievalToggles(bm25=True, dense=True, graph=True, rerank=False),
    "Hybrid + rerank": RetrievalToggles(bm25=True, dense=True, graph=False, rerank=True),
    "Full: hybrid + graph + rerank": RetrievalToggles(bm25=True, dense=True, graph=True, rerank=True),
}


class CachedScorer:
    """Memoise (query, passage) scores so overlapping ablation configs rerank each pair once."""

    def __init__(self, inner: Scorer):
        self.inner = inner
        self.cache: dict[tuple[str, str, str], float] = {}
        self.pairs_scored = 0
        self.seconds = 0.0

    def score(self, query: str, docs: list[str], instruction: str = "") -> list[float]:
        keys = [(instruction, query, d) for d in docs]
        todo = [d for k, d in zip(keys, docs, strict=True) if k not in self.cache]
        if todo:
            t = time.perf_counter()
            fresh = (
                self.inner.score(query, todo, instruction) if instruction else self.inner.score(query, todo)
            )
            self.seconds += time.perf_counter() - t
            self.pairs_scored += len(todo)
            for d, s in zip(todo, fresh, strict=True):
                self.cache[(instruction, query, d)] = s
        return [self.cache[k] for k in keys]


def retrieval_ablation(engine, items: list[dict], k: int = 10) -> dict:
    retriever = engine.retriever
    cached = CachedScorer(engine.scorer)
    retriever.scorer = cached
    questions = [it["question"] for it in items]
    t = time.perf_counter()
    qvecs = engine.embedder.embed_queries(questions) if retriever.dense is not None else [None] * len(items)
    embed_s = time.perf_counter() - t
    out: dict = {"k": k, "n": len(items), "query_embedding_seconds": round(embed_s, 1), "configs": {}}
    for name, toggles in CONFIGS.items():
        t0 = time.perf_counter()
        per_item = []
        for it, qv in zip(items, qvecs, strict=True):
            passages, _ = retriever.retrieve(it["question"], toggles, k=k, query_vec=qv)
            ranked = [p.chunk.chunk_id for p in passages]
            gold = set(it["gold"])
            per_item.append(
                {
                    "id": it["id"],
                    "type": it["type"],
                    "recall@5": recall_at_k(ranked, gold, 5),
                    "recall@10": recall_at_k(ranked, gold, 10),
                    "all@8": all_at_k(ranked, gold, 8),
                    "mrr@10": mrr(ranked, gold, 10),
                    "ndcg@10": ndcg_at_k(ranked, gold, 10),
                    "top": ranked[:5],
                }
            )
        summary: dict[str, dict] = {}
        for subset in ("factual", "cross"):
            rows = [r for r in per_item if r["type"] == subset]
            if not rows:
                continue
            summary[subset] = {
                m: round(float(np.mean([r[m] for r in rows])), 4)
                for m in ("recall@5", "recall@10", "all@8", "mrr@10", "ndcg@10")
            }
            lo, hi = bootstrap_ci([r["recall@5"] for r in rows])
            summary[subset]["recall@5_ci95"] = [round(lo, 4), round(hi, 4)]
            summary[subset]["n"] = len(rows)
        out["configs"][name] = {
            "toggles": toggles.model_dump(),
            "summary": summary,
            "seconds": round(time.perf_counter() - t0, 1),
            "items": per_item,
        }
        log.info("%s %s", name, json.dumps(summary))
    out["rerank_pairs_scored"] = cached.pairs_scored
    out["rerank_seconds"] = round(cached.seconds, 1)
    retriever.scorer = engine.scorer
    return out


def answer_eval(engine, items: list[dict], out_path: Path | None = None) -> dict:
    """End-to-end Ask mode with the full retrieval stack. Resumable through ``out_path``."""
    agent = engine.ask_agent
    done: dict[str, dict] = {}
    if out_path and out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["id"]] = r
    for it in items:
        if it["id"] in done:
            continue
        t = time.perf_counter()
        try:
            res = agent.run(it["question"])
        except Exception as exc:
            log.warning("answer failed for %s: %s", it["id"], exc)
            continue
        cited_chunks = [c.chunk_id for c in res.citations]
        sentences = res.sentences
        cite_total = sum(len(s.citations) for s in sentences)
        cite_ok = sum(len(s.citations) for s in sentences if s.supported)
        row = {
            "id": it["id"],
            "type": it["type"],
            "question": it["question"],
            "gold_answer": it.get("answer"),
            "answer": res.answer,
            "refused": res.refused,
            "faithfulness": res.faithfulness,
            "n_sentences": len(sentences),
            "citations": cited_chunks,
            "citation_precision": (cite_ok / cite_total) if cite_total else None,
            "gold_cited": bool(set(it["gold"]) & set(cited_chunks)) if it["gold"] else None,
            "token_f1": token_f1(res.answer, it["answer"]) if it.get("answer") and not res.refused else None,
            "answer_recall": answer_recall(res.answer, it["answer"])
            if it.get("answer") and not res.refused
            else None,
            "top_rerank": res.passages[0].rerank_score if res.passages else None,
            "seconds": round(time.perf_counter() - t, 2),
            "timings": {k: round(v, 2) for k, v in res.timings.items()},
        }
        done[it["id"]] = row
        if out_path:
            with out_path.open("a") as f:
                f.write(json.dumps(row) + "\n")
        log.info(
            "%s refused=%s faith=%s f1=%s", it["id"], row["refused"], row["faithfulness"], row["token_f1"]
        )
    return summarise_answers(list(done.values()))


def summarise_answers(rows: list[dict]) -> dict:
    out: dict = {}
    for subset in ("factual", "cross", "unanswerable"):
        rs = [r for r in rows if r["type"] == subset]
        if not rs:
            continue
        answered = [r for r in rs if not r["refused"]]
        s = {
            "n": len(rs),
            "refusal_rate": round(sum(r["refused"] for r in rs) / len(rs), 4),
            "answered": len(answered),
        }
        if subset != "unanswerable":
            s.update(
                {
                    "faithfulness": _r(mean([r["faithfulness"] for r in answered])),
                    "citation_precision": _r(mean([r["citation_precision"] for r in answered])),
                    "gold_cited": _r(
                        mean([float(r["gold_cited"]) for r in answered if r["gold_cited"] is not None])
                    ),
                    "token_f1": _r(mean([r["token_f1"] for r in answered])),
                    "answer_recall": _r(mean([r["answer_recall"] for r in answered])),
                    "median_seconds": _r(float(np.median([r["seconds"] for r in rs]))),
                }
            )
        out[subset] = s
    return out


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def analyze_eval(engine, tasks: list[dict], runs_dir: Path, out_path: Path | None = None) -> dict:
    agent = engine.analyze_agent
    done: dict[str, dict] = {}
    if out_path and out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["id"]] = r
    for task in tasks:
        if task["id"] in done:
            continue
        t = time.perf_counter()
        try:
            res = agent.run(task["question"], reference=True, run_id=f"bench-{task['id']}")
            n = res.numbers
            est, ref = n.get("water_km2"), n.get("reference_km2")
            row = {
                "id": task["id"],
                "lake": task["lake"],
                "month": task["month"],
                "ok": res.ok,
                "attempts": len(res.attempts),
                "repairs": len(res.attempts) - 1,
                "errors": [a.error for a in res.attempts if a.error],
                "water_km2": est,
                "reference_km2": ref,
                "abs_pct_error": round(abs(est - ref) / ref * 100, 2)
                if res.ok and est is not None and ref
                else None,
                "iou": n.get("iou_vs_reference"),
                "observed_fraction": n.get("observed_fraction"),
                "scenes": n.get("scene_dates"),
                "seconds": round(time.perf_counter() - t, 1),
            }
        except Exception as exc:
            row = {
                "id": task["id"],
                "lake": task["lake"],
                "month": task["month"],
                "ok": False,
                "attempts": 0,
                "repairs": 0,
                "errors": [f"{type(exc).__name__}: {exc}"],
                "seconds": round(time.perf_counter() - t, 1),
            }
        done[task["id"]] = row
        if out_path:
            with out_path.open("a") as f:
                f.write(json.dumps(row) + "\n")
        log.info("%s ok=%s err=%s", task["id"], row["ok"], row.get("abs_pct_error"))
    rows = list(done.values())
    ok = [r for r in rows if r["ok"]]
    errs = [r["abs_pct_error"] for r in ok if r.get("abs_pct_error") is not None]
    return {
        "n": len(rows),
        "success_rate": round(len(ok) / len(rows), 4) if rows else None,
        "first_try_success_rate": round(sum(r["ok"] and r["repairs"] == 0 for r in rows) / len(rows), 4)
        if rows
        else None,
        "mean_repairs": round(float(np.mean([r["repairs"] for r in rows])), 3) if rows else None,
        "median_abs_pct_error": round(float(np.median(errs)), 2) if errs else None,
        "mean_iou": round(float(np.mean([r["iou"] for r in ok if r.get("iou") is not None])), 4)
        if ok
        else None,
        "within_10pct": round(sum(e <= 10 for e in errs) / len(errs), 4) if errs else None,
        "median_seconds": round(float(np.median([r["seconds"] for r in rows])), 1) if rows else None,
        "items": rows,
    }
