"""Corpus annotator — automatically tags corpus JSON documents with concept local names.

Scans all document JSON files in data/corpus/real and data/corpus/synthetic,
matches concept labels from medical_ontology.ttl against document text,
and updates the 'concepts' list in each document JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path
from src.config import REAL_CORPUS_DIR, SYNTHETIC_CORPUS_DIR
from src.ontology.reasoner import OntologyReasoner


def annotate_directory(corpus_dir: Path, reasoner: OntologyReasoner) -> int:
    """Annotate all JSON documents in a directory.

    Docs that already carry a non-empty 'concepts' list are left untouched
    (preserves manual annotations and makes the script idempotent).

    Args:
        corpus_dir: Directory containing document JSON files.
        reasoner: Initialized OntologyReasoner instance.

    Returns:
        Number of documents updated.
    """
    if not corpus_dir.exists():
        return 0

    updated_count = 0
    for filepath in sorted(corpus_dir.glob("*.json")):
        with open(filepath, "r", encoding="utf-8") as f:
            doc = json.load(f)

        # Skip docs already annotated (manual or previous run).
        if doc.get("concepts"):
            continue

        full_text = f"{doc.get('title', '')} {doc.get('text', '')}"
        matches = reasoner.match_concepts(full_text)

        # Extract unique concept local names
        concept_ids = sorted(list({m["concept_id"] for m in matches}))
        doc["concepts"] = concept_ids

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        updated_count += 1

    return updated_count


def main():
    print("=" * 60)
    print("Annotating Corpus Documents with Ontology Concepts")
    print("=" * 60)

    reasoner = OntologyReasoner()

    real_count = annotate_directory(REAL_CORPUS_DIR, reasoner)
    synth_count = annotate_directory(SYNTHETIC_CORPUS_DIR, reasoner)

    print(f"\n[OK] Annotated {real_count} real documents in {REAL_CORPUS_DIR}")
    print(f"[OK] Annotated {synth_count} synthetic documents in {SYNTHETIC_CORPUS_DIR}")


if __name__ == "__main__":
    main()
