"""Data models shared by the indexer, the agent, the API and the evaluation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["gis", "remote_sensing", "lidar", "digital_twin", "geo_cv", "docs", "catalogue", "glossary"]
Mode = Literal["ask", "analyze", "design", "explore"]


class Document(BaseModel):
    doc_id: str
    source: str  # arxiv | openalex | docs | catalogue | glossary
    title: str
    text: str
    domain: str
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    url: str | None = None
    licence: str | None = None
    sections: list[tuple[str, str]] | None = None  # (heading, body) when the source is structured


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    domain: str
    year: int | None = None
    url: str | None = None
    page: int | None = None
    kind: Literal["text", "figure"] = "text"

    @property
    def indexed_text(self) -> str:
        """Text that goes into BM25 and the embedder: title and section give each chunk context."""
        head = (
            self.title if not self.section or self.section == self.title else f"{self.title} — {self.section}"
        )
        return f"{head}\n{self.text}"


class Passage(BaseModel):
    chunk: Chunk
    score: float = 0.0
    sources: dict[str, int] = Field(default_factory=dict)  # retriever name -> rank (1-based)
    rerank_score: float | None = None
    entities: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    n: int
    chunk_id: str
    doc_id: str
    title: str
    url: str | None = None
    year: int | None = None
    section: str = ""
    quote: str = ""


class Sentence(BaseModel):
    text: str
    citations: list[int] = Field(default_factory=list)
    support: float | None = None
    supported: bool = True


class RetrievalToggles(BaseModel):
    bm25: bool = True
    dense: bool = True
    graph: bool = True
    rerank: bool = True
    figures: bool = False


class Query(BaseModel):
    question: str
    mode: Mode | Literal["auto"] = "auto"
    toggles: RetrievalToggles = Field(default_factory=RetrievalToggles)
    domains: list[str] | None = None


class AskResult(BaseModel):
    mode: Literal["ask"] = "ask"
    question: str
    answer: str
    sentences: list[Sentence]
    citations: list[Citation]
    refused: bool = False
    refusal_reason: str | None = None
    related: list[str] = Field(default_factory=list)
    faithfulness: float | None = None
    passages: list[Passage] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)


class DesignSection(BaseModel):
    key: str
    heading: str
    markdown: str
    citations: list[int] = Field(default_factory=list)
    supported_ratio: float | None = None


class DesignResult(BaseModel):
    mode: Literal["design"] = "design"
    question: str
    title: str
    sections: list[DesignSection]
    citations: list[Citation]
    datasets: list[dict] = Field(default_factory=list)
    markdown: str
    faithfulness: float | None = None
    timings: dict[str, float] = Field(default_factory=dict)


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    degree: int = 0
    seed: bool = False
    definition: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float
    chunks: list[str] = Field(default_factory=list)


class ExploreResult(BaseModel):
    mode: Literal["explore"] = "explore"
    question: str
    seeds: list[str]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    paths: list[list[str]] = Field(default_factory=list)
    summary: str = ""
    citations: list[Citation] = Field(default_factory=list)
    passages: dict[str, Citation] = Field(default_factory=dict)
    timings: dict[str, float] = Field(default_factory=dict)


class AnalysisPlan(BaseModel):
    task: Literal["water_change", "water_extent", "ndvi"]
    place: str
    bbox: tuple[float, float, float, float] | None = None  # lon_min, lat_min, lon_max, lat_max
    periods: list[str]  # "YYYY-MM" months; two for a change task
    index: Literal["MNDWI", "NDWI", "NDVI"] = "MNDWI"
    threshold: float = 0.0
    max_cloud: float = 30.0
    max_scenes: int = 4
    resolution: int = 20
    rationale: str = ""


class Attempt(BaseModel):
    n: int
    plan: AnalysisPlan
    code: str
    ok: bool
    seconds: float
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class AnalyzeResult(BaseModel):
    mode: Literal["analyze"] = "analyze"
    question: str
    plan: AnalysisPlan
    code: str
    attempts: list[Attempt]
    ok: bool
    run_id: str
    outputs: dict[str, str] = Field(default_factory=dict)  # name -> relative path in the run folder
    numbers: dict = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    explanation: str = ""
    timings: dict[str, float] = Field(default_factory=dict)
