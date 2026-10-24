"""Shared state schema for the LangGraph orchestration graph.

All three pipelines share the same node contract; the only thing that
differs between them is the query-expansion strategy selected at the
routing step.
"""

from __future__ import annotations

from typing import Any, TypedDict


class OrchestrationState(TypedDict, total=False):
    """State flowing through the orchestration graph.

    Fields marked "input" are set by the caller; all others are written
    by graph nodes.
    """
    # ── Input fields ────────────────────────────────────────────
    query: str                       # user's medical question
    pipeline: str                    # "baseline" | "dictionary" | "ontology_enhanced"
    top_k: int                       # number of chunks to retrieve
    generate: bool                   # whether to run the LLM generation node
    ablation: dict[str, bool]        # relation toggles for ontology expansion

    # ── Written by the expansion nodes ──────────────────────────
    expansion_strategy: str          # which expansion ran ("none"/"dictionary"/"ontology")
    expanded_terms: list[str]        # terms added to the query
    reasoning_trace: dict[str, Any] | None  # ontology reasoning trace (Pipeline 3)

    # ── Written by the retrieve node ────────────────────────────
    retrieved_chunk_ids: list[str]
    retrieved_doc_ids: list[str]
    retrieved_texts: list[str]

    # ── Written by the generate node ────────────────────────────
    answer: str

    # ── Final metadata ──────────────────────────────────────────
    metadata: dict[str, Any]


def build_initial_state(
    query: str,
    pipeline: str = "baseline",
    top_k: int = 5,
    generate: bool = True,
    ablation: dict[str, bool] | None = None,
) -> OrchestrationState:
    """Construct the initial state for a graph invocation."""
    default_ablation = {
        "equivalence": True,
        "hierarchy": True,
        "properties": True,
    }
    if ablation is None:
        ablation = default_ablation

    return {
        "query": query,
        "pipeline": pipeline,
        "top_k": top_k,
        "generate": generate,
        "ablation": {**default_ablation, **ablation},
        "expansion_strategy": "none",
        "expanded_terms": [],
        "reasoning_trace": None,
        "retrieved_chunk_ids": [],
        "retrieved_doc_ids": [],
        "retrieved_texts": [],
        "answer": "",
        "metadata": {},
    }