# Results

Test numbers are on the **complete test split (n = 500)** unless marked dev.
Gates are fitted on dev (n = 283 judged questions).
`results/metrics/final_report.md` is the generated source of truth; this page
adds interpretation and the checks the generator does not perform.

## Headline

| System | Coverage | Selective accuracy |
|---|---|---|
| Always answer (judge prompt, same model) | 100% | 58.8% |
| Always answer, forced (maybe -> yes) | 100% | 67.4% |
| Majority class (always yes) | 100% | 55.3% |
| Ontology coverage only, dev threshold | 77% | 59.0% |
| **Fused gate (judge + self-abstention)** | **65.2%** | **78.2%** |
| 95% bootstrap CI on the fused gate | | [73.6%, 82.5%] |

The dev-fitted threshold lands exactly at the top score level, so the learned
gate makes identical decisions to a rule with **no training at all**:

> Answer only when the judge is fully confident (sufficiency 1) and did not
> answer "maybe".

That deterministic rule gives 78.2% at 65.2% coverage on test (n = 326) and
83.2% at 67.1% coverage on dev. Abstentions are never counted as correct.

## Baselines

| Split | Always answer | Forced answer | Abstain = maybe | Majority class |
|---|---|---|---|---|
| Dev (n=283) | 0.618 | 0.731 | 0.042 | 0.562 |
| Test (n=500) | 0.588 | 0.674 | 0.060 | 0.553 |

"Abstain = maybe" counts an abstention as the gold `maybe` class. It is not a
real accuracy; it is reported only so that the earlier experiment, which used
this convention, remains comparable.

## Gate quality

AUC against per-question correctness.

| Gate | Dev AUC | Test AUC | Test AURC |
|---|---|---|---|
| similarity (top-1 dense score) | 0.552 | 0.527 | 0.395 |
| ontology coverage (top-3) | 0.502 | 0.493 | 0.409 |
| ontology coverage (all 10) | 0.497 | 0.491 | 0.413 |
| ontology relation (sentence) | 0.461 | 0.559 | 0.383 |
| ontology heading coverage | 0.512 | 0.534 | 0.382 |
| **LLM judge score** | **0.768** | **0.736** | 0.291 |
| **Judge + self-abstention** | **0.812** | **0.770** | 0.254 |
| Judge fully confident (deterministic) | 0.803 | 0.761 | 0.256 |
| Fused judge + is-maybe (learned) | 0.816 | **0.774** | 0.254 |
| Fused + ontology coverage | 0.815 | 0.766 | 0.262 |
| Fused all features | 0.834 | 0.772 | 0.247 |

Reading:

* With 500 test questions the picture is now stable. Judge score alone is
  0.736; adding the single binary "did the judge answer maybe" lifts it to
  0.770, and the dev-fitted two-feature gate reaches 0.774.
* With 283 dev rows the learned gates fared better than in the pilot, but the
  ontology still adds nothing: `fused_judge_maybe_coverage` has the same dev
  AUC as the two-feature gate and drops on test.
* The ontology-only gates sit between 0.46 and 0.56. On this sample size that
  is a solid finding, not noise: ontology concept coverage is *not* a sufficiency
  signal on PubMedQA.
* `fused_all` shows the largest dev-test gap (0.834 -> 0.772) and is reported to
  make overfitting visible.

## Selective accuracy at matched coverage (test)

Cells are `accuracy@coverage`. Dev chooses the threshold; test applies it.

| Gate | 100% | 80% | 70% | 60% | 50% | 40% | 30% |
|---|---|---|---|---|---|---|---|
| similarity | .587@100 | .607@85 | .605@77 | .604@67 | .599@59 | .594@48 | .610@40 |
| ontology coverage | .597@96 | .595@79 | .590@77 | .590@77 | .590@77 | .590@77 | .590@77 |
| ontology coverage (all) | .597@96 | .592@84 | .592@84 | .592@84 | .592@84 | .592@84 | .592@84 |
| ontology relation | .580@52 | .580@52 | .580@52 | .580@52 | .580@52 | .580@52 | .626@21 |
| ontology heading | .597@96 | .597@96 | .607@74 | .609@69 | .635@46 | .633@44 | .633@44 |
| judge score | .588@100 | .647@87 | .751@69 | .751@69 | .751@69 | .751@69 | .751@69 |
| **judge confident rule** | .588@100 | .588@100 | .588@100 | **.782@65** | .782@65 | .782@65 | .782@65 |
| fused judge+maybe | .588@100 | .646@89 | .749@72 | **.782@65** | .782@65 | .782@65 | .782@65 |
| fused + coverage | .588@100 | .659@86 | .751@72 | .781@62 | .771@52 | .771@52 | .771@52 |
| fused all | .589@100 | .671@83 | .775@69 | .785@61 | .778@52 | .788@41 | .787@30 |

The ontology coverage gate is flat from 77% coverage downward because coverage
is ternary in practice: 0, 0.5 or 1 for most questions, so a threshold splits
the data into the same two groups at every target. That is the saturation
problem seen from the other side.

## Where the ontology does pay: the cascade

Rule: abstain without calling the judge when `coverage_top3 <= a`; otherwise
abstain if the judge says "maybe"; otherwise answer.

| Screen `a` | Judge calls saved | Coverage | Selective accuracy |
|---|---|---|---|
| 0.00 | 5.6% | 64.2% | 0.782 |
| 0.50 | 14.4% | 58.2% | 0.780 |
| 0.75 | **19.4%** | 54.6% | 0.773 |
| 0.99 | 19.6% | 54.4% | 0.772 |

At `a = 0.75` the ontology removes about 1 judge call in 5 for a 0.9-point
accuracy cost. Dev and test agree (dev: 20.5% saved, 83.2% -> 82.5%). The
screen removes questions that are *not* the hardest (see error analysis), so it
is a pure cost saving with a small, stable accuracy tax, not an accuracy
mechanism.

## Retrieval

Dev, 200 questions, no API calls (`results/metrics/retrieval_dev_open.json`).

| Variant | R@1 | R@3 | R@10 | MRR |
|---|---|---|---|---|
| Dense | 0.885 | 0.940 | 0.970 | 0.916 |
| Best ontology-blended rerank | 0.890 | 0.945 | 0.970 | 0.921 |

The best blend changes one question's rank@1. There is no headroom: the gold
abstract is already in the top-10 for 97% of questions. Ontology reranking
cannot matter when retrieval is solved at this scale. Ontology query expansion
was tested earlier in the project and *reduced* recall, because synonyms pulled
in unrelated abstracts sharing a MeSH term.

## Coverage saturation

* Mean document-level coverage: 0.932.
* Share of questions with coverage exactly 1.0: 87.1%.
* Mean number of linked question concepts: 1.75.

Most PubMedQA questions name one or two concepts, and a ten-abstract context
almost always mentions them. A gate that asks "are the question's terms
present?" has almost no variance to work with. This explains both the weak
ontology AUC and the flat risk-coverage curve. Any future coverage signal needs
to be relational or hierarchical, not lexical presence.

## Error analysis (test, n = 500)

Judge answers against gold labels:

| Judge answer | n | Gold yes | Gold no | Gold maybe | Answer accuracy |
|---|---|---|---|---|---|
| yes | 215 | 171 | 19 | 25 | **0.795** |
| no | 124 | 16 | 93 | 15 | 0.750 |
| maybe | 161 | 73 | 58 | 30 | **0.186** |

Three things follow.

1. **"Maybe" really is uncertainty.** Only 18.6% of "maybe" answers are right,
   so abstaining on them is correct roughly 81% of the time. The gold labels of
   those 161 questions are balanced (73 yes, 58 no, 30 maybe), which means the
   judge is not simply detecting the gold `maybe` class: it is flagging hard
   questions of all three classes.
2. **Earlier asymmetry was small-sample.** On the 85-question interim test the
   `no` answer looked weak (0.562 vs 0.825 for `yes`). On 500 questions the
   classes are 0.795 and 0.750 - close. The class-aware gates we tried for that
   asymmetry (one-hot on the answer label) do not beat the plain gate
   (dev 0.824 -> test 0.767) and are not adopted.
3. **The score is monotone with correctness.** Judge sufficiency `yes` ->
   75.1% answer accuracy (n = 346), `partial` -> 24.4% (n = 90), `no` -> 18.8%
   (n = 64). This is why the confident-rule threshold separates so cleanly.

Screened versus passed questions (`coverage_top3 <= 0.75`):

| Group | n | Judge accuracy | Judge "maybe" rate |
|---|---|---|---|
| Screened out | 97 | 0.619 | 0.320 |
| Passed to judge | 403 | 0.581 | 0.323 |

The screen removes slightly *easier-than-average* questions rather than the
hardest ones. That is consistent with the cascade's plain cost story: it saves
calls without improving accuracy and only mildly affects it.

## Per-specialty (test, judge gate at dev 50% coverage)

| MeSH | n | Always | Coverage | Selective |
|---|---|---|---|---|
| C04 Neoplasms | 93 | 0.602 | 0.645 | 0.767 |
| C23 Pathological Conditions | 57 | 0.667 | 0.737 | 0.881 |
| C14 Cardiovascular Diseases | 53 | 0.623 | 0.698 | 0.838 |
| C10 Nervous System Diseases | 34 | 0.500 | 0.647 | 0.636 |
| C01 Infections | 32 | 0.688 | 0.625 | 0.800 |
| C06 Digestive System Diseases | 28 | 0.571 | 0.607 | 0.824 |
| C12 Urogenital Diseases | 24 | 0.542 | 0.667 | 0.812 |
| C05 Musculoskeletal Diseases | 18 | 0.389 | 0.444 | 0.625 |
| M01 Named Groups | 15 | 0.800 | 0.733 | 0.909 |
| C08 Respiratory Tract Diseases | 15 | 0.667 | 0.800 | 0.750 |
| C26 Wounds and Injuries | 15 | 0.400 | 0.400 | 0.667 |
| N05 Health Care | 13 | 0.692 | 0.538 | 0.857 |
| E05 Techniques | 10 | 0.200 | 1.000 | 0.200 |
| C18 Nutritional and Metabolic | 10 | 0.500 | 0.400 | 1.000 |

The gate improves selective accuracy over always-answer in every specialty with
n >= 10 except one: E05 Techniques is degenerate (always-answer 0.200 because
the judge answers `maybe` on 10 of 10, so the rule abstains and selective
accuracy stays at 0.200). C10 Nervous System Diseases is the weakest real
improvement (0.500 -> 0.636). Categories with n < 10 are illustrative only.
Oncology (C04, n = 93) behaves like the overall result: always-answer 60.2% ->
selective 76.7% at 64.5% coverage.

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

Against a *stronger* answerer, the gate's gain at matched coverage is small and
not significant. Its reliable contributions are **selective abstention itself**
(explicit "I do not know" for 35% of questions) and the cheap screen. The new
headline is measured against the same-model judge prompt; both numbers are
reported so the claim can be audited.

Caveat: the plain-prompt run used `gemini-3.5-flash-lite` and the sweep used
`gemini-3.1-flash-lite`, so this is indicative, not a controlled ablation. A
same-model plain-prompt arm remains the most useful missing experiment.

## Judge model matters

| Model | Rows | Judge AUC | Gate |
|---|---|---|---|
| `gemini-3.5-flash-lite` (pilot, 96 rows) | 96 | 0.823 | 0.80 @ 52% coverage |
| `gemini-3.1-flash-lite` (final) | 283 + 500 | 0.74-0.77 | 0.782 @ 65% coverage |

`3.5-flash-lite` was retired or quota-locked during the project; its
replacement is a somewhat weaker judge, but with 283 dev rows for fitting the
final numbers recovered. The system design is unchanged; absolute levels are
model-dependent. Reporting both prevents the pilot from looking like the final
result.

## Hard mode (exclude-own)

Twelve dev questions retrieved with the source abstract removed. The judge
declared the evidence insufficient in all twelve cases and the system abstained
on all twelve. Accuracy 0.0. The retrieved distractors are topically related
but do not contain the study that answers the question. This is recorded as a
negative result: the pipeline is not a closed-book QA system.

## Threats to validity

1. **Dev has 283 judged questions, not 500.** The dev-test AUC gap of the
   learned gates (~0.04) is consistent with moderate overfitting; the resumable
   sweep can still add the missing 217 dev rows, and the analysis refits on the
   full file.
2. **One model, one prompt.** Every judge-based number is conditional on
   `gemini-3.1-flash-lite` and the judge prompt.
3. **The corpus is small and easy.** Retrieval saturation means the
   retrieval-side conclusions may not transfer to a full PubMed index. The
   ontology's null result is equally tied to this data structure.
4. **`maybe` is only 11% of gold labels** in the full 1,000; per-class estimates
   remain noisier than the overall accuracy.
5. **Selection.** The 60% coverage target was fixed before test evaluation, and
   the report shows all targets rather than the best one. The deterministic
   rule was not searched: it is the exact behaviour of the dev-fitted threshold.
