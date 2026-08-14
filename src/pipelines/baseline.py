"""Pipeline 1: Baseline Semantic RAG.

Query → Embed → Vector Search → Generator
No query expansion — pure semantic similarity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.corpus.vectorstore import search
from src.generation.generator import generate_answer
from src.config import TOP_K_PRIMARY


@dataclass
class PipelineResult:
    """Result from a pipeline run."""
    pipeline_name: str
    query: str
    retrieved_chunk_ids: list[str]
    retrieved_doc_ids: list[str]
    retrieved_texts: list[str]
    answer: str
    metadata: dict = field(default_factory=dict)


def run_baseline(query: str, top_k: int = TOP_K_PRIMARY, generate: bool = True) -> PipelineResult:
    """Run Pipeline 1: Baseline Semantic RAG.

    Args:
        query: The user's medical question.
        top_k: Number of chunks to retrieve.
        generate: Whether to generate an answer with the LLM.

    Returns:
        PipelineResult with retrieved chunks and generated answer.
    """
    # Step 1: Vector search (no expansion)
    results = search(query, top_k=top_k)

    # Extract results
    chunk_ids = results["ids"][0] if results["ids"] else []
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []

    # Extract unique doc_ids from metadata
    doc_ids = [m.get("doc_id", "") for m in metadatas]

    # Step 2: Generate answer
    answer = ""
    if generate and documents:
        answer = generate_answer(
            question=query,
            context_chunks=documents,
        )

    return PipelineResult(
        pipeline_name="baseline_semantic_rag",
        query=query,
        retrieved_chunk_ids=chunk_ids,
        retrieved_doc_ids=doc_ids,
        retrieved_texts=documents,
        answer=answer,
    )
