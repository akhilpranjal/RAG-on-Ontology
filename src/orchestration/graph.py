"""Builds the unified LangGraph orchestration graph.

Layout
------
START
  → route_expansion (conditional)
      → no_expansion          (Pipeline 1: baseline)
      → dictionary_expansion  (Pipeline 2: synonym dictionary)
      → ontology_expansion    (Pipeline 3: ontology traversal)
  → retrieve                  (shared node, all pipelines)
  → route_generate (conditional)
      → generate              (shared LLM node)
      → END

Retrieval and generation are single shared nodes; only query expansion
differs per pipeline, selected at runtime via conditional routing.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from src.config import TOP_K_PRIMARY
from src.orchestration.nodes import (
    PIPELINE_BASELINE,
    PIPELINE_DICTIONARY,
    PIPELINE_ONTOLOGY,
    dictionary_expansion,
    generate,
    no_expansion,
    ontology_expansion,
    retrieve,
    route_expansion,
)
from src.orchestration.state import OrchestrationState, build_initial_state
from src.pipelines.baseline import PipelineResult


def _route_generate(state: dict[str, Any]) -> str:
    """Conditional edge: run the LLM only if generation was requested."""
    return "generate" if state.get("generate", True) else "end"


def build_graph():
    """Build and compile the unified orchestration graph.

    Returns:
        A compiled `langgraph.graph.StateGraph` instance.
    """
    graph = StateGraph(OrchestrationState)

    # Expansion nodes (dispatched per pipeline)
    graph.add_node(PIPELINE_BASELINE, no_expansion)
    graph.add_node(PIPELINE_DICTIONARY, dictionary_expansion)
    graph.add_node(PIPELINE_ONTOLOGY, ontology_expansion)

    # Shared nodes
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)

    # Routing
    graph.add_conditional_edges(
        START,
        route_expansion,
        {
            PIPELINE_BASELINE: PIPELINE_BASELINE,
            PIPELINE_DICTIONARY: PIPELINE_DICTIONARY,
            PIPELINE_ONTOLOGY: PIPELINE_ONTOLOGY,
        },
    )
    graph.add_edge(PIPELINE_BASELINE, "retrieve")
    graph.add_edge(PIPELINE_DICTIONARY, "retrieve")
    graph.add_edge(PIPELINE_ONTOLOGY, "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        _route_generate,
        {
            "generate": "generate",
            "end": END,
        },
    )
    graph.add_edge("generate", END)

    return graph.compile()


def run_pipeline(
    query: str,
    pipeline: str = PIPELINE_BASELINE,
    top_k: int = TOP_K_PRIMARY,
    generate: bool = True,
    ablation: dict[str, bool] | None = None,
) -> PipelineResult:
    """Run a single pipeline through the unified LangGraph.

    Args:
        query: The user's medical question.
        pipeline: "baseline", "dictionary", or "ontology_enhanced".
        top_k: Number of chunks to retrieve.
        generate: Whether to run the LLM generation node.
        ablation: Ontology relation toggles (Pipeline 3 only).

    Returns:
        A PipelineResult matching the pipeline-module return type.
    """
    app = build_graph()

    initial_state = build_initial_state(
        query=query,
        pipeline=pipeline,
        top_k=top_k,
        generate=generate,
        ablation=ablation,
    )

    final_state = app.invoke(initial_state)

    return PipelineResult(
        pipeline_name=f"langgraph_{pipeline}",
        query=query,
        retrieved_chunk_ids=final_state.get("retrieved_chunk_ids", []),
        retrieved_doc_ids=final_state.get("retrieved_doc_ids", []),
        retrieved_texts=final_state.get("retrieved_texts", []),
        answer=final_state.get("answer", ""),
        metadata={
            "expansion_strategy": final_state.get("expansion_strategy", "none"),
            "expanded_terms": final_state.get("expanded_terms", []),
            "expansion_count": len(final_state.get("expanded_terms", [])),
            "reasoning_trace": final_state.get("reasoning_trace"),
            "ablation_config": initial_state.get("ablation", {}),
        },
    )


def run_all_pipelines(
    query: str,
    top_k: int = TOP_K_PRIMARY,
    generate: bool = True,
    ablation: dict[str, bool] | None = None,
) -> dict[str, PipelineResult]:
    """Run all three pipelines through the same graph for one query.

    Returns:
        Dict keyed by pipeline name ("baseline", "dictionary", "ontology_enhanced").
    """
    results = {}
    for pipeline in (PIPELINE_BASELINE, PIPELINE_DICTIONARY, PIPELINE_ONTOLOGY):
        results[pipeline] = run_pipeline(
            query=query,
            pipeline=pipeline,
            top_k=top_k,
            generate=generate,
            ablation=ablation,
        )
    return results