"""Reciprocal rank fusion, the method Azure AI Search uses to merge hybrid result sets."""

from __future__ import annotations

from collections.abc import Sequence

RRF_K = 60


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = RRF_K
) -> list[tuple[str, float]]:
    """Merge ranked id lists. Each id scores ``sum(1 / (k + rank))`` over the lists it is in.

    Ties are broken by id so the output is deterministic.
    """
    if k <= 0:
        msg = "k must be positive"
        raise ValueError(msg)
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
