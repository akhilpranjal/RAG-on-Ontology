"""Ontology-guided reranking evaluated with retrieval metrics (no API calls).

The graph's first role in this project was query expansion, which hurt. This
script tests a different retrieval-side role that needs no model calls: keep the
dense candidate list, then rerank it by how well each passage covers the
question's ontology-linked concepts.

Metrics are computed against the source abstract of each question (the abstract
that answers it). Because the corpus contains the source abstract, this is the
standard PubMedQA open-book setting; ``--exclude-own`` switches to the hard mode
where the source abstract is removed from the candidate pool.

Outputs ``results/metrics/retrieval_{split}.json``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_gate.config import (
    INDEX_DIR,
    METRICS_DIR,
    PUBMEDQA_DIR,
    ST_MODEL,
)
from evidence_gate.coverage import ConceptCoverageScorer
from evidence_gate.evaluate import load_jsonl
from evidence_gate.ontology import OntologyGraph
from evidence_gate.retriever import DenseRetriever


def rank_of_gold(passages, gold_id: str) -> int:
    for rank, passage in enumerate(passages, start=1):
        if passage.id == gold_id:
            return rank
    return 0


def summarize_ranks(ranks: list[int], ks=(1, 3, 5, 10)) -> dict:
    n = len(ranks)
    out = {}
    for k in ks:
        out[f"recall@{k}"] = round(sum(1 for r in ranks if 0 < r <= k) / n, 4)
    out["mrr"] = round(sum(1.0 / r for r in ranks if r > 0) / n, 4)
    out["mrr@10"] = round(sum((1.0 / r) if 0 < r <= 10 else 0.0 for r in ranks) / n, 4)
    out["found_rate"] = round(sum(1 for r in ranks if r > 0) / n, 4)
    out["rank_hist"] = dict(sorted(Counter(ranks).items()))
    return out


def rerank(passages, weights: list[float], blend: float):
    scored = []
    max_sim = max(p.score for p in passages) or 1.0
    for passage, weight in zip(passages, weights):
        sim = passage.score / max_sim if max_sim else 0.0
        scored.append((blend * sim + (1.0 - blend) * weight, passage))
    scored.sort(key=lambda item: -item[0])
    return [passage for _, passage in scored]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--exclude-own", action="store_true")
    parser.add_argument(
        "--variants",
        nargs="+",
        default=["coverage", "coverage_weighted", "coverage_top3"],
    )
    args = parser.parse_args()

    labeled = {row["pubid"]: row for row in load_jsonl(PUBMEDQA_DIR / "labeled.jsonl")}
    splits = json.loads((PUBMEDQA_DIR / "splits.json").read_text(encoding="utf-8"))
    ids = splits[args.split]
    if args.limit:
        ids = ids[: args.limit]

    retriever = DenseRetriever(backend="st", st_model=ST_MODEL)
    retriever.load_index(INDEX_DIR)
    coverage = ConceptCoverageScorer(graph=OntologyGraph())

    result = {
        "split": args.split,
        "n": len(ids),
        "top_k": args.top_k,
        "exclude_own": args.exclude_own,
        "retriever": ST_MODEL,
        "variants": {},
    }
    base_ranks = []
    per_variant = {name: [] for name in args.variants}
    started = time.time()

    for index, pubid in enumerate(ids, 1):
        question = labeled[pubid]["question"]
        passages = retriever.search(
            question,
            top_k=args.top_k,
            exclude_ids={pubid} if args.exclude_own else set(),
        )
        base_ranks.append(rank_of_gold(passages, pubid))
        coverage_result = coverage.score(question, passages)
        weights = {
            "coverage": coverage_result.coverage,
            "coverage_weighted": coverage_result.coverage_weighted,
            "coverage_top3": coverage_result.coverage_top3,
            "heading_coverage": coverage_result.heading_coverage,
        }
        # Per-passage scores: reuse the document-level scorer on each passage.
        per_passage = []
        for passage in passages:
            single = coverage.score(question, [passage])
            per_passage.append(
                {
                    "coverage": single.coverage,
                    "coverage_weighted": single.coverage_weighted,
                    "coverage_top3": single.coverage,
                    "heading_coverage": single.heading_coverage,
                }
            )
        for name in args.variants:
            if name == "dense":
                continue
            weights_vector = [item[name] for item in per_passage]
            for blend in (0.0, 0.25, 0.5, 0.75, 1.0):
                key = f"{name}_blend{blend:g}"
                if key not in per_variant:
                    per_variant[key] = []
                ranked = rerank(passages, weights_vector, blend)
                per_variant[key].append(rank_of_gold(ranked, pubid))
        if index % 50 == 0 or index == len(ids):
            print(f"    {index}/{len(ids)} ({time.time() - started:.0f}s)", flush=True)

    result["variants"]["dense"] = summarize_ranks(base_ranks)
    for key, ranks in per_variant.items():
        if ranks:
            result["variants"][key] = summarize_ranks(ranks)

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "hard" if args.exclude_own else "open"
    out_path = METRICS_DIR / f"retrieval_{args.split}_{suffix}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"\n[retrieval] {args.split} n={len(ids)} exclude_own={args.exclude_own}")
    for name, summary in result["variants"].items():
        print(
            f"  {name:28s} R@1={summary['recall@1']:.3f} R@3={summary['recall@3']:.3f} "
            f"R@10={summary['recall@10']:.3f} MRR={summary['mrr']:.3f}"
        )
    print(f"[write] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
