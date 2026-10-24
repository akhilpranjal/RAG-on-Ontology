import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence_gate.evaluate import auc_score, mcnemar_test


def load(path):
    p = Path(path)
    return [json.loads(l) for l in p.open(encoding="utf-8")] if p.exists() else []


def stats(rows, threshold=None, answered_only=False):
    if threshold is None:
        sel = rows
    else:
        sel = [r for r in rows if r["sufficiency"] >= threshold]
    if answered_only:
        sel = [r for r in sel if r["decision"] != "ABSTAIN"]
    if not sel:
        return None
    correct = sum(r["answer"] == r["gold"] for r in sel)
    return {
        "n": len(sel),
        "coverage": round(len(sel) / len(rows), 3),
        "accuracy": round(correct / len(sel), 3),
    }


for split in ["dev", "test"]:
    print(f"\n=== {split} ===")
    std = load(f"results/runs/{split}_standard_rag.jsonl")
    score = load(f"results/runs/{split}_score_only.jsonl")
    gate_file = load(f"results/runs/{split}_gate_only.jsonl")
    onto = load(f"results/runs/{split}_ontogate.jsonl")

    if std:
        print("standard_rag", stats(std))
    if score:
        print("score_only (all)", stats(score))
        print("score_only yes-only", stats(score, threshold=0.75))
        print("score_only partial+yes", stats(score, threshold=0.25))
        s = [r["sufficiency"] for r in score]
        y = [1 if r["answer"] == r["gold"] else 0 for r in score]
        print("AUC(sufficiency -> correct)", round(auc_score(s, y), 3))
    if gate_file:
        print("gate_only", stats(gate_file), "ans", stats(gate_file, answered_only=True))
    if onto:
        print("ontogate", stats(onto), "ans", stats(onto, answered_only=True))
    if std and gate_file:
        print("mcnemar gate vs standard", mcnemar_test(gate_file, std))
    if std and onto:
        print("mcnemar onto vs standard", mcnemar_test(onto, std))
    if std and score:
        ids = {r["pubid"] for r in score if r["sufficiency"] >= 0.75}
        sub = [r for r in std if r["pubid"] in ids]
        if sub:
            print("standard on yes-only subset", round(sum(r["answer"] == r["gold"] for r in sub) / len(sub), 3), len(sub))
