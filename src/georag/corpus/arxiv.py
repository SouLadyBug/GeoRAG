"""Select domain papers from the arXiv metadata snapshot.

arXiv releases its metadata (titles, authors, abstracts) under CC0, which makes it a clean,
reproducible source: the repository stores only the list of identifiers, and anyone can rebuild
the corpus from the public snapshot on the Hugging Face Hub
(``librarian-bots/arxiv-metadata-snapshot``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from georag.schemas import Document

SNAPSHOT_REPO = "librarian-bots/arxiv-metadata-snapshot"
SNAPSHOT_SHARDS = 11
COLUMNS = ["id", "title", "abstract", "authors", "categories", "license", "doi", "versions"]

# Licence of the paper itself; the metadata we index is CC0 either way. Open licences are
# preferred so that a full-text upgrade of the same corpus stays legal.
OPEN_LICENCES = ("creativecommons.org/licenses/by/", "creativecommons.org/publicdomain/zero/")


def _compile(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    compiled = []
    for p in patterns:
        # All-caps acronyms (GIS, SAR, TLS) are matched case-sensitively; everything else is not.
        flags = 0 if re.fullmatch(r"[A-Z0-9\-]+", p) else re.IGNORECASE
        compiled.append(re.compile(rf"(?<![\w-]){p}(?![\w-])", flags))
    return compiled


@dataclass
class DomainRule:
    name: str
    label: str
    require: list[re.Pattern[str]]
    boost: list[re.Pattern[str]]
    require_categories: set[str] = field(default_factory=set)
    exclude_categories: set[str] = field(default_factory=set)
    openalex_search: str = ""

    def score(self, title: str, abstract: str, categories: set[str]) -> float:
        if self.exclude_categories & categories:
            return 0.0
        if self.require_categories and not (self.require_categories & categories):
            return 0.0
        text = f"{title}\n{abstract}"
        req_title = sum(bool(p.search(title)) for p in self.require)
        req_all = sum(bool(p.search(text)) for p in self.require)
        if req_all == 0:
            return 0.0
        boost = sum(bool(p.search(text)) for p in self.boost)
        return 3.0 * req_title + 1.5 * req_all + boost


def load_domain_rules(path: Path) -> tuple[dict[str, DomainRule], dict]:
    cfg = yaml.safe_load(path.read_text())
    rules = {}
    for name, d in cfg["domains"].items():
        rules[name] = DomainRule(
            name=name,
            label=d["label"],
            require=_compile(d["require"]),
            boost=_compile(d.get("boost", [])),
            require_categories=set(d.get("require_categories", [])),
            exclude_categories=set(d.get("exclude_categories", [])),
            openalex_search=d.get("openalex_search", ""),
        )
    return rules, cfg


def _first_version_year(versions: list[dict] | None) -> int | None:
    if not versions:
        return None
    try:
        return parsedate_to_datetime(versions[0]["created"]).year
    except (TypeError, ValueError, KeyError):
        return None


def _literal_prefix(pattern: str) -> str:
    """The literal text at the start of a compiled domain pattern, lower-cased."""
    core = pattern.split(")", 1)[1]  # drop the leading look-behind
    return re.split(r"[\\(\[?*+]", core)[0].lower().strip()


def _id_year(arxiv_id: str) -> int | None:
    """Submission year from a new-style identifier (YYMM.NNNNN); old-style ids are pre-2007."""
    m = re.match(r"(\d{2})(\d{2})\.\d{4,5}", arxiv_id)
    return 2000 + int(m.group(1)) if m else 2000


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def iter_snapshot(shards: Iterable[Path]) -> Iterator[dict]:
    for shard in shards:
        pf = pq.ParquetFile(shard)
        for batch in pf.iter_batches(columns=COLUMNS, batch_size=20_000):
            yield from batch.to_pylist()


@dataclass
class Candidate:
    record: dict
    year: int
    scores: dict[str, float]
    open_licence: bool


def select_papers(
    shards: Iterable[Path],
    rules: dict[str, DomainRule],
    years: tuple[int, int],
    per_domain: int,
) -> list[Document]:
    """Score every snapshot record against every domain and keep the best ``per_domain`` each.

    A paper is assigned to one domain only. Domains are filled round-robin from their ranked
    candidate lists so a paper that fits two domains goes to whichever reaches it first, which
    keeps the domains balanced.
    """
    lo, hi = years
    pools: dict[str, list[Candidate]] = {name: [] for name in rules}
    # Plain substring tests reject the ~98 % of arXiv that matches no domain at all; a combined
    # regex with look-arounds is two orders of magnitude slower on 2.9 million abstracts.
    literals = {_literal_prefix(p.pattern) for r in rules.values() for p in r.require}
    keywords = sorted(k for k in literals if len(k) > 4)
    # Short acronyms (GIS, SAR, ALS) would match inside ordinary words, so they get a word-bounded regex.
    acronyms = re.compile(r"\b(?:" + "|".join(sorted(k.upper() for k in literals if len(k) <= 4)) + r")\b")
    for rec in iter_snapshot(shards):
        id_year = _id_year(rec["id"])
        if id_year is not None and not lo <= id_year <= hi:
            continue
        raw = f"{rec['title'] or ''} {rec['abstract'] or ''}"
        low = raw.lower()
        if not any(k in low for k in keywords) and not acronyms.search(raw):
            continue
        title, abstract = _clean(rec["title"]), _clean(rec["abstract"])
        if len(abstract) < 400:
            continue
        year = _first_version_year(rec.get("versions"))
        if year is None or not lo <= year <= hi:
            continue
        cats = set((rec.get("categories") or "").split())
        scores = {name: rule.score(title, abstract, cats) for name, rule in rules.items()}
        if max(scores.values()) < 6.0:
            continue
        licence = rec.get("license") or ""
        cand = Candidate(
            record={**rec, "title": title, "abstract": abstract},
            year=year,
            scores=scores,
            open_licence=any(s in licence for s in OPEN_LICENCES),
        )
        for name, s in scores.items():
            if s >= 6.0:
                pools[name].append(cand)

    for name, pool in pools.items():
        # Score first; prefer openly licensed papers, then newer ones, on ties.
        pool.sort(key=lambda c: (c.scores[name] + (0.5 if c.open_licence else 0.0), c.year), reverse=True)

    taken: set[str] = set()
    chosen: dict[str, list[Candidate]] = {name: [] for name in rules}
    cursors = dict.fromkeys(rules, 0)
    while any(len(chosen[n]) < per_domain and cursors[n] < len(pools[n]) for n in rules):
        for name in rules:
            pool = pools[name]
            while len(chosen[name]) < per_domain and cursors[name] < len(pool):
                cand = pool[cursors[name]]
                cursors[name] += 1
                if cand.record["id"] not in taken:
                    taken.add(cand.record["id"])
                    chosen[name].append(cand)
                    break

    docs = []
    for name, cands in chosen.items():
        for c in cands:
            r = c.record
            authors = [a.strip() for a in re.split(r",| and ", _clean(r.get("authors"))) if a.strip()]
            docs.append(
                Document(
                    doc_id=f"arxiv:{r['id']}",
                    source="arxiv",
                    title=r["title"],
                    text=r["abstract"],
                    domain=name,
                    year=c.year,
                    authors=authors[:12],
                    doi=r.get("doi") or None,
                    url=f"https://arxiv.org/abs/{r['id']}",
                    licence=r.get("license") or "arXiv non-exclusive (metadata CC0)",
                )
            )
    return docs


def snapshot_urls() -> list[str]:
    base = f"https://huggingface.co/datasets/{SNAPSHOT_REPO}/resolve/main/data"
    return [f"{base}/train-{i:05d}-of-{SNAPSHOT_SHARDS:05d}.parquet" for i in range(SNAPSHOT_SHARDS)]
