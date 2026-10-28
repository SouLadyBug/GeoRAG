"""Hybrid retrieval: BM25 + dense + knowledge graph, fused with RRF, then reranked.

Each component can be switched off per query (``RetrievalToggles``), which is what the live
ablation switches in the UI and the evaluation's ablation table use.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from georag.index.dense import DenseIndex, Embedder
from georag.index.fusion import reciprocal_rank_fusion
from georag.index.graph import KnowledgeGraph
from georag.index.rerank import RERANK_INSTRUCTION, Scorer
from georag.index.sparse import BM25Index
from georag.schemas import Chunk, Passage, RetrievalToggles


@dataclass
class RetrievalTrace:
    lists: dict[str, list[str]] = field(default_factory=dict)
    entities: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    top_rerank: float | None = None


class Retriever:
    def __init__(
        self,
        chunks: list[Chunk],
        bm25: BM25Index | None,
        dense: DenseIndex | None,
        embedder: Embedder | None,
        graph: KnowledgeGraph | None,
        scorer: Scorer | None,
        rrf_k: int = 60,
        candidates: int = 50,
        rerank_top_k: int = 30,
        graph_hops: int = 2,
    ):
        self.chunks = {c.chunk_id: c for c in chunks}
        self.order = [c.chunk_id for c in chunks]
        self.pos = {cid: i for i, cid in enumerate(self.order)}
        self.bm25 = bm25
        self.dense = dense
        self.embedder = embedder
        self.graph = graph
        self.scorer = scorer
        self.rrf_k = rrf_k
        self.candidates = candidates
        self.rerank_top_k = rerank_top_k
        self.graph_hops = graph_hops
        self._domain = np.array([c.domain for c in chunks])
        self._is_figure = np.array([c.kind == "figure" for c in chunks])

    def _mask(self, domains: list[str] | None, figures: bool) -> np.ndarray | None:
        mask = np.ones(len(self.order), dtype=bool)
        if domains:
            mask &= np.isin(self._domain, domains)
        if not figures:
            mask &= ~self._is_figure
        return None if mask.all() else mask

    def _remap(self, ids: list[str], index_ids: list[str], mask: np.ndarray | None) -> np.ndarray | None:
        if mask is None or index_ids == self.order:
            return mask
        return np.array([mask[self.pos[i]] for i in index_ids])

    def candidate_lists(
        self,
        question: str,
        toggles: RetrievalToggles,
        domains: list[str] | None = None,
        query_vec: np.ndarray | None = None,
        trace: RetrievalTrace | None = None,
    ) -> dict[str, list[str]]:
        trace = trace or RetrievalTrace()
        mask = self._mask(domains, toggles.figures)
        lists: dict[str, list[str]] = {}
        if toggles.bm25 and self.bm25 is not None:
            t = time.perf_counter()
            lists["bm25"] = [
                i
                for i, _ in self.bm25.search(
                    question, self.candidates, self._remap(self.order, self.bm25.ids, mask)
                )
            ]
            trace.timings["bm25"] = time.perf_counter() - t
        if toggles.dense and self.dense is not None and (self.embedder is not None or query_vec is not None):
            t = time.perf_counter()
            qv = query_vec if query_vec is not None else self.embedder.embed_queries([question])[0]  # type: ignore[union-attr]
            lists["dense"] = [
                i
                for i, _ in self.dense.search(
                    qv, self.candidates, self._remap(self.order, self.dense.ids, mask)
                )
            ]
            trace.timings["dense"] = time.perf_counter() - t
        if toggles.graph and self.graph is not None:
            t = time.perf_counter()
            allowed = None if mask is None else {cid for cid, ok in zip(self.order, mask, strict=True) if ok}
            trace.entities = self.graph.link(question)
            ranked = self.graph.retrieve(question, self.candidates, self.graph_hops, allowed)
            if ranked:
                lists["graph"] = [i for i, _ in ranked]
            trace.timings["graph"] = time.perf_counter() - t
        trace.lists = lists
        return lists

    def retrieve(
        self,
        question: str,
        toggles: RetrievalToggles | None = None,
        k: int = 8,
        domains: list[str] | None = None,
        query_vec: np.ndarray | None = None,
        rerank_query: str | None = None,
    ) -> tuple[list[Passage], RetrievalTrace]:
        toggles = toggles or RetrievalToggles()
        trace = RetrievalTrace()
        lists = self.candidate_lists(question, toggles, domains, query_vec, trace)
        if not lists:
            return [], trace
        # The graph list is a recall booster; weight it below the two text retrievers in fusion.
        fused = reciprocal_rank_fusion(lists, k=self.rrf_k, weights={"bm25": 1.0, "dense": 1.0, "graph": 0.6})
        passages = [
            Passage(chunk=self.chunks[cid], score=score, sources=ranks)
            for cid, score, ranks in fused[: self.candidates]
        ]

        if toggles.rerank and self.scorer is not None and passages:
            t = time.perf_counter()
            head = passages[: self.rerank_top_k]
            scores = self.scorer.score(
                rerank_query or question, [p.chunk.indexed_text for p in head], RERANK_INSTRUCTION
            )
            for p, s in zip(head, scores, strict=True):
                p.rerank_score = float(s)
            head.sort(key=lambda p: -(p.rerank_score or 0.0))
            passages = head + passages[self.rerank_top_k :]
            trace.timings["rerank"] = time.perf_counter() - t
            trace.top_rerank = head[0].rerank_score if head else None

        if self.graph is not None:
            for p in passages[:k]:
                p.entities = self.graph.chunk_entities.get(p.chunk.chunk_id, [])[:8]
        return passages[:k], trace
