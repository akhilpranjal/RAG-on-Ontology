"""Plain-prompt RAG baseline, same model and passages as the sweep.

The sweep's always-answer arm uses the *judge* prompt, which tends to abstain;
this runner answers with the plain prompt in :meth:`GenerationClient.answer`.
Pairing it with the sweep answers the question "is the gate's gain an artefact
of a weak baseline?" under a controlled model version.

The retrieval settings (index, top-k, include-own) are identical to
``eg_run_sweep.py``, so only the generation prompt differs.

Usage
-----
    uv run python scripts/eg_run_baseline.py --split test --limit 100
    uv run python scripts/eg_paired_baseline.py --baseline results/runs/test_baseline.jsonl
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
from evidence_gate.config import GENERATOR_MODEL, INDEX_DIR, PUBMEDQA_DIR, RESULTS_DIR, ST_MODEL
from evidence_gate.evaluate import append_jsonl, load_jsonl
from evidence_gate.retriever import DenseRetriever


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="test", choices=["dev", "test"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--include-own",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include the question's own abstract in the passages (matches the sweep's final setting)",
    )
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR / "runs")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    labeled = {row["pubid"]: row for row in load_jsonl(PUBMEDQA_DIR / "labeled.jsonl")}
    splits = json.loads((PUBMEDQA_DIR / "splits.json").read_text(encoding="utf-8"))
    ids = splits[args.split]
    if args.offset:
        ids = ids[args.offset :]
    if args.limit:
        ids = ids[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.split}_baseline.jsonl"
    if args.force and out_path.exists():
        out_path.unlink()
    done = {row["pubid"] for row in load_jsonl(out_path)} if out_path.exists() else set()
    pending = [pubid for pubid in ids if pubid not in done]

    print(f"[baseline] split={args.split} total={len(ids)} done={len(done)} pending={len(pending)}")
    if not pending:
        print("[baseline] nothing to do")
        return 0

    retriever = DenseRetriever(backend="st", st_model=ST_MODEL)
    retriever.load_index(INDEX_DIR)
    generator = GenerationClient(model=args.model or GENERATOR_MODEL)

    started = time.time()
    for index, pubid in enumerate(pending, 1):
        row = labeled[pubid]
        passages = retriever.search(
            row["question"],
            top_k=args.top_k,
            exclude_ids=set() if args.include_own else {pubid},
        )
        try:
            payload = generator.answer(
                row["question"], [p.text for p in passages]
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            print(f"    [skip] {pubid}: {message[:140]}", flush=True)
            if "RESOURCE_EXHAUSTED" in message or "429" in message:
                print(
                    "[baseline] daily quota exhausted; stopping. "
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
                "answer": payload["answer"],
            },
        )
        if index % 25 == 0 or index == len(pending):
            elapsed = time.time() - started
            rate = index / max(elapsed, 1e-9)
            remaining = (len(pending) - index) / max(rate, 1e-9)
            print(
                f"    {index}/{len(pending)} api_calls={generator.n_api_calls} "
                f"eta={remaining / 60:.1f}min",
                flush=True,
            )

    if out_path.exists():
        rows = load_jsonl(out_path)
        hits = sum(1 for row in rows if row["answer"] == row["gold"])
        print(
            f"[done] wrote {out_path} ({len(rows)} rows, "
            f"accuracy {hits / max(len(rows), 1):.3f})"
        )
    else:
        print(f"[done] no rows written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
