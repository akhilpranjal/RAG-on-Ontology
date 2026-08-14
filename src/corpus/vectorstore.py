"""ChromaDB vector store setup, indexing, and search.

Manages the ChromaDB collection for medical document chunks,
providing indexing and similarity search functionality.
"""

from __future__ import annotations

from typing import Any

import chromadb
from chromadb.config import Settings

from src.config import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR, TOP_K_PRIMARY
from src.corpus.loader import DocumentChunk
from src.corpus.embedder import embed_texts, embed_query


def get_chroma_client() -> chromadb.ClientAPI:
    """Get a persistent ChromaDB client."""
    return chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )


def get_or_create_collection(client: chromadb.ClientAPI | None = None) -> chromadb.Collection:
    """Get or create the medical corpus collection."""
    if client is None:
        client = get_chroma_client()
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def index_chunks(chunks: list[DocumentChunk], batch_size: int = 50, reset: bool = False) -> None:
    """Embed and index document chunks into ChromaDB.

    Args:
        chunks: List of DocumentChunk dicts to index.
        batch_size: Number of chunks to process at a time.
        reset: If True, delete any existing collection before indexing
            (used when the corpus has changed and needs a fresh rebuild).
    """
    client = get_chroma_client()
    if reset:
        try:
            client.delete_collection(CHROMA_COLLECTION_NAME)
            print(f"Reset collection '{CHROMA_COLLECTION_NAME}' for fresh indexing.")
        except Exception:  # noqa: BLE001 - collection may not exist
            pass

    collection = get_or_create_collection(client)

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]

        ids = [chunk["chunk_id"] for chunk in batch]
        texts = [chunk["text"] for chunk in batch]
        metadatas = [
            {
                "doc_id": chunk["doc_id"],
                "source": chunk["source"],
                "source_file": chunk["source_file"],
                "concepts": ",".join(chunk["concepts"]),
            }
            for chunk in batch
        ]

        # Generate embeddings
        embeddings = embed_texts(texts, task_type="retrieval_document")

        # Upsert (idempotent for re-indexing; handles duplicate IDs safely)
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    print(f"Indexed {len(chunks)} chunks into ChromaDB collection '{CHROMA_COLLECTION_NAME}'.")


def search(query: str, top_k: int = TOP_K_PRIMARY, query_embedding: list[float] | None = None) -> dict[str, Any]:
    """Search the vector store for chunks relevant to a query.

    Args:
        query: The search query string.
        top_k: Number of results to return.
        query_embedding: Pre-computed query embedding. If None, will be computed.

    Returns:
        ChromaDB query results dict with keys: ids, documents, metadatas, distances.
    """
    collection = get_or_create_collection()

    if query_embedding is None:
        query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    return results


def search_with_expanded_query(
    original_query: str,
    expanded_terms: list[str],
    top_k: int = TOP_K_PRIMARY,
) -> dict[str, Any]:
    """Search using an expanded query that combines original + expansion terms.

    Constructs an expanded query string and embeds it for retrieval.
    This is the core mechanism for Pipelines 2 and 3.

    Args:
        original_query: The original user query.
        expanded_terms: Additional terms from synonym/ontology expansion.
        top_k: Number of results to return.

    Returns:
        ChromaDB query results dict.
    """
    # Combine original query with expansion terms
    expansion_text = " ".join(expanded_terms)
    expanded_query = f"{original_query} {expansion_text}"

    return search(expanded_query, top_k=top_k)
