"""Pipeline 2: Dictionary Expansion RAG.

Query → Synonym Dictionary Lookup → Expanded Query → Vector Search → Generator
Proves whether a full ontology is better than a simple synonym list.
"""

from __future__ import annotations

from src.corpus.vectorstore import search_with_expanded_query
from src.generation.generator import generate_answer
from src.ontology.synonym_expander import SynonymExpander
from src.pipelines.baseline import PipelineResult
from src.config import TOP_K_PRIMARY


def run_dictionary(query: str, top_k: int = TOP_K_PRIMARY, generate: bool = True) -> PipelineResult:
    """Run Pipeline 2: Dictionary Expansion RAG.

    Args:
        query: The user's medical question.
        top_k: Number of chunks to retrieve.
        generate: Whether to generate an answer with the LLM.

    Returns:
        PipelineResult with retrieved chunks and generated answer.
    """
    # Step 1: Expand query using synonym dictionary
    expander = SynonymExpander()
    expanded_terms = expander.expand(query)

    # Step 2: Search with expanded query
    results = search_with_expanded_query(
        original_query=query,
        expanded_terms=expanded_terms,
        top_k=top_k,
    )

    # Extract results
    chunk_ids = results["ids"][0] if results["ids"] else []
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    doc_ids = [m.get("doc_id", "") for m in metadatas]

    # Step 3: Generate answer (no ontology context in the prompt)
    answer = ""
    if generate and documents:
        answer = generate_answer(
            question=query,
            context_chunks=documents,
        )

    return PipelineResult(
        pipeline_name="dictionary_expansion_rag",
        query=query,
        retrieved_chunk_ids=chunk_ids,
        retrieved_doc_ids=doc_ids,
        retrieved_texts=documents,
        answer=answer,
        metadata={
            "expanded_terms": expanded_terms,
            "expansion_count": len(expanded_terms),
        },
    )
