# Paper / report notes

Working notes for turning this repository into the final-year report and, if
desired, a short paper. Numbers refer to `results.md` and
`results/metrics/final_report.md`.

---

## Draft abstract

Biomedical question answering systems rarely say "I do not know". We present
OntoGate-RAG, a selective retrieval-augmented pipeline for PubMedQA that
combines an LLM evidence judge with concept coverage computed over a curated
MeSH + Hetionet knowledge graph. On a paired test set, the system raises
accuracy from 58.8% (always answer) to 78.2% at 65.2% coverage. The strongest
signal is not the judge's numeric sufficiency score but its own uncertainty: the
fitted gate reduces exactly to a deterministic rule - answer only when the judge
is fully confident (sufficiency 1) and not "maybe" - which needs no training and
gives the same result. The ontology is a weak
standalone sufficiency signal (AUC 0.49) whose document-level coverage
saturates, and ontology reranking and query expansion do not improve an already
saturated retrieval stage; however, a free ontology pre-screen removes 19.4% of
judge calls at a cost of 0.9 accuracy points. We report these negative and
cost-side results explicitly, because they delimit where a curated knowledge
graph is worth its complexity in selective RAG.

## Contributions

1. **A paired, cost-aware evaluation protocol** for selective RAG in which one
   LLM call per question is sufficient to evaluate every gate offline. All arms
   see identical questions, passages and model output.
2. **The self-abstention finding**: the judge's three-way answer is a better
   gate signal than its numeric sufficiency score (AUC 0.770 vs 0.736), and the
   dev-fitted gate collapses to a deterministic rule - answer only when the
   judge is fully confident (sufficiency 1) and not "maybe" - which gives the
   same 78.2% accuracy at 65.2% coverage with no training.
3. **A concrete negative result for ontology gating**: concept coverage
   saturates (87.1% of questions at 1.0) and is a weak gate; relation and
   heading variants are no better; fusion with the judge does not generalise.
4. **A concrete positive result for ontology screening**: the same coverage
   score, used as a free pre-filter, removes 19.4% of paid judge calls for 0.9
   accuracy points.
5. **A reproducible artefact**: 683k-triple graph built from public sources
   (no LLM), full pipeline, all prompts, and cached model responses.

## Related work map

Fill in exact citations before submission; entries marked *verify* are worth
double-checking.

* **PubMedQA** - Jin et al., EMNLP 2019. The benchmark and its three-way labels.
* **RAG** - Lewis et al., NeurIPS 2020. Retrieval-augmented generation.
* **Selective prediction** - Chow, 1970 (reject option); El-Yaniv & Wiener,
  2010 (selective classification); Geifman & El-Yaniv, 2019 (SelectiveNet).
  These motivate coverage-accuracy curves and AURC.
* **Self-reflective RAG** - Asai et al., ICLR 2024 (Self-RAG) uses reflection
  tokens including a sufficiency judgement. Our judge is in that spirit but we
  study the *abstention* channel of the judge rather than training reflection
  tokens. *verify exact venue.*
* **Corrective RAG** - Yan et al., 2024. Uses a retrieval evaluator to decide
  whether to correct retrieval. *verify.*
* **Graph-augmented RAG** - Edge et al., 2024 (GraphRAG); KAPING; G-Retriever.
  These use graphs on the retrieval/generation side; we test the graph on the
  *decision* side and report where it fails. *verify venues.*
* **Hetionet** - Himmelstein et al., eLife 2017. Source of the clinical
  relations.
* **MeSH** - U.S. National Library of Medicine. Source of the vocabulary and
  hierarchy.
* **Calibration** - Guo et al., ICML 2017. Background for why a 0/0.5/1 score
  should not be trusted as a probability.

Positioning sentence: prior work uses knowledge graphs to retrieve or to
generate; we ask whether a knowledge graph is a useful *evidence-sufficiency
signal*, and answer with a measured yes for cost and a measured no for accuracy.

## Claims to evidence

| Claim | Evidence | Where |
|---|---|---|
| Selective accuracy improves substantially | 58.8% -> 78.2% at 65.2% coverage, CI [73.6, 82.5], n = 326 answered | `final_report.md` headline |
| The judge answer beats the judge score | AUC 0.736 -> 0.770 | gate table |
| The rule matches the learned gate | 78.2% vs 78.2%, same 326 questions | gate table |
| Ontology is a weak standalone gate | AUC 0.493, coverage-only 59.0% | gate table |
| Ontology coverage saturates | 87.1% at 1.0; mean 0.916 | saturation section |
| Ontology fusion does not generalise | dev 0.769 -> test 0.738 | gate table |
| Ontology reranking has no headroom | R@10 0.970; best variant R@1 0.890 vs 0.885 | retrieval table |
| Ontology query expansion hurts | recall drop in earlier run | `docs/issues.md` #10 |
| Ontology screening saves calls | 19.4% saved, -0.9 points | cascade table |
| Gain over a stronger baseline is small | +3.1 points, p = 1.0 | paired check |
| Hard mode collapses | 0/12 answered | hard-mode note |

## Figures for the report

1. `results/plots/risk_coverage.png` - the main result: risk vs coverage for
   similarity, ontology, judge, self-abstention and fused gates.
2. `results/plots/gate_auc.png` - one bar per signal; makes the ontology's
   weakness visible at a glance.
3. `results/plots/coverage_saturation.png` - histogram concentrated at 1.0;
   explains *why* the ontology fails.
4. Architecture diagram from `docs/architecture.md` (redraw as a figure).
5. Optional: cascade bar chart (calls saved vs accuracy loss).

## Threats to validity (for the limitations section)

* Test half complete (n = 500), so headline CIs are narrow; the dev half has
  283 judged questions, which is the residual limitation.
* One LLM (`gemini-3.1-flash-lite`) and one judge prompt.
* Open-book corpus with three abstracts per question, so retrieval saturates.
* Fitted gates have 283 dev rows (of 500); dev-test gaps are reported.
* The paired baseline uses a different model version, so it is indicative.
* `maybe` is 11% of gold labels; per-class estimates are noisy.

## Future work

1. Finish the dev sweep to 500 questions (queue it after quota reset; re-run
   `eg_run_sweep.py --split dev --include-own` and refit).
2. Run the same-model plain-prompt baseline
   (`scripts/eg_run_baseline.py --split test --limit 100`) to remove the model
   confound from the paired comparison; the runner is ready and fails cleanly
   on quota.
3. Relational coverage over *claims*: extract (drug, disease) pairs from
   passages and check whether the relation asserted in the question is the one
   the passage asserts, rather than checking term co-occurrence.
4. Scope the graph to a specialty at inference time (oncology-only) and test
   whether coverage stops saturating.
5. Extend to a full PubMed-scale pool, where retrieval and coverage are not
   trivially solved and the ontology has room to matter.
6. Cost-aware learning: optimise the screen threshold directly for
   accuracy-per-call rather than accuracy at fixed coverage.

## What not to claim

* Do not claim state-of-the-art accuracy. The corpus is small and the setting is
  open-book.
* Do not claim the ontology improves accuracy. It does not, beyond noise.
* Do not claim the fused model is necessary. The rule matches it.
* Do not claim the +19-point gain over "standard RAG". It is over the same
  model's judge-prompt always-answer; the paired plain-prompt comparison is
  +3.1 points and not significant.
* Do not compare the 96-row pilot (AUC 0.823) with the final run as if they were
  the same experiment; the judge model changed.
