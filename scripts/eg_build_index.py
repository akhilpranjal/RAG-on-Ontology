"""Build the FAISS index for the PubMedQA retrieval corpus."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_gate.config import INDEX_DIR, PASSAGE_MODEL, PUBMEDQA_DIR, RETRIEVER_BACKEND, ST_MODEL
from evidence_gate.retriever import DenseRetriever


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default=RETRIEVER_BACKEND, choices=["st", "medcpt"])
    parser.add_argument("--model", default=ST_MODEL, help="SentenceTransformer model name")
    parser.add_argument("--corpus", type=Path, default=PUBMEDQA_DIR / "corpus.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="Use only the first N abstracts")
    parser.add_argument("--out", type=Path, default=INDEX_DIR)
    args = parser.parse_args()

    rows = []
    with open(args.corpus, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    if args.limit:
        rows = rows[: args.limit]
    print(f"[data] {len(rows)} passages from {args.corpus}")

    retriever = DenseRetriever(backend=args.backend, st_model=args.model)
    started = time.time()
    retriever.build_index(
        ids=[row["id"] for row in rows],
        texts=[row["text"] for row in rows],
        metadata=[
            {"meshes": row.get("meshes", []), "title": row.get("title", "")}
            for row in rows
        ],
        save=False,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    retriever.save_index(args.out)
    elapsed = time.time() - started
    meta = json.loads((args.out / "index_meta.json").read_text(encoding="utf-8"))
    meta.update(
        {
            "build_seconds": round(elapsed, 1),
            "passages_per_second": round(len(rows) / max(elapsed, 1e-9), 1),
            "corpus_file": str(args.corpus),
            "medcpt_passage_model": PASSAGE_MODEL,
        }
    )
    (args.out / "index_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
