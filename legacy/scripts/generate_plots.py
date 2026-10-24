"""Plotting script — generates charts from experiment results.

Generates:
  1. overall_comparison.png — Bar chart comparing Recall@5, MRR, nDCG@5 across pipelines
  2. category_breakdown.png — Grouped bar chart comparing Recall@5 per category
  3. ablation_study.png — Bar chart showing contribution of relation types
  4. answer_quality.png — Bar chart of concept-coverage F1 + judge correctness
  5. trace_breakdown.png — Stacked bar of ontology relation usage per query category
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from src.config import METRICS_DIR, PLOTS_DIR, QUERY_CATEGORIES, REASONING_LOGS_DIR, ensure_directories

# Map raw relation strings from the reasoning traces to clean families.
_RELATION_FAMILIES = [
    ("equivalence", "Equivalence"),
    ("hierarchy", "Hierarchy"),
    ("symptom", "Symptom"),
    ("treatment", "Treatment"),
    ("diagnosis", "Diagnosis"),
    ("related", "Related"),
]


def _relation_family(relation: str) -> str:
    rel = relation.lower()
    for key, _ in _RELATION_FAMILIES:
        if key in rel:
            return key
    return "other"


CATEGORY_LABELS = {
    "lay_terminology": "Lay Terms",
    "disease_hierarchy": "Hierarchy",
    "symptom_reasoning": "Symptom",
    "treatment_reasoning": "Treatment",
    "multi_hop": "Multi-hop",
    "control_exact_clinical": "Exact Control",
}


def load_summary() -> dict:
    summary_file = METRICS_DIR / "experiment_summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"Summary file not found at {summary_file}. Run scripts/run_experiments.py first.")

    with open(summary_file, "r", encoding="utf-8") as f:
        return json.load(f)


def plot_overall_comparison(summary: dict):
    """Plot overall metrics comparison across the 3 main pipelines."""
    plt.figure(figsize=(10, 6))

    pipelines = ["Pipeline 1 (Baseline)", "Pipeline 2 (Dictionary)", "Pipeline 3 (Ontology)"]
    keys = ["pipeline_1_baseline", "pipeline_2_dictionary", "pipeline_3_ontology_full"]

    metrics = ["recall@5", "precision@5", "mrr", "ndcg@5"]
    metric_labels = ["Recall@5", "Precision@5", "MRR", "nDCG@5"]

    x = np.arange(len(metric_labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ["#4C72B0", "#DD8452", "#55A868"]

    for i, (p_key, label, color) in enumerate(zip(keys, pipelines, colors)):
        p_data = summary["pipelines"][p_key]
        vals = [p_data[m]["mean"] for m in metrics]
        rects = ax.bar(x + i * width, vals, width, label=label, color=color)

        # Value labels on top of bars
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f"{height:.3f}",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha="center", va="bottom", fontsize=8)

    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("Overall Retrieval Quality Across Pipelines", fontsize=14, fontweight="bold")
    ax.set_xticks(x + width)
    ax.set_xticklabels(metric_labels, fontsize=11)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    output_path = PLOTS_DIR / "overall_comparison.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved {output_path}")


def plot_category_breakdown(summary: dict):
    """Plot category-wise Recall@5 breakdown."""
    cat_breakdown = summary.get("category_breakdown", {})
    if not cat_breakdown:
        return

    cat_labels = {
        "lay_terminology": "Lay Terms",
        "disease_hierarchy": "Hierarchy",
        "symptom_reasoning": "Symptom",
        "treatment_reasoning": "Treatment",
        "multi_hop": "Multi-hop",
        "control_exact_clinical": "Exact Control",
    }

    categories = [cat for cat in QUERY_CATEGORIES if cat in cat_breakdown["pipeline_1_baseline"]]
    display_cats = [cat_labels.get(c, c) for c in categories]

    p1_vals = [cat_breakdown["pipeline_1_baseline"][c]["recall@5"]["mean"] for c in categories]
    p2_vals = [cat_breakdown["pipeline_2_dictionary"][c]["recall@5"]["mean"] for c in categories]
    p3_vals = [cat_breakdown["pipeline_3_ontology_full"][c]["recall@5"]["mean"] for c in categories]

    x = np.arange(len(display_cats))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))

    colors = ["#4C72B0", "#DD8452", "#55A868"]

    ax.bar(x - width, p1_vals, width, label="Pipeline 1 (Baseline)", color=colors[0])
    ax.bar(x, p2_vals, width, label="Pipeline 2 (Dictionary)", color=colors[1])
    ax.bar(x + width, p3_vals, width, label="Pipeline 3 (Ontology)", color=colors[2])

    ax.set_ylabel("Recall@5", fontsize=12)
    ax.set_title("Category-Wise Retrieval Performance (Recall@5)", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(display_cats, fontsize=11)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    output_path = PLOTS_DIR / "category_breakdown.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved {output_path}")


def plot_ablation_study(summary: dict):
    """Plot ablation study results on Pipeline 3."""
    pipelines = summary["pipelines"]

    ablation_keys = [
        ("pipeline_1_baseline", "Baseline (No Expansion)"),
        ("ablation_equivalence_only", "Equivalence Only"),
        ("ablation_hierarchy_only", "Hierarchy Only"),
        ("ablation_properties_only", "Properties Only"),
        ("pipeline_3_ontology_full", "Full Ontology"),
    ]

    labels = [label for _, label in ablation_keys]
    recall_vals = [pipelines[key]["recall@5"]["mean"] for key, _ in ablation_keys]

    fig, ax = plt.subplots(figsize=(10, 5))

    colors = ["#7f7f7f", "#aec7e8", "#ffbb78", "#98df8a", "#2ca02c"]
    bars = ax.bar(labels, recall_vals, color=colors, width=0.5)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f"{height:.3f}",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_ylabel("Recall@5", fontsize=12)
    ax.set_title("Ablation Study: Contribution of Ontology Relation Types", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    output_path = PLOTS_DIR / "ablation_study.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved {output_path}")


def plot_answer_quality(summary: dict):
    """Plot answer-quality metrics: concept F1 and judge correctness."""
    pipelines = summary.get("pipelines", {})
    if not pipelines:
        return

    keys = ["pipeline_1_baseline", "pipeline_2_dictionary", "pipeline_3_ontology_full"]
    labels = ["Pipeline 1 (Baseline)", "Pipeline 2 (Dictionary)", "Pipeline 3 (Ontology)"]

    f1_vals = [pipelines[k]["aggregate"]["concept_f1"]["mean"] for k in keys if k in pipelines]
    judge_vals = [
        pipelines[k]["aggregate"].get("judge_correctness", {}).get("mean", None)
        for k in keys
        if k in pipelines
    ]

    x = np.arange(len(labels))
    width = 0.32

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#4C72B0", "#DD8452", "#55A868"]

    bars1 = ax.bar(x - width / 2, f1_vals, width, label="Concept-Coverage F1", color=colors[0])
    for bar in bars1:
        ax.annotate(f"{bar.get_height():.3f}",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)

    if all(v is not None for v in judge_vals):
        bars2 = ax.bar(x + width / 2, judge_vals, width, label="LLM Judge Correctness", color=colors[2])
        for bar in bars2:
            ax.annotate(f"{bar.get_height():.3f}",
                        xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)

    ax.set_ylabel("Score", fontsize=12)
    ax.set_title("Answer Quality Across Pipelines", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    output_path = PLOTS_DIR / "answer_quality.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved {output_path}")


def load_answer_summary() -> dict:
    answer_file = METRICS_DIR / "answer_summary.json"
    if not answer_file.exists():
        return {}
    with open(answer_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_ontology_reasoning_logs() -> list[dict]:
    """Load the full-ontology reasoning traces (Pipeline 3)."""
    log_file = REASONING_LOGS_DIR / "pipeline_3_ontology_full_reasoning_logs.json"
    if not log_file.exists():
        return []
    with open(log_file, "r", encoding="utf-8") as f:
        return json.load(f)


def plot_trace_breakdown(logs: list[dict]):
    """Stacked bar: ontology relation-family usage per query category."""
    if not logs:
        print("[SKIP] No reasoning logs — run scripts/run_experiments.py first.")
        return

    rel_by_cat = defaultdict(Counter)
    for rec in logs:
        for exp in rec.get("trace", {}).get("expansions", []):
            rel_by_cat[rec["category"]][_relation_family(exp.get("relation", ""))] += 1

    categories = [c for c in QUERY_CATEGORIES if c in rel_by_cat]
    families = [f for _, f in _RELATION_FAMILIES]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(categories))
    bottoms = np.zeros(len(categories))
    colors = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860"]

    for i, (key, label) in enumerate(_RELATION_FAMILIES):
        vals = [rel_by_cat[c][key] for c in categories]
        ax.bar(x, vals, bottom=bottoms, label=label, color=colors[i], width=0.6)
        bottoms += np.array(vals)

    ax.set_ylabel("Number of expansions", fontsize=12)
    ax.set_title("Ontology Relation Usage per Query Category (Pipeline 3)",
                 fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([CATEGORY_LABELS.get(c, c) for c in categories], fontsize=11)
    ax.legend(fontsize=10, title="Relation family")
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    output_path = PLOTS_DIR / "trace_breakdown.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved {output_path}")


def plot_adaptive_comparison():
    """Headline figure for Experiment 2: AdaOnto-RAG vs baselines + ablations.

    Panel A: Recall@5 across P1/P2/P3 and the three adaptive variants.
    Panel B: Judge-correctness across P1/P2/P3 and adaptive-full.
    Reads results/metrics/adaptive_summary.json + answer_summary.json.
    """
    adapt_file = METRICS_DIR / "adaptive_summary.json"
    if not adapt_file.exists():
        print("[SKIP] No adaptive_summary.json yet — run scripts/run_adaptive_experiment.py first.")
        return
    with open(adapt_file, "r", encoding="utf-8") as f:
        adapt = json.load(f)
    try:
        exp1 = load_summary()
    except FileNotFoundError:
        print("[SKIP] No experiment_summary.json — run scripts/run_experiments.py first.")
        return

    retr_labels = ["Baseline", "Dictionary", "Ontology", "Adapt\n(select)", "Adapt\n(mmr)", "Adapt\n(full)"]
    retr_keys = [("exp1", "pipeline_1_baseline"), ("exp1", "pipeline_2_dictionary"),
                 ("exp1", "pipeline_3_ontology_full"), ("adapt", "pipeline_4_adaptive_selective"),
                 ("adapt", "pipeline_4_adaptive_mmr"), ("adapt", "pipeline_4_adaptive_full")]
    retr_vals = []
    for src, key in retr_keys:
        src_data = exp1 if src == "exp1" else adapt
        retr_vals.append(src_data["pipelines"][key]["recall@5"]["mean"])

    answer_summary = load_answer_summary()
    judge_labels, judge_vals = [], []
    if answer_summary and "pipelines" in answer_summary:
        for label, key in [("Baseline", "pipeline_1_baseline"),
                           ("Dictionary", "pipeline_2_dictionary"),
                           ("Ontology", "pipeline_3_ontology_full"),
                           ("Adapt (full)", "pipeline_4_adaptive_full")]:
            agg = answer_summary["pipelines"].get(key, {}).get("aggregate", {})
            if "judge_correctness" in agg:
                judge_labels.append(label)
                judge_vals.append(agg["judge_correctness"]["mean"])

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    colors_a = ["#4C72B0", "#DD8452", "#55A868", "#C4C4C4", "#999999", "#C44E52"]
    bars = axes[0].bar(retr_labels, retr_vals, color=colors_a)
    for rect in bars:
        h = rect.get_height()
        axes[0].annotate(f"{h:.3f}", xy=(rect.get_x() + rect.get_width() / 2, h),
                         xytext=(0, 3), textcoords="offset points",
                         ha="center", va="bottom", fontsize=9)
    axes[0].set_ylabel("Recall@5", fontsize=12)
    axes[0].set_title("A: Retrieval — AdaOnto-RAG vs baselines", fontsize=13, fontweight="bold")
    axes[0].set_ylim(0, max(retr_vals) * 1.25)
    axes[0].grid(axis="y", linestyle="--", alpha=0.7)

    if judge_vals:
        colors_b = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]
        bars = axes[1].bar(judge_labels, judge_vals, color=colors_b)
        for rect in bars:
            h = rect.get_height()
            axes[1].annotate(f"{h:.3f}", xy=(rect.get_x() + rect.get_width() / 2, h),
                             xytext=(0, 3), textcoords="offset points",
                             ha="center", va="bottom", fontsize=9)
        axes[1].set_ylabel("Judge correctness", fontsize=12)
        axes[1].set_title("B: Answer quality — judge correctness", fontsize=13, fontweight="bold")
        axes[1].set_ylim(0, max(judge_vals) * 1.25)
        axes[1].grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    output_path = PLOTS_DIR / "adaptive_comparison.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"[OK] Saved {output_path}")


def main():
    ensure_directories()
    summary = load_summary()

    sns.set_theme(style="whitegrid")

    plot_overall_comparison(summary)
    plot_category_breakdown(summary)
    plot_ablation_study(summary)
    plot_trace_breakdown(load_ontology_reasoning_logs())
    plot_adaptive_comparison()

    answer_summary = load_answer_summary()
    if answer_summary:
        plot_answer_quality(answer_summary)
    else:
        print("[SKIP] No answer_summary.json yet — run scripts/run_answer_eval.py first.")

    print(f"\n[OK] All plots generated in {PLOTS_DIR}")


if __name__ == "__main__":
    main()
