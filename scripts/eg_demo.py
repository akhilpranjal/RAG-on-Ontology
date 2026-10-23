"""Interactive demo of one OntoGate-RAG query, end to end.

Shows exactly what the final system does:

1. dense retrieval over the PubMedQA corpus,
2. MeSH + Hetionet ontology linking of the question,
3. concept coverage of the retrieved passages (free, local),
4. one LLM judge call (sufficiency + answer),
5. the gate decision: the coverage screen, the judge's own "maybe"
   abstention, and the dev-fitted fused score,
6. the final answer or an explicit abstention.

Examples
--------
    uv run python scripts/eg_demo.py --split test
    uv run python scripts/eg_demo.py --question "Does metformin help Alzheimer's?"
    uv run python scripts/eg_demo.py --split dev --no-generate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_gate.api import GenerationClient
from evidence_gate.config import INDEX_DIR, METRICS_DIR, PUBMEDQA_DIR, ST_MODEL, TOP_K
from evidence_gate.coverage import ConceptCoverageScorer, FOCUS_KINDS
from evidence_gate.evaluate import load_jsonl
from evidence_gate.llm_judge import LLMEvidenceJudge
from evidence_gate.ontology import OntologyGraph
from evidence_gate.retriever import DenseRetriever
from evidence_gate.selective import LogisticSelector

ASCII_MAP = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u2192": "->",
    "\u2265": ">=",
    "\u2264": "<=",
    "\u00b5": "u",
    "\u00d7": "x",
}


def safe(text: str) -> str:
    for src, dst in ASCII_MAP.items():
        text = text.replace(src, dst)
    return text.encode("ascii", "replace").decode("ascii")


def separator(title: str) -> None:
    print("\n" + "-" * 78)
    print(title)
    print("-" * 78)


def load_primary_selector() -> tuple[LogisticSelector | None, float]:
    """Load the dev-fitted fused gate and its 60%-coverage threshold."""
    path = METRICS_DIR / "final_report.json"
    if not path.exists():
        return None, 0.5
    report = json.loads(path.read_text(encoding="utf-8"))
    payload = report.get("selectors", {}).get("fused_judge_maybe")
    tau = (
        report.get("gates", {})
        .get("fused_judge_maybe", {})
        .get("coverage_targets", {})
        .get("0.6", {})
        .get("tau")
    )
    if not payload or tau is None:
        return None, 0.5
    return LogisticSelector.from_dict(payload), float(tau)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pubid", default=None)
    parser.add_argument("--question", default=None)
    parser.add_argument("--split", default="test", choices=["dev", "test"])
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--include-own", action="store_true", default=True)
    parser.add_argument("--exclude-own", action="store_true")
    parser.add_argument("--no-generate", action="store_true")
    parser.add_argument("--screen", type=float, default=0.5,
                        help="abstain without a judge call when coverage <= this")
    args = parser.parse_args()

    labeled = {row["pubid"]: row for row in load_jsonl(PUBMEDQA_DIR / "labeled.jsonl")}
    if args.question:
        pubid, question, gold = "", args.question, None
    else:
        if args.pubid is None:
            splits = json.loads((PUBMEDQA_DIR / "splits.json").read_text(encoding="utf-8"))
            pubid = splits[args.split][0]
        else:
            pubid = args.pubid
        row = labeled[pubid]
        question, gold = row["question"], row["final_decision"]

    print("=" * 78)
    print("QUESTION:", safe(question))
    if gold:
        print("GOLD    :", gold)
    if pubid:
        print("PUBID   :", pubid)
    print("=" * 78)

    # -- 1. retrieval ---------------------------------------------------
    retriever = DenseRetriever(backend="st", st_model=ST_MODEL)
    retriever.load_index(INDEX_DIR)
    exclude = {pubid} if (args.exclude_own and pubid) else None
    passages = retriever.search(question, top_k=args.top_k, exclude_ids=exclude)

    separator("[1] DENSE RETRIEVAL")
    own = [p for p in passages if p.id == pubid]
    print(f"{len(passages)} passages; best similarity={passages[0].score:.3f}")
    print(f"source abstract retrieved: {'yes' if own else 'no'}")
    for i, passage in enumerate(passages[:5], 1):
        print(f"  {i}. sim={passage.score:.3f}  id={passage.id}")
        print("     " + safe(passage.text[:160]).replace("\n", " "))

    # -- 2. ontology linking --------------------------------------------
    graph = OntologyGraph()
    scorer = ConceptCoverageScorer(graph=graph)
    concepts = scorer.question_concepts(question)
    separator("[2] ONTOLOGY LINKING (MeSH 2026 + Hetionet)")
    if not concepts:
        print("no question concept linked to the graph")
    for i, entity in enumerate(concepts, 1):
        marker = "*" if entity.kind in FOCUS_KINDS else " "
        print(f"  {i}. [{entity.kind:10s}] {safe(entity.label)[:60]}{marker}")

    coverage = scorer.score(question, passages)
    separator("[3] CONCEPT COVERAGE (free, no API)")

    def show(value) -> str:
        return "n/a" if value != value else f"{value:.3f}"

    print(f"linked concepts        : {coverage.n_concepts}")
    print(f"coverage (all passages): {show(coverage.coverage)}")
    print(f"coverage (top-3)       : {show(coverage.coverage_top3)}")
    print(f"idf-weighted           : {show(coverage.coverage_weighted)}")
    print(f"relation coverage      : {show(coverage.relation_coverage)}  "
          f"(intent: {coverage.intent})")

    # -- 3. gate: coverage screen ---------------------------------------
    separator("[4] GATE STAGE 1 - ONTOLOGY SCREEN")
    screened_out = coverage.coverage_top3 <= args.screen and coverage.n_concepts > 0
    if screened_out:
        print(f"coverage {coverage.coverage_top3:.3f} <= {args.screen:.2f} "
              "-> ABSTAIN without calling the judge (API call saved)")
        print("\nFINAL: maybe (abstained; no ontology-grounding evidence)")
        return 0
    print(f"coverage {coverage.coverage_top3:.3f} > {args.screen:.2f} -> pass to the judge")

    if args.no_generate:
        print("\n(generation skipped)")
        return 0

    # -- 4. LLM judge ---------------------------------------------------
    generator = GenerationClient()
    judge = LLMEvidenceJudge(generator)
    result = judge.judge(question, [p.text for p in passages])

    separator("[5] GATE STAGE 2 - LLM EVIDENCE JUDGE")
    print(f"sufficient : {result.sufficient}")
    print(f"answer     : {result.answer}")
    print(f"score      : {result.sufficiency_score:.2f}")

    # -- 5. fused decision ----------------------------------------------
    selector, tau = load_primary_selector()
    fused = None
    if selector is not None:
        features = {
            "llm_judge": result.sufficiency_score,
            "judge_answer_maybe": 1.0 if result.answer == "maybe" else 0.0,
        }
        matrix = [[features[name] for name in selector.feature_names]]
        fused = float(selector.predict_proba(matrix)[0])

    separator("[6] GATE STAGE 3 - DECISION")
    if result.answer == "maybe":
        print("judge answered 'maybe' -> self-abstention")
        decision = "maybe"
    elif fused is not None and fused + 1e-6 < tau:
        print(f"fused gate score {fused:.3f} < dev threshold {tau:.3f} -> ABSTAIN")
        decision = "maybe"
    else:
        if fused is not None:
            print(f"fused gate score {fused:.3f} >= dev threshold {tau:.3f} -> ANSWER")
        else:
            print("no fitted selector found; using the judge's own answer")
        decision = result.answer

    print(f"\nFINAL: {decision}")
    if gold:
        print(f"GOLD : {gold}")
        print("MATCH" if decision == gold else "MISMATCH")
    print(f"API calls this session: {generator.n_api_calls}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
