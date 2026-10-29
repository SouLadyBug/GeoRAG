"""Paraphrase the factual questions and rerun the retrieval ablation on them."""

from __future__ import annotations

import json
import logging

from georag.config import get_settings
from georag.engine import Engine
from georag.eval.bench import build_paraphrased, load_bench
from georag.eval.run import retrieval_ablation


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    s = get_settings()
    eng = Engine(s)
    bench = load_bench(s.paths.bench)
    items = build_paraphrased(bench["qa"], eng.llm, s.paths.bench / "paraphrased.jsonl")
    out = retrieval_ablation(eng, items)
    (s.paths.results / "retrieval_ablation_paraphrased.json").write_text(json.dumps(out, indent=1))
    sizes = json.loads((s.paths.results / "bench_sizes.json").read_text())
    sizes["paraphrased"] = len(items)
    (s.paths.results / "bench_sizes.json").write_text(json.dumps(sizes, indent=2))


if __name__ == "__main__":
    main()
