"""Embedding module using Google's GenAI SDK.

Generates embeddings for document chunks and queries using
the Google GenAI embedding API.

All embeddings are cached to disk (keyed by model + task_type + text) so
that repeated queries across runs do not re-burn the free-tier API quota.
"""

from __future__ import annotations

import hashlib
import json

from google import genai
from google.genai import types
from tqdm import tqdm

from src.config import GOOGLE_API_KEY, EMBEDDING_MODEL, EMBEDDING_CACHE_FILE
from src.rate_limiter import acquire_embedding

_CACHE_VERSION = 1


def _get_client() -> genai.Client:
    return genai.Client(api_key=GOOGLE_API_KEY)


def _cache_key(model: str, task_type: str, text: str) -> str:
    raw = f"{_CACHE_VERSION}|{model}|{task_type}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class _EmbeddingCache:
    """Simple JSON-backed embedding cache with incremental persistence."""

    def __init__(self, path=EMBEDDING_CACHE_FILE):
        self._path = path
        self._data: dict[str, list[float]] = {}
        self._dirty = 0
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str) -> list[float] | None:
        return self._data.get(key)

    def set(self, key: str, embedding: list[float]) -> None:
        self._data[key] = embedding
        self._dirty += 1
        # Persist periodically so a crash/quota error doesn't lose progress.
        if self._dirty >= 20:
            self.save()

    def save(self) -> None:
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f)
        self._dirty = 0


_cache = _EmbeddingCache()


def _embed_one(model: str, text: str, task_type: str) -> list[float]:
    key = _cache_key(model, task_type, text)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    # Lazy client construction: a cache hit must work WITHOUT an API key so
    # collaborators can run retrieval demos straight after cloning.
    client = _get_client()
    acquire_embedding()
    response = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    embedding = list(response.embeddings[0].values)
    _cache.set(key, embedding)
    return embedding


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT", batch_size: int = 20) -> list[list[float]]:
    """Generate embeddings for a list of texts using Google GenAI SDK.

    Args:
        texts: List of text strings to embed.
        task_type: Retrieval task type ("RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY").
        batch_size: Number of texts to embed per API call.

    Returns:
        List of embedding vectors (list of floats).
    """
    all_embeddings = []

    # google.genai SDK embeds list of strings as a single content, so we loop individually.
    for text in tqdm(texts, desc="Embedding"):
        all_embeddings.append(_embed_one(EMBEDDING_MODEL, text, task_type))

    _cache.save()
    return all_embeddings


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a single query string (cached)."""
    embedding = _embed_one(EMBEDDING_MODEL, query, "RETRIEVAL_QUERY")
    _cache.save()
    return embedding