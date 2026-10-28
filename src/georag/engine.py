"""Load the indexes and models once and expose the four modes behind one object."""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path

from georag.agent.analyze import AnalyzeAgent
from georag.agent.modes import AskAgent, DesignAgent, ExploreAgent, route
from georag.config import Settings, get_settings
from georag.index.dense import DenseIndex, HashingEmbedder, SentenceTransformerEmbedder
from georag.index.graph import KnowledgeGraph, load_glossary
from georag.index.rerank import LexicalScorer, QwenReranker
from georag.index.sparse import BM25Index
from georag.index.store import load_chunks
from georag.llm import OpenAICompatLLM
from georag.retrieval import Retriever
from georag.schemas import Query

log = logging.getLogger("georag")


class Engine:
    def __init__(self, settings: Settings | None = None, light: bool = False, llm=None):
        """``light`` skips the neural models (hashing embedder, lexical scorer) for tests."""
        self.s = settings or get_settings()
        self.light = light
        self._llm = llm

    @property
    def index_dir(self) -> Path:
        return self.s.paths.index

    @cached_property
    def chunks(self):
        return load_chunks(self.index_dir / "chunks.parquet")

    @cached_property
    def embedder(self):
        dense_model = (
            (self.index_dir / "dense" / "model.txt").read_text().strip()
            if (self.index_dir / "dense" / "model.txt").exists()
            else ""
        )
        if self.light or dense_model.startswith("hashing"):
            return HashingEmbedder(
                int(dense_model.split("-")[1]) if dense_model.startswith("hashing") else 256
            )
        return SentenceTransformerEmbedder(
            dense_model or self.s.retrieval.embedding_model, self.s.retrieval.device, self.s.paths.models
        )

    @cached_property
    def scorer(self):
        if self.light:
            return LexicalScorer()
        return QwenReranker(self.s.retrieval.reranker_model, self.s.retrieval.device)

    @cached_property
    def graph(self) -> KnowledgeGraph | None:
        path = self.index_dir / "graph"
        if not (path / "nodes.parquet").exists():
            return None
        return KnowledgeGraph.load(path, load_glossary(self.s.paths.glossary))

    @cached_property
    def retriever(self) -> Retriever:
        r = self.s.retrieval
        bm25 = (
            BM25Index.load(self.index_dir / "bm25")
            if (self.index_dir / "bm25" / "ids.txt").exists()
            else None
        )
        dense = (
            DenseIndex.load(self.index_dir / "dense")
            if (self.index_dir / "dense" / "vectors.npy").exists()
            else None
        )
        return Retriever(
            self.chunks,
            bm25,
            dense,
            self.embedder if dense else None,
            self.graph,
            self.scorer,
            r.rrf_k,
            r.candidates,
            r.rerank_top_k,
            r.graph_hops,
        )

    @property
    def llm(self):
        if self._llm is None:
            c = self.s.llm
            self._llm = OpenAICompatLLM(
                c.base_url, c.model, c.api_key, c.temperature, c.max_tokens, c.timeout_s, c.no_think
            )
        return self._llm

    @cached_property
    def ask_agent(self) -> AskAgent:
        r = self.s.retrieval
        return AskAgent(
            self.retriever, self.llm, self.scorer, r.refusal_threshold, r.support_threshold, k=r.final_k
        )

    @cached_property
    def design_agent(self) -> DesignAgent:
        return DesignAgent(self.retriever, self.llm, self.scorer, self.s.retrieval.support_threshold)

    @cached_property
    def explore_agent(self) -> ExploreAgent:
        if self.graph is None:
            raise RuntimeError("the knowledge graph has not been built; run `georag index`")
        return ExploreAgent(self.retriever, self.graph, self.llm)

    @cached_property
    def analyze_agent(self) -> AnalyzeAgent:
        sb = self.s.sandbox
        return AnalyzeAgent(
            self.retriever,
            self.llm,
            self.s.paths.runs,
            sb.timeout_s,
            sb.memory_mb,
            sb.max_repairs,
            sb.allowed_hosts,
        )

    def warm(self) -> None:
        _ = self.retriever
        if not self.light:
            self.embedder.embed_queries(["warm up"])
            self.scorer.score("warm up", ["warm up"])

    def run(self, q: Query, emit=lambda e: None, stream: bool = False):
        mode, reason = (q.mode, "selected by the user") if q.mode != "auto" else route(q.question, self.llm)
        emit({"type": "route", "mode": mode, "reason": reason})
        if mode == "ask":
            return self.ask_agent.run(q.question, q.toggles, emit, stream=stream, domains=q.domains)
        if mode == "design":
            return self.design_agent.run(q.question, q.toggles, emit)
        if mode == "explore":
            return self.explore_agent.run(q.question, emit)
        return self.analyze_agent.run(q.question, emit)
