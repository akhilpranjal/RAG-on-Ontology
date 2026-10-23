"""Metrics and significance tests for PubMedQA answer prediction."""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

from evidence_gate.config import LABEL_NAMES

LABELS = list(LABEL_NAMES)


def load_jsonl(path: Path | str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path | str, row: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def accuracy(rows: list[dict]) -> float:
    if not rows:
        return float("nan")
    return sum(row["answer"] == row["gold"] for row in rows) / len(rows)


def per_class_report(rows: list[dict]) -> dict:
    report = {}
    for label in LABELS:
        tp = sum(r["answer"] == label and r["gold"] == label for r in rows)
        fp = sum(r["answer"] == label and r["gold"] != label for r in rows)
        fn = sum(r["answer"] != label and r["gold"] == label for r in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(r["gold"] == label for r in rows),
        }
    return report


def macro_f1(rows: list[dict]) -> float:
    report = per_class_report(rows)
    return float(np.mean([report[label]["f1"] for label in LABELS]))


def confusion(rows: list[dict]) -> dict:
    matrix = {gold: {pred: 0 for pred in LABELS} for gold in LABELS}
    for row in rows:
        if row["gold"] in matrix and row["answer"] in matrix[row["gold"]]:
            matrix[row["gold"]][row["answer"]] += 1
    return matrix


def bootstrap_ci(rows: list[dict], n_boot: int = 1000, seed: int = 42) -> list[float]:
    if not rows:
        return [float("nan"), float("nan")]
    rng = random.Random(seed)
    values = [1.0 if r["answer"] == r["gold"] else 0.0 for r in rows]
    means = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(len(values))] for _ in range(len(values))]
        means.append(sum(sample) / len(sample))
    means.sort()
    return [round(means[int(0.025 * n_boot)], 4), round(means[int(0.975 * n_boot) - 1], 4)]


def mcnemar_test(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """Paired McNemar test on correctness (A vs B)."""
    by_id_a = {row["pubid"]: row for row in rows_a}
    by_id_b = {row["pubid"]: row for row in rows_b}
    shared = sorted(set(by_id_a) & set(by_id_b))
    b = c = 0
    for pubid in shared:
        correct_a = by_id_a[pubid]["answer"] == by_id_a[pubid]["gold"]
        correct_b = by_id_b[pubid]["answer"] == by_id_b[pubid]["gold"]
        if correct_a and not correct_b:
            b += 1
        elif correct_b and not correct_a:
            c += 1
    n = b + c
    if n == 0:
        p_value = 1.0
        statistic = 0.0
    elif n < 25:
        p_value = float(stats.binomtest(b, n, 0.5, alternative="two-sided").pvalue)
        statistic = float(min(b, c))
    else:
        statistic = (abs(b - c) - 1) ** 2 / n
        p_value = float(stats.chi2.sf(statistic, df=1))
    return {
        "n_pairs": len(shared),
        "a_only_correct": b,
        "b_only_correct": c,
        "statistic": round(statistic, 4),
        "p_value": p_value,
        "significant": p_value < 0.05,
        "method": "exact_binomial" if n < 25 else "chi2_continuity",
    }


def auc_score(scores: list[float], labels: list[int]) -> float:
    """Rank-based AUC (Mann-Whitney U); higher score should mean label=1."""
    pairs = [(s, l) for s, l in zip(scores, labels) if not math.isnan(s)]
    positives = sum(l for _, l in pairs)
    negatives = len(pairs) - positives
    if positives == 0 or negatives == 0:
        return float("nan")
    pairs.sort(key=lambda item: item[0])
    rank_sum = 0.0
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            if pairs[k][1] == 1:
                rank_sum += avg_rank
        i = j + 1
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def summarize(rows: list[dict], system: str | None = None) -> dict:
    if not rows:
        return {"system": system, "n": 0}
    correct = [1 if row["answer"] == row["gold"] else 0 for row in rows]
    decisions = Counter(row["decision"] for row in rows)
    abstained = [row for row in rows if row["decision"] == "ABSTAIN"]
    abstain_gold = Counter(row["gold"] for row in abstained)
    maybe_rows = [row for row in rows if row["gold"] == "maybe"]
    answered = [row for row in rows if row.get("decision") != "ABSTAIN"]
    sufficiency = [row["sufficiency"] for row in rows if not math.isnan(row.get("sufficiency", float("nan")))]
    ess_auc = (
        auc_score(
            [row["sufficiency"] for row in answered],
            [1 if row["answer"] == row["gold"] else 0 for row in answered],
        )
        if sufficiency and answered
        else float("nan")
    )
    return {
        "system": system or rows[0].get("system", "unknown"),
        "n": len(rows),
        "accuracy": round(float(np.mean(correct)), 4),
        "accuracy_ci95": bootstrap_ci(rows),
        "macro_f1": round(macro_f1(rows), 4),
        "per_class": per_class_report(rows),
        "confusion": confusion(rows),
        "decisions": dict(decisions),
        "abstained": len(abstained),
        "abstained_gold": dict(abstain_gold),
        "abstain_precision_maybe": round(
            abstain_gold.get("maybe", 0) / len(abstained), 4
        )
        if abstained
        else None,
        "maybe_recall": round(
            sum(1 for row in maybe_rows if row["answer"] == "maybe") / len(maybe_rows), 4
        )
        if maybe_rows
        else None,
        "ess_auc_correct": round(ess_auc, 4) if not math.isnan(ess_auc) else None,
        "mean_latency_s": round(float(np.mean([row.get("latency_s", 0.0) for row in rows])), 2),
        "re_retrieval_rate": round(
            sum(1 for row in rows if row.get("rounds", 0) > 0) / len(rows), 4
        ),
    }
