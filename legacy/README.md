# Legacy archive

Superseded code and data, kept for provenance and for the "problems faced"
write-up. **Nothing here is used by the final system.**

| Path | What it was |
|---|---|
| `data/corpus/real/` | A hand-collected corpus of recent PubMed abstracts used before PubMedQA was adopted |
| `scripts/eg_run_experiment.py` | Runner for the earlier gate designs (standard RAG, CRAG, score-only, gate-only, OntoGate, LLM-only) |
| `scripts/eg_calibrate.py` | Threshold calibration for the NLI-based gate |
| `scripts/report_numbers.py` | Reporting helpers for the earlier runs |
| `evidence_gate/pipeline.py` | The earlier multi-system pipeline |
| `evidence_gate/evidence_scorer.py` | PubMedBERT-MNLI cross-encoder sufficiency scorer |
| `evidence_gate/gate_policy.py` | Tau-low/tau-high decision policy with re-retrieval |

These files import modules by their historical package paths. They are not
expected to run against the current `evidence_gate/` package.

The final system is documented in [`../docs/architecture.md`](../docs/architecture.md).
