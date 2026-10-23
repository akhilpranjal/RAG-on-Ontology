"""Download PubMedQA and build the open-book retrieval corpus.

Outputs
-------
data/pubmedqa/labeled.jsonl  1000 expert-labelled instances (question + context)
data/pubmedqa/splits.json    fixed 500/500 dev-test split (seed 42)
data/pubmedqa/corpus.jsonl   unique PubMed abstracts used as the retrieval corpus
data/pubmedqa/stats.json     dataset statistics for the paper
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "pubmedqa"


def section_text(context: dict) -> str:
    parts = []
    for label, text in zip(context.get("labels", []), context.get("contexts", [])):
        text = (text or "").strip()
        if text:
            parts.append(f"{label}: {text}")
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--corpus-size",
        type=int,
        default=22000,
        help="Total abstracts in the retrieval corpus (including the 1000 labelled).",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("[hf] loading pqa_labeled ...", flush=True)
    labeled = load_dataset("qiaojin/PubMedQA", "pqa_labeled", split="train")
    label_rows = []
    for row in labeled:
        label_rows.append(
            {
                "pubid": str(row["pubid"]),
                "question": row["question"].strip(),
                "contexts": row["context"]["contexts"],
                "labels": row["context"]["labels"],
                "meshes": row["context"]["meshes"],
                "long_answer": row["long_answer"],
                "final_decision": row["final_decision"],
            }
        )

    order = list(range(len(label_rows)))
    random.Random(args.seed).shuffle(order)
    dev_idx = sorted(order[:500])
    test_idx = sorted(order[500:1000])
    splits = {
        "seed": args.seed,
        "dev": [label_rows[i]["pubid"] for i in dev_idx],
        "test": [label_rows[i]["pubid"] for i in test_idx],
    }
    (DATA_DIR / "splits.json").write_text(json.dumps(splits, indent=2), encoding="utf-8")
    with open(DATA_DIR / "labeled.jsonl", "w", encoding="utf-8") as fh:
        for row in label_rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")
    print(f"[ok ] labeled: {len(label_rows)} rows, dev={len(dev_idx)}, test={len(test_idx)}")

    print("[hf] loading pqa_artificial ...", flush=True)
    artificial = load_dataset("qiaojin/PubMedQA", "pqa_artificial", split="train")
    print(f"[ok ] artificial rows: {len(artificial)}")

    abstracts: dict[str, dict] = {}
    # The 1000 expert-labelled abstracts are always part of the corpus, so a
    # retrieval system can in principle find the source study. The runner may
    # exclude a question's own abstract as a leakage-control setting.
    for row in label_rows:
        text = section_text(
            {"contexts": row["contexts"], "labels": row["labels"]}
        )
        if text:
            abstracts[row["pubid"]] = {
                "id": row["pubid"],
                "text": text,
                "meshes": row["meshes"],
                "title": row["question"],
                "n_chars": len(text),
            }

    for row in artificial:
        pubid = str(row["pubid"])
        if pubid in abstracts:
            continue
        context = row["context"]
        text = section_text(context)
        if not text:
            continue
        abstracts[pubid] = {
            "id": pubid,
            "text": text,
            "meshes": context.get("meshes", []),
            "title": row.get("question", "").strip(),
            "n_chars": len(text),
        }
    print(f"[ok ] unique abstracts: {len(abstracts)}")

    labeled_ids = {row["pubid"] for row in label_rows}
    distractors = [row for pid, row in abstracts.items() if pid not in labeled_ids]
    rng = random.Random(args.seed)
    target_distractors = max(0, (args.corpus_size or 0) - len(labeled_ids)) if args.corpus_size else len(distractors)
    if target_distractors < len(distractors):
        distractors = rng.sample(distractors, target_distractors)
    corpus = [abstracts[pid] for pid in sorted(labeled_ids) if pid in abstracts]
    corpus.extend(distractors)
    corpus.sort(key=lambda x: x["id"])
    print(f"[ok ] corpus: {len(corpus)} abstracts ({len(labeled_ids)} labelled + {len(distractors)} distractors)")

    with open(DATA_DIR / "corpus.jsonl", "w", encoding="utf-8") as fh:
        for row in corpus:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")

    label_counts = Counter(row["final_decision"] for row in label_rows)
    stats = {
        "labeled": len(label_rows),
        "dev": len(dev_idx),
        "test": len(test_idx),
        "label_distribution": dict(label_counts),
        "unique_abstracts": len(abstracts),
        "corpus_size": len(corpus),
        "corpus_chars_mean": round(
            sum(row["n_chars"] for row in corpus) / max(len(corpus), 1), 1
        ),
        "split_seed": args.seed,
    }
    (DATA_DIR / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
