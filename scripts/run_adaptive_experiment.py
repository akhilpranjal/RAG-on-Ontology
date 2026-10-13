"""Experiment 2 — AdaOnto-RAG evaluation (pre-registered design).

Evaluates the novel adaptive architecture on the SAME 66-query testbed as
Experiment 1 (same queries, judgments, metrics, statistics):
  - pipeline_4_adaptive_full      (router + selective expansion + MMR)
  - pipeline_4_adaptive_selective (router + selective expansion, no MMR)
  - pipeline_4_adaptive_mmr       (no expansion, dense + MMR)

Compares adaptive_full vs Pipelines 1-3 on Recall@5 (primary metric).
Writes results/metrics/adaptive_summary.json (experiment_summary.json untouched).

Usage:
    uv run python -m scripts.run_adaptive_experiment
"""

from __future__ import annotations

import collections
import json

from src.config import (
    QUERIES_FILE,
    RELEVANCE_JUDGMENTS_FILE,
    METRICS_DIR,
    QUERY_CATEGORIES,
    ensure_directories,
)
from src.evaluation.statistical_tests import full_comparison
from src.pipelines.adaptive import run_adaptive

from scripts.run_experiments import get_or_run_pipeline


def _recall5(results: dict) -> list[float]:
    return [r["metrics"]["recall@5"] for r in results["per_query_results"]]


def _load_saved(name: str) -> dict:
    with open(METRICS_DIR / f"{name}_results.json", "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    ensure_directories()

    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)
    with open(RELEVANCE_JUDGMENTS_FILE, "r", encoding="utf-8") as f:
        relevance_judgments = json.load(f)

    print("=" * 60)
    print(f"Experiment 2 (AdaOnto-RAG) across {len(queries)} queries")
    print("=" * 60)

    full = get_or_run_pipeline(
        run_adaptive, "pipeline_4_adaptive_full", queries, relevance_judgments, mode="full",
    )
    selective = get_or_run_pipeline(
        run_adaptive, "pipeline_4_adaptive_selective", queries, relevance_judgments, mode="selective",
    )
    mmr = get_or_run_pipeline(
        run_adaptive, "pipeline_4_adaptive_mmr", queries, relevance_judgments, mode="mmr",
    )

    # Router intent distribution (reporting only).
    from src.pipelines.router import QueryRouter

    router = QueryRouter()
    dist = collections.Counter(router.route(q["text"])["intent"] for q in queries)
    print("\nRouter intent distribution (66 queries):")
    for intent, count in sorted(dist.items()):
        print(f"  - {intent}: {count}")

    # Persist per-query router decisions alongside results (deterministic free
    # recompute; additive only, does not touch retrieval outcomes).
    for name, results in (
        ("pipeline_4_adaptive_full", full),
        ("pipeline_4_adaptive_selective", selective),
        ("pipeline_4_adaptive_mmr", mmr),
    ):
        for rec in results["per_query_results"]:
            info = router.route(rec["query"])
            rec["adaptive"] = {
                "intent": info["intent"],
                "mask": info["mask"],
                "lay_terms_found": info["lay_terms_found"],
                "matched_concepts": info["matched_concepts"],
            }
        with open(METRICS_DIR / f"{name}_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    # Baselines from Experiment 1 (frozen files).
    p1 = _load_saved("pipeline_1_baseline")
    p2 = _load_saved("pipeline_2_dictionary")
    p3 = _load_saved("pipeline_3_ontology_full")

    r_full, r_sel, r_mmr = _recall5(full), _recall5(selective), _recall5(mmr)
    r1, r2, r3 = _recall5(p1), _recall5(p2), _recall5(p3)

    stats = {
        "adaptive_full_vs_baseline": full_comparison(r_full, r1, "Adaptive (full)", "Baseline"),
        "adaptive_full_vs_dictionary": full_comparison(r_full, r2, "Adaptive (full)", "Dictionary"),
        "adaptive_full_vs_ontology": full_comparison(r_full, r3, "Adaptive (full)", "Ontology-full"),
        "adaptive_selective_vs_baseline": full_comparison(r_sel, r1, "Adaptive (selective)", "Baseline"),
        "adaptive_mmr_vs_baseline": full_comparison(r_mmr, r1, "Adaptive (mmr)", "Baseline"),
    }

    summary = {
        "pipelines": {
            "pipeline_4_adaptive_full": full["overall_metrics"],
            "pipeline_4_adaptive_selective": selective["overall_metrics"],
            "pipeline_4_adaptive_mmr": mmr["overall_metrics"],
        },
        "statistical_tests": stats,
        "category_breakdown": {
            "pipeline_4_adaptive_full": full["category_metrics"],
            "pipeline_4_adaptive_selective": selective["category_metrics"],
            "pipeline_4_adaptive_mmr": mmr["category_metrics"],
        },
        "router_intents": dict(dist),
    }
    out = METRICS_DIR / "adaptive_summary.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("EXPERIMENT 2 SUMMARY (Recall@5 mean)")
    print("=" * 60)
    print(f"Baseline (P1):            {p1['overall_metrics']['recall@5']['mean']:.4f}")
    print(f"Dictionary (P2):          {p2['overall_metrics']['recall@5']['mean']:.4f}")
    print(f"Ontology-full (P3):       {p3['overall_metrics']['recall@5']['mean']:.4f}")
    print(f"Adaptive selective-only:  {selective['overall_metrics']['recall@5']['mean']:.4f}")
    print(f"Adaptive mmr-only:        {mmr['overall_metrics']['recall@5']['mean']:.4f}")
    print(f"Adaptive FULL (novel):    {full['overall_metrics']['recall@5']['mean']:.4f}")
    print("-" * 60)
    for key in ("adaptive_full_vs_baseline", "adaptive_full_vs_dictionary", "adaptive_full_vs_ontology"):
        s = stats[key]
        print(f"{key}: p={s['wilcoxon']['p_value']:.4f}, d={s['cohens_d']:.4f}, cliff={s['cliffs_delta']:.4f}")
    print("=" * 60)
    print(f"\n[OK] Experiment 2 summary saved to {out}")


if __name__ == "__main__":
    main()
