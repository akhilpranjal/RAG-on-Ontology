"""Demo: unified LangGraph orchestration across all 3 pipelines.

Runs a set of sample queries through the shared graph and prints the
retrieval + (optionally) generation results for each pipeline.

Usage:
    uv run python -m scripts.orchestrate_demo
    uv run python -m scripts.orchestrate_demo --generate
"""

from __future__ import annotations

import sys

from src.corpus.vectorstore import get_or_create_collection
from src.orchestration.graph import build_graph, run_all_pipelines
from src.config import QUERIES_FILE

SAMPLE_QUERIES = [
    "What is high blood pressure and how is it treated?",
    "My heart feels like it is skipping beats. What could this be?",
    "What medications are used for type 2 diabetes?",
    "What is the relationship between obesity and heart disease?",
    "Chest pain and shortness of breath — what condition might this indicate?",
]


def main():
    generate = "--generate" in sys.argv

    print("=" * 70)
    print("UNIFIED LANGGRAPH ORCHESTRATION — ALL 3 PIPELINES")
    print("=" * 70)

    app = build_graph()
    print("[OK] Compiled LangGraph with nodes:", sorted(app.get_graph().nodes.keys()))

    collection = get_or_create_collection()
    print(f"[OK] Vector store ready: {collection.count()} chunks indexed.\n")

    queries = SAMPLE_QUERIES
    # If the evaluation set exists, prefer a few queries from it.
    if QUERIES_FILE.exists():
        import json
        with open(QUERIES_FILE, "r", encoding="utf-8") as f:
            eval_queries = json.load(f)
        queries = [q["text"] for q in eval_queries[:3]] + queries

    for query in queries:
        print("-" * 70)
        print(f"QUERY: {query}")
        print("-" * 70)

        results = run_all_pipelines(query, top_k=5, generate=generate)

        for pipeline, res in results.items():
            print(f"\n  [{res.pipeline_name}]")
            print(f"    Expansion ({res.metadata['expansion_strategy']}): "
                  f"{res.metadata['expanded_terms'][:6]}"
                  f"{'...' if len(res.metadata['expanded_terms']) > 6 else ''}")
            print(f"    Retrieved docs ({len(res.retrieved_doc_ids)}): "
                  f"{res.retrieved_doc_ids[:5]}")
            if generate and res.answer:
                print(f"    Answer: {res.answer[:180]}...")

    print("\n[OK] Orchestration demo complete.")


if __name__ == "__main__":
    main()