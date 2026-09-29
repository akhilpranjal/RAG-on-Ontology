"""Live demo for panel presentation: 3 pipelines, one query, full transparency.

Runs a single query through the unified LangGraph and prints, for each
pipeline (Baseline / Dictionary / Ontology):
  - what expansion happened (incl. full ontology reasoning trace)
  - which documents were retrieved, with titles + concept tags
  - the generated answer (Gemini), when generation is enabled

Usage:
    uv run python -m scripts.live_demo                       # default lay query, with answers
    uv run python -m scripts.live_demo --query "your query"  # custom query
    uv run python -m scripts.live_demo --no-generate         # retrieval only (no API cost)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import time

from src.config import GOOGLE_API_KEY, GENERATOR_MODEL, TOP_K_PRIMARY, QUERIES_FILE, RELEVANCE_JUDGMENTS_FILE
from src.corpus.vectorstore import get_or_create_collection
from src.generation.generator import generate_answer
from src.ontology.reasoner import OntologyReasoner
from src.pipelines.baseline import run_baseline
from src.pipelines.dictionary import run_dictionary
from src.pipelines.ontology_enhanced import run_ontology_enhanced

# Hero query: treatment reasoning where baseline retrieves ZERO relevant docs
# and ontology finds 4/5 (dictionary finds 2/5) - the clearest live contrast.
DEFAULT_QUERY = "What antiplatelet and anticoagulant medications reduce thrombosis risk?"

PIPELINES = [
    ("Pipeline 1 - Baseline", run_baseline, "none (raw query)"),
    ("Pipeline 2 - Dictionary", run_dictionary, "dictionary (flat synonym list)"),
    ("Pipeline 3 - Ontology", run_ontology_enhanced, "ontology traversal"),
]


def _generate_with_retry(question: str, context_chunks: list[str],
                         ontology_context: str | None = None,
                         retries: int = 8) -> str:
    """Generate an answer, backing off on 429/503 so a demo never crashes."""
    for attempt in range(retries):
        try:
            return generate_answer(question=question, context_chunks=context_chunks,
                                   ontology_context=ontology_context)
        except Exception as e:  # noqa: BLE001 - surface transient API errors
            msg = str(e)
            if "429" in msg or "503" in msg or "RESOURCE_EXHAUSTED" in msg or "high demand" in msg:
                delay = min(5 * (2 ** attempt), 45)
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", msg)
                if match:
                    delay = max(delay, float(match.group(1)) + 5.0)
                print(f"    [API busy] retrying in {delay:.0f}s ...")
                time.sleep(delay)
            else:
                raise
    return "[generation unavailable - API busy; demo continues in retrieval mode]"


def _load_ground_truth(query_text: str) -> tuple[str | None, set[str]]:
    """Find the eval query_id + relevant doc set for a query text (if any)."""
    if not (QUERIES_FILE.exists() and RELEVANCE_JUDGMENTS_FILE.exists()):
        return None, set()
    with open(QUERIES_FILE, "r", encoding="utf-8") as f:
        queries = json.load(f)
    match = next((q for q in queries if q["text"].strip() == query_text.strip()), None)
    if not match:
        return None, set()
    with open(RELEVANCE_JUDGMENTS_FILE, "r", encoding="utf-8") as f:
        judgments = json.load(f)
    return match["id"], set(judgments.get(match["id"], []))


def _load_titles() -> dict[str, str]:
    """Map doc_id -> document title from the corpus JSON files."""
    titles = {}
    for pattern in ("data/corpus/real/*.json", "data/corpus/synthetic/*.json"):
        for path in glob.glob(pattern):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                doc_id = doc.get("doc_id") or os.path.splitext(os.path.basename(path))[0]
                titles[doc_id] = doc.get("title", "")[:110]
            except (json.JSONDecodeError, OSError):
                continue
    return titles


def _print_header(text: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {text}")
    print("=" * 78)


def _print_pipeline(name: str, result, titles: dict[str, str],
                    relevant: set[str] | None = None,
                    strategy_default: str = "n/a") -> int:
    print(f"\n--- {name} ---")
    meta = result.metadata
    strategy = meta.get("expansion_strategy") or strategy_default
    expanded = meta.get("expanded_terms", [])

    print(f"  Expansion strategy : {strategy}")
    print(f"  Expanded terms     : {expanded if expanded else '(none - raw query)'}")

    trace = meta.get("reasoning_trace")
    if trace:
        print("  Reasoning trace    :")
        for m in trace.get("matched_concepts", []):
            print(f"      matched : '{m.get('term')}' -> {m.get('concept_id')} ({m.get('label')})")
        for e in trace.get("expansions", []):
            print(f"      {e.get('source')} --[{e.get('relation')}]--> {e.get('target')}")

    print(f"  Retrieved ({len(result.retrieved_doc_ids)} chunks):")
    seen: set[str] = set()
    found_relevant: set[str] = set()
    for i, doc_id in enumerate(result.retrieved_doc_ids, 1):
        title = titles.get(doc_id, "(title unavailable)")
        mark = ""
        if doc_id in seen:
            mark = "  (duplicate chunk of same doc)"
        elif relevant is not None and doc_id in relevant:
            found_relevant.add(doc_id)
            mark = "  [OK] RELEVANT (ground truth)"
        seen.add(doc_id)
        print(f"      {i}. {title}   [{doc_id}]{mark}")

    if relevant:
        print(f"  Ground truth hits  : {len(found_relevant)}/{len(relevant)} "
              f"relevant documents retrieved")

    if result.answer:
        print("  Generated answer:")
        print("      " + result.answer.strip().replace("\n", "\n      "))
    return len(found_relevant)


def main() -> None:
    parser = argparse.ArgumentParser(description="Panel live demo")
    parser.add_argument("--query", default=None, help="custom query (default: lay-phrasing demo)")
    parser.add_argument("--no-generate", action="store_true", help="retrieval only (no API cost)")
    parser.add_argument("--top-k", type=int, default=TOP_K_PRIMARY)
    args = parser.parse_args()

    query = args.query or DEFAULT_QUERY

    do_generate = not args.no_generate
    if do_generate and not GOOGLE_API_KEY:
        print("[WARN] GOOGLE_API_KEY missing  -  falling back to retrieval only.")
        do_generate = False

    query_id, relevant = _load_ground_truth(query)

    _print_header("LIVE DEMO: ONE QUERY, THREE PIPELINES (shared LangGraph graph)")
    print(f"  Query : {query}")
    print(f"  Mode  : {'retrieval + generation (' + GENERATOR_MODEL + ')' if do_generate else 'retrieval only (no API cost)'}")
    print(f"  top_k : {args.top_k}")
    if query_id:
        print(f"  Eval  : {query_id} with ground truth ({len(relevant)} relevant docs)")

    collection = get_or_create_collection()
    print(f"  Index : {collection.count()} chunks loaded")

    titles = _load_titles()

    # Precompute the ontology trace once so generation can reuse it.
    reasoner = OntologyReasoner()
    ont_trace = reasoner.expand_query(query)
    ont_terms = ont_trace.get_all_terms()

    verdict: dict[str, int] = {}
    for name, fn, strategy_default in PIPELINES:
        _print_header(name)
        # Always retrieve first (generation is retried separately so a
        # transient 503/429 can never crash the live demo).
        result = fn(query, top_k=args.top_k, generate=False)
        if do_generate:
            ontology_context = ont_trace.format_for_prompt() if fn is run_ontology_enhanced else None
            result.answer = _generate_with_retry(
                question=query,
                context_chunks=result.retrieved_texts,
                ontology_context=ontology_context,
            )
        verdict[name] = _print_pipeline(name, result, titles, relevant or None,
                                        strategy_default)

    _print_header("SUMMARY - what the ontology contributed")
    print(f"  Matched concepts  : {[m['concept_id'] for m in ont_trace.matched_concepts]}")
    print(f"  Relations used    : {sorted({e['relation'] for e in ont_trace.expansions})}")
    print(f"  Expanded terms    : {ont_terms}")
    if query_id:
        print(f"\n  Verdict (relevant docs found in top-{args.top_k}):")
        for name, hits in verdict.items():
            bar = "#" * hits + "." * max(len(relevant) - hits, 0)
            print(f"    {name:30s} {bar}  {hits}/{len(relevant)}")
    else:
        print("\n  (Custom query  -  no ground-truth verdict; use an eval-set query for scoring.)")
    print("\n  Baseline searched the RAW query only.")
    print("  Dictionary added flat synonyms from a word list.")
    print("  Ontology added structurally related medical concepts (with a logged trace).")
    print("\n[OK] Demo complete.")


if __name__ == "__main__":
    main()