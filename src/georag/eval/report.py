"""Turn ``results/*.json`` into charts, ``results/REPORT.md`` and the site's ``data/site.json``."""

from __future__ import annotations

import json
import platform
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SHORT = {
    "BM25": "BM25",
    "Dense": "Dense",
    "Hybrid (RRF)": "Hybrid\n(RRF)",
    "Hybrid + graph": "+ graph",
    "Hybrid + rerank": "+ rerank",
    "Full: hybrid + graph + rerank": "Full",
}
DARK = {
    "bg": "#0b1120",
    "fg": "#e2e8f0",
    "muted": "#94a3b8",
    "grid": "#1e293b",
    "a": "#2dd4bf",
    "b": "#38bdf8",
}


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def _style(ax):
    ax.set_facecolor(DARK["bg"])
    ax.tick_params(colors=DARK["muted"])
    for s in ax.spines.values():
        s.set_color(DARK["grid"])
    ax.yaxis.grid(True, color=DARK["grid"], lw=0.8)
    ax.set_axisbelow(True)


def ablation_chart(retrieval: dict, out: Path, paraphrased: dict | None = None) -> Path:
    names = list(retrieval["configs"])
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), facecolor=DARK["bg"])
    for ax, (metric, title) in zip(
        axes, (("recall@5", "Recall@5"), ("mrr@10", "MRR@10"), ("ndcg@10", "nDCG@10")), strict=True
    ):
        _style(ax)
        x = range(len(names))
        series = [
            (
                "factual (generated wording)",
                [retrieval["configs"][n]["summary"]["factual"][metric] for n in names],
                DARK["a"],
            )
        ]
        if paraphrased:
            series.append(
                (
                    "factual (paraphrased)",
                    [
                        paraphrased["configs"][n]["summary"].get("paraphrased", {}).get(metric, 0)
                        for n in names
                    ],
                    "#a78bfa",
                )
            )
        series.append(
            (
                "cross-domain",
                [retrieval["configs"][n]["summary"].get("cross", {}).get(metric, 0) for n in names],
                DARK["b"],
            )
        )
        w = 0.8 / len(series)
        groups = []
        for j, (label, vals, color) in enumerate(series):
            offs = (j - (len(series) - 1) / 2) * w
            groups.append(ax.bar([i + offs for i in x], vals, w, color=color, label=label))
        for bars in groups:
            for b in bars:
                ax.text(
                    b.get_x() + b.get_width() / 2,
                    b.get_height() + 0.012,
                    f"{b.get_height():.2f}",
                    ha="center",
                    color=DARK["fg"],
                    fontsize=7.5,
                )
        ax.set_xticks(list(x), [SHORT.get(n, n) for n in names], fontsize=8.5)
        ax.set_ylim(0, 1.05)
        ax.set_title(title, color=DARK["fg"])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=len(labels),
        frameon=False,
        labelcolor=DARK["fg"],
        fontsize=10,
    )
    fig.suptitle("GeoRAG-Bench retrieval ablation", color=DARK["fg"], fontsize=14)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out, dpi=140, facecolor=DARK["bg"])
    plt.close(fig)
    return out


def analyze_chart(analyze: dict, out: Path) -> Path:
    ok = [r for r in analyze["items"] if r.get("ok") and r.get("reference_km2")]
    fig, ax = plt.subplots(figsize=(6.2, 5.6), facecolor=DARK["bg"])
    _style(ax)
    ax.xaxis.grid(True, color=DARK["grid"], lw=0.8)
    xs = [r["reference_km2"] for r in ok]
    ys = [r["water_km2"] for r in ok]
    lim = (min(xs + ys) * 0.7, max(xs + ys) * 1.4)
    ax.plot(lim, lim, ls="--", color=DARK["muted"], lw=1)
    ax.scatter(xs, ys, s=46, color=DARK["a"], edgecolor=DARK["bg"], zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("JRC Global Surface Water, occurrence ≥ 50 % (km²)", color=DARK["muted"])
    ax.set_ylabel("GeoRAG Analyze, Sentinel-2 MNDWI (km²)", color=DARK["muted"])
    ax.set_title(
        f"{len(ok)} lake-month tasks · median error {analyze['median_abs_pct_error']:.1f} %", color=DARK["fg"]
    )
    fig.tight_layout()
    fig.savefig(out, dpi=140, facecolor=DARK["bg"])
    plt.close(fig)
    return out


def _fmt(x, pct=False, digits=3):
    if x is None:
        return "—"
    return f"{100 * x:.1f} %" if pct else f"{x:.{digits}f}"


def write_report(results: Path, models: dict) -> Path:
    corpus = _load(results / "corpus_stats.json") or {}
    graph = _load(results / "graph_stats.json") or {}
    retrieval = _load(results / "retrieval_ablation.json")
    answers = _load(results / "answers_summary.json")
    answers_small = _load(results / "answers_small_summary.json")
    analyze = _load(results / "analyze_summary.json")
    bench = _load(results / "bench_sizes.json") or {}
    lines = [
        "# GeoRAG Copilot — evaluation report",
        "",
        f"_Generated {time.strftime('%Y-%m-%d')} by `make eval`. All numbers in this file are produced by the code in `src/georag/eval/`._",
        "",
        "## Setup",
        "",
        f"- **Hardware:** {models['hardware']} (tier `{models['tier']}`)",
        f"- **Generator:** `{models['generator']}`"
        + (f"; small generator `{models['generator_small']}`" if models.get("generator_small") else ""),
        f"- **Embedding:** `{models['embedding']}` · **Reranker:** `{models['reranker']}`",
        f"- **Corpus:** {corpus.get('documents', '—')} documents ({', '.join(f'{k}: {v}' for k, v in corpus.get('by_source', {}).items())}); "
        f"knowledge graph with {graph.get('nodes', '—')} concepts and {graph.get('edges', '—')} links.",
        f"- **GeoRAG-Bench:** {', '.join(f'{v} {k}' for k, v in bench.items())}.",
        "",
    ]
    if retrieval:
        lines += [
            "## 1. Retrieval ablation",
            "",
            "Gold = the passage a question was generated from (both passages for cross-domain questions). "
            "Hybrid = BM25 and dense lists fused with reciprocal rank fusion (k = 60); the graph list enters fusion with weight 0.6; "
            "the reranker reorders the fused top 20 (CPU tier; 30 on GPU tiers).",
            "",
            "| Configuration | R@5 | R@10 | MRR@10 | nDCG@10 | Cross both@8 | Cross nDCG@10 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for name, c in retrieval["configs"].items():
            f, x = c["summary"]["factual"], c["summary"].get("cross", {})
            lines.append(
                f"| {name} | {_fmt(f['recall@5'])} | {_fmt(f['recall@10'])} | {_fmt(f['mrr@10'])} | {_fmt(f['ndcg@10'])} | {_fmt(x.get('all@8'))} | {_fmt(x.get('ndcg@10'))} |"
            )
        full = (
            retrieval["configs"]
            .get("Full: hybrid + graph + rerank", {})
            .get("summary", {})
            .get("factual", {})
        )
        if full.get("recall@5_ci95"):
            lo, hi = full["recall@5_ci95"]
            lines += [
                "",
                f"95 % bootstrap interval for the full system's factual Recall@5: {lo:.3f}–{hi:.3f}.",
            ]
        para = _load(results / "retrieval_ablation_paraphrased.json")
        if para:
            lines += [
                "",
                f"**Paraphrased questions.** The {para['n']} factual questions were reworded by the generator to limit word overlap "
                "with the original question (and hence with the gold passage), keeping the same gold passages:",
                "",
                "| Configuration | R@5 | R@10 | MRR@10 | nDCG@10 |",
                "|---|---:|---:|---:|---:|",
            ]
            for name, c in para["configs"].items():
                f = c["summary"].get("paraphrased", {})
                lines.append(
                    f"| {name} | {_fmt(f.get('recall@5'))} | {_fmt(f.get('recall@10'))} | {_fmt(f.get('mrr@10'))} | {_fmt(f.get('ndcg@10'))} |"
                )
        lines += [
            "",
            "The figure-index stage (`+ figures`) is implemented for the PDF path but not evaluated: the abstract corpus contains no figures.",
            "",
            "![Retrieval ablation](ablation.png)",
            "",
        ]
    if answers:
        lines += [
            "## 2. End-to-end answers (Ask mode, full retrieval)",
            "",
            "| Set | n | Refused | Faithfulness | Citation precision | Gold cited | Answer recall | Token F1 | Median s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for tag, summ in (("", answers), (" (small generator)", answers_small or {})):
            for k in ("factual", "cross", "unanswerable"):
                s = summ.get(k)
                if not s:
                    continue
                lines.append(
                    f"| {k}{tag} | {s['n']} | {_fmt(s['refusal_rate'], True)} | {_fmt(s.get('faithfulness'), True)} | {_fmt(s.get('citation_precision'), True)} | "
                    f"{_fmt(s.get('gold_cited'), True)} | {_fmt(s.get('answer_recall'), True)} | {_fmt(s.get('token_f1'))} | {s.get('median_seconds', '—')} |"
                )
        lines += [
            "",
            "*Faithfulness* is the share of answer sentences whose cited passage the reranker judges as supporting (P(yes) ≥ 0.25); "
            "*citation precision* is the same at the level of individual citations; *refused* on the unanswerable set is the correct-refusal rate, "
            "and on the answerable sets it is the false-refusal rate.",
            "",
        ]
    if analyze:
        lines += [
            "## 3. Analyze tasks",
            "",
            f"{analyze['n']} natural-language requests (one lake, one month each). Success rate **{_fmt(analyze['success_rate'], True)}** "
            f"({_fmt(analyze['first_try_success_rate'], True)} on the first attempt; mean {analyze['mean_repairs']} repairs). "
            f"Water area against JRC GSW occurrence ≥ 50 %: median absolute error **{analyze['median_abs_pct_error']} %**, "
            f"{_fmt(analyze['within_10pct'], True)} of tasks within 10 %, mean IoU {analyze['mean_iou']}.",
            "",
            "| Lake | Month | GeoRAG km² | JRC km² | Error | IoU | Attempts |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for r in analyze["items"]:
            lines.append(
                f"| {r['lake']} | {r['month']} | {_fmt(r.get('water_km2'), digits=2)} | {_fmt(r.get('reference_km2'), digits=2)} | "
                f"{(str(r['abs_pct_error']) + ' %') if r.get('abs_pct_error') is not None else ('failed' if not r['ok'] else '—')} | {_fmt(r.get('iou'), digits=2)} | {r['attempts']} |"
            )
        lines += ["", "![Analyze vs JRC](analyze_vs_jrc.png)", ""]
    lines += [
        "## Limitations",
        "",
        "1. **Synthetic questions.** Factual and cross-domain questions were written by the local generator from the gold passages and filtered automatically "
        "(self-contained wording, answer words present in the passage). This favours lexical overlap with the gold passage and the generator's own phrasing; "
        "absolute scores are optimistic, the differences between configurations are the informative part. `eval/bench/review_sample.md` lists a random 10 % for manual checking.",
        "2. **Abstracts, not full text.** Full-text hosts were not reachable from the build machine, so the corpus is arXiv titles and abstracts (CC0 metadata) "
        "plus technical documentation and dataset descriptions. The OpenAlex CC BY full-text path (`georag corpus --source openalex`) is implemented but was not run.",
        "3. **Automatic judges.** Faithfulness and citation precision are judged by a 0.6B cross-encoder, which measures whether a passage plausibly supports a sentence, not whether the sentence is true.",
        "4. **Reference data.** JRC GSW occurrence summarises 1984–2021; a single month in 2020 or 2024 legitimately differs, especially for seasonal or regulated lakes.",
        "5. **Scope of Analyze.** Tasks are single-step template analyses. Complex multi-step GIS workflows, where GIS Copilot and GeoAnalystBench report the largest failure rates, are not evaluated and no parity is claimed.",
        "6. **Sample sizes.** On the CPU tier each end-to-end answer takes about a minute, so the answer evaluation uses a stratified "
        "100 of the 200 factual questions (20 per domain), and cross-domain generation was stopped at 27 accepted questions (about one "
        "generation in five passes the automatic filter). Bootstrap intervals in `results/retrieval_ablation.json` show the resulting uncertainty.",
        "",
    ]
    out = results / "REPORT.md"
    out.write_text("\n".join(lines))
    return out


def _strip_items(data: dict | None) -> dict | None:
    if data:
        for c in data["configs"].values():
            c.pop("items", None)
    return data


def build_site_json(
    results: Path,
    site_dir: Path,
    models: dict,
    graph_overview: dict,
    chunks: int,
    hero: tuple[str, str] | None,
) -> Path:
    corpus = _load(results / "corpus_stats.json") or {}
    years = sorted(int(y) for y in corpus.get("papers_by_year", {}))
    retrieval = _load(results / "retrieval_ablation.json")
    if retrieval:
        for c in retrieval["configs"].values():
            c.pop("items", None)
    compute = []
    log = results / "compute_log.jsonl"
    if log.exists():
        compute = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    site = {
        "generated": time.strftime("%Y-%m-%d"),
        "author": {"name": "Emna Saada", "github": "https://github.com/emna-saada", "linkedin": None},
        "models": models,
        "corpus": {
            "documents": corpus.get("documents"),
            "papers": sum(v for k, v in corpus.get("by_source", {}).items() if k in ("arxiv", "openalex")),
            "chunks": chunks,
            "by_domain": corpus.get("by_domain", {}),
            "by_source": corpus.get("by_source", {}),
            "papers_by_year": corpus.get("papers_by_year", {}),
            "year_range": f"{years[0]}–{years[-1]}" if years else "",
            "open_licence_papers": corpus.get("open_licence_papers"),
        },
        "graph": _load(results / "graph_stats.json"),
        "graph_overview": graph_overview,
        "benchmark": {
            "retrieval": retrieval,
            "retrieval_paraphrased": _strip_items(_load(results / "retrieval_ablation_paraphrased.json")),
            "answers": _load(results / "answers_summary.json"),
            "answers_small": _load(results / "answers_small_summary.json"),
            "analyze": _load(results / "analyze_summary.json"),
            "bench_sizes": _load(results / "bench_sizes.json"),
        },
        "compute": compute,
        "generation": _load(results / "generation_speed.json"),
    }
    if hero:
        site["hero_figure"], site["hero_caption"] = hero
    site_dir.mkdir(parents=True, exist_ok=True)
    out = site_dir / "site.json"
    out.write_text(json.dumps(site, default=str))
    return out


def hardware_string() -> str:
    import os

    from georag.hardware import detect_gpus

    gpus = detect_gpus()
    if gpus:
        return ", ".join(f"{g.name} ({g.vram_gb} GB)" for g in gpus)
    cpu = platform.processor() or platform.machine()
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return f"CPU only: {cpu}, {os.cpu_count()} threads"
