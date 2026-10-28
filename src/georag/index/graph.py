"""Domain knowledge graph.

Nodes are glossary entities (methods, sensors, datasets, products, applications, places,
standards) plus any terms proposed by the optional LLM extractor. Two entities are linked when
they are mentioned in the same chunk; each edge keeps the chunks that support it and a
normalised PMI weight, so frequent-but-uninformative pairs (``transformer`` and
``deep learning``) do not dominate.

At query time the graph does two jobs: graph-augmented retrieval (chunks that mention the
question's entities and their strongest neighbours) and Explore mode (a subgraph with paths
between the entities in the question).
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import networkx as nx
import pandas as pd
import yaml

from georag.schemas import Chunk, GraphEdge, GraphNode


@dataclass
class Entity:
    id: str
    label: str
    type: str
    aliases: list[str]
    definition: str = ""
    broader: str | None = None


def load_glossary(path: Path) -> list[Entity]:
    return [
        Entity(
            id=t["id"],
            label=t["label"],
            type=t["type"],
            aliases=list(dict.fromkeys([t["label"], *t["aliases"]])),
            definition=t.get("definition", ""),
            broader=t.get("broader"),
        )
        for t in yaml.safe_load(path.read_text())
    ]


class EntityMatcher:
    """Whole-word alias matcher. All-caps aliases (SAR, DSM) are case-sensitive."""

    def __init__(self, entities: list[Entity]):
        self.entities = {e.id: e for e in entities}
        # "airborne LiDAR" is also a mention of "LiDAR": the longest alias wins the match, so the
        # broader concept is added explicitly.
        self.broader = {e.id: e.broader for e in entities if e.broader}
        sensitive: dict[str, str] = {}
        insensitive: dict[str, str] = {}
        for e in entities:
            for alias in e.aliases:
                if re.fullmatch(r"[A-Z0-9][A-Z0-9\-+.]*s?", alias) and any(c.isupper() for c in alias):
                    sensitive.setdefault(alias, e.id)
                else:
                    insensitive.setdefault(alias.lower(), e.id)
        self._sensitive = sensitive
        self._insensitive = insensitive
        self._re_s = self._compile(sensitive.keys(), 0)
        self._re_i = self._compile(insensitive.keys(), re.IGNORECASE)

    @staticmethod
    def _compile(aliases, flags) -> re.Pattern[str] | None:
        aliases = sorted(aliases, key=len, reverse=True)
        if not aliases:
            return None
        alt = "|".join(re.escape(a) for a in aliases)
        return re.compile(rf"(?<![\w-])(?:{alt})(?![\w-])", flags)

    def find(self, text: str) -> list[str]:
        found: dict[str, None] = {}
        if self._re_s:
            for m in self._re_s.finditer(text):
                found[self._sensitive[m.group(0)]] = None
        if self._re_i:
            for m in self._re_i.finditer(text):
                eid = self._insensitive.get(m.group(0).lower())
                if eid:
                    found[eid] = None
        for eid in list(found):
            parent = self.broader.get(eid)
            if parent and parent in self.entities:
                found[parent] = None
        return list(found)


class KnowledgeGraph:
    def __init__(
        self, graph: nx.Graph, mentions: dict[str, list[str]], matcher: EntityMatcher, n_chunks: int
    ):
        self.g = graph
        self.mentions = mentions  # entity id -> chunk ids
        self.matcher = matcher
        self.n_chunks = n_chunks
        self.chunk_entities: dict[str, list[str]] = defaultdict(list)
        for eid, chunk_ids in mentions.items():
            for cid in chunk_ids:
                self.chunk_entities[cid].append(eid)

    # ------------------------------------------------------------------ build / io
    @classmethod
    def build(cls, chunks: list[Chunk], entities: list[Entity], max_edge_chunks: int = 40) -> KnowledgeGraph:
        matcher = EntityMatcher(entities)
        mentions: dict[str, list[str]] = defaultdict(list)
        pair_chunks: dict[tuple[str, str], list[str]] = defaultdict(list)
        pair_count: Counter[tuple[str, str]] = Counter()
        domains: dict[str, Counter[str]] = defaultdict(Counter)
        for ch in chunks:
            found = sorted(set(matcher.find(ch.indexed_text)))
            for eid in found:
                mentions[eid].append(ch.chunk_id)
                domains[eid][ch.domain] += 1
            for a, b in combinations(found, 2):
                pair_count[(a, b)] += 1
                if len(pair_chunks[(a, b)]) < max_edge_chunks:
                    pair_chunks[(a, b)].append(ch.chunk_id)

        n = max(1, len(chunks))
        g = nx.Graph()
        for e in entities:
            if e.id in mentions:
                g.add_node(
                    e.id,
                    label=e.label,
                    type=e.type,
                    definition=e.definition,
                    count=len(mentions[e.id]),
                    domains=dict(domains[e.id]),
                )
        for (a, b), c in pair_count.items():
            if c < 2:
                continue
            pa, pb, pab = len(mentions[a]) / n, len(mentions[b]) / n, c / n
            npmi = math.log(pab / (pa * pb)) / -math.log(pab) if pab < 1 else 1.0
            if npmi <= 0:
                continue
            g.add_edge(a, b, count=c, npmi=round(npmi, 4), chunks=pair_chunks[(a, b)])
        return cls(g, dict(mentions), matcher, n)

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        nodes = [
            {"id": n, **{k: v for k, v in d.items() if k != "domains"}, "domains": str(d.get("domains", {}))}
            for n, d in self.g.nodes(data=True)
        ]
        edges = [
            {"source": a, "target": b, "count": d["count"], "npmi": d["npmi"], "chunks": d["chunks"]}
            for a, b, d in self.g.edges(data=True)
        ]
        mentions = [{"entity": e, "chunk_id": c} for e, cs in self.mentions.items() for c in cs]
        pd.DataFrame(nodes).to_parquet(path / "nodes.parquet", index=False)
        pd.DataFrame(edges).to_parquet(path / "edges.parquet", index=False)
        pd.DataFrame(mentions).to_parquet(path / "mentions.parquet", index=False)
        (path / "meta.yaml").write_text(yaml.safe_dump({"n_chunks": self.n_chunks}))

    @classmethod
    def load(cls, path: Path, entities: list[Entity]) -> KnowledgeGraph:
        import ast

        g = nx.Graph()
        for r in pd.read_parquet(path / "nodes.parquet").to_dict("records"):
            nid = r.pop("id")
            r["domains"] = ast.literal_eval(r.get("domains") or "{}")
            g.add_node(nid, **r)
        for r in pd.read_parquet(path / "edges.parquet").to_dict("records"):
            g.add_edge(
                r["source"],
                r["target"],
                count=int(r["count"]),
                npmi=float(r["npmi"]),
                chunks=list(r["chunks"]),
            )
        mentions: dict[str, list[str]] = defaultdict(list)
        for r in pd.read_parquet(path / "mentions.parquet").itertuples():
            mentions[r.entity].append(r.chunk_id)
        n_chunks = yaml.safe_load((path / "meta.yaml").read_text())["n_chunks"]
        known = {e.id for e in entities}
        extra = [
            Entity(
                id=n,
                label=d["label"],
                type=d["type"],
                aliases=[d["label"]],
                definition=d.get("definition") or "",
            )
            for n, d in g.nodes(data=True)
            if n not in known
        ]
        return cls(g, dict(mentions), EntityMatcher(entities + extra), n_chunks)

    # ------------------------------------------------------------------ query time
    def link(self, text: str) -> list[str]:
        """Entities mentioned in ``text`` that exist in the graph, rarest first."""
        found = [e for e in self.matcher.find(text) if e in self.g]
        return sorted(found, key=lambda e: self.g.nodes[e]["count"])

    def idf(self, eid: str) -> float:
        return math.log(1 + self.n_chunks / (1 + len(self.mentions.get(eid, []))))

    def neighbours(self, eid: str, k: int = 8) -> list[tuple[str, float]]:
        if eid not in self.g:
            return []
        nbrs = [(n, d["npmi"] * math.log1p(d["count"])) for n, d in self.g[eid].items()]
        return sorted(nbrs, key=lambda x: -x[1])[:k]

    def retrieve(
        self, question: str, k: int = 50, hops: int = 2, allowed: set[str] | None = None
    ) -> list[tuple[str, float]]:
        """Rank chunks by how many (and how specific) question entities and neighbours they mention."""
        seeds = self.link(question)
        if not seeds:
            return []
        weights: dict[str, float] = {s: self.idf(s) for s in seeds}
        if hops >= 1:
            for s in seeds:
                for n, w in self.neighbours(s, k=6):
                    weights.setdefault(n, 0.0)
                    weights[n] = max(weights[n], 0.35 * w * self.idf(n) / (1 + w))
        if hops >= 2:
            first = [n for s in seeds for n, _ in self.neighbours(s, k=3)]
            for f in first:
                for n, w in self.neighbours(f, k=3):
                    weights.setdefault(n, 0.12 * self.idf(n) * w / (1 + w))
        scores: dict[str, float] = defaultdict(float)
        seed_hits: dict[str, int] = defaultdict(int)
        for eid, w in weights.items():
            for cid in self.mentions.get(eid, []):
                if allowed is not None and cid not in allowed:
                    continue
                scores[cid] += w
                if eid in seeds:
                    seed_hits[cid] += 1
        # Chunks connecting several seed entities are what cross-domain questions need.
        for cid, hits in seed_hits.items():
            if hits > 1:
                scores[cid] *= 1 + 0.5 * (hits - 1)
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        return ranked[:k]

    def subgraph(
        self, question: str, max_nodes: int = 40
    ) -> tuple[list[GraphNode], list[GraphEdge], list[list[str]], list[str]]:
        seeds = self.link(question)
        nodes: dict[str, None] = dict.fromkeys(seeds)
        paths: list[list[str]] = []
        cost = {
            (a, b): 1.0 / (d["npmi"] * math.log1p(d["count"]) + 1e-6) for a, b, d in self.g.edges(data=True)
        }
        nx.set_edge_attributes(self.g, {e: c for e, c in cost.items()}, "cost")
        for a, b in combinations(seeds, 2):
            try:
                p = nx.shortest_path(self.g, a, b, weight="cost")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            paths.append(p)
            nodes.update(dict.fromkeys(p))
        per_seed = max(3, (max_nodes - len(nodes)) // max(1, len(seeds)))
        for s in seeds:
            for n, _ in self.neighbours(s, k=per_seed):
                if len(nodes) >= max_nodes:
                    break
                nodes.setdefault(n, None)
        keep = set(nodes)
        out_nodes = [
            GraphNode(
                id=n,
                label=self.g.nodes[n]["label"],
                type=self.g.nodes[n]["type"],
                degree=int(self.g.nodes[n]["count"]),
                seed=n in seeds,
                definition=self.g.nodes[n].get("definition"),
            )
            for n in nodes
        ]
        out_edges = [
            GraphEdge(source=a, target=b, weight=float(d["npmi"]), chunks=list(d["chunks"])[:12])
            for a, b, d in self.g.subgraph(keep).edges(data=True)
            if d["count"] >= 2
        ]
        return out_nodes, out_edges, paths, seeds

    def stats(self) -> dict:
        types = Counter(d["type"] for _, d in self.g.nodes(data=True))
        return {
            "nodes": self.g.number_of_nodes(),
            "edges": self.g.number_of_edges(),
            "mentions": sum(len(v) for v in self.mentions.values()),
            "types": dict(types),
        }
