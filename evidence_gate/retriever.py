"""Dense passage retrieval over the PubMedQA abstract corpus."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np

from evidence_gate.config import (
    INDEX_DIR,
    PASSAGE_MODEL,
    RETRIEVER_BACKEND,
    RETRIEVER_MODEL,
    ST_MODEL,
    TOP_K,
    configure_cpu,
)

logger = logging.getLogger(__name__)


@dataclass
class Passage:
    id: str
    text: str
    score: float
    metadata: dict

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "score": self.score,
            "metadata": self.metadata,
        }


class DenseRetriever:
    """Bi-encoder retrieval with an exact FAISS inner-product index."""

    def __init__(
        self,
        backend: str = RETRIEVER_BACKEND,
        st_model: str = ST_MODEL,
        query_model: str = RETRIEVER_MODEL,
        passage_model: str = PASSAGE_MODEL,
        device: str | None = None,
    ):
        import torch

        configure_cpu()
        self.backend = backend
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.index: faiss.IndexFlatIP | None = None
        self.passage_ids: list[str] = []
        self.passage_texts: list[str] = []
        self.passage_metadata: list[dict] = []
        self.dim: int | None = None

        if backend == "st":
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformer retriever: %s", st_model)
            self.st_model_name = st_model
            self.st = SentenceTransformer(st_model, device=self.device)
            self.dim = self.st.get_sentence_embedding_dimension()
        elif backend == "medcpt":
            from transformers import AutoModel, AutoTokenizer

            logger.info("Loading MedCPT query encoder: %s", query_model)
            self.query_tokenizer = AutoTokenizer.from_pretrained(query_model)
            self.query_model = AutoModel.from_pretrained(query_model).to(self.device).eval()
            logger.info("Loading MedCPT passage encoder: %s", passage_model)
            self.passage_tokenizer = AutoTokenizer.from_pretrained(passage_model)
            self.passage_model = AutoModel.from_pretrained(passage_model).to(self.device).eval()
            self.dim = self.query_model.config.hidden_size
        else:
            raise ValueError(f"Unknown retriever backend: {backend}")

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------
    def _encode(self, texts: list[str], kind: str) -> np.ndarray:
        if self.backend == "st":
            embeddings = self.st.encode(
                texts,
                batch_size=64,
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 256,
                convert_to_numpy=True,
            )
            return embeddings.astype(np.float32)

        import torch

        tokenizer = self.query_tokenizer if kind == "query" else self.passage_tokenizer
        model = self.query_model if kind == "query" else self.passage_model
        max_length = 256 if kind == "query" else 512
        batch_size = 32
        out: list[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                inputs = tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                ).to(self.device)
                hidden = model(**inputs).last_hidden_state[:, 0, :]
                hidden = torch.nn.functional.normalize(hidden, dim=-1)
                out.append(hidden.cpu().numpy())
        return np.vstack(out).astype(np.float32)

    # ------------------------------------------------------------------
    # Index lifecycle
    # ------------------------------------------------------------------
    def build_index(
        self,
        ids: list[str],
        texts: list[str],
        metadata: list[dict] | None = None,
        save: bool = True,
    ) -> None:
        logger.info("Encoding %d passages ...", len(texts))
        embeddings = self._encode(texts, kind="passage")
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)
        self.passage_ids = list(ids)
        self.passage_texts = list(texts)
        self.passage_metadata = list(metadata or [{} for _ in ids])
        self.dim = embeddings.shape[1]
        logger.info("Built FAISS index: %d vectors, dim=%d", self.index.ntotal, self.dim)
        if save:
            self.save_index()

    def save_index(self, index_dir: Path | None = None) -> None:
        index_dir = Path(index_dir or INDEX_DIR)
        index_dir.mkdir(parents=True, exist_ok=True)
        if self.index is None:
            raise RuntimeError("No index to save.")
        faiss.write_index(self.index, str(index_dir / "index.faiss"))
        with open(index_dir / "passages.json", "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "ids": self.passage_ids,
                    "texts": self.passage_texts,
                    "metadata": self.passage_metadata,
                },
                fh,
                ensure_ascii=True,
            )
        meta = {
            "backend": self.backend,
            "model": self.st_model_name if self.backend == "st" else PASSAGE_MODEL,
            "dim": self.dim,
            "n_passages": len(self.passage_ids),
        }
        (index_dir / "index_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("Saved index to %s", index_dir)

    def load_index(self, index_dir: Path | None = None) -> None:
        index_dir = Path(index_dir or INDEX_DIR)
        self.index = faiss.read_index(str(index_dir / "index.faiss"))
        with open(index_dir / "passages.json", encoding="utf-8") as fh:
            data = json.load(fh)
        self.passage_ids = data["ids"]
        self.passage_texts = data["texts"]
        self.passage_metadata = data.get("metadata", [{} for _ in self.passage_ids])
        meta_path = index_dir / "index_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("model") != (
                self.st_model_name if self.backend == "st" else PASSAGE_MODEL
            ):
                logger.warning(
                    "Index was built with %s but retriever uses %s",
                    meta.get("model"),
                    self.st_model_name if self.backend == "st" else PASSAGE_MODEL,
                )
        self.dim = self.index.d
        logger.info("Loaded FAISS index: %d vectors", self.index.ntotal)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        exclude_ids: set[str] | None = None,
    ) -> list[Passage]:
        if self.index is None:
            raise RuntimeError("No index loaded.")
        exclude_ids = exclude_ids or set()
        fetch_k = top_k + len(exclude_ids)
        query_emb = self._encode([query], kind="query")
        scores, indices = self.index.search(query_emb, fetch_k)

        results: list[Passage] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            passage_id = self.passage_ids[idx]
            if passage_id in exclude_ids:
                continue
            results.append(
                Passage(
                    id=passage_id,
                    text=self.passage_texts[idx],
                    score=float(score),
                    metadata=self.passage_metadata[idx],
                )
            )
            if len(results) >= top_k:
                break
        return results
