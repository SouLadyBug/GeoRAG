"""FastAPI backend for the live app.

``POST /api/query`` streams Server-Sent Events: ``route``, ``retrieval``, ``token``, ``plan``,
``code``, ``attempt``, ``section``, ``graph`` and finally ``result`` (or ``error``). The engine is
synchronous, so each query runs in a worker thread and pushes events through a queue.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from georag import __version__
from georag.config import get_settings
from georag.engine import Engine
from georag.schemas import Query

_LOCK = threading.Lock()  # one generation at a time on one GPU


def create_app(light: bool = False, engine: Engine | None = None) -> FastAPI:
    settings = get_settings()
    engine = engine or Engine(settings, light=light)
    app = FastAPI(title="GeoRAG Copilot", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict:
        llm_ok = bool(getattr(engine.llm, "available", lambda: True)())
        stats_path = settings.paths.results / "corpus_stats.json"
        return {
            "version": __version__,
            "tier": settings.tier,
            "llm": {"model": engine.llm.model, "available": llm_ok},
            "embedding": settings.retrieval.embedding_model,
            "reranker": settings.retrieval.reranker_model,
            "corpus": json.loads(stats_path.read_text()) if stats_path.exists() else None,
        }

    @app.post("/api/query")
    async def query(q: Query, request: Request):
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def emit(event: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def work() -> None:
            try:
                with _LOCK:
                    result = engine.run(q, emit, stream=True)
                emit({"type": "result", "result": json.loads(result.model_dump_json())})
            except Exception as exc:
                emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            finally:
                emit({"type": "_end"})

        threading.Thread(target=work, daemon=True).start()

        async def events():
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                if event["type"] == "_end":
                    break
                yield {"event": event["type"], "data": json.dumps(event, default=str)}

        return EventSourceResponse(events())

    @app.get("/api/chunk/{chunk_id:path}")
    def chunk(chunk_id: str) -> dict:
        c = engine.retriever.chunks.get(chunk_id)
        if c is None:
            raise HTTPException(404, "unknown chunk")
        return c.model_dump()

    @app.get("/api/sources")
    def sources(domain: str | None = None, q: str | None = None, limit: int = 100, offset: int = 0) -> dict:
        df = pd.read_parquet(settings.paths.manifest)
        if domain:
            df = df[df.domain == domain]
        if q:
            df = df[df.title.str.contains(q, case=False, regex=False)]
        page = df.iloc[offset : offset + limit]
        return {"total": len(df), "items": json.loads(page.to_json(orient="records"))}

    @app.get("/api/graph/overview")
    def graph_overview(limit: int = 60) -> dict:
        g = engine.graph
        if g is None:
            raise HTTPException(404, "graph not built")
        top = sorted(g.g.nodes(data=True), key=lambda x: -x[1]["count"])[:limit]
        keep = {n for n, _ in top}
        nodes = [{"id": n, "label": d["label"], "type": d["type"], "degree": d["count"]} for n, d in top]
        edges = [
            {"source": a, "target": b, "weight": d["npmi"]}
            for a, b, d in g.g.subgraph(keep).edges(data=True)
            if d["count"] >= 5
        ]
        return {"nodes": nodes, "edges": edges}

    @app.get("/api/runs/{run_id}/{name}")
    def run_file(run_id: str, name: str):
        base = settings.paths.runs.resolve()
        path = (base / run_id / name).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise HTTPException(404, "not found")
        return FileResponse(path)

    dist = Path(settings.paths.root) / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    else:

        @app.get("/")
        def root() -> JSONResponse:
            return JSONResponse(
                {"message": "API is running. Build the web app with `make web` or run `npm run dev` in web/."}
            )

    return app
