"""Reciprocal rank fusion (Cormack, Clarke & Büttcher, 2009).

RRF scores a document by ``sum(1 / (k + rank))`` over the ranked lists it appears in. It needs
no score calibration between retrievers, which is exactly the problem when mixing BM25 scores
(unbounded) with cosine similarities (bounded) and graph walk weights.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def reciprocal_rank_fusion(
    ranked_lists: Mapping[str, Sequence[str]],
    k: int = 60,
    weights: Mapping[str, float] | None = None,
) -> list[tuple[str, float, dict[str, int]]]:
    """Fuse named ranked lists of ids.

    Returns ``(id, score, {list_name: rank})`` sorted by descending score; ties keep the order
    in which ids were first seen so results are deterministic.
    """
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    order: dict[str, int] = {}
    for name, ids in ranked_lists.items():
        w = 1.0 if weights is None else weights.get(name, 1.0)
        seen: set[str] = set()
        for rank, doc_id in enumerate(ids, start=1):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (k + rank)
            ranks.setdefault(doc_id, {})[name] = rank
            order.setdefault(doc_id, len(order))
    fused = sorted(scores, key=lambda d: (-scores[d], order[d]))
    return [(d, scores[d], ranks[d]) for d in fused]
