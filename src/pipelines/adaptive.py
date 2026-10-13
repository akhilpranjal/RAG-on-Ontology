"""Pipeline 4: AdaOnto-RAG — adaptive ontology-gated retrieval (Experiment 2).

Query → Symbolic Router → Selective Expansion → Dense Retrieve (pool) →
MMR Diversity Rerank → Trace-Grounded Generation.

Modes (component ablations, same protocol):
  - "full":      router + selective expansion + MMR rerank (the new architecture)
  - "selective": router + selective expansion, dense order (no rerank)
  - "mmr":       no expansion, dense + MMR rerank (router bypassed)

Pre-registered constants: POOL_SIZE = 20 (see docs/report/architecture_design.md).
"""

from __future__ import annotations

from src.config import TOP_K_PRIMARY
from src.corpus.vectorstore import (
    get_or_create_collection,
    search,
    search_with_expanded_query,
)
from src.generation.generator import generate_answer
from src.ontology.reasoner import OntologyReasoner, ReasoningTrace
from src.pipelines.baseline import PipelineResult
from src.pipelines.router import QueryRouter
from src.retrieval.rerank import mmr_rerank

POOL_SIZE = 20  # pre-registered candidate pool for MMR

_router: QueryRouter | None = None
_reasoner: OntologyReasoner | None = None


def _get_router() -> QueryRouter:
    global _router
    if _router is None:
        _router = QueryRouter()
    return _router


def _get_reasoner() -> OntologyReasoner:
    global _reasoner
    if _reasoner is None:
        _reasoner = OntologyReasoner()
    return _reasoner


def _fetch_embeddings(chunk_ids: list[str]) -> dict[str, list[float]]:
    """Local fetch of stored chunk embeddings (no API cost)."""
    collection = get_or_create_collection()
    got = collection.get(ids=list(chunk_ids), include=["embeddings"])
    ids = got.get("ids")
    embs = got.get("embeddings")
    if ids is None or embs is None:
        return {}
    return {cid: list(emb) for cid, emb in zip(ids, embs) if emb is not None}


def run_adaptive(
    query: str,
    top_k: int = TOP_K_PRIMARY,
    generate: bool = True,
    mode: str = "full",
) -> PipelineResult:
    """Run Pipeline 4: AdaOnto-RAG.

    Args:
        query: The user's medical question.
        top_k: Number of chunks to return.
        generate: Whether to generate an answer with the LLM.
        mode: "full" (router+selective+MMR), "selective" (no MMR),
            "mmr" (no expansion/router, dense+MMR).
    """
    if mode not in ("full", "selective", "mmr"):
        raise ValueError(f"unknown mode: {mode}")

    use_router = mode in ("full", "selective")
    use_rerank = mode in ("full", "mmr")

    # Step 1: route -> selective expansion mask.
    route_info: dict = {}
    if use_router:
        route_info = _get_router().route(query)
        trace: ReasoningTrace | None = None
        expanded_terms: list[str] = []
        if route_info["use_expansion"]:
            trace = _get_reasoner().expand_query(
                query,
                use_equivalence=route_info["use_equivalence"],
                use_hierarchy=route_info["use_hierarchy"],
                use_properties=route_info["use_properties"],
            )
            expanded_terms = trace.get_all_terms()
    else:
        trace = None
        expanded_terms = []

    # Step 2: dense retrieve a candidate pool.
    pool_n = max(POOL_SIZE, top_k) if use_rerank else top_k
    if expanded_terms:
        results = search_with_expanded_query(query, expanded_terms, top_k=pool_n)
    else:
        results = search(query, top_k=pool_n)

    chunk_ids = list(results["ids"][0]) if results["ids"] else []
    documents = list(results["documents"][0]) if results["documents"] else []
    metadatas = list(results["metadatas"][0]) if results["metadatas"] else []
    distances = list(results["distances"][0]) if results.get("distances") else [0.0] * len(chunk_ids)
    doc_ids = [m.get("doc_id", "") for m in metadatas]

    # Step 3: MMR diversity rerank (dedup by doc_id).
    reranked = False
    if use_rerank and chunk_ids:
        emb_map = _fetch_embeddings(chunk_ids)
        order = [i for i in range(len(chunk_ids)) if chunk_ids[i] in emb_map]
        if order:
            sel = mmr_rerank(
                [chunk_ids[i] for i in order],
                [distances[i] for i in order],
                [doc_ids[i] for i in order],
                [emb_map[chunk_ids[i]] for i in order],
                top_k=top_k,
            )
            order = [order[i] for i in sel]
            chunk_ids = [chunk_ids[i] for i in order]
            documents = [documents[i] for i in order]
            metadatas = [metadatas[i] for i in order]
            doc_ids = [doc_ids[i] for i in order]
            reranked = True
    else:
        chunk_ids, documents, metadatas, doc_ids = (
            chunk_ids[:top_k],
            documents[:top_k],
            metadatas[:top_k],
            doc_ids[:top_k],
        )

    # Step 4: generate (trace-grounded when expansion was used).
    answer = ""
    if generate and documents:
        answer = generate_answer(
            question=query,
            context_chunks=documents,
            ontology_context=trace.format_for_prompt() if trace is not None else None,
        )

    metadata: dict = {
        "mode": mode,
        "intent": route_info.get("intent"),
        "mask": route_info.get("mask"),
        "lay_terms_found": route_info.get("lay_terms_found", []),
        "matched_concepts": route_info.get("matched_concepts", []),
        "expanded_terms": expanded_terms,
        "expansion_count": len(expanded_terms),
        "reranked": reranked,
        "pool_size": pool_n if use_rerank else top_k,
    }
    if trace is not None:
        metadata["reasoning_trace"] = trace.to_dict()

    names = {"full": "adaptive_full", "selective": "adaptive_selective", "mmr": "adaptive_mmr"}
    return PipelineResult(
        pipeline_name=names[mode],
        query=query,
        retrieved_chunk_ids=chunk_ids,
        retrieved_doc_ids=doc_ids,
        retrieved_texts=documents,
        answer=answer,
        metadata=metadata,
    )
