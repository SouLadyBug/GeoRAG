"""Generate GeoRAG-Bench question sets with the local LLM (resumable)."""

from __future__ import annotations

import argparse
import json
import logging
import random

from georag.config import get_settings
from georag.engine import Engine
from georag.eval.bench import build_cross, build_qa, load_bench


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-domain", type=int, default=40)
    ap.add_argument("--cross", type=int, default=27)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    s = get_settings()
    eng = Engine(s, light=True)  # question generation needs only the chunks, the graph and the LLM
    bench = s.paths.bench
    build_qa(eng.chunks, eng.llm, bench / "qa.jsonl", per_domain=args.per_domain)
    build_cross(eng.chunks, eng.graph, eng.llm, bench / "cross.jsonl", n=args.cross)
    b = load_bench(bench)
    sizes = {
        "factual": len(b["qa"]),
        "cross-domain": len(b["cross"]),
        "unanswerable": len(b["unanswerable"]),
        "analyze": len(b["analyze"]),
    }
    (s.paths.results / "bench_sizes.json").write_text(json.dumps(sizes, indent=2))

    # A random 10 % for a human spot check.
    rng = random.Random(3)
    sample = rng.sample(b["qa"] + b["cross"], k=max(1, (len(b["qa"]) + len(b["cross"])) // 10))
    by_id = {c.chunk_id: c for c in eng.chunks}
    lines = [
        "# GeoRAG-Bench spot-check sample",
        "",
        "A random 10 % of the generated questions with their gold passages. Mark each as OK / ambiguous / wrong.",
        "",
    ]
    for it in sample:
        lines += [f"## {it['id']}", "", f"**Q:** {it['question']}", "", f"**A:** {it['answer']}", ""]
        for g in it["gold"]:
            c = by_id.get(g)
            if c:
                lines += [f"> *{c.title}* — {c.text[:700]}", ""]
        lines += ["Verdict: ☐ OK ☐ ambiguous ☐ wrong", ""]
    (bench / "review_sample.md").write_text("\n".join(lines))
    print(json.dumps(sizes))


if __name__ == "__main__":
    main()
