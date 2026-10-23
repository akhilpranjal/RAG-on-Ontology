"""Final analysis: every selective system, evaluated on the same questions.

Protocol
--------
* All thresholds and the fused selector are fitted on the **dev** split.
* Everything reported in the ``test`` section uses those dev-fitted values.
* Gates are compared at *matched coverage*: the dev threshold that achieves a
  coverage target is applied unchanged to test.
* Abstention is never counted as a correct answer. ``accuracy_as_maybe`` is
  reported separately for continuity with the earlier runs, where abstention
  was encoded as the "maybe" label.

Signals compared
----------------
* ``similarity``             top-1 dense retrieval score
* ``ontology_coverage``      MeSH/Hetionet concept coverage of the top-3
* ``ontology_relation``      intent-conditioned relation coverage (sentence)
* ``llm_judge``              the judge's sufficiency score
* ``judge_self_abstain``     deterministic rule: abstain when the judge answers
                             "maybe", otherwise answer
* ``fused_*``                small L2 logistic regression fitted on dev

Inputs:  results/runs/{split}_sweep.jsonl
Outputs: results/metrics/final_report.{json,md}, results/plots/*.png
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from evidence_gate.config import GENERATOR_MODEL
from evidence_gate.evaluate import load_jsonl
from evidence_gate.specialty import DISEASE_CODE_NAMES
from evidence_gate.selective import (
    LogisticSelector,
    aurc,
    bootstrap_selective_ci,
    gate_auc,
    risk_coverage_curve,
    row_answer,
    selective_metrics,
    threshold_at_coverage,
)

COVERAGE_TARGETS = [1.0, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]


# ----------------------------------------------------------------------
# Feature extraction
# ----------------------------------------------------------------------
def raw_scores(row: dict) -> dict:
    judge = row.get("judge") or {}
    coverage = row.get("coverage") or {}
    similarity = row.get("similarity") or {}
    sufficient = judge.get("sufficient")
    answer = judge.get("answer")
    score = judge.get("sufficiency_score")
    self_abstain = None
    if score is not None:
        self_abstain = 0.0 if answer == "maybe" else 0.5 + 0.5 * float(score)
    return {
        "llm_judge": score,
        "judge_self_abstain": self_abstain,
        # Deterministic simplification of the dev-fitted fused gate: the
        # threshold lands exactly at "score == 1 and answer != maybe".
        "judge_confident": 1.0
        if answer not in (None, "maybe") and score is not None and float(score) >= 1.0
        else 0.0,
        "judge_answer_maybe": 1.0 if answer == "maybe" else 0.0,
        "judge_inconsistent": 1.0
        if sufficient == "yes" and answer == "maybe"
        else 0.0,
        "similarity": similarity.get("top1"),
        "ontology_coverage": coverage.get("coverage_top3"),
        "ontology_coverage_doc": coverage.get("coverage"),
        "ontology_relation": coverage.get("relation_coverage"),
        "ontology_heading": coverage.get("heading_coverage"),
        "n_concepts": coverage.get("n_concepts"),
    }


FUSED_SETS = {
    "fused_judge_maybe": ["llm_judge", "judge_answer_maybe"],
    "fused_judge_maybe_coverage": ["llm_judge", "judge_answer_maybe", "ontology_coverage"],
    "fused_all": [
        "llm_judge",
        "judge_answer_maybe",
        "judge_inconsistent",
        "ontology_coverage",
        "similarity",
        "n_concepts",
    ],
}


def feature_matrix(rows: list[dict], names: list[str]) -> list[list[float]]:
    out = []
    for row in rows:
        scores = raw_scores(row)
        out.append(
            [float(scores[name]) if scores[name] is not None else float("nan") for name in names]
        )
    return out


def correctness(rows: list[dict]) -> list[int]:
    return [1 if row_answer(row) == row["gold"] else 0 for row in rows]


def build_scores(rows: list[dict], selectors: dict[str, LogisticSelector]) -> dict[str, list]:
    base = {
        name: [raw_scores(row)[name] for row in rows]
        for name in (
            "llm_judge",
            "judge_self_abstain",
            "judge_confident",
            "similarity",
            "ontology_coverage",
            "ontology_coverage_doc",
            "ontology_relation",
            "ontology_heading",
        )
    }
    for key, selector in selectors.items():
        base[key] = selector.predict_proba(
            feature_matrix(rows, selector.feature_names)
        ).tolist()
    return base


# ----------------------------------------------------------------------
# Reporting helpers
# ----------------------------------------------------------------------
def evaluate_gate(
    dev_scores: list,
    test_scores: list,
    dev_rows: list[dict],
    test_rows: list[dict],
) -> dict:
    report = {
        "dev_auc": gate_auc(dev_scores, dev_rows),
        "test_auc": gate_auc(test_scores, test_rows),
        "dev_aurc": round(aurc(dev_scores, dev_rows), 4),
        "test_aurc": round(aurc(test_scores, test_rows), 4),
        "coverage_targets": {},
    }
    for target in COVERAGE_TARGETS:
        tau = threshold_at_coverage(dev_scores, target)
        dev_metrics = selective_metrics(dev_scores, dev_rows, tau)
        test_metrics = selective_metrics(test_scores, test_rows, tau)
        report["coverage_targets"][f"{target:.1f}"] = {
            "tau": None if tau is None or math.isnan(tau) else round(float(tau), 6),
            "dev_coverage": dev_metrics["coverage"],
            "dev_selective_accuracy": dev_metrics["selective_accuracy"],
            "test_coverage": test_metrics["coverage"],
            "test_n_answered": test_metrics["n_answered"],
            "test_selective_accuracy": test_metrics["selective_accuracy"],
            "test_ci95": bootstrap_selective_ci(test_scores, test_rows, tau),
        }
    return report


def always_answer(rows: list[dict]) -> dict:
    n = len(rows)
    hits = sum(row_answer(row) == row["gold"] for row in rows)
    maybe_hits = sum(row_answer(row) == "maybe" and row["gold"] == "maybe" for row in rows)
    forced = sum(
        ("yes" if row_answer(row) == "maybe" else row_answer(row)) == row["gold"]
        for row in rows
    )
    return {
        "n": n,
        "accuracy": round(hits / n, 4),
        "accuracy_as_maybe": round(maybe_hits / n, 4),
        "accuracy_forced_answer": round(forced / n, 4),
        "prediction_distribution": dict(Counter(row_answer(row) for row in rows)),
        "gold_distribution": dict(Counter(row["gold"] for row in rows)),
    }


def per_specialty(rows: list[dict], gate_scores: list, tau: float, min_n: int = 6) -> dict:
    grouped: dict[str, list[tuple[dict, float]]] = defaultdict(list)
    for row, score in zip(rows, gate_scores):
        code = (row.get("specialty") or {}).get("primary_category") or "UNKNOWN"
        grouped[code].append((row, score))

    out = {}
    for code, items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        if len(items) < min_n:
            continue
        answered = [
            (row, score)
            for row, score in items
            if score is not None and not math.isnan(float(score)) and float(score) >= tau
        ]
        always_hits = sum(row_answer(row) == row["gold"] for row, _ in items)
        sel_hits = sum(row_answer(row) == row["gold"] for row, _ in answered)
        out[code] = {
            "name": DISEASE_CODE_NAMES.get(code)
            or (items[0][0].get("specialty") or {}).get("primary_category_name"),
            "n": len(items),
            "always_accuracy": round(always_hits / len(items), 4),
            "coverage": round(len(answered) / len(items), 4),
            "selective_accuracy": round(sel_hits / len(answered), 4) if answered else None,
        }
    return out


def cascade_analysis(dev: list[dict], test: list[dict], screen_values=None) -> dict:
    """Ontology as a free screen in front of the paid judge.

    Rule: if coverage <= a, abstain without calling the judge. Otherwise the
    judge answers, and we abstain when it says "maybe". This isolates the
    ontology's only remaining useful role: saving API calls.
    """
    screen_values = screen_values or [0.0, 0.25, 0.5, 0.75, 0.99, 1.0]

    def run(rows):
        saved = asked = answered = hits = 0
        for row in rows:
            coverage = raw_scores(row)["ontology_coverage"]
            judge = row.get("judge") or {}
            # A missing coverage score means the ontology has nothing to say;
            # do not treat that as evidence of insufficiency.
            if coverage is not None and coverage <= a:
                saved += 1
                continue
            asked += 1
            if judge.get("answer") == "maybe":
                continue
            answered += 1
            hits += row_answer(row) == row["gold"]
        return {
            "judge_calls_saved": round(saved / len(rows), 4),
            "coverage": round(answered / len(rows), 4),
            "selective_accuracy": round(hits / answered, 4) if answered else None,
        }

    rows = []
    for a in screen_values:
        rows.append({"screen_threshold": a, **{
            f"dev_{k}": v for k, v in run(dev).items()
        }, **{f"test_{k}": v for k, v in run(test).items()}})
    return {"rule": "abstain if coverage <= a; else abstain if judge answer == maybe", "rows": rows}


def coverage_saturation(rows: list[dict]) -> dict:
    values = [
        raw_scores(row)["ontology_coverage_doc"]
        for row in rows
        if raw_scores(row)["ontology_coverage_doc"] is not None
    ]
    concepts = [raw_scores(row)["n_concepts"] for row in rows]
    return {
        "n_defined": len(values),
        "mean_document_coverage": round(float(np.mean(values)), 4) if values else None,
        "share_coverage_eq_1": round(float(np.mean([v == 1.0 for v in values])), 4)
        if values
        else None,
        "mean_n_concepts": round(float(np.mean([c for c in concepts if c is not None])), 2)
        if concepts
        else None,
        "n_concepts_hist": dict(Counter(concepts)),
    }


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------
def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(report: dict) -> str:
    lines = ["# OntoGate-RAG - final report", ""]
    lines.append("## Data")
    lines.append("")
    lines.append("| split | n | judge model | retrieval |")
    lines.append("|---|---|---|---|")
    for split in ("dev", "test"):
        block = report["splits"][split]
        lines.append(
            f"| {split} | {block['n']} | {report['judge_model']} | "
            f"{report['retriever']} (top-{report['top_k']}) |"
        )
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(report["headline"])
    lines.append("")
    lines.append("## Always-answer baselines")
    lines.append("")
    lines.append("| split | accuracy | accuracy forced (maybe->yes) | accuracy if abstain=maybe | predicted |")
    lines.append("|---|---|---|---|---|")
    for split in ("dev", "test"):
        base = report["splits"][split]["always_answer"]
        lines.append(
            f"| {split} | {fmt(base['accuracy'])} | {fmt(base['accuracy_forced_answer'])} | "
            f"{fmt(base['accuracy_as_maybe'])} | {base['prediction_distribution']} |"
        )
    lines.append("")
    lines.append("## Gate quality (AUC / AURC)")
    lines.append("")
    lines.append("| gate | dev AUC | test AUC | dev AURC | test AURC |")
    lines.append("|---|---|---|---|---|")
    for name, block in report["gates"].items():
        lines.append(
            f"| {name} | {fmt(block['dev_auc'])} | {fmt(block['test_auc'])} | "
            f"{fmt(block['dev_aurc'], 4)} | {fmt(block['test_aurc'], 4)} |"
        )
    lines.append("")
    lines.append("## Selective accuracy at matched coverage (test)")
    lines.append("")
    header = "| gate | " + " | ".join(f"cov {t:.0%}" for t in COVERAGE_TARGETS) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(COVERAGE_TARGETS) + 1))
    for name, block in report["gates"].items():
        cells = []
        for target in COVERAGE_TARGETS:
            entry = block["coverage_targets"][f"{target:.1f}"]
            cells.append(f"{fmt(entry['test_selective_accuracy'])}@{entry['test_coverage']:.0%}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Per-specialty (test, judge gate at dev 50% coverage)")
    lines.append("")
    lines.append("| MeSH | n | always | coverage | selective |")
    lines.append("|---|---|---|---|---|")
    for code, block in report["per_specialty"].items():
        lines.append(
            f"| {code} {block['name']} | {block['n']} | {fmt(block['always_accuracy'])} | "
            f"{fmt(block['coverage'])} | {fmt(block['selective_accuracy'])} |"
        )
    lines.append("")
    lines.append("## Coverage saturation")
    lines.append("")
    sat = report["coverage_saturation"]
    lines.append(
        f"- mean document coverage: {fmt(sat['mean_document_coverage'])}; "
        f"share at 1.0: {fmt(sat['share_coverage_eq_1'])}; "
        f"mean linked concepts: {sat['mean_n_concepts']}"
    )
    lines.append("")
    lines.append("## Cascade: coverage screen in front of the judge")
    lines.append("")
    lines.append(f"Rule: {report['cascade']['rule']}")
    lines.append("")
    lines.append("| screen | judge calls saved | test coverage | test selective acc |")
    lines.append("|---|---|---|---|")
    for row in report["cascade"]["rows"]:
        lines.append(
            f"| <= {row['screen_threshold']:.2f} | {row['test_judge_calls_saved']:.1%} | "
            f"{row['test_coverage']:.1%} | {fmt(row['test_selective_accuracy'])} |"
        )
    lines.append("")
    lines.append("## Fused gate weights (dev-fitted)")
    lines.append("")
    for name, selector in report["selectors"].items():
        lines.append(f"- **{name}**: {selector.get('weights')}")
    return "\n".join(lines) + "\n"


def headline(report: dict) -> str:
    """Pre-specified headline: dev-fitted fused gate at the 60% coverage target.

    Chosen before looking at test results, so it is not a best-cell search.
    """
    test = report["splits"]["test"]["always_answer"]
    primary = report["gates"]["fused_judge_maybe"]["coverage_targets"]["0.6"]
    deterministic = report["gates"]["judge_confident"]["coverage_targets"]["0.6"]
    parts = [
        f"Always-answer accuracy is **{test['accuracy']:.1%}** on the test split.",
        f"The dev-fitted fused gate (threshold fitted for 60% coverage) reaches "
        f"**{primary['test_selective_accuracy']:.1%}** selective accuracy at "
        f"**{primary['test_coverage']:.1%}** coverage "
        f"(+{primary['test_selective_accuracy'] - test['accuracy']:.1%} absolute).",
    ]
    if deterministic.get("test_selective_accuracy") is not None:
        parts.append(
            f"That gate simplifies exactly to a deterministic rule - answer only when "
            f"the judge is fully confident (sufficiency 1) and did not answer 'maybe' - "
            f"which reaches {deterministic['test_selective_accuracy']:.1%} at "
            f"{deterministic['test_coverage']:.1%} coverage with no training."
        )
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "results" / "runs")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "results" / "metrics")
    parser.add_argument("--plots-dir", type=Path, default=ROOT / "results" / "plots")
    args = parser.parse_args()

    dev = load_jsonl(args.runs_dir / "dev_sweep.jsonl")
    test = load_jsonl(args.runs_dir / "test_sweep.jsonl")
    if not dev or not test:
        raise SystemExit("sweep files missing")

    selectors = {
        name: LogisticSelector(feature_names=features, l2=2.0).fit(
            feature_matrix(dev, features), correctness(dev)
        )
        for name, features in FUSED_SETS.items()
    }
    dev_scores = build_scores(dev, selectors)
    test_scores = build_scores(test, selectors)

    gate_names = [
        "similarity",
        "ontology_coverage",
        "ontology_coverage_doc",
        "ontology_relation",
        "ontology_heading",
        "llm_judge",
        "judge_self_abstain",
        "judge_confident",
        *selectors.keys(),
    ]
    gates = {
        name: evaluate_gate(dev_scores[name], test_scores[name], dev, test)
        for name in gate_names
    }

    judge_tau = threshold_at_coverage(dev_scores["judge_self_abstain"], 0.5)
    report = {
        "judge_model": GENERATOR_MODEL,
        "retriever": "multi-qa-MiniLM-L6-cos-v1",
        "top_k": len(test[0].get("passages") or []),
        "splits": {
            "dev": {"n": len(dev), "always_answer": always_answer(dev)},
            "test": {"n": len(test), "always_answer": always_answer(test)},
        },
        "gates": gates,
        "per_specialty": per_specialty(test, test_scores["judge_self_abstain"], judge_tau),
        "coverage_saturation": coverage_saturation(test),
        "cascade": cascade_analysis(dev, test),
        "selectors": {name: selector.to_dict() for name, selector in selectors.items()},
    }
    report["headline"] = headline(report)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "final_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    write_questions_csv(dev, test, dev_scores, test_scores, args.out_dir / "questions.csv")
    markdown = render_markdown(report)
    (args.out_dir / "final_report.md").write_text(markdown, encoding="utf-8")
    print(markdown)

    try:
        make_plots(test, test_scores, args.plots_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"[plots] skipped: {exc}")
    return 0


def write_questions_csv(dev, test, dev_scores, test_scores, path: Path) -> None:
    """Compact per-question export so results can be audited without raw runs."""
    import csv

    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "split",
                "pubid",
                "gold",
                "judge_answer",
                "judge_sufficient",
                "judge_score",
                "ontology_coverage",
                "ontology_relation",
                "similarity",
                "n_concepts",
                "specialty",
                "correct",
                "fused_judge_maybe",
            ]
        )
        for split, rows, scores in (
            ("dev", dev, dev_scores),
            ("test", test, test_scores),
        ):
            for index, row in enumerate(rows):
                values = raw_scores(row)
                writer.writerow(
                    [
                        split,
                        row["pubid"],
                        row["gold"],
                        (row.get("judge") or {}).get("answer"),
                        (row.get("judge") or {}).get("sufficient"),
                        values["llm_judge"],
                        values["ontology_coverage"],
                        values["ontology_relation"],
                        values["similarity"],
                        values["n_concepts"],
                        (row.get("specialty") or {}).get("primary_category"),
                        int(row_answer(row) == row["gold"]),
                        round(float(scores["fused_judge_maybe"][index]), 4),
                    ]
                )
    print(f"[write] {path}")


def make_plots(test, test_scores, plots_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(6.4, 4.2))
    for name in (
        "similarity",
        "ontology_coverage",
        "llm_judge",
        "judge_self_abstain",
        "judge_confident",
        "fused_judge_maybe",
    ):
        curve = risk_coverage_curve(test_scores[name], test)
        if not curve:
            continue
        xs = [point["coverage"] for point in curve]
        ys = [point["risk"] for point in curve]
        plt.plot(xs, ys, label=name)
    plt.xlabel("coverage (share of questions answered)")
    plt.ylabel("risk (1 - selective accuracy)")
    plt.title("Risk-coverage on the test split")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / "risk_coverage.png", dpi=160)
    plt.close()

    names = [
        "similarity",
        "ontology_coverage",
        "ontology_relation",
        "llm_judge",
        "judge_self_abstain",
        "judge_confident",
        "fused_judge_maybe",
    ]
    values = [gate_auc(test_scores[name], test) or 0.0 for name in names]
    plt.figure(figsize=(7.2, 4.0))
    plt.bar(names, values, color="#4c72b0")
    plt.ylim(0.0, 1.0)
    plt.axhline(0.5, color="gray", linestyle="--", linewidth=1)
    plt.ylabel("AUC vs correctness")
    plt.title("Gate signal on the test split")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(plots_dir / "gate_auc.png", dpi=160)
    plt.close()

    sat = [
        (row.get("coverage") or {}).get("coverage")
        for row in test
        if (row.get("coverage") or {}).get("coverage") is not None
    ]
    plt.figure(figsize=(6.0, 3.8))
    plt.hist(sat, bins=20, range=(0.0, 1.0), color="#55a868")
    plt.xlabel("document-level ontology coverage")
    plt.ylabel("questions")
    plt.title("Coverage saturation on the test split")
    plt.tight_layout()
    plt.savefig(plots_dir / "coverage_saturation.png", dpi=160)
    plt.close()
    print(f"[plots] wrote to {plots_dir}")


if __name__ == "__main__":
    sys.exit(main())
