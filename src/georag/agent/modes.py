"""Ask, Design and Explore modes, and the router that picks between all four."""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from pydantic import BaseModel

from georag.agent import prompts
from georag.agent.grounding import (
    check_support,
    format_sources,
    is_coverage_note,
    make_citation,
    render_cited,
    split_cited,
)
from georag.index.graph import KnowledgeGraph
from georag.index.rerank import Scorer
from georag.llm import LLM
from georag.retrieval import Retriever
from georag.schemas import (
    AskResult,
    Citation,
    DesignResult,
    DesignSection,
    ExploreResult,
    Mode,
    Passage,
    RetrievalToggles,
)

EventSink = Callable[[dict], None]
REFUSAL_TOKEN = "INSUFFICIENT_EVIDENCE"


def _noop(_: dict) -> None:
    return None


# ---------------------------------------------------------------------------------------- router
_ANALYZE = re.compile(
    r"\b(map|compute|calculate|measure|plot|show)\b.*\b(ndvi|ndwi|mndwi|water|vegetation|extent|area|index)\b"
    r"|\b(19|20)\d{2}\b.*\b(vs\.?|versus|compared?|and)\b.*\b(19|20)\d{2}\b",
    re.I | re.S,
)
_DESIGN = re.compile(
    r"\b(design|plan|propose|draft|outline)\b.{0,40}\b(study|project|experiment|research|proposal|campaign)\b",
    re.I,
)
_EXPLORE = re.compile(
    r"\b(connected|connection|relate[ds]?|relationship|link(?:ed|s)?|meet|intersect)\b", re.I
)


class _Route(BaseModel):
    mode: Mode
    reason: str = ""


def route(question: str, llm: LLM | None = None) -> tuple[Mode, str]:
    q = question.strip()
    if _DESIGN.search(q):
        return "design", "asks for a study design"
    if _ANALYZE.search(q) and re.search(r"\b(19|20)\d{2}\b", q):
        return "analyze", "asks for a computation on satellite data for a place and date"
    if _EXPLORE.search(q) and re.search(r"\bhow\b|\bwhat\b", q, re.I):
        return "explore", "asks how concepts are connected"
    if llm is not None and len(q.split()) > 6:
        try:
            r = llm.json(
                [{"role": "system", "content": prompts.ROUTER_SYSTEM}, {"role": "user", "content": q}],
                _Route,
                max_tokens=80,
            )
            return r.mode, r.reason
        except Exception:
            pass
    return "ask", "default: a question for the literature"


# ------------------------------------------------------------------------------------------- ask
class AskAgent:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLM,
        scorer: Scorer | None,
        refusal_threshold: float,
        support_threshold: float,
        k: int = 8,
        max_words: int = 250,
    ):
        self.retriever = retriever
        self.llm = llm
        self.scorer = scorer
        self.refusal_threshold = refusal_threshold
        self.support_threshold = support_threshold
        self.k = k
        self.max_words = max_words

    def run(
        self,
        question: str,
        toggles: RetrievalToggles | None = None,
        emit: EventSink = _noop,
        stream: bool = False,
        domains: list[str] | None = None,
    ) -> AskResult:
        timings: dict[str, float] = {}
        t0 = time.perf_counter()
        toggles = toggles or RetrievalToggles()
        passages, trace = self.retriever.retrieve(question, toggles, k=self.k, domains=domains)
        timings["retrieval"] = time.perf_counter() - t0
        emit(
            {
                "type": "retrieval",
                "passages": [p.model_dump() for p in passages],
                "entities": trace.entities,
                "lists": {k: len(v) for k, v in trace.lists.items()},
            }
        )

        related = self._related(trace.entities)
        if not passages or (trace.top_rerank is not None and trace.top_rerank < self.refusal_threshold):
            reason = "No passage in the corpus is relevant enough to answer this question."
            return AskResult(
                question=question,
                answer=reason,
                sentences=[],
                citations=[],
                refused=True,
                refusal_reason=reason,
                related=related,
                passages=passages,
                timings=timings,
            )

        messages = [
            {"role": "system", "content": prompts.ASK_SYSTEM.format(max_words=self.max_words)},
            {
                "role": "user",
                "content": prompts.ASK_USER.format(sources=format_sources(passages), question=question),
            },
        ]
        t1 = time.perf_counter()
        if stream:
            parts = []
            for tok in self.llm.stream(messages, max_tokens=int(self.max_words * 2.2)):
                parts.append(tok)
                emit({"type": "token", "text": tok})
            raw = "".join(parts)
        else:
            raw = self.llm.chat(messages, max_tokens=int(self.max_words * 2.2))
        timings["generation"] = time.perf_counter() - t1

        if REFUSAL_TOKEN in raw[:60]:
            reason = "The retrieved passages do not contain the answer."
            return AskResult(
                question=question,
                answer=reason,
                sentences=[],
                citations=[],
                refused=True,
                refusal_reason=reason,
                related=related,
                passages=passages,
                timings=timings,
            )

        sources = {i + 1: p for i, p in enumerate(passages)}
        sentences = split_cited(raw, set(sources))
        if sentences and all(is_coverage_note(s.text) for s in sentences):
            # The model found the passages relevant but not sufficient: that is a refusal.
            reason = sentences[0].text
            return AskResult(
                question=question,
                answer=reason,
                sentences=[],
                citations=[],
                refused=True,
                refusal_reason=reason,
                related=related,
                passages=passages,
                timings=timings,
            )
        t2 = time.perf_counter()
        faithfulness = check_support(sentences, sources, self.scorer, self.support_threshold)
        timings["support_check"] = time.perf_counter() - t2
        cited = sorted({n for s in sentences for n in s.citations})
        citations = [make_citation(n, sources[n]) for n in cited]
        timings["total"] = time.perf_counter() - t0
        return AskResult(
            question=question,
            answer=render_cited(sentences),
            sentences=sentences,
            citations=citations,
            related=related,
            faithfulness=faithfulness,
            passages=passages,
            timings=timings,
        )

    def _related(self, entities: list[str]) -> list[str]:
        g = self.retriever.graph
        if g is None:
            return []
        out: dict[str, None] = {}
        for e in entities[:3]:
            for n, _ in g.neighbours(e, k=4):
                if n not in entities:
                    out[g.g.nodes[n]["label"]] = None
        return list(out)[:8]


# ---------------------------------------------------------------------------------------- design
class DesignAgent:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLM,
        scorer: Scorer | None,
        support_threshold: float,
        k: int = 5,
        max_words: int = 180,
    ):
        self.retriever = retriever
        self.llm = llm
        self.scorer = scorer
        self.support_threshold = support_threshold
        self.k = k
        self.max_words = max_words

    def run(
        self, question: str, toggles: RetrievalToggles | None = None, emit: EventSink = _noop
    ) -> DesignResult:
        t0 = time.perf_counter()
        toggles = toggles or RetrievalToggles()
        registry: dict[str, int] = {}
        passages_by_n: dict[int, Passage] = {}
        sections: list[DesignSection] = []
        datasets: list[dict] = []
        all_sentences = []
        for key, heading, brief, focus in prompts.DESIGN_SECTIONS:
            emit({"type": "section_start", "key": key, "heading": heading})
            domains = (
                ["catalogue", "remote_sensing", "lidar", "gis", "digital_twin", "geo_cv", "docs"]
                if key == "data"
                else None
            )
            passages, _ = self.retriever.retrieve(
                f"{question} {focus}",
                toggles,
                k=self.k,
                domains=domains,
                rerank_query=f"{question} ({heading.lower()})",
            )
            if key == "data":
                cat, _ = self.retriever.retrieve(question, toggles, k=4, domains=["catalogue"])
                seen = {p.chunk.chunk_id for p in passages}
                passages = passages + [p for p in cat if p.chunk.chunk_id not in seen]
                datasets = [
                    {
                        "title": p.chunk.title.removeprefix("Dataset: "),
                        "url": p.chunk.url,
                        "chunk_id": p.chunk.chunk_id,
                    }
                    for p in cat
                ]
            numbers = []
            for p in passages:
                cid = p.chunk.chunk_id
                if cid not in registry:
                    registry[cid] = len(registry) + 1
                    passages_by_n[registry[cid]] = p
                numbers.append(registry[cid])
            messages = [
                {"role": "system", "content": prompts.DESIGN_SYSTEM.format(max_words=self.max_words)},
                {
                    "role": "user",
                    "content": prompts.DESIGN_USER.format(
                        question=question,
                        heading=heading,
                        brief=brief,
                        sources=format_sources(passages, numbers),
                    ),
                },
            ]
            raw = self.llm.chat(messages, max_tokens=int(self.max_words * 2.4))
            md, sents = self._ground_markdown(raw, set(numbers), passages_by_n)
            all_sentences.extend(sents)
            ratio = (sum(s.supported for s in sents) / len(sents)) if sents else None
            cites = sorted({n for s in sents for n in s.citations})
            sections.append(
                DesignSection(key=key, heading=heading, markdown=md, citations=cites, supported_ratio=ratio)
            )
            emit({"type": "section", "section": sections[-1].model_dump()})

        used = sorted({n for s in sections for n in s.citations})
        citations = [make_citation(n, passages_by_n[n]) for n in used]
        title = f"Study design: {question.rstrip('.?')}"
        refs = "\n".join(
            f"{c.n}. {c.title}{f' ({c.year})' if c.year else ''}. {c.url or ''}" for c in citations
        )
        markdown = (
            f"# {title}\n\n"
            + "\n\n".join(f"## {s.heading}\n\n{s.markdown}" for s in sections)
            + f"\n\n## References\n\n{refs}\n"
        )
        faith = (sum(s.supported for s in all_sentences) / len(all_sentences)) if all_sentences else None
        return DesignResult(
            question=question,
            title=title,
            sections=sections,
            citations=citations,
            datasets=datasets,
            markdown=markdown,
            faithfulness=faith,
            timings={"total": time.perf_counter() - t0},
        )

    def _ground_markdown(self, raw: str, valid: set[int], sources: dict[int, Passage]):
        """Check support line by line while keeping the model's Markdown structure (lists, bold)."""
        out_lines = []
        sentences_all = []
        for line in raw.strip().splitlines():
            stripped = line.strip()
            if not stripped:
                out_lines.append(line)
                continue
            # Headings and bold title lines repeat the section name; they are labels, not claims.
            if (
                stripped.startswith("#")
                or re.fullmatch(r"\*\*[^*]{1,80}\*\*[.:]?", stripped)
                or (stripped.endswith(":") and len(stripped.split()) <= 6)
            ):
                continue
            m = re.match(r"^(\s*(?:[-*+]|\d+[.)])\s+)(.*)$", line)
            prefix, body = (m.group(1), m.group(2)) if m else ("", line)
            sents = split_cited(body, valid)
            check_support(sents, sources, self.scorer, self.support_threshold)
            sentences_all.extend(sents)
            out_lines.append(prefix + render_cited(sents))
        return "\n".join(out_lines), sentences_all


# --------------------------------------------------------------------------------------- explore
class ExploreAgent:
    def __init__(self, retriever: Retriever, graph: KnowledgeGraph, llm: LLM | None, summarise: bool = True):
        self.retriever = retriever
        self.graph = graph
        self.llm = llm
        self.summarise = summarise

    def run(self, question: str, emit: EventSink = _noop) -> ExploreResult:
        t0 = time.perf_counter()
        nodes, edges, paths, seeds = self.graph.subgraph(question)
        passages: dict[str, Citation] = {}
        n = 0
        for e in edges:
            for cid in e.chunks[:4]:
                if cid not in passages and cid in self.retriever.chunks:
                    n += 1
                    passages[cid] = make_citation(n, Passage(chunk=self.retriever.chunks[cid]))
        emit(
            {
                "type": "graph",
                "nodes": [x.model_dump() for x in nodes],
                "edges": [x.model_dump() for x in edges],
                "paths": paths,
            }
        )

        summary, citations = "", []
        if self.summarise and self.llm is not None and seeds:
            # Ground the summary in chunks that mention at least two of the seed concepts.
            bridge = [
                cid for cid, ents in self.graph.chunk_entities.items() if len(set(ents) & set(seeds)) >= 2
            ]
            ps, _ = self.retriever.retrieve(question, RetrievalToggles(), k=6)
            ps = [Passage(chunk=self.retriever.chunks[c]) for c in bridge[:3]] + [
                p for p in ps if p.chunk.chunk_id not in bridge[:3]
            ]
            ps = ps[:6]
            label = {x.id: x.label for x in nodes}
            path_txt = "; ".join(" → ".join(label.get(i, i) for i in p) for p in paths[:4]) or "none"
            raw = self.llm.chat(
                [
                    {"role": "system", "content": prompts.EXPLORE_SYSTEM},
                    {
                        "role": "user",
                        "content": prompts.EXPLORE_USER.format(
                            question=question, paths=path_txt, sources=format_sources(ps)
                        ),
                    },
                ],
                max_tokens=320,
            )
            sources = {i + 1: p for i, p in enumerate(ps)}
            sents = split_cited(raw, set(sources))
            summary = render_cited(sents, mark_unsupported=False)
            citations = [
                make_citation(k, sources[k]) for k in sorted({c for s in sents for c in s.citations})
            ]
        label_of = {x.id: x.label for x in nodes}
        return ExploreResult(
            question=question,
            seeds=[label_of.get(s, s) for s in seeds],
            nodes=nodes,
            edges=edges,
            paths=paths,
            summary=summary,
            citations=citations,
            passages=passages,
            timings={"total": time.perf_counter() - t0},
        )
