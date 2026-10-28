"""End-to-end tests on the 20-document fixture corpus with the light models and a scripted LLM."""

import json

import pytest

from georag.agent.modes import route
from georag.llm import ScriptedLLM, extract_json, strip_thinking
from georag.schemas import Query, RetrievalToggles


def test_index_artifacts(built_settings):
    idx = built_settings.paths.index
    for f in (
        "chunks.parquet",
        "bm25/ids.txt",
        "dense/vectors.npy",
        "graph/nodes.parquet",
        "graph/edges.parquet",
    ):
        assert (idx / f).exists(), f
    log = (built_settings.paths.results / "compute_log.jsonl").read_text().splitlines()
    assert {json.loads(x)["stage"] for x in log} >= {"chunk", "bm25", "dense", "graph"}


def test_index_is_idempotent(built_settings):
    from georag.pipeline import build_index

    before = (built_settings.paths.results / "compute_log.jsonl").read_text()
    build_index(built_settings, light=True)
    assert (built_settings.paths.results / "compute_log.jsonl").read_text() == before


@pytest.mark.parametrize(
    "toggles",
    [
        RetrievalToggles(bm25=True, dense=False, graph=False, rerank=False),
        RetrievalToggles(),
        RetrievalToggles(bm25=False, dense=False, graph=True, rerank=True),
    ],
)
def test_retrieval_finds_the_right_paper(engine, toggles):
    passages, trace = engine.retriever.retrieve(
        "Which water index uses the SWIR band for turbid lakes?", toggles, k=5
    )
    assert passages
    assert any("MNDWI" in p.chunk.title for p in passages[:3])
    if toggles.graph:
        assert "mndwi" in trace.entities or "lake_monitoring" in trace.entities


def test_domain_filter(engine):
    passages, _ = engine.retriever.retrieve(
        "point cloud segmentation", RetrievalToggles(), k=5, domains=["lidar"]
    )
    assert passages and all(p.chunk.domain == "lidar" for p in passages)


def test_ask_cites_and_checks_support(engine):
    events = []
    res = engine.ask_agent.run("Which water index uses the SWIR band for turbid lakes?", emit=events.append)
    assert not res.refused
    assert res.citations and res.citations[0].n == 1
    assert res.faithfulness is not None
    assert events[0]["type"] == "retrieval"


def test_ask_refuses_without_evidence(engine):
    res = engine.ask_agent.run("Who won the 2019 Wimbledon men's singles final?")
    assert res.refused


def test_ask_honours_llm_refusal(built_settings):
    from georag.engine import Engine

    eng = Engine(built_settings, light=True, llm=ScriptedLLM(lambda m: "INSUFFICIENT_EVIDENCE"))
    res = eng.ask_agent.run("Which water index uses the SWIR band for turbid lakes?")
    assert res.refused


def test_design_has_all_sections_and_references(engine):
    res = engine.design_agent.run(
        "Design a study on rooftop solar potential from airborne LiDAR in a Mediterranean city."
    )
    assert [s.key for s in res.sections] == ["question", "area", "data", "method", "validation", "risks"]
    assert "## References" in res.markdown
    assert res.citations


def test_explore_builds_subgraph(engine):
    res = engine.explore_agent.run("How are LiDAR and digital twins connected?")
    assert res.nodes and res.edges
    assert any(n.seed for n in res.nodes)


def test_router():
    assert route("Map MNDWI water extent at Ichkeul for February 2020 vs February 2025.")[0] == "analyze"
    assert route("Design a study on flood mapping in Tunis")[0] == "design"
    assert route("How are LiDAR and digital twins connected?")[0] == "explore"
    assert route("What is MNDWI?")[0] == "ask"


def test_engine_run_dispatch(engine):
    res = engine.run(Query(question="What is MNDWI?", mode="auto"))
    assert res.mode == "ask"


def test_json_helpers():
    assert extract_json('<think>hmm</think> Sure: ```json\n{"a": [1, {"b": "}"}]}\n```') == {
        "a": [1, {"b": "}"}]
    }
    assert strip_thinking("<think>x</think>Answer") == "Answer"


def test_api(built_settings, engine):
    from fastapi.testclient import TestClient

    from georag.server import create_app

    client = TestClient(create_app(engine=engine))
    assert client.get("/api/health").json()["llm"]["model"] == "scripted"
    with client.stream("POST", "/api/query", json={"question": "What is MNDWI?", "mode": "ask"}) as r:
        body = "".join(r.iter_text())
    assert "event: retrieval" in body and "event: result" in body
    from urllib.parse import quote

    cid = engine.chunks[0].chunk_id
    assert client.get(f"/api/chunk/{quote(cid, safe='')}").json()["chunk_id"] == cid
    assert client.get("/api/runs/../../etc/passwd").status_code == 404


@pytest.mark.network
def test_analyze_end_to_end(engine):
    res = engine.analyze_agent.run(
        "Map the open-water extent of Lake Bled (bbox 14.07, 46.35, 14.12, 46.375) in August 2023.",
        reference=True,
    )
    assert res.ok, res.attempts[-1].stderr
    assert 1.0 < res.numbers["water_km2"] < 1.7
    assert res.numbers["iou_vs_reference"] > 0.7
