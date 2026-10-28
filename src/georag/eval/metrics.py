"""Retrieval and answer metrics used by GeoRAG-Bench."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence


def recall_at_k(ranked: Sequence[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(ranked[:k]) & gold) / len(gold)


def all_at_k(ranked: Sequence[str], gold: set[str], k: int) -> float:
    return float(bool(gold) and gold <= set(ranked[:k]))


def mrr(ranked: Sequence[str], gold: set[str], k: int = 10) -> float:
    for i, cid in enumerate(ranked[:k], start=1):
        if cid in gold:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence[str], gold: set[str], k: int = 10) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, cid in enumerate(ranked[:k], start=1) if cid in gold)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(gold), k) + 1))
    return dcg / ideal if ideal else 0.0


_STOP = frozenset(
    "a an the of and or in on for to is are was were be been with by as at from that this these "
    "those it its their which what how why when where who does do did can could should would may "
    "might than then into over under via using use used based also such not no yes".split()
)


def content_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.lower()) if t not in _STOP]


def token_f1(pred: str, gold: str) -> float:
    p, g = content_tokens(pred), content_tokens(gold)
    if not p or not g:
        return 0.0
    common: dict[str, int] = {}
    gc: dict[str, int] = {}
    for t in g:
        gc[t] = gc.get(t, 0) + 1
    for t in p:
        if gc.get(t, 0) > 0:
            common[t] = common.get(t, 0) + 1
            gc[t] -= 1
    n = sum(common.values())
    if n == 0:
        return 0.0
    prec, rec = n / len(p), n / len(g)
    return 2 * prec * rec / (prec + rec)


def answer_recall(pred: str, gold: str) -> float:
    """Share of the gold answer's content words that appear in the prediction."""
    g = set(content_tokens(gold))
    if not g:
        return 0.0
    return len(g & set(content_tokens(pred))) / len(g)


def mean(xs: Sequence[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else None


def bootstrap_ci(
    xs: Sequence[float], n: int = 2000, alpha: float = 0.05, seed: int = 7
) -> tuple[float, float]:
    import numpy as np

    arr = np.asarray(xs, dtype=float)
    if arr.size == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(arr, size=(n, arr.size), replace=True).mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))
