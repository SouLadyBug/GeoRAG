"""BM25 over chunk text (``bm25s`` with an English Snowball stemmer).

Sparse retrieval matters in this domain: band names (B11), EPSG codes, dataset identifiers
(Sen1Floods11) and acronyms are exact tokens that dense embeddings tend to blur.
"""

from __future__ import annotations

import re
from pathlib import Path

import bm25s
import numpy as np

try:
    import Stemmer

    _STEMMER = Stemmer.Stemmer("english")
except ImportError:  # pragma: no cover - PyStemmer is a declared dependency
    _STEMMER = None

# Keep hyphenated and alphanumeric identifiers (Sentinel-2, B11, EPSG:4326) as single tokens.
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-:.][A-Za-z0-9]+)*")


def _normalise(texts: list[str]) -> list[str]:
    return [" ".join(_TOKEN.findall(t)) for t in texts]


class BM25Index:
    def __init__(self, retriever: bm25s.BM25, ids: list[str]):
        self.retriever = retriever
        self.ids = ids

    @classmethod
    def build(cls, ids: list[str], texts: list[str]) -> BM25Index:
        tokens = bm25s.tokenize(_normalise(texts), stopwords="en", stemmer=_STEMMER, show_progress=False)
        retriever = bm25s.BM25(k1=1.2, b=0.75)
        retriever.index(tokens, show_progress=False)
        return cls(retriever, ids)

    def search(self, query: str, k: int = 50, allowed: np.ndarray | None = None) -> list[tuple[str, float]]:
        tokens = bm25s.tokenize(_normalise([query]), stopwords="en", stemmer=_STEMMER, show_progress=False)
        if not tokens.vocab:
            return []
        n = len(self.ids)
        k_eff = min(n, k if allowed is None else n)
        docs, scores = self.retriever.retrieve(tokens, k=k_eff, show_progress=False, n_threads=1)
        out = []
        for idx, score in zip(docs[0], scores[0], strict=True):
            if score <= 0:
                continue
            if allowed is not None and not allowed[idx]:
                continue
            out.append((self.ids[int(idx)], float(score)))
            if len(out) >= k:
                break
        return out

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.retriever.save(str(path))
        (path / "ids.txt").write_text("\n".join(self.ids))

    @classmethod
    def load(cls, path: Path) -> BM25Index:
        retriever = bm25s.BM25.load(str(path))
        ids = (path / "ids.txt").read_text().split("\n")
        return cls(retriever, ids)
