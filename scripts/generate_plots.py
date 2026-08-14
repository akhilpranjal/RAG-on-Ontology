"""Plotting script — generates charts from experiment results.

Generates:
  1. overall_comparison.png — Bar chart comparing Recall@5, MRR, nDCG@5 across pipelines
  2. category_breakdown.png — Grouped bar chart comparing Recall@5 per category
  3. ablation_study.png — Bar chart showing contribution of relation types
  4. answer_quality.png — Bar chart of concept-coverage F1 + judge correctness
"""

from __future__ import annotations

import json
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from src.config import METRICS_DIR, PLOTS_DIR, QUERY_CATEGORIES, ensure_directories


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


def main():
    ensure_directories()
    summary = load_summary()

    sns.set_theme(style="whitegrid")

    plot_overall_comparison(summary)
    plot_category_breakdown(summary)
    plot_ablation_study(summary)

    answer_summary = load_answer_summary()
    if answer_summary:
        plot_answer_quality(answer_summary)
    else:
        print("[SKIP] No answer_summary.json yet — run scripts/run_answer_eval.py first.")

    print(f"\n[OK] All plots generated in {PLOTS_DIR}")


if __name__ == "__main__":
    main()
