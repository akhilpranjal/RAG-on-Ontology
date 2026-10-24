"""Run OntoGate-RAG and baselines on the dev or test split.

Runs are resumable: completed PubMed IDs are skipped, and every generation
call is cached on disk, so multi-day API-quota runs are safe.
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
from evidence_gate.config import (
    INDEX_DIR,
    METRICS_DIR,
    PUBMEDQA_DIR,
    RESULTS_DIR,
    ST_MODEL,
    TOP_K,
)
from evidence_gate.evidence_scorer import EvidenceSufficiencyScorer
from evidence_gate.evaluate import append_jsonl, load_jsonl, mcnemar_test, summarize
from evidence_gate.gate_policy import GatePolicy
from evidence_gate.llm_judge import LLMEvidenceJudge
from evidence_gate.ontology import OntologyGraph
from evidence_gate.pipeline import OntoGatePipeline
from evidence_gate.reasoner import OntologyReasoner
from evidence_gate.retriever import DenseRetriever

ALL_SYSTEMS = [
    "llm_only",
    "standard_rag",
    "crag",
    "score_only",
    "gate_only",
    "ontogate",
    "ontogate_llm_refine",
]


def load_thresholds() -> tuple[float, float]:
    from evidence_gate.config import TAU_HIGH, TAU_LOW

    print(f"[gate] using fixed judge thresholds {TAU_LOW:.2f} / {TAU_HIGH:.2f}")
    return TAU_LOW, TAU_HIGH


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="test", choices=["dev", "test"])
    parser.add_argument("--systems", nargs="+", default=ALL_SYSTEMS, choices=ALL_SYSTEMS)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR / "runs")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--include-own",
        action="store_true",
        help="Keep each question's own abstract in retrieval (leakage mode).",
    )
    args = parser.parse_args()

    labeled = {row["pubid"]: row for row in load_jsonl(PUBMEDQA_DIR / "labeled.jsonl")}
    splits = json.loads((PUBMEDQA_DIR / "splits.json").read_text(encoding="utf-8"))
    ids = splits[args.split]
    if args.limit:
        ids = ids[: args.limit]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    METRICS_DIR.mkdir(parents=True, exist_ok=True)

    tau_low, tau_high = load_thresholds()
    print(f"[gate] tau_low={tau_low} tau_high={tau_high}")

    retriever = DenseRetriever(backend="st", st_model=ST_MODEL)
    retriever.load_index(INDEX_DIR)
    reasoner = OntologyReasoner(OntologyGraph())
    generator = GenerationClient()
    pipeline = OntoGatePipeline(
        retriever=retriever,
        scorer=None,
        gate=GatePolicy(tau_high=tau_high, tau_low=tau_low),
        reasoner=reasoner,
        generator=generator,
        judge=LLMEvidenceJudge(generator),
        exclude_own=not args.include_own,
        top_k=args.top_k,
    )

    runners = {
        "llm_only": pipeline.run_llm_only,
        "standard_rag": pipeline.run_standard_rag,
        "crag": pipeline.run_crag_style,
        "score_only": pipeline.run_score_only,
        "gate_only": pipeline.run_gate_only,
        "ontogate": pipeline.run_ontogate,
        "ontogate_llm_refine": pipeline.run_ontogate_llm_refine,
    }

    summaries = {}
    for system in args.systems:
        path = args.out_dir / f"{args.split}_{system}.jsonl"
        if args.force and path.exists():
            path.unlink()
        done = {row["pubid"] for row in load_jsonl(path)} if path.exists() else set()
        pending = [pubid for pubid in ids if pubid not in done]
        print(f"[run] {system}: {len(done)} done, {len(pending)} pending -> {path}")
        for i, pubid in enumerate(pending, 1):
            row = labeled[pubid]
            try:
                result = runners[system](pubid, row["question"], row["final_decision"])
            except Exception as exc:  # noqa: BLE001
                print(f"    [skip] {pubid}: generation error: {str(exc)[:120]}", flush=True)
                continue
            append_jsonl(path, result.to_dict())
            if i % 10 == 0 or i == len(pending):
                print(
                    f"    {i}/{len(pending)}  answer={result.answer} "
                    f"gold={result.gold} s={result.sufficiency:.3f} "
                    f"decision={result.decision}",
                    flush=True,
                )
        rows = load_jsonl(path)
        summary = summarize(rows, system)
        summaries[system] = summary
        print(
            f"[done] {system}: n={summary['n']} acc={summary['accuracy']} "
            f"macroF1={summary['macro_f1']} abstain={summary['decisions'].get('ABSTAIN', 0)}"
        )

    if "standard_rag" in summaries:
        base = load_jsonl(args.out_dir / f"{args.split}_standard_rag.jsonl")
        for system, rows in [
            (name, load_jsonl(args.out_dir / f"{args.split}_{name}.jsonl"))
            for name in args.systems
            if name != "standard_rag"
        ]:
            summaries[system]["mcnemar_vs_standard_rag"] = mcnemar_test(rows, base)

    out = METRICS_DIR / f"{args.split}_summary.json"
    out.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"[write] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
