"""Diversity reranking for AdaOnto-RAG (Experiment 2, pre-registered).

Maximal Marginal Relevance (MMR) over dense-retrieval candidates with a hard
same-document dedup constraint. Uses ONLY retrieval scores, chunk embeddings,
and document IDs — never relevance judgments or concept annotations.

Pre-registered constants: POOL candidates in, LAMBDA = 0.5.
"""

from __future__ import annotations

import math

LAMBDA = 0.5  # pre-registered MMR trade-off (standard default, not tuned)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def mmr_rerank(
    chunk_ids: list[str],
    distances: list[float],
    doc_ids: list[str],
    chunk_embeddings: list[list[float]],
    top_k: int,
    lambda_: float = LAMBDA,
) -> list[int]:
    """Greedy MMR selection; returns indices into the candidate lists.

    Relevance = min-max normalized negative distance (higher is better).
    Redundancy = max cosine similarity to already-selected chunks.
    Candidates whose doc_id is already selected are skipped (hard dedup).
    If the pool exhausts before top_k, the remainder is filled ignoring dedup.
    """
    n = len(chunk_ids)
    if n == 0 or top_k <= 0:
        return []

    lo, hi = min(distances), max(distances)
    span = (hi - lo) if hi > lo else 1.0
    relevance = [1.0 - (d - lo) / span for d in distances]

    selected: list[int] = []
    selected_docs: set[str] = set()
    remaining = set(range(n))

    def pick(allow_dup: bool) -> int | None:
        best, best_score = None, None
        for i in sorted(remaining):
            if not allow_dup and doc_ids[i] in selected_docs:
                continue
            redundancy = 0.0
            for j in selected:
                redundancy = max(redundancy, _cosine(chunk_embeddings[i], chunk_embeddings[j]))
            score = lambda_ * relevance[i] - (1.0 - lambda_) * redundancy
            if best_score is None or score > best_score:
                best, best_score = i, score
        return best

    while len(selected) < min(top_k, n) and remaining:
        nxt = pick(allow_dup=False)
        if nxt is None:  # pool exhausted under dedup -> fill ignoring it
            nxt = pick(allow_dup=True)
            if nxt is None:
                break
        selected.append(nxt)
        selected_docs.add(doc_ids[nxt])
        remaining.discard(nxt)

    return selected
