# Results

All numbers are on the test split unless marked dev. Test n = 85.
`results/metrics/final_report.md` is the generated source of truth; this page
adds interpretation and the checks that the generator does not perform.

## Headline

| System | Coverage | Selective accuracy |
|---|---|---|
| Always answer (judge prompt, same model) | 100% | 58.8% |
| Always answer, forced (maybe -> yes) | 100% | 62.4% |
| Ontology coverage only, dev threshold at 70% coverage | 70.6% | 63.3% |
| **Fused gate (judge + self-abstention)** | **61.2%** | **76.9%** |
| 95% bootstrap CI on the fused gate | | [65.4%, 88.5%] |

The gate is a 1.8x improvement in accuracy over always answering, at the price
of declining to answer 39% of the questions. Abstentions are never counted as
correct.

## Baselines

| Split | Always answer | Forced answer | Abstain = maybe | Majority class |
|---|---|---|---|---|
| Dev (n=200) | 0.600 | 0.675 | 0.060 | 0.560 |
| Test (n=85) | 0.588 | 0.624 | 0.094 | 0.553 |

"Abstain = maybe" counts an abstention as the gold `maybe` class. It is not a
real accuracy; it is reported only so that the earlier experiment, which used
this convention, remains comparable.

## Gate quality

AUC against per-question correctness, dev and test.

| Gate | Dev AUC | Test AUC | Test AURC |
|---|---|---|---|
| similarity (top-1 dense score) | 0.561 | 0.552 | 0.353 |
| ontology coverage (top-3) | 0.530 | 0.547 | 0.406 |
| ontology coverage (all 10) | 0.519 | 0.495 | 0.421 |
| ontology relation (sentence) | 0.506 | **0.442** | 0.469 |
| ontology heading coverage | 0.528 | 0.514 | 0.385 |
| **LLM judge score** | **0.700** | **0.705** | 0.328 |
| **Judge + self-abstention (rule)** | **0.757** | **0.737** | 0.260 |
| Fused judge + is-maybe (learned) | 0.758 | 0.747 | 0.254 |
| Fused + ontology coverage | 0.769 | 0.738 | 0.271 |
| Fused all features | 0.776 | 0.704 | 0.349 |

Reading:

* Everything ontology-only is between 0.44 and 0.55. The relation gate is
  *below chance* on test, which means the intent-conditioned relation feature is
  noise at this sample size, not a weak signal.
* The judge's score alone is 0.705. Adding a single binary feature, "did the
  judge answer maybe", lifts it to 0.747. This is the most important result in
  the project and it costs nothing.
* Adding ontology coverage to the learned gate raises dev AUC (0.758 -> 0.769)
  but lowers test AUC (0.747 -> 0.738). That is the signature of fitting noise.
  The ontology does not add information beyond the judge.
* `fused_all` looks best on dev (0.776) and drops to 0.704 on test, the worst
  generalisation of the learned gates. It is reported to make overfitting
  visible, not as a recommendation.

## Selective accuracy at matched coverage (test)

Cells are `accuracy@coverage`. Dev chooses the threshold; test applies it.

| Gate | 100% | 80% | 70% | 60% | 50% | 40% | 30% |
|---|---|---|---|---|---|---|---|
| similarity | .583@99 | .612@79 | .623@72 | .612@58 | .579@45 | .621@34 | .667@32 |
| ontology coverage | .613@94 | .645@73 | .633@71 | .633@71 | .633@71 | .633@71 | .633@71 |
| ontology coverage (all) | .613@94 | .606@78 | .606@78 | .606@78 | .606@78 | .606@78 | .606@78 |
| ontology relation | .561@48 | .561@48 | .561@48 | .561@48 | .561@48 | .561@48 | .474@22 |
| ontology heading | .613@94 | .613@94 | .610@69 | .611@64 | .649@44 | .639@42 | .639@42 |
| judge score | .588@100 | .653@85 | .729@69 | .729@69 | .729@69 | .729@69 | .729@69 |
| **judge self-abstain** | .588@100 | .588@100 | .588@100 | **.769@61** | .769@61 | .769@61 | .769@61 |
| fused judge+maybe | .588@100 | .640@88 | .714@74 | **.769@61** | .769@61 | .769@61 | .769@61 |
| fused + coverage | .588@100 | .662@84 | .714@74 | .766@55 | .756@48 | .756@48 | .756@48 |
| fused all | .588@100 | .697@78 | .737@67 | .775@58 | .775@47 | .750@42 | .692@31 |

The ontology coverage gate is flat from 71% coverage downward because its
feature is ternary in practice: coverage is 0, 0.5 or 1 for most questions, so
a single threshold splits the data into the same two groups at every target.
That is the saturation problem, seen from the other side.

## Where the ontology does pay: the cascade

Rule: abstain without calling the judge when `coverage_top3 <= a`; otherwise
ask the judge; abstain if the judge says "maybe".

| Screen `a` | Judge calls saved | Coverage | Selective accuracy |
|---|---|---|---|
| 0.00 | 5.9% | 63.5% | 0.759 |
| 0.50 | 15.3% | 58.8% | 0.760 |
| 0.75 | **23.5%** | 51.8% | 0.750 |
| 1.00 | 94.1% | 2.4% | 0.500 |

At `a = 0.75` the ontology removes almost one judge call in four and costs
1.9 accuracy points (75.9% -> 75.0% at the `a = 0` setting, or 76.9% -> 75.0%
against the no-screen headline). This is the positive, quantified role of the
ontology in the final system: **a free cost filter**, not an accuracy signal.
Dev and test both show the saving (dev 19.5%, test 23.5%), so it is not a
one-split artefact.

## Retrieval

Dev, 200 questions, no API calls (`results/metrics/retrieval_dev_open.json`).

| Variant | R@1 | R@3 | R@10 | MRR |
|---|---|---|---|---|
| Dense | 0.885 | 0.940 | 0.970 | 0.916 |
| Best ontology-blended rerank | 0.890 | 0.945 | 0.970 | 0.921 |

The best blend changes one question's rank@1. There is no headroom: the gold
abstract is already in the top-10 for 97% of questions. Ontology reranking
cannot matter when retrieval is solved at this scale. Ontology query expansion
was tested earlier and *reduced* recall, because synonyms pulled in unrelated
abstracts that shared the same MeSH term.

## Coverage saturation

* Mean document-level coverage: 0.916.
* Share of questions with coverage exactly 1.0: 82.5%.
* Mean number of linked question concepts: 1.72.

Most PubMedQA questions name one or two concepts, and a ten-abstract context
almost always mentions them. A gate that asks "are the question's terms
present?" therefore has almost no variance to work with. This explains both the
weak AUC and the flat risk-coverage curve. Any future coverage signal needs to
be relational or hierarchical, not lexical presence.

## Error analysis (test)

Judge answers against gold labels:

| Judge answer | n | Gold yes | Gold no | Gold maybe | Answer accuracy |
|---|---|---|---|---|---|
| yes | 40 | 33 | 2 | 5 | **0.825** |
| no | 16 | 3 | 9 | 4 | 0.562 |
| maybe | 29 | 11 | 10 | 8 | 0.276 |

Three things follow.

1. **The judge is asymmetric.** It is good at confirming a positive claim
   (82.5%) and weak at confirming a negative one (56.2%). A `no` answer is
   barely better than a coin flip on this sample. Any future work should
   calibrate the two answer classes separately instead of thresholding a single
   score.
2. **"Maybe" really is uncertainty.** Only 27.6% of "maybe" answers are right,
   so abstaining on them is correct about 72% of the time. The gold labels of
   those 29 questions are balanced (11 yes, 10 no, 8 maybe), which means the
   judge is not simply detecting the gold `maybe` class: it is flagging hard
   questions of all three classes. That is the behaviour a selective system
   should have.
3. **The score adds a little on top of the answer.** Judge sufficiency
   `yes` -> 72.9% answer accuracy (n=59), `partial` -> 30.8% (n=13), `no` ->
   23.1% (n=13). The three-way sufficiency label is monotone with correctness,
   which is why the thresholded self-abstention score (0.769) is slightly above
   the plain rule "answer every non-maybe" (42/56 = 75.0% at 65.9% coverage).

Screened versus passed questions (`coverage_top3 <= 0.75`):

| Group | n | Judge accuracy | Judge "maybe" rate |
|---|---|---|---|
| Screened out | 20 | 0.550 | 0.40 |
| Passed to judge | 65 | 0.600 | 0.32 |

The screen removes questions that are only slightly harder than average. That
is exactly why it saves 23.5% of calls for a 1.9-point accuracy cost: it is a
cheap, mildly informative filter, not a sharp classifier.

### Class-aware gates overfit

The asymmetry suggests giving the two answer classes separate weights. A
one-hot logistic gate on {is_yes, is_no, is_maybe, score} raises dev AUC to
0.766 but drops test AUC to 0.684. Adding ontology coverage and similarity
raises dev further (0.778) and leaves test at 0.697. With 200 dev rows and a
40-question `yes` class, class-specific weights are fitting noise. The
two-feature gate is kept, and class-conditional calibration is listed as future
work rather than claimed as a result.

## Per-specialty (test)

Judge gate, threshold chosen on dev for 50% coverage.

| MeSH | n | Always | Coverage | Selective |
|---|---|---|---|---|
| C04 Neoplasms | 22 | 0.591 | 0.50 | 0.727 |
| C14 Cardiovascular Diseases | 10 | 0.600 | 0.70 | 0.857 |
| C10 Nervous System Diseases | 6 | 0.333 | 0.67 | 0.500 |
| C01 Infections | 6 | 0.667 | 0.33 | 1.000 |

Only four categories reach n = 6 in the 85-question test set, so these rows are
illustrative. The oncology row is the only one with enough data to be
moderately stable, and it behaves like the overall result (+13.6 points). The
specialty analysis is therefore reported but not used to claim domain-specific
behaviour.

## Paired check against a stronger baseline

The sweep's always-answer baseline uses the *judge* prompt, which abstains
often and answers less accurately than a plain answer prompt. On the 50 test
questions that also have an earlier plain-prompt run:

| Metric | Value |
|---|---|
| Shared questions | 50 |
| Answered by the gate | 32 (64%) |
| Plain-prompt RAG, all 50 | 66.0% |
| Plain-prompt RAG, on the 32 answered | 71.9% |
| Gate, on the same 32 | 75.0% |
| Difference | +3.1 points |
| McNemar (discordant 0 vs 1) | p = 1.0 |

Conclusion: against a *stronger* answerer, the gate's gain at matched coverage
is small and not significant. Its reliable contribution is **selective
abstention itself** (you get an explicit "I do not know" for 36% of questions)
plus the cheap screen. The +18.1 headline is honest but it is measured against
the judge prompt; both numbers are reported so the claim can be audited.

Caveat: the plain-prompt run used `gemini-3.5-flash-lite` and the sweep used
`gemini-3.1-flash-lite`, so this is indicative, not a controlled ablation.
A same-model plain-prompt arm is the single most important missing experiment.

## Judge model matters

| Model | Rows | Judge AUC | Gate |
|---|---|---|---|
| `gemini-3.5-flash-lite` (pilot, 96 rows) | 96 | 0.823 | 0.80 @ 52% coverage |
| `gemini-3.1-flash-lite` (final) | 285 | 0.70-0.74 | 0.769 @ 61% coverage |

`3.5-flash-lite` was retired or quota-locked during the project, and its
replacement is a weaker judge. The system design is unchanged; the absolute
numbers are model-dependent. Reporting both prevents the pilot from looking
like the final result.

## Hard mode (exclude-own)

Twelve dev questions retrieved with the source abstract removed. The judge
declared the evidence insufficient in all twelve cases and the system abstained
on all twelve. Accuracy 0.0. The retrieved distractors are topically related
but do not contain the study that answers the question. This is recorded as a
negative result: the pipeline is not a closed-book QA system.

## Threats to validity

1. **Test n = 85.** The 95% CI on the headline is wide ([65.4%, 88.5%]). The
   run is resumable; extending it to 500 is the first thing to do when quota
   resets.
2. **One model, one prompt.** Every judge-based number is conditional on
   `gemini-3.1-flash-lite` and the judge prompt.
3. **The corpus is small and easy.** Retrieval saturation means the
   retrieval-side conclusions may not transfer to a full PubMed index.
4. **The fusion is fitted on 200 rows.** Dev-test AUC gaps of 0.05-0.07 show
   this is at the edge of what 200 rows can support. The two-parameter fused
   gate is the only one that generalises cleanly (0.758 -> 0.747).
5. **Selection.** The 60% coverage target was fixed before test evaluation, and
   the report shows all targets rather than the best one.
