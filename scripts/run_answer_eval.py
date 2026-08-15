"""Answer-quality evaluation runner.

For every query and pipeline:
  - generates an answer (Gemini generator)
  - computes concept-coverage Precision/Recall/F1 (objective)
  - optionally grades the answer with a *different* Gemini model (LLM judge)

Persists results per-query so a quota/rate-limit interruption resumes cleanly.

Usage:
    uv run python -m scripts.run_answer_eval                 # full run + judge
    uv run python -m scripts.run_answer_eval --no-judge      # skip LLM judge
    uv run python -m scripts.run_answer_eval --limit 3       # smoke test
"""

from __future__ import annotations

import argparse
import json
import re
import time

from google.genai.errors import ClientError

from src.config import (
    QUERIES_FILE,
    METRICS_DIR,
    QUERY_CATEGORIES,
    ensure_directories,
)
from src.evaluation.answer_metrics import ConceptResolver, concept_coverage_f1, judge_answer
from src.evaluation.retrieval_metrics import aggregate_metrics
from src.evaluation.statistical_tests import full_comparison
from src.generation.generator import generate_answer
from src.pipelines.baseline import run_baseline
from src.pipelines.dictionary import run_dictionary
from src.pipelines.ontology_enhanced import run_ontology_enhanced

PIPELINES = {
    "pipeline_1_baseline": (run_baseline, "Pipeline 1 (Baseline)"),
    "pipeline_2_dictionary": (run_dictionary, "Pipeline 2 (Dictionary)"),
    "pipeline_3_ontology_full": (run_ontology_enhanced, "Pipeline 3 (Ontology)"),
}

SLEEP_BETWEEN_QUERIES = 1.0  # seconds, to respect RPM limits


def _format_trace(trace: dict) -> str:
    """Format a saved reasoning trace for the generator prompt (Pipeline 3)."""
    lines = [f"Query: {trace.get('original_query', '')}"]
    for match in trace.get("matched_concepts", []):
        lines.append(
            f"  Matched: '{match.get('term', '')}' → "
            f"{match.get('concept_id', '')} ({match.get('label', '')})"
        )
    for exp in trace.get("expansions", []):
        lines.append(
            f"  Expansion ({exp.get('relation', '')}): "
            f"{exp.get('source', '')} → {exp.get('target', '')} "
            f"({exp.get('target_label', '')})"
        )
    return "\n".join(lines)


def _load_retrieval_records(pipeline_key: str) -> dict | None:
    """Load saved retrieval results to reuse chunk texts (avoids re-embedding)."""
    result_file = METRICS_DIR / f"{pipeline_key}_results.json"
    if not result_file.exists():
        return None
    with open(result_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {r["query_id"]: r for r in data.get("per_query_results", [])}


def retry_call(fn, retries: int = 12, base_delay: float = 20.0, max_delay: float = 90.0):
    """Call fn, retrying on rate-limit (429) / transient server errors (503)."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - surface any transient API error
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "high demand" in msg:
                delay = min(base_delay * (2 ** attempt), max_delay)
                # Respect the server's suggested retry delay when present.
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", msg)
                if match:
                    delay = max(delay, float(match.group(1)) + 5.0)
                print(f"    [quota/server] retrying in {delay:.0f}s ...")
                time.sleep(delay)
            else:
                raise
    raise RuntimeError("Persistent rate limiting after retries.")


def run_pipeline_answers(
    pipeline_fn,
    pipeline_name: str,
    queries: list[dict],
    use_judge: bool,
    resolver: ConceptResolver,
) -> list[dict]:
    """Generate + grade answers for a pipeline across all queries (resumable).

    If the retrieval experiment already saved chunk texts for this pipeline,
    they are reused for generation (no re-embedding needed). Otherwise the
    full pipeline (retrieve + generate) is run.
    """
    out_file = METRICS_DIR / f"{pipeline_name}_answers.json"
    retrieval_records = _load_retrieval_records(pipeline_name)

    records = []
    if out_file.exists():
        with open(out_file, "r", encoding="utf-8") as f:
            records = json.load(f)
        print(f"[OK] {pipeline_name}: loaded {len(records)} existing answer records")

    done_ids = {r["query_id"] for r in records}
    new_count = 0
    backfilled = 0

    for q in queries:
        existing_idx = next(
            (i for i, r in enumerate(records) if r["query_id"] == q["id"]), None
        )
        if existing_idx is not None and use_judge and "judge" not in records[existing_idx]:
            # Backfill judge for records created during a --no-judge run.
            records[existing_idx]["judge"] = retry_call(
                lambda: judge_answer(q["text"], q.get("target_concepts", []), records[existing_idx]["answer"])
            )
            backfilled += 1
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            continue

        if existing_idx is not None:
            continue

        # Prefer cached retrieved texts from the retrieval experiment.
        cached = retrieval_records.get(q["id"]) if retrieval_records else None
        if cached and cached.get("retrieved_texts"):
            answer = retry_call(
                lambda: generate_answer(
                    question=q["text"],
                    context_chunks=cached["retrieved_texts"],
                    ontology_context=(
                        _format_trace(cached["reasoning_trace"])
                        if cached.get("reasoning_trace") else None
                    ),
                )
            )
        else:
            answer = retry_call(
                lambda: pipeline_fn(q["text"], generate=True).answer
            )

        record = {
            "query_id": q["id"],
            "category": q["category"],
            "query": q["text"],
            "answer": answer,
            "concept_metrics": concept_coverage_f1(
                answer, q.get("target_concepts", []), resolver
            ),
        }

        if use_judge:
            record["judge"] = retry_call(
                lambda: judge_answer(q["text"], q.get("target_concepts", []), answer)
            )

        records.append(record)
        new_count += 1

        # Persist after every query so interruption doesn't lose progress.
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

        if new_count % 5 == 0:
            print(f"    {pipeline_name}: {len(records)}/{len(queries)} answered")
        time.sleep(SLEEP_BETWEEN_QUERIES)

    if backfilled:
        print(f"    {pipeline_name}: backfilled {backfilled} judge grades")

    return records


def aggregate_answers(records: list[dict]) -> dict:
    """Aggregate per-query answer metrics into summary statistics."""
    f1_scores = [r["concept_metrics"]["f1"] for r in records]
    prec_scores = [r["concept_metrics"]["precision"] for r in records]
    recall_scores = [r["concept_metrics"]["recall"] for r in records]

    agg = {
        "concept_f1": aggregate_metrics([{"f1": v} for v in f1_scores]).get("f1", {}),
        "concept_precision": aggregate_metrics([{"p": v} for v in prec_scores]).get("p", {}),
        "concept_recall": aggregate_metrics([{"r": v} for v in recall_scores]).get("r", {}),
    }

    judged = [r for r in records if "judge" in r]
    if judged:
        correct_vals = [1.0 if r["judge"].get("correct") else 0.0 for r in judged]
        score_vals = [float(r["judge"].get("score", 0)) for r in judged]
        agg["judge_correctness"] = {
            "mean": sum(correct_vals) / len(correct_vals),
            "n": len(correct_vals),
        }
        agg["judge_score"] = aggregate_metrics([{"s": v} for v in score_vals]).get("s", {})

    return agg


def category_aggregates(records: list[dict]) -> dict:
    """Per-category mean concept F1."""
    result = {}
    for cat in QUERY_CATEGORIES:
        cat_records = [r for r in records if r["category"] == cat]
        if cat_records:
            result[cat] = {
                "concept_f1": sum(r["concept_metrics"]["f1"] for r in cat_records) / len(cat_records),
                "n": len(cat_records),
            }
    return result


def main():
    parser = argparse.ArgumentParser(description="Answer-quality evaluation")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    parser.add_argument("--limit", type=int, default=None, help="only first N queries (smoke test)")
    args = parser.parse_args()

    ensure_directories()

    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)
    if args.limit:
        queries = queries[: args.limit]

    print("=" * 60)
    print(f"Answer-quality evaluation on {len(queries)} queries "
          f"(judge={'ON' if not args.no_judge else 'OFF'})")
    print("=" * 60)

    resolver = ConceptResolver()
    pipeline_records = {}
    summary = {"pipelines": {}, "statistical_tests": {}, "category_breakdown": {}}

    for key, (pipeline_fn, label) in PIPELINES.items():
        print(f"\n--- {label} ---")
        records = run_pipeline_answers(
            pipeline_fn, key, queries, use_judge=not args.no_judge, resolver=resolver
        )
        pipeline_records[key] = records
        summary["pipelines"][key] = {
            "label": label,
            "aggregate": aggregate_answers(records),
            "category_metrics": category_aggregates(records),
        }

    # Statistical comparisons on concept F1 (paired across queries)
    f1_by_pipeline = {
        key: [r["concept_metrics"]["f1"] for r in records]
        for key, records in pipeline_records.items()
    }

    for pair_key, (a, b, la, lb) in {
        "ontology_vs_baseline": ("pipeline_3_ontology_full", "pipeline_1_baseline",
                                 "Pipeline 3 (Ontology)", "Pipeline 1 (Baseline)"),
        "ontology_vs_dictionary": ("pipeline_3_ontology_full", "pipeline_2_dictionary",
                                   "Pipeline 3 (Ontology)", "Pipeline 2 (Dictionary)"),
        "dictionary_vs_baseline": ("pipeline_2_dictionary", "pipeline_1_baseline",
                                   "Pipeline 2 (Dictionary)", "Pipeline 1 (Baseline)"),
    }.items():
        summary["statistical_tests"][pair_key] = full_comparison(
            f1_by_pipeline[a], f1_by_pipeline[b], la, lb
        )

    summary_file = METRICS_DIR / "answer_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("ANSWER QUALITY SUMMARY (Concept-Coverage F1)")
    print("=" * 60)
    for key, label in [("pipeline_1_baseline", "Pipeline 1 (Baseline)"),
                       ("pipeline_2_dictionary", "Pipeline 2 (Dictionary)"),
                       ("pipeline_3_ontology_full", "Pipeline 3 (Ontology)")]:
        agg = summary["pipelines"][key]["aggregate"]
        judge_line = ""
        if "judge_correctness" in agg:
            judge_line = f" | Judge correct: {agg['judge_correctness']['mean']:.3f}"
        print(f"{label}: F1={agg['concept_f1']['mean']:.4f} "
              f"(P={agg['concept_precision']['mean']:.3f}, "
              f"R={agg['concept_recall']['mean']:.3f}){judge_line}")
    print("-" * 60)
    for key, test in summary["statistical_tests"].items():
        print(f"{key}: p={test['wilcoxon']['p_value']:.4f}, "
              f"Cohen's d={test['cohens_d']:.3f}, "
              f"Cliff's delta={test['cliffs_delta']['cliffs_delta']:.3f}")
    print("=" * 60)
    print(f"\n[OK] Answer summary saved to {summary_file}")


if __name__ == "__main__":
    main()