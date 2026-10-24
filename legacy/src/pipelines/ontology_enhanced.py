"""Pipeline 3: Ontology-Enhanced RAG.

Query → Ontology Reasoning (rdflib traversal) → Expanded Query + Reasoning Log → Vector Search → Generator
The core experimental pipeline that uses structured ontology traversal.
"""

from __future__ import annotations

from src.corpus.vectorstore import search_with_expanded_query
from src.generation.generator import generate_answer
from src.ontology.reasoner import OntologyReasoner, ReasoningTrace
from src.pipelines.baseline import PipelineResult
from src.config import TOP_K_PRIMARY


def run_ontology_enhanced(
    query: str,
    top_k: int = TOP_K_PRIMARY,
    generate: bool = True,
    enable_equivalence: bool = True,
    enable_hierarchy: bool = True,
    enable_properties: bool = True,
) -> PipelineResult:
    """Run Pipeline 3: Ontology-Enhanced RAG.

    Args:
        query: The user's medical query.
        top_k: Number of chunks to retrieve.
        generate: Whether to generate an answer with the LLM.
        enable_equivalence: Use owl:equivalentClass.
        enable_hierarchy: Use rdfs:subClassOf.
        enable_properties: Use hasSymptom, treatedBy, etc.

    Returns:
        PipelineResult with retrieved chunks, generated answer, and reasoning trace.
    """
    # Initialize reasoner
    reasoner = OntologyReasoner()

    # Step 1: Expand query using Ontology Reasoner
    reasoning_trace = reasoner.expand_query(
        query,
        use_equivalence=enable_equivalence,
        use_hierarchy=enable_hierarchy,
        use_properties=enable_properties,
    )

    expanded_terms = reasoning_trace.get_all_terms()

    # Step 2: Retrieve
    results = search_with_expanded_query(query, expanded_terms, top_k=top_k)

    chunk_ids = results["ids"][0] if results["ids"] else []
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    doc_ids = [m.get("doc_id", "") for m in metadatas]

    # Step 3: Generate answer, including the reasoning trace as context
    answer = ""
    if generate and documents:
        answer = generate_answer(
            question=query,
            context_chunks=documents,
            ontology_context=reasoning_trace.format_for_prompt(),
        )

    return PipelineResult(
        pipeline_name="ontology_enhanced_rag",
        query=query,
        retrieved_chunk_ids=chunk_ids,
        retrieved_doc_ids=doc_ids,
        retrieved_texts=documents,
        answer=answer,
        metadata={
            "reasoning_trace": reasoning_trace.to_dict(),
            "expanded_terms": expanded_terms,
            "expansion_count": len(expanded_terms),
            "ablation_config": {
                "equivalence": enable_equivalence,
                "hierarchy": enable_hierarchy,
                "properties": enable_properties,
            },
        },
    )
