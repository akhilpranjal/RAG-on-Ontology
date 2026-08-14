"""Main experiment runner — executes all 3 pipelines and ablations across all queries.

Pipeline 1: Baseline Semantic RAG
Pipeline 2: Dictionary Expansion RAG
Pipeline 3: Ontology-Enhanced RAG

Metrics computed:
  - Recall@5, Recall@10, Precision@5, Hit@5, MRR, nDCG@5
  - Category-wise breakdown across all 6 query categories
  - Statistical tests: Wilcoxon signed-rank, Cohen's d, Cliff's delta
  - Ablation study on Pipeline 3 (Equivalence only, Hierarchy only, Properties only, Full)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import (
    QUERIES_FILE,
    RELEVANCE_JUDGMENTS_FILE,
    METRICS_DIR,
    REASONING_LOGS_DIR,
    QUERY_CATEGORIES,
    ensure_directories,
)
from src.corpus.loader import load_and_chunk_corpus
from src.corpus.vectorstore import index_chunks, get_or_create_collection
from src.evaluation.retrieval_metrics import compute_all_retrieval_metrics, aggregate_metrics
from src.evaluation.statistical_tests import full_comparison
from src.pipelines.baseline import run_baseline
from src.pipelines.dictionary import run_dictionary
from src.pipelines.ontology_enhanced import run_ontology_enhanced


def ensure_vectorstore():
    """Ensure ChromaDB is populated with corpus chunks before running experiments."""
    collection = get_or_create_collection()
    if collection.count() == 0:
        print("Vector store is empty. Indexing corpus chunks...")
        chunks = load_and_chunk_corpus()
        index_chunks(chunks)
        print(f"Indexed {len(chunks)} chunks.")
    else:
        print(f"Vector store ready: {collection.count()} chunks indexed.")


def run_pipeline_eval(
    pipeline_fn,
    pipeline_name: str,
    queries: list[dict],
    relevance_judgments: dict[str, list[str]],
    **pipeline_kwargs,
) -> dict:
    """Run a single pipeline across all queries and compute retrieval metrics.

    Returns dict with per_query_results, aggregated_metrics, and category_metrics.
    Persists per-query results immediately so progress survives API quota errors.
    """
    print(f"\nRunning {pipeline_name}...")
    per_query_results = []
    reasoning_logs = []

    for q in queries:
        q_id = q["id"]
        q_text = q["text"]
        relevant_docs = relevance_judgments.get(q_id, [])

        # Run pipeline without hitting Gemini generation API (save quota, we only need retrieval metrics)
        res = pipeline_fn(q_text, generate=False, **pipeline_kwargs)

        # Compute metrics
        metrics = compute_all_retrieval_metrics(
            retrieved_doc_ids=res.retrieved_doc_ids,
            relevant_doc_ids=relevant_docs,
        )

        query_record = {
            "query_id": q_id,
            "category": q["category"],
            "query": q_text,
            "retrieved_chunk_ids": res.retrieved_chunk_ids,
            "retrieved_doc_ids": res.retrieved_doc_ids,
            "relevant_doc_ids": relevant_docs,
            "metrics": metrics,
        }
        per_query_results.append(query_record)

        # Collect reasoning logs for Pipeline 3
        if "reasoning_trace" in res.metadata:
            reasoning_logs.append({
                "query_id": q_id,
                "category": q["category"],
                "trace": res.metadata["reasoning_trace"],
            })

    # Overall aggregated metrics
    query_metric_dicts = [r["metrics"] for r in per_query_results]
    overall_aggregated = aggregate_metrics(query_metric_dicts)

    # Category-wise aggregated metrics
    category_metrics = {}
    for cat in QUERY_CATEGORIES:
        cat_results = [r["metrics"] for r in per_query_results if r["category"] == cat]
        if cat_results:
            category_metrics[cat] = aggregate_metrics(cat_results)

    # Save reasoning logs if present
    if reasoning_logs:
        REASONING_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = REASONING_LOGS_DIR / f"{pipeline_name}_reasoning_logs.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(reasoning_logs, f, indent=2, ensure_ascii=False)

    results = {
        "pipeline_name": pipeline_name,
        "overall_metrics": overall_aggregated,
        "category_metrics": category_metrics,
        "per_query_results": per_query_results,
    }

    # Persist pipeline results so a quota failure mid-run doesn't lose progress.
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    result_file = METRICS_DIR / f"{pipeline_name}_results.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[OK] {pipeline_name} results saved to {result_file}")

    return results


def get_or_run_pipeline(
    pipeline_fn,
    pipeline_name: str,
    queries: list[dict],
    relevance_judgments: dict[str, list[str]],
    **pipeline_kwargs,
) -> dict:
    """Resume from saved results if available, otherwise run the pipeline."""
    result_file = METRICS_DIR / f"{pipeline_name}_results.json"
    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("pipeline_name") == pipeline_name and len(saved.get("per_query_results", [])) == len(queries):
            print(f"[OK] {pipeline_name} loaded from cache: {result_file}")
            return saved
    return run_pipeline_eval(pipeline_fn, pipeline_name, queries, relevance_judgments, **pipeline_kwargs)


def main():
    ensure_directories()
    ensure_vectorstore()

    # Load queries and relevance judgments
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)
    with open(RELEVANCE_JUDGMENTS_FILE, "r", encoding="utf-8") as f:
        relevance_judgments = json.load(f)

    print("=" * 60)
    print(f"Running Controlled Experiment across {len(queries)} queries")
    print("=" * 60)

    # 1. Run Pipeline 1 (Baseline RAG)
    p1_results = get_or_run_pipeline(
        run_baseline,
        "pipeline_1_baseline",
        queries,
        relevance_judgments,
    )

    # 2. Run Pipeline 2 (Dictionary Expansion RAG)
    p2_results = get_or_run_pipeline(
        run_dictionary,
        "pipeline_2_dictionary",
        queries,
        relevance_judgments,
    )

    # 3. Run Pipeline 3 (Ontology-Enhanced RAG — Full)
    p3_results = get_or_run_pipeline(
        run_ontology_enhanced,
        "pipeline_3_ontology_full",
        queries,
        relevance_judgments,
    )

    # 4. Run Ablation Studies on Pipeline 3
    print("\nRunning Ablation Studies...")
    p3_equiv = get_or_run_pipeline(
        run_ontology_enhanced,
        "pipeline_3_ablation_equivalence_only",
        queries,
        relevance_judgments,
        enable_equivalence=True,
        enable_hierarchy=False,
        enable_properties=False,
    )

    p3_hier = get_or_run_pipeline(
        run_ontology_enhanced,
        "pipeline_3_ablation_hierarchy_only",
        queries,
        relevance_judgments,
        enable_equivalence=False,
        enable_hierarchy=True,
        enable_properties=False,
    )

    p3_props = get_or_run_pipeline(
        run_ontology_enhanced,
        "pipeline_3_ablation_properties_only",
        queries,
        relevance_judgments,
        enable_equivalence=False,
        enable_hierarchy=False,
        enable_properties=True,
    )

    # 5. Statistical Comparisons
    print("\nRunning Statistical Tests...")
    recall_p1 = [r["metrics"]["recall@5"] for r in p1_results["per_query_results"]]
    recall_p2 = [r["metrics"]["recall@5"] for r in p2_results["per_query_results"]]
    recall_p3 = [r["metrics"]["recall@5"] for r in p3_results["per_query_results"]]

    stats_p3_vs_p1 = full_comparison(recall_p3, recall_p1, "Pipeline 3 (Ontology)", "Pipeline 1 (Baseline)")
    stats_p3_vs_p2 = full_comparison(recall_p3, recall_p2, "Pipeline 3 (Ontology)", "Pipeline 2 (Dictionary)")
    stats_p2_vs_p1 = full_comparison(recall_p2, recall_p1, "Pipeline 2 (Dictionary)", "Pipeline 1 (Baseline)")

    # 6. Save All Results
    summary = {
        "pipelines": {
            "pipeline_1_baseline": p1_results["overall_metrics"],
            "pipeline_2_dictionary": p2_results["overall_metrics"],
            "pipeline_3_ontology_full": p3_results["overall_metrics"],
            "ablation_equivalence_only": p3_equiv["overall_metrics"],
            "ablation_hierarchy_only": p3_hier["overall_metrics"],
            "ablation_properties_only": p3_props["overall_metrics"],
        },
        "statistical_tests": {
            "ontology_vs_baseline": stats_p3_vs_p1,
            "ontology_vs_dictionary": stats_p3_vs_p2,
            "dictionary_vs_baseline": stats_p2_vs_p1,
        },
        "category_breakdown": {
            "pipeline_1_baseline": p1_results["category_metrics"],
            "pipeline_2_dictionary": p2_results["category_metrics"],
            "pipeline_3_ontology_full": p3_results["category_metrics"],
        },
    }

    summary_file = METRICS_DIR / "experiment_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS SUMMARY (Recall@5)")
    print("=" * 60)
    print(f"Pipeline 1 (Baseline):   {p1_results['overall_metrics']['recall@5']['mean']:.4f}")
    print(f"Pipeline 2 (Dictionary): {p2_results['overall_metrics']['recall@5']['mean']:.4f}")
    print(f"Pipeline 3 (Ontology):   {p3_results['overall_metrics']['recall@5']['mean']:.4f}")
    print("-" * 60)
    print(f"Ontology vs Baseline:   p={stats_p3_vs_p1['wilcoxon']['p_value']:.4f}, Cohen's d={stats_p3_vs_p1['cohens_d']:.4f}")
    print(f"Ontology vs Dictionary: p={stats_p3_vs_p2['wilcoxon']['p_value']:.4f}, Cohen's d={stats_p3_vs_p2['cohens_d']:.4f}")
    print("=" * 60)
    print(f"\n[OK] Full results saved to {summary_file}")


if __name__ == "__main__":
    main()
