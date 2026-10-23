"""One-call-per-question sweep that powers every gate comparison.

Design goal: the API budget buys exactly one LLM judge call per question. From
that single call plus purely local signals (ontology coverage, retrieval
similarity) the analysis derives every system, so all gates are evaluated on
*identical* questions, passages and answers -- a fully paired comparison.

For each question the sweep stores:

* ``passages``         retrieval output (ids, scores, truncated text)
* ``judge``            the LLM evidence judge: sufficiency label + answer
* ``coverage``         ontology concept coverage of the retrieved set
* ``similarity``       top-1 / mean / spread of the retriever scores
* ``specialty``        MeSH tree-based tag, analysis only

Runs are resumable: any question already in the output file is skipped, and
every API response is cached on disk, so the sweep can be spread across days.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_gate.api import GenerationClient
from evidence_gate.config import (
    INDEX_DIR,
    PUBMEDQA_DIR,
    RESULTS_DIR,
    SPECIALTY_PATH,
    ST_MODEL,
    TOP_K,
)
from evidence_gate.coverage import ConceptCoverageScorer, build_passage_concepts
from evidence_gate.evaluate import append_jsonl, load_jsonl
from evidence_gate.llm_judge import LLMEvidenceJudge
from evidence_gate.ontology import OntologyGraph
from evidence_gate.retriever import DenseRetriever

TEXT_PREVIEW = 400


def load_specialties() -> dict:
    path = Path(SPECIALTY_PATH)
    if not path.exists():
        from evidence_gate.specialty import build_specialties

        return build_specialties()
    return json.loads(path.read_text(encoding="utf-8"))


def similarity_features(passages) -> dict:
    scores = [float(p.score) for p in passages]
    if not scores:
        return {"top1": None, "mean_topk": None, "spread": None, "n_passages": 0}
    top1 = scores[0]
    mean = sum(scores) / len(scores)
    spread = top1 - scores[-1] if len(scores) > 1 else 0.0
    return {
        "top1": round(top1, 4),
        "mean_topk": round(mean, 4),
        "spread": round(spread, 4),
        "n_passages": len(scores),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    parser.add_argument(
        "--model",
        default=None,
        help="Override the generation model (defaults to GENERATOR_MODEL).",
    )
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR / "runs")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--include-own",
        action="store_true",
        help="Keep each question's own abstract retrievable (leakage mode).",
    )
    args = parser.parse_args()

    labeled = {row["pubid"]: row for row in load_jsonl(PUBMEDQA_DIR / "labeled.jsonl")}
    splits = json.loads((PUBMEDQA_DIR / "splits.json").read_text(encoding="utf-8"))
    ids = splits[args.split]
    if args.offset:
        ids = ids[args.offset :]
    if args.limit:
        ids = ids[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.split}_sweep.jsonl"
    if args.force and out_path.exists():
        out_path.unlink()
    done = {row["pubid"] for row in load_jsonl(out_path)} if out_path.exists() else set()
    pending = [pubid for pubid in ids if pubid not in done]

    print(f"[sweep] split={args.split} total={len(ids)} done={len(done)} pending={len(pending)}")
    if not pending:
        print("[sweep] nothing to do")
        return 0

    graph = OntologyGraph()
    if not Path(PUBMEDQA_DIR / "corpus.jsonl").exists():
        raise SystemExit("corpus.jsonl missing; run scripts/eg_prepare_data.py first")
    from evidence_gate.config import PASSAGE_CONCEPTS_PATH

    if not Path(PASSAGE_CONCEPTS_PATH).exists():
        print("[sweep] building passage concept index (one-off, local) ...")
        build_passage_concepts(graph=graph)
    coverage = ConceptCoverageScorer(graph=graph)
    specialties = load_specialties()

    retriever = DenseRetriever(backend="st", st_model=ST_MODEL)
    retriever.load_index(INDEX_DIR)
    from evidence_gate.config import GENERATOR_MODEL

    generator = GenerationClient(model=args.model or GENERATOR_MODEL)
    judge = LLMEvidenceJudge(generator)

    started = time.time()
    for index, pubid in enumerate(pending, 1):
        row = labeled[pubid]
        try:
            passages = retriever.search(
                row["question"],
                top_k=args.top_k,
                exclude_ids=set() if args.include_own else {pubid},
            )
            judgement = judge.judge(row["question"], [p.text for p in passages])
            coverage_result = coverage.score(row["question"], passages)
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            print(f"    [skip] {pubid}: {message[:140]}", flush=True)
            if "RESOURCE_EXHAUSTED" in message or "429" in message:
                print(
                    "[sweep] daily quota exhausted; stopping. "
                    "Re-run the same command after the quota resets.",
                    flush=True,
                )
                break
            continue

        append_jsonl(
            out_path,
            {
                "pubid": pubid,
                "question": row["question"],
                "gold": row["final_decision"],
                "specialty": specialties.get(pubid, {}),
                "judge": judgement.to_dict(),
                "coverage": coverage_result.to_dict(),
                "similarity": similarity_features(passages),
                "passages": [
                    {
                        "id": p.id,
                        "score": round(float(p.score), 4),
                        "text": p.text[:TEXT_PREVIEW],
                    }
                    for p in passages
                ],
            },
        )
        if index % 10 == 0 or index == len(pending):
            elapsed = time.time() - started
            rate = index / max(elapsed, 1e-9)
            remaining = (len(pending) - index) / max(rate, 1e-9)
            print(
                f"    {index}/{len(pending)} api_calls={generator.n_api_calls} "
                f"sufficient={judgement.sufficient} cov={coverage_result.coverage:.2f} "
                f"eta={remaining / 60:.1f}min",
                flush=True,
            )

    print(
        f"[done] wrote {out_path} "
        f"({len(load_jsonl(out_path))} rows, {generator.n_api_calls} new API calls)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
