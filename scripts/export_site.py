"""Export everything the static showcase needs into web/public/ (site.json, sources.json, charts)."""

from __future__ import annotations

import json
import shutil

from georag.config import get_settings
from georag.engine import Engine
from georag.eval.report import ablation_chart, analyze_chart, build_site_json, hardware_string, write_report
from georag.showcase import export_sources


def main() -> None:
    s = get_settings()
    res = s.paths.results
    web = s.paths.root / "web" / "public"
    eng = Engine(s, light=True)

    gen = (
        json.loads((res / "answers_summary.json").read_text()).get("generator")
        if (res / "answers_summary.json").exists()
        else s.llm.model
    )
    small = (
        json.loads((res / "answers_small_summary.json").read_text()).get("generator")
        if (res / "answers_small_summary.json").exists()
        else None
    )
    models = {
        "generator": gen,
        "generator_small": small,
        "embedding": s.retrieval.embedding_model,
        "reranker": s.retrieval.reranker_model,
        "tier": s.tier,
        "hardware": hardware_string(),
    }

    figs = res / "figures"
    figs.mkdir(exist_ok=True)
    if (res / "retrieval_ablation.json").exists():
        ablation_chart(json.loads((res / "retrieval_ablation.json").read_text()), res / "ablation.png")
    if (res / "analyze_summary.json").exists():
        analyze_chart(json.loads((res / "analyze_summary.json").read_text()), res / "analyze_vs_jrc.png")
    write_report(res, models)

    g = eng.graph
    top = sorted(g.g.nodes(data=True), key=lambda x: -x[1]["count"])[:90]
    keep = {n for n, _ in top}
    overview = {
        "nodes": [
            {"id": n, "label": d["label"], "type": d["type"], "degree": int(d["count"])} for n, d in top
        ],
        "edges": [
            {"source": a, "target": b, "weight": float(d["npmi"])}
            for a, b, d in g.g.subgraph(keep).edges(data=True)
            if d["count"] >= 8
        ],
    }
    hero = None
    hero_png = web / "demo" / "analyze-ichkeul" / "map.png"
    if hero_png.exists():
        run = json.loads((web / "demo" / "analyze-ichkeul" / "run.json").read_text())["result"]
        hero = ("demo/analyze-ichkeul/map.png", run.get("explanation", "").split(". ")[0] + ".")
    build_site_json(res, web / "data", models, overview, len(eng.chunks), hero)
    export_sources(s.paths.manifest, web / "data" / "sources.json")
    for name in ("ablation.png", "analyze_vs_jrc.png"):
        if (res / name).exists():
            shutil.copy2(res / name, web / "data" / name)
    print("site data exported")


if __name__ == "__main__":
    main()
