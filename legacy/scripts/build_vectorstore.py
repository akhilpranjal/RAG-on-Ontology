"""Build the vector store from the corpus.

One-time script to load documents, chunk them, embed them,
and index them into ChromaDB.
"""

from src.config import ensure_directories
from src.corpus.loader import load_and_chunk_corpus
from src.corpus.vectorstore import index_chunks


def main():
    """Build the ChromaDB vector store from all corpus documents."""
    print("=" * 60)
    print("Building Vector Store")
    print("=" * 60)

    # Ensure all directories exist
    ensure_directories()

    # Load and chunk all documents
    print("\n1. Loading and chunking corpus...")
    chunks = load_and_chunk_corpus()
    print(f"   Total chunks: {len(chunks)}")

    if not chunks:
        print("\n⚠  No documents found in corpus directories.")
        print("   Please add documents to data/corpus/real/ and/or data/corpus/synthetic/")
        print("   Run scripts/collect_pubmed.py to download PubMed abstracts first.")
        return

    # Index into ChromaDB
    print("\n2. Embedding and indexing chunks...")
    index_chunks(chunks)

    print("\n[OK] Vector store built successfully!")
    print(f"  Chunks indexed: {len(chunks)}")


if __name__ == "__main__":
    main()
