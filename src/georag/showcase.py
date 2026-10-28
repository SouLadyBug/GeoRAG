"""Pre-generate the showcase: demo runs and the data files behind the static site.

The demo scenarios double as integration tests — each one runs the real engine end to end and
records every event it emits, so the static site can replay a run exactly as it happened.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path

import pandas as pd

from georag.schemas import Query

log = logging.getLogger("georag.showcase")

DEMOS: tuple[dict, ...] = (
    {
        "id": "analyze-ichkeul",
        "mode": "analyze",
        "title": "Water extent at Ichkeul, Feb 2020 vs Feb 2025",
        "question": "Map MNDWI water extent at Ichkeul for February 2020 vs February 2025.",
        "blurb": "Sentinel-2 composites, SCL cloud mask, change map and areas.",
    },
    {
        "id": "ask-water-indices",
        "mode": "ask",
        "title": "MNDWI vs NDWI for open water",
        "question": "How does MNDWI differ from NDWI for mapping open water, and when is each preferred?",
        "blurb": "Cited answer with a sentence-level support check.",
    },
    {
        "id": "analyze-bizerte-ndvi",
        "mode": "analyze",
        "title": "Summer NDVI around Bizerte",
        "question": "Compute NDVI around Bizerte for July 2024.",
        "blurb": "Vegetation index map and class statistics.",
    },
    {
        "id": "design-rooftop-solar",
        "mode": "design",
        "title": "Study design: rooftop solar from airborne LiDAR",
        "question": "Design a study on rooftop solar potential from airborne LiDAR in a Mediterranean city.",
        "blurb": "Six-section brief with dataset links and references.",
    },
    {
        "id": "explore-foundation-wetlands",
        "mode": "explore",
        "title": "Foundation models ↔ wetlands",
        "question": "How are foundation models and wetlands connected in the corpus?",
        "blurb": "Concept paths and the passages behind each link.",
    },
    {
        "id": "explore-lidar-twins",
        "mode": "explore",
        "title": "LiDAR ↔ digital twins",
        "question": "How are LiDAR and digital twins connected in the corpus?",
        "blurb": "Knowledge-graph subgraph between two fields.",
    },
    {
        "id": "ask-lidar-roofs",
        "mode": "ask",
        "title": "Roof planes from airborne LiDAR",
        "question": "How are roof planes extracted from airborne LiDAR point clouds for LoD2 building models?",
        "blurb": "Methods across reconstruction papers, cited.",
    },
    {
        "id": "ask-refusal",
        "mode": "ask",
        "title": "Out of scope: the assistant declines",
        "question": "How many tourists visited Lake Ichkeul in the summer of 2023?",
        "blurb": "Refuses rather than guesses when the corpus has no answer.",
    },
)


def run_demo(engine, demo: dict, out_dir: Path) -> dict:
    events: list[dict] = []
    t0 = time.perf_counter()
    q = Query(question=demo["question"], mode=demo["mode"])
    result = engine.run(q, events.append, stream=True)
    seconds = time.perf_counter() - t0
    data = json.loads(result.model_dump_json())
    demo_dir = out_dir / demo["id"]
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir(parents=True)
    if demo["mode"] == "analyze":
        run_dir = engine.s.paths.runs / result.run_id
        for f in run_dir.iterdir():
            if f.suffix in (".png", ".tif", ".py") and not f.name.startswith("."):
                shutil.copy2(f, demo_dir / f.name)
    # Passages are large; keep the retrieval event light in the recording.
    for e in events:
        if e.get("type") == "retrieval":
            for p in e.get("passages", []):
                p["chunk"]["text"] = p["chunk"]["text"][:600]
    (demo_dir / "run.json").write_text(
        json.dumps(
            {"query": q.model_dump(), "events": events, "result": data, "seconds": round(seconds, 1)},
            default=str,
        )
    )
    log.info("%s done in %.0f s", demo["id"], seconds)
    return {k: demo[k] for k in ("id", "mode", "question", "title", "blurb")} | {"seconds": round(seconds, 1)}


def generate_demos(engine, out_dir: Path, only: list[str] | None = None) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.json"
    existing = {d["id"]: d for d in json.loads(index_path.read_text())} if index_path.exists() else {}
    for demo in DEMOS:
        if only and demo["id"] not in only:
            continue
        try:
            existing[demo["id"]] = run_demo(engine, demo, out_dir)
        except Exception as exc:
            log.exception("demo %s failed: %s", demo["id"], exc)
    ordered = [existing[d["id"]] for d in DEMOS if d["id"] in existing]
    index_path.write_text(json.dumps(ordered, indent=2))
    return ordered


def export_sources(manifest: Path, out: Path) -> int:
    df = pd.read_parquet(manifest)
    cols = ["doc_id", "source", "domain", "title", "authors", "year", "url", "licence"]
    df = df[cols].copy()
    df["year"] = df["year"].astype("Int64")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(df.to_json(orient="records"))
    return len(df)
