"""Run GeoRAG-Bench and write results/ (each part is resumable and can be run on its own)."""

from __future__ import annotations

import argparse
import json
import logging

from georag.config import get_settings
from georag.engine import Engine
from georag.eval.bench import load_bench
from georag.eval.run import analyze_eval, answer_eval, retrieval_ablation, summarise_answers


def stratified(items: list[dict], per_domain: int) -> list[dict]:
    """The first ``per_domain`` questions of each domain (generation order is already random)."""
    if per_domain <= 0:
        return items
    out, seen = [], dict[str, int]()
    for it in items:
        if seen.get(it["domain"], 0) < per_domain:
            out.append(it)
            seen[it["domain"]] = seen.get(it["domain"], 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--parts",
        default="retrieval,answers,analyze",
        help="comma-separated: retrieval,answers,small,analyze",
    )
    ap.add_argument(
        "--small-model", default=None, help="model name served for the small-generator comparison"
    )
    ap.add_argument("--small-url", default=None, help="base URL of the small generator")
    ap.add_argument(
        "--small-n",
        type=int,
        default=50,
        help="factual questions for the small-generator run, stratified by domain (+ all unanswerable)",
    )
    ap.add_argument(
        "--factual-per-domain",
        type=int,
        default=20,
        help="factual questions per domain for the end-to-end answer run (0 = all)",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    s = get_settings()
    res = s.paths.results
    res.mkdir(parents=True, exist_ok=True)
    bench = load_bench(s.paths.bench)
    eng = Engine(s)
    parts = set(args.parts.split(","))

    if "retrieval" in parts:
        out = retrieval_ablation(eng, bench["qa"] + bench["cross"])
        (res / "retrieval_ablation.json").write_text(json.dumps(out, indent=1))

    if "answers" in parts:
        items = stratified(bench["qa"], args.factual_per_domain) + bench["cross"] + bench["unanswerable"]
        summary = answer_eval(eng, items, res / "answers.jsonl")
        summary["generator"] = eng.llm.model
        (res / "answers_summary.json").write_text(json.dumps(summary, indent=2))
        u = eng.llm.usage
        (res / "generation_speed.json").write_text(
            json.dumps(
                {
                    "model": eng.llm.model,
                    "calls": u.calls,
                    "completion_tokens": u.completion_tokens,
                    "seconds": round(u.seconds, 1),
                    "tokens_per_second": round(u.tokens_per_second, 2),
                },
                indent=2,
            )
        )

    if "small" in parts and args.small_model:
        from georag.llm import OpenAICompatLLM

        small = OpenAICompatLLM(
            args.small_url or s.llm.base_url, args.small_model, no_think=True, timeout_s=s.llm.timeout_s
        )
        eng_small = Engine(s, llm=small)
        eng_small.__dict__["retriever"] = eng.retriever  # share loaded indexes and models
        eng_small.__dict__["scorer"] = eng.scorer
        items = stratified(bench["qa"], args.small_n // 5) + bench["unanswerable"]
        summary = answer_eval(eng_small, items, res / "answers_small.jsonl")
        summary["generator"] = args.small_model
        (res / "answers_small_summary.json").write_text(json.dumps(summary, indent=2))

    if "analyze" in parts and bench["analyze"]:
        summary = analyze_eval(eng, bench["analyze"], s.paths.runs, res / "analyze.jsonl")
        (res / "analyze_summary.json").write_text(json.dumps(summary, indent=2))

    if (res / "answers.jsonl").exists() and "answers" not in parts:
        rows = [json.loads(line) for line in (res / "answers.jsonl").read_text().splitlines() if line.strip()]
        (res / "answers_summary.json").write_text(
            json.dumps(summarise_answers(rows) | {"generator": eng.llm.model}, indent=2)
        )


if __name__ == "__main__":
    main()
