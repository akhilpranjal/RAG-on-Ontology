"""Retrieval evaluation metrics.

Computes standard IR metrics for comparing pipeline retrieval quality:
Recall@k, Precision@k, Hit@k, MRR, nDCG@k.
"""

from __future__ import annotations

import math
import numpy as np


def recall_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int = 5) -> float:
    """Fraction of relevant documents that appear in the top-k retrieved results.

    Recall@k = |retrieved_top_k ∩ relevant| / |relevant|
    """
    if not relevant_doc_ids:
        return 0.0
    top_k = set(retrieved_doc_ids[:k])
    relevant = set(relevant_doc_ids)
    return len(top_k & relevant) / len(relevant)


def precision_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int = 5) -> float:
    """Fraction of top-k retrieved documents that are relevant.

    Precision@k = |retrieved_top_k ∩ relevant| / k
    """
    if k == 0:
        return 0.0
    top_k = set(retrieved_doc_ids[:k])
    relevant = set(relevant_doc_ids)
    return len(top_k & relevant) / k


def hit_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int = 5) -> float:
    """Binary: is at least one relevant document in the top-k?

    Hit@k = 1.0 if any relevant doc is in top-k, else 0.0
    """
    top_k = set(retrieved_doc_ids[:k])
    relevant = set(relevant_doc_ids)
    return 1.0 if top_k & relevant else 0.0


def mrr(retrieved_doc_ids: list[str], relevant_doc_ids: list[str]) -> float:
    """Mean Reciprocal Rank: 1/rank of the first relevant document.

    MRR = 1 / rank_of_first_relevant
    """
    relevant = set(relevant_doc_ids)
    for i, doc_id in enumerate(retrieved_doc_ids):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int = 5) -> float:
    """Normalized Discounted Cumulative Gain at k.

    Uses binary relevance (1 if relevant, 0 otherwise).
    nDCG@k = DCG@k / IDCG@k
    """
    relevant = set(relevant_doc_ids)

    # Compute DCG@k
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_doc_ids[:k]):
        rel = 1.0 if doc_id in relevant else 0.0
        dcg += rel / math.log2(i + 2)  # log2(rank + 1), rank is 1-indexed

    # Compute IDCG@k (ideal: all relevant docs first)
    ideal_rels = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_rels))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def compute_all_retrieval_metrics(
    retrieved_doc_ids: list[str],
    relevant_doc_ids: list[str],
    k_primary: int = 5,
    k_extended: int = 10,
) -> dict[str, float]:
    """Compute all retrieval metrics for a single query.

    Returns a dict with all metric values.
    """
    return {
        f"recall@{k_primary}": recall_at_k(retrieved_doc_ids, relevant_doc_ids, k_primary),
        f"recall@{k_extended}": recall_at_k(retrieved_doc_ids, relevant_doc_ids, k_extended),
        f"precision@{k_primary}": precision_at_k(retrieved_doc_ids, relevant_doc_ids, k_primary),
        f"hit@{k_primary}": hit_at_k(retrieved_doc_ids, relevant_doc_ids, k_primary),
        "mrr": mrr(retrieved_doc_ids, relevant_doc_ids),
        f"ndcg@{k_primary}": ndcg_at_k(retrieved_doc_ids, relevant_doc_ids, k_primary),
    }


def aggregate_metrics(query_metrics: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    """Aggregate per-query metrics into summary statistics.

    Returns dict with mean, std, median, min, max for each metric.
    """
    if not query_metrics:
        return {}

    metric_names = query_metrics[0].keys()
    aggregated = {}

    for name in metric_names:
        values = [qm[name] for qm in query_metrics]
        arr = np.array(values)
        aggregated[name] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "median": float(np.median(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }

    return aggregated
