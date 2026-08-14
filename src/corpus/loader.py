"""Document loader and chunker for the medical corpus.

Loads documents from the real/ and synthetic/ corpus directories,
splits them into chunks suitable for embedding, and returns them
with metadata (source, document ID, ground-truth concepts).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from src.config import REAL_CORPUS_DIR, SYNTHETIC_CORPUS_DIR, CHUNK_SIZE, CHUNK_OVERLAP


class DocumentChunk(TypedDict):
    """Represents a single chunk of a medical document."""
    chunk_id: str
    doc_id: str
    text: str
    source: str           # "real" or "synthetic"
    source_file: str      # original filename
    concepts: list[str]   # ground-truth ontology concept local names


def load_documents(corpus_dir: Path) -> list[dict]:
    """Load all .json document files from a corpus directory.

    Each JSON file should have the schema:
    {
        "doc_id": "pubmed_12345",
        "title": "...",
        "text": "...",
        "source": "PubMed",
        "url": "...",
        "concepts": ["Hypertension", "ACEInhibitor", ...]
    }
    """
    documents = []
    if not corpus_dir.exists():
        return documents

    for filepath in sorted(corpus_dir.glob("*.json")):
        with open(filepath, "r", encoding="utf-8") as f:
            doc = json.load(f)
            doc["_source_file"] = filepath.name
            documents.append(doc)

    return documents


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks.

    Uses a simple character-based sliding window. For medical text,
    this is sufficient given the relatively short document lengths
    (abstracts, fact sheets).
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def load_and_chunk_corpus() -> list[DocumentChunk]:
    """Load all documents from real and synthetic corpus, chunk them, and return.

    Returns a list of DocumentChunk dicts ready for embedding and indexing.
    """
    all_chunks: list[DocumentChunk] = []

    for source_label, corpus_dir in [("real", REAL_CORPUS_DIR), ("synthetic", SYNTHETIC_CORPUS_DIR)]:
        documents = load_documents(corpus_dir)

        for doc in documents:
            text = doc.get("text", "")
            title = doc.get("title", "")

            # Prepend title to text for richer context
            full_text = f"{title}\n\n{text}" if title else text

            chunks = chunk_text(full_text)

            for i, chunk_text_content in enumerate(chunks):
                chunk_id = f"{doc['doc_id']}_chunk_{i:03d}"
                all_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        doc_id=doc["doc_id"],
                        text=chunk_text_content,
                        source=source_label,
                        source_file=doc.get("_source_file", ""),
                        concepts=doc.get("concepts", []),
                    )
                )

    return all_chunks
