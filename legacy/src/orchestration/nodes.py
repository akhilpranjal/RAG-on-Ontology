"""Shared node implementations for the orchestration graph.

Nodes are pure functions taking an `OrchestrationState` and returning a
partial state dict; LangGraph merges returned keys into the graph state.
"""

from __future__ import annotations

from typing import Any

from src.config import TOP_K_PRIMARY
from src.corpus.vectorstore import search, search_with_expanded_query
from src.generation.generator import generate_answer
from src.ontology.reasoner import OntologyReasoner
from src.ontology.synonym_expander import SynonymExpander

PIPELINE_BASELINE = "baseline"
PIPELINE_DICTIONARY = "dictionary"
PIPELINE_ONTOLOGY = "ontology_enhanced"


def route_expansion(state: dict[str, Any]) -> str:
    """Route to the correct expansion node based on the requested pipeline."""
    return state.get("pipeline", PIPELINE_BASELINE)


def no_expansion(state: dict[str, Any]) -> dict[str, Any]:
    """Pipeline 1: no query expansion — pure semantic retrieval."""
    return {
        "expansion_strategy": "none",
        "expanded_terms": [],
        "reasoning_trace": None,
    }


def dictionary_expansion(state: dict[str, Any]) -> dict[str, Any]:
    """Pipeline 2: expand the query with lay↔clinical synonyms."""
    expander = SynonymExpander()
    expanded_terms = expander.expand(state["query"])

    return {
        "expansion_strategy": "dictionary",
        "expanded_terms": expanded_terms,
        "reasoning_trace": None,
    }


def ontology_expansion(state: dict[str, Any]) -> dict[str, Any]:
    """Pipeline 3: expand via ontology graph traversal (with ablation toggles)."""
    reasoner = OntologyReasoner()

    ablation = state.get("ablation", {})
    reasoning_trace = reasoner.expand_query(
        state["query"],
        use_equivalence=ablation.get("equivalence", True),
        use_hierarchy=ablation.get("hierarchy", True),
        use_properties=ablation.get("properties", True),
    )

    return {
        "expansion_strategy": "ontology",
        "expanded_terms": reasoning_trace.get_all_terms(),
        "reasoning_trace": reasoning_trace.to_dict(),
    }


def retrieve(state: dict[str, Any]) -> dict[str, Any]:
    """Shared retrieval node — used by all three pipelines.

    Uses expanded terms when present, otherwise plain vector search.
    """
    top_k = state.get("top_k", TOP_K_PRIMARY)
    expanded_terms = state.get("expanded_terms", [])

    if expanded_terms:
        results = search_with_expanded_query(
            original_query=state["query"],
            expanded_terms=expanded_terms,
            top_k=top_k,
        )
    else:
        results = search(state["query"], top_k=top_k)

    chunk_ids = results["ids"][0] if results["ids"] else []
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    doc_ids = [m.get("doc_id", "") for m in metadatas]

    return {
        "retrieved_chunk_ids": chunk_ids,
        "retrieved_doc_ids": doc_ids,
        "retrieved_texts": documents,
    }


def generate(state: dict[str, Any]) -> dict[str, Any]:
    """Shared generation node — used by all three pipelines.

    Pipeline 3 additionally supplies the ontology reasoning trace as
    context to the generator prompt.
    """
    if not state.get("retrieved_texts"):
        return {"answer": ""}

    reasoning_trace = state.get("reasoning_trace")
    ontology_context = None
    if reasoning_trace:
        trace = reasoning_trace
        lines = [f"Query: {trace.get('original_query', '')}"]
        for match in trace.get("matched_concepts", []):
            lines.append(
                f"  Matched: '{match.get('term', '')}' → "
                f"{match.get('concept_id', '')} ({match.get('label', '')})"
            )
        for exp in trace.get("expansions", []):
            lines.append(
                f"  Expansion ({exp.get('relation', '')}): "
                f"{exp.get('source', '')} → {exp.get('target', '')} "
                f"({exp.get('target_label', '')})"
            )
        ontology_context = "\n".join(lines)

    answer = generate_answer(
        question=state["query"],
        context_chunks=state["retrieved_texts"],
        ontology_context=ontology_context,
    )

    return {"answer": answer}