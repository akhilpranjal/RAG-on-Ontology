"""Paired check against the plain-prompt RAG baseline.

The main sweep answers with the *judge* prompt (JSON with sufficiency + answer).
That prompt makes the model abstain far more often than a plain answer prompt,
so the always-answer accuracy of the sweep (58.8% on test) understates how well
a standard RAG pipeline answers. This script pairs the sweep with an earlier
plain-prompt run on the questions they share and reports both arms on the same
answered subset, so the gate's gain is not inflated by a weak baseline.

Note the model confound: the plain-prompt run used ``gemini-3.5-flash-lite``
while the sweep used ``gemini-3.1-flash-lite``. The comparison is indicative,
not a controlled ablation. The fully paired, same-model comparison is the
judge-prompt always-answer baseline in ``results/metrics/final_report.md``.

Usage
-----
    uv run python scripts/eg_paired_baseline.py \
        --baseline results/runs/test_standard_rag.jsonl \
        --sweep results/runs/test_sweep.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_gate.evaluate import load_jsonl
from evidence_gate.config import METRICS_DIR
from evidence_gate.selective import row_answer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "results" / "runs" / "test_standard_rag.jsonl")
    parser.add_argument("--sweep", type=Path, default=ROOT / "results" / "runs" / "test_sweep.jsonl")
    parser.add_argument("--out", type=Path, default=METRICS_DIR / "paired_baseline.json")
    parser.add_argument("--note", default=None, help="override the caveat text recorded in the output")
    args = parser.parse_args()

    baseline = {row["pubid"]: row for row in load_jsonl(args.baseline)}
    sweep = {row["pubid"]: row for row in load_jsonl(args.sweep)}
    shared = [pubid for pubid in baseline if pubid in sweep]
    if not shared:
        raise SystemExit("no shared questions between the two runs")

    def baseline_answer(pubid: str) -> str:
        row = baseline[pubid]
        return row.get("answer") or (row.get("judge") or {}).get("answer")

    answered = [pubid for pubid in shared if row_answer(sweep[pubid]) != "maybe"]
    gate_hits = [row_answer(sweep[p]) == sweep[p]["gold"] for p in answered]
    base_hits = [baseline_answer(p) == sweep[p]["gold"] for p in answered]

    def acc(flags):
        return round(sum(flags) / len(flags), 4) if flags else None

    b = sum(1 for base, gate in zip(base_hits, gate_hits) if base and not gate)
    c = sum(1 for base, gate in zip(base_hits, gate_hits) if gate and not base)
    n_discordant = b + c
    from scipy import stats as scipy_stats

    p_value = (
        1.0
        if n_discordant == 0
        else float(scipy_stats.binomtest(b, n_discordant, 0.5, alternative="two-sided").pvalue)
    )

    result = {
        "n_shared": len(shared),
        "n_answered_by_gate": len(answered),
        "coverage": round(len(answered) / len(shared), 4),
        "baseline_accuracy_all_shared": acc(
            [baseline_answer(p) == sweep[p]["gold"] for p in shared]
        ),
        "baseline_accuracy_on_answered": acc(base_hits),
        "gate_accuracy_on_answered": acc(gate_hits),
        "delta_on_answered": (
            round(acc(gate_hits) - acc(base_hits), 4) if base_hits else None
        ),
        "mcnemar_on_answered": {
            "n_pairs": len(answered),
            "baseline_only_correct": b,
            "gate_only_correct": c,
            "p_value": round(p_value, 4),
        },
        "caveat": args.note or (
            "baseline used gemini-3.5-flash-lite with a plain answer prompt; "
            "the sweep used gemini-3.1-flash-lite with the judge prompt"
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
