"""Calibrate the evidence-gate thresholds on the dev split.

No LLM calls are made. For each dev question we record

  * s0: sufficiency of the first retrieval round
  * s1: sufficiency after ontology-grounded re-retrieval (if grounded)
  * the NLI-only proxy answer for each round

and then grid-search (tau_low, tau_high) to maximise dev accuracy of the
full decision policy. The chosen thresholds are written to
results/metrics/calibration.json and reused by the test run.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_gate.config import (
    INDEX_DIR,
    METRICS_DIR,
    PUBMEDQA_DIR,
    RERETRIEVAL_TOP_K,
    RESULTS_DIR,
    ST_MODEL,
    TOP_K,
)
from evidence_gate.evidence_scorer import EvidenceSufficiencyScorer
from evidence_gate.evaluate import append_jsonl, auc_score, load_jsonl
from evidence_gate.ontology import OntologyGraph
from evidence_gate.reasoner import OntologyReasoner
from evidence_gate.retriever import DenseRetriever


def load_split() -> tuple[list[dict], dict]:
    rows = {row["pubid"]: row for row in load_jsonl(PUBMEDQA_DIR / "labeled.jsonl")}
    splits = json.loads((PUBMEDQA_DIR / "splits.json").read_text(encoding="utf-8"))
    return rows, splits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "runs" / "calibration_scores.jsonl")
    parser.add_argument("--reuse", action="store_true", help="Reuse an existing scores file")
    parser.add_argument("--include-own", action="store_true")
    args = parser.parse_args()

    rows, splits = load_split()
    ids = splits[args.split]
    if args.limit:
        ids = ids[: args.limit]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    cached: dict[str, dict] = {}
    if args.reuse and args.out.exists():
        cached = {row["pubid"]: row for row in load_jsonl(args.out)}
        print(f"[cache] {len(cached)} calibration rows")
    elif args.out.exists():
        args.out.unlink()

    retriever = DenseRetriever(backend="st", st_model=ST_MODEL)
    retriever.load_index(INDEX_DIR)
    scorer = EvidenceSufficiencyScorer()
    graph = OntologyGraph()
    reasoner = OntologyReasoner(graph)

    records: list[dict] = []
    for i, pubid in enumerate(ids, 1):
        if pubid in cached:
            records.append(cached[pubid])
            continue
        row = rows[pubid]
        question = row["question"]
        passages = retriever.search(question, top_k=TOP_K, exclude_ids=set() if args.include_own else {pubid})
        ess0 = scorer.score(question, [p.text for p in passages])
        refinement = reasoner.refine(question, [p.text for p in passages[:3]])
        record = {
            "pubid": pubid,
            "gold": row["final_decision"],
            "s0": ess0.sufficiency_score,
            "nli0": ess0.nli_answer,
            "grounded": refinement.grounded,
            "intent": refinement.intent,
            "added_terms": refinement.added_terms,
            "relations": refinement.relations,
            "s1": None,
            "nli1": None,
            "refined_query": refinement.query if refinement.grounded else None,
        }
        if refinement.grounded:
            new_passages = retriever.search(
                refinement.query, top_k=RERETRIEVAL_TOP_K, exclude_ids=set() if args.include_own else {pubid}
            )
            merged: dict[str, object] = {}
            for passage in [*passages, *new_passages]:
                merged.setdefault(passage.id, passage)
            merged_list = sorted(
                merged.values(), key=lambda p: p.score, reverse=True
            )[:TOP_K]
            ess1 = scorer.score(question, [p.text for p in merged_list])
            record["s1"] = ess1.sufficiency_score
            record["nli1"] = ess1.nli_answer
        records.append(record)
        if args.out.exists() and not args.reuse:
            pass
        append_jsonl(args.out, record)
        if i % 25 == 0:
            print(f"[calib] {i}/{len(ids)} ...", flush=True)

    golds = [r["gold"] for r in records]
    nli_correct = [r["nli0"] == r["gold"] for r in records]
    print(f"[baseline] NLI-only accuracy: {np.mean(nli_correct):.4f}")
    ess_auc = auc_score(
        [r["s0"] for r in records],
        [1 if r["nli0"] == r["gold"] else 0 for r in records],
    )
    print(f"[ess] AUC(s0 -> NLI answer correct): {ess_auc:.4f}")
    print(f"[refine] grounded: {np.mean([r['grounded'] for r in records]):.3f}")

    def policy_accuracy(tau_low: float, tau_high: float) -> tuple[float, float]:
        correct = 0
        re_retrievals = 0
        for record in records:
            s0 = record["s0"]
            if s0 >= tau_high:
                prediction = record["nli0"]
            elif s0 >= tau_low:
                if record["grounded"] and record["s1"] is not None:
                    re_retrievals += 1
                    prediction = (
                        record["nli1"] if record["s1"] >= tau_low else "maybe"
                    )
                else:
                    prediction = record["nli0"]
            else:
                prediction = "maybe"
            correct += prediction == record["gold"]
        return correct / len(records), re_retrievals / len(records)

    grid = []
    for tau_low, tau_high in itertools.product(
        np.arange(0.15, 0.81, 0.05), np.arange(0.20, 0.96, 0.05)
    ):
        if tau_high - tau_low < 0.05:
            continue
        acc, rr = policy_accuracy(float(tau_low), float(tau_high))
        grid.append(
            {
                "tau_low": round(float(tau_low), 3),
                "tau_high": round(float(tau_high), 3),
                "accuracy": round(acc, 4),
                "re_retrieval_rate": round(rr, 4),
            }
        )
    grid.sort(key=lambda row: (-row["accuracy"], row["re_retrieval_rate"]))
    best = grid[0]
    print(f"[best] tau_low={best['tau_low']} tau_high={best['tau_high']} "
          f"acc={best['accuracy']} re-retrieve={best['re_retrieval_rate']}")

    payload = {
        "split": args.split,
        "n": len(records),
        "nli_only_accuracy": round(float(np.mean(nli_correct)), 4),
        "ess_auc_nli_correct": round(float(ess_auc), 4),
        "grounded_rate": round(float(np.mean([r["grounded"] for r in records])), 4),
        "tau_low": best["tau_low"],
        "tau_high": best["tau_high"],
        "dev_accuracy_at_best": best["accuracy"],
        "dev_re_retrieval_rate": best["re_retrieval_rate"],
        "top_grid": grid[:15],
    }
    out = METRICS_DIR / "calibration.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

