# Experiments

## Research questions

**RQ1.** Can an LLM sufficiency judge plus an ontology coverage score support a
selective answering policy that is substantially more accurate than always
answering, at a useful coverage?

**RQ2.** Does the ontology add information *beyond* the judge, as
(a) a standalone gate, (b) a component of a fused gate, or (c) a retrieval
component (query expansion / reranking)?

**RQ3.** What does the ontology buy at the system level, in API calls saved?

## Protocol

* **Splits.** Fixed 500/500 dev/test from `splits.json` (seed 42).
* **Dev is for fitting only.** Every threshold, every logistic weight, and
  every screen value is fitted on dev. Test is touched once per arm to produce
  the final number. Thresholds are transferred by *matched coverage*: the dev
  threshold that achieves a coverage target is applied unchanged to test.
* **Paired design.** One judge call per question produces every signal, so all
  arms see identical questions, passages and model output.
* **Abstention is never correct.** Accuracy is computed over answered
  questions. `accuracy_as_maybe` is reported separately for continuity.
* **Coverage targets** for the gate sweep: 100%, 80%, 70%, 60%, 50%, 40%, 30%.
* **Uncertainty.** Selective accuracy carries a 95% bootstrap CI
  (`bootstrap_selective_ci`, 1,000 resamples).

## Arms

All arms are reconstructed offline from the same sweep rows.

| Arm | Signal | Fitted? |
|---|---|---|
| `similarity` | Top-1 dense retrieval similarity | No |
| `ontology_coverage` | Concept coverage of the top-3 passages | No |
| `ontology_coverage_doc` | Concept coverage of all ten passages | No |
| `ontology_relation` | Intent-conditioned sentence relation coverage | No |
| `ontology_heading` | Coverage of curated MeSH headings | No |
| `llm_judge` | Judge sufficiency score (0 / 0.5 / 1) | No |
| `judge_self_abstain` | 0 if the judge answered "maybe", else 0.5 + 0.5 x score | No |
| `judge_confident` | 1 only if score = 1 and answer != maybe; the learned gate's exact simplification | No |
| `fused_judge_maybe` | Logistic regression on {judge score, is-maybe} | Dev |
| `fused_judge_maybe_coverage` | Above plus ontology coverage | Dev |
| `fused_all` | Above plus inconsistency flag, similarity, concept count | Dev |
| `always_answer` | Judge's answer, never abstain | No |

`fused_all` was fixed before the test numbers were inspected; it is reported
with its dev AUC so that overfitting is visible (dev 0.834, test 0.772).

## Cascade

A separate system-level experiment asks whether the ontology can pay for itself
in *calls*. Rule:

```
if coverage_top3 <= a:  abstain without calling the judge
elif judge says "maybe": abstain
else: answer
```

`a` is swept over {0, 0.25, 0.5, 0.75, 0.99, 1.0} and both dev and test numbers
are reported. This is the only place where the ontology produces a positive,
quantified result.

## Retrieval experiments (zero API)

`scripts/eg_eval_retrieval.py` compares dense retrieval with ontology reranking:

* blend the normalized dense score with concept coverage,
* variants for document-level, top-3 and IDF-weighted coverage,
* blend weights 0.0 / 0.25 / 0.5 / 0.75 / 1.0.

Metrics: recall@1/3/5/10, MRR, and the rank histogram of the gold abstract.
Output: `results/metrics/retrieval_dev_open.json`.

Ontology **query expansion** was tested earlier in the project (expanding the
query with one-hop neighbours from the graph). It consistently reduced recall
and was dropped. The expansion code remains in `reasoner.py` for the negative
result and for the demo's intent detection.

## Reproducing everything

```powershell
# 1. data (downloads PubMedQA, ~1 min)
uv run python scripts/eg_prepare_data.py

# 2. ontology (downloads MeSH XML ~300 MB and Hetionet, then builds the graph)
uv run python scripts/eg_build_ontology.py

# 3. retrieval index (embeds 3,000 abstracts)
uv run python scripts/eg_build_index.py

# 4. specialty tags and the passage concept index
uv run python -m evidence_gate.specialty
uv run python -c "from evidence_gate.coverage import build_passage_concepts; build_passage_concepts()"

# 5. the sweep: ONE judge call per question, resumable
uv run python scripts/eg_run_sweep.py --split dev  --include-own
uv run python scripts/eg_run_sweep.py --split test --include-own

# 6. retrieval evaluation (no API)
uv run python scripts/eg_eval_retrieval.py --split dev --limit 200

# 7. final report, tables and plots (no API)
uv run python scripts/eg_analyze.py

# 8. paired baseline comparison (no API)
uv run python scripts/eg_paired_baseline.py

# 9. one-question demo
uv run python scripts/eg_demo.py --split test
```

Steps 5 uses the API. Everything else is deterministic and free. Use
`--limit N` to cap the number of judged questions and `--force` to ignore
existing rows.

## Sample sizes actually collected

| Split | Questions judged | Notes |
|---|---|---|
| Test | 500 | complete test half |
| Dev | 283 | resumes on the next quota reset; fitting always refits on the full file |
| Hard mode (dev, exclude-own) | 12 | negative result |

The free tier for `gemini-3.1-flash-lite` allows roughly 200 requests per day.
The model in `config.py` is the one that was actually available; earlier
versions of this project used `gemini-3.5-flash-lite`, whose numbers are kept
for comparison in `results.md`.

## What is frozen and what is not

Frozen: splits, corpus, ontology, retrieval index, all fitted thresholds and
weights, and the analysis code.

Not frozen: the number of judged questions. Extending the sweep only adds rows;
it does not change any fitted parameter, because the analysis always refits on
the full dev file.
