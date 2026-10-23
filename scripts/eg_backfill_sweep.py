"""Backfill sweep rows from archived runs (offline, zero API calls).

The archived runs stored retrieved passages and the judge output but predate the
coverage features. This script recomputes the local signals so the coverage
machinery can be validated without spending API quota.

Note: the archived runs were executed with ``--include-own`` (the source
abstract was retrievable). They are therefore a *leakage-mode pilot*, not the
main result. The main experiment uses ``eg_run_sweep.py`` with exclude-own.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_gate.coverage import ConceptCoverageScorer
from evidence_gate.evaluate import append_jsonl, load_jsonl
from evidence_gate.ontology import OntologyGraph
from evidence_gate.retriever import Passage


def corpus_meshes(path: Path) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                row = json.loads(line)
                lookup[row["id"]] = row.get("meshes") or []
    return lookup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev")
    parser.add_argument("--source", default="gate_only")
    parser.add_argument("--out", type=Path, default=Path("results/runs/pilot_sweep.jsonl"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    from evidence_gate.config import PUBMEDQA_DIR, SPECIALTY_PATH

    labeled = {row["pubid"]: row for row in load_jsonl(PUBMEDQA_DIR / "labeled.jsonl")}
    meshes = corpus_meshes(PUBMEDQA_DIR / "corpus.jsonl")
    specialties = json.loads(Path(SPECIALTY_PATH).read_text(encoding="utf-8"))
    rows = load_jsonl(Path("results/runs") / f"{args.split}_{args.source}.jsonl")
    if args.force and args.out.exists():
        args.out.unlink()
    done = {row["pubid"] for row in load_jsonl(args.out)} if args.out.exists() else set()

    graph = OntologyGraph()
    coverage = ConceptCoverageScorer(graph=graph)
    written = 0
    for row in rows:
        if row["pubid"] in done:
            continue
        trace = row.get("trace") or {}
        judge = trace.get("ess_round0")
        if not judge:
            continue
        passages = [
            Passage(
                id=p["id"],
                text=p["text"],
                score=float(p["score"]),
                metadata={"meshes": meshes.get(p["id"], [])},
            )
            for p in row["passages"]
        ]
        result = coverage.score(row["question"], passages)
        scores = [p.score for p in passages]
        append_jsonl(
            args.out,
            {
                "pubid": row["pubid"],
                "question": row["question"],
                "gold": row["gold"],
                "specialty": specialties.get(row["pubid"], {}),
                "judge": judge,
                "coverage": result.to_dict(),
                "similarity": {
                    "top1": round(scores[0], 4) if scores else None,
                    "mean_topk": round(sum(scores) / len(scores), 4) if scores else None,
                    "spread": round(scores[0] - scores[-1], 4) if len(scores) > 1 else 0.0,
                    "n_passages": len(scores),
                },
                "passages": [
                    {"id": p.id, "score": round(float(p.score), 4), "text": p.text[:400]}
                    for p in passages
                ],
                "source": f"{args.split}_{args.source}",
                "leakage_mode": True,
                "gold_row_present": row["pubid"] in labeled,
            },
        )
        written += 1
    print(f"[backfill] wrote {written} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
