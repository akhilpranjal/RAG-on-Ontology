"""Reasoning-trace explainability exhibit.

Produces `results/trace_exhibits.md`: for every query category, a worked
example of Pipeline 3's ontology reasoning trace (query -> matched concept
-> expansions by relation -> expanded terms), plus a per-category aggregate
summary of how many concepts matched and which relation types fired.

Usage:
    uv run python -m scripts.generate_trace_report
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

from src.config import QUERY_CATEGORIES, REASONING_LOGS_DIR, RESULTS_DIR, ensure_directories

LOG_FILE = REASONING_LOGS_DIR / "pipeline_3_ontology_full_reasoning_logs.json"
OUT_FILE = RESULTS_DIR / "trace_exhibits.md"

CATEGORY_LABELS = {
    "lay_terminology": "Lay Terminology",
    "disease_hierarchy": "Disease Hierarchy",
    "symptom_reasoning": "Symptom Reasoning",
    "treatment_reasoning": "Treatment Reasoning",
    "multi_hop": "Multi-Hop",
    "control_exact_clinical": "Control: Exact Clinical",
}


def _expand_relation(relation: str) -> str:
    return {
        "equivalentClass": "is equivalent to",
        "subClassOf (parent)": "is subclass of",
        "subClassOf (child, depth=1)": "has subclass (direct)",
        "subClassOf (child, depth=2)": "has subclass (nested)",
        "hasSymptom": "has symptom",
        "hasSymptom (inverse)": "is a symptom of",
        "treatedBy": "is treated by",
        "treatedBy (inverse)": "treats",
        "diagnosedBy": "is diagnosed by",
        "diagnosedBy (inverse)": "diagnoses",
        "relatedCondition": "is related to",
        "relatedCondition (inverse)": "is related to (inv)",
    }.get(relation, relation)


def _format_trace(trace: dict) -> str:
    lines = [f"> **Query:** {trace.get('original_query', '')}\n"]
    for m in trace.get("matched_concepts", []):
        lines.append(
            f"**Matched concept:** `{m.get('term', '')}` → `{m.get('concept_id', '')}`"
            f" ({m.get('label', '')})\n"
        )
    for exp in trace.get("expansions", []):
        lines.append(
            f"- `{exp.get('source', '')}` *{_expand_relation(exp.get('relation', ''))}* "
            f"`{exp.get('target', '')}` ({exp.get('target_label', '')})\n"
        )
    terms = trace.get("expanded_terms", [])
    lines.append(f"\n**Expanded query terms:** `{'`, `'.join(terms)}`\n")
    return "".join(lines)


def main():
    ensure_directories()
    if not LOG_FILE.exists():
        raise FileNotFoundError(f"Reasoning logs not found at {LOG_FILE}. Run scripts/run_experiments.py first.")

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for rec in logs:
        by_cat[rec["category"]].append(rec)

    out = ["# Ontology Reasoning Traces — Worked Examples", ""]
    out.append("Pipeline 3 (ontology expansion) traces for the 66-query evaluation set, "
               "grouped by query category. Generated from "
               "`results/reasoning_logs/pipeline_3_ontology_full_reasoning_logs.json`.\n")

    # Aggregate per-category summary.
    out.append("## Per-Category Aggregates\n")
    out.append("| Category | Queries | Avg matched concepts | Total expansions | "
               "Top relation families |")
    out.append("|---|---|---|---|---|")
    for cat in QUERY_CATEGORIES:
        recs = by_cat.get(cat, [])
        if not recs:
            continue
        n = len(recs)
        avg_match = sum(len(r["trace"].get("matched_concepts", [])) for r in recs) / n
        exp_counter = Counter(
            exp.get("relation", "") for r in recs for exp in r["trace"].get("expansions", [])
        )
        total = sum(exp_counter.values())
        top = ", ".join(f"{rel} ({cnt})" for rel, cnt in exp_counter.most_common(3))
        out.append(
            f"| {CATEGORY_LABELS.get(cat, cat)} | {n} | {avg_match:.2f} | {total} | {top} |"
        )
    out.append("")

    # Worked examples: first query of each category (skip control if uninteresting).
    for cat in QUERY_CATEGORIES:
        recs = by_cat.get(cat, [])
        if not recs:
            continue
        out.append(f"## {CATEGORY_LABELS.get(cat, cat)}")
        out.append(f"*{len(recs)} queries*")
        out.append("")
        for rec in recs[:2]:
            out.append(_format_trace(rec["trace"]))
        out.append("")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"[OK] Saved {OUT_FILE}")


if __name__ == "__main__":
    main()