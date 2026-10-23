# OntoGate-RAG - final report

## Data

| split | n | judge model | retrieval |
|---|---|---|---|
| dev | 283 | gemini-3.1-flash-lite | multi-qa-MiniLM-L6-cos-v1 (top-10) |
| test | 500 | gemini-3.1-flash-lite | multi-qa-MiniLM-L6-cos-v1 (top-10) |

## Headline

Always-answer accuracy is **58.8%** on the test split. The dev-fitted fused gate (threshold fitted for 60% coverage) reaches **78.2%** selective accuracy at **65.2%** coverage (+19.4% absolute). That gate simplifies exactly to a deterministic rule - answer only when the judge is fully confident (sufficiency 1) and did not answer 'maybe' - which reaches 78.2% at 65.2% coverage with no training.

## Always-answer baselines

| split | accuracy | accuracy forced (maybe->yes) | accuracy if abstain=maybe | predicted |
|---|---|---|---|---|
| dev | 0.618 | 0.731 | 0.042 | {'no': 54, 'yes': 143, 'maybe': 86} |
| test | 0.588 | 0.674 | 0.060 | {'yes': 215, 'maybe': 161, 'no': 124} |

## Gate quality (AUC / AURC)

| gate | dev AUC | test AUC | dev AURC | test AURC |
|---|---|---|---|---|
| similarity | 0.552 | 0.527 | 0.3209 | 0.3950 |
| ontology_coverage | 0.502 | 0.493 | 0.3579 | 0.4087 |
| ontology_coverage_doc | 0.497 | 0.491 | 0.3656 | 0.4133 |
| ontology_relation | 0.461 | 0.559 | 0.4047 | 0.3828 |
| ontology_heading | 0.512 | 0.534 | 0.3518 | 0.3821 |
| llm_judge | 0.768 | 0.736 | 0.2481 | 0.2906 |
| judge_self_abstain | 0.812 | 0.770 | 0.2144 | 0.2538 |
| judge_confident | 0.803 | 0.761 | 0.2171 | 0.2563 |
| fused_judge_maybe | 0.816 | 0.774 | 0.2152 | 0.2535 |
| fused_judge_maybe_coverage | 0.815 | 0.766 | 0.2003 | 0.2619 |
| fused_all | 0.834 | 0.772 | 0.1811 | 0.2468 |

## Selective accuracy at matched coverage (test)

| gate | cov 100% | cov 80% | cov 70% | cov 60% | cov 50% | cov 40% | cov 30% |
|---|---|---|---|---|---|---|---|
| similarity | 0.587@100% | 0.607@85% | 0.605@77% | 0.604@67% | 0.599@59% | 0.594@48% | 0.610@40% |
| ontology_coverage | 0.597@96% | 0.595@79% | 0.590@77% | 0.590@77% | 0.590@77% | 0.590@77% | 0.590@77% |
| ontology_coverage_doc | 0.597@96% | 0.592@84% | 0.592@84% | 0.592@84% | 0.592@84% | 0.592@84% | 0.592@84% |
| ontology_relation | 0.580@52% | 0.580@52% | 0.580@52% | 0.580@52% | 0.580@52% | 0.580@52% | 0.626@21% |
| ontology_heading | 0.597@96% | 0.597@96% | 0.607@74% | 0.609@69% | 0.635@46% | 0.633@44% | 0.633@44% |
| llm_judge | 0.588@100% | 0.647@87% | 0.751@69% | 0.751@69% | 0.751@69% | 0.751@69% | 0.751@69% |
| judge_self_abstain | 0.588@100% | 0.588@100% | 0.588@100% | 0.782@65% | 0.782@65% | 0.782@65% | 0.782@65% |
| judge_confident | 0.588@100% | 0.588@100% | 0.588@100% | 0.782@65% | 0.782@65% | 0.782@65% | 0.782@65% |
| fused_judge_maybe | 0.588@100% | 0.646@89% | 0.749@72% | 0.782@65% | 0.782@65% | 0.782@65% | 0.782@65% |
| fused_judge_maybe_coverage | 0.588@100% | 0.659@86% | 0.751@72% | 0.781@62% | 0.771@52% | 0.771@52% | 0.771@52% |
| fused_all | 0.589@100% | 0.671@83% | 0.775@69% | 0.785@61% | 0.778@52% | 0.788@41% | 0.787@30% |

## Per-specialty (test, judge gate at dev 50% coverage)

| MeSH | n | always | coverage | selective |
|---|---|---|---|---|
| C04 Neoplasms | 93 | 0.602 | 0.645 | 0.767 |
| C23 Pathological Conditions, Signs and Symptoms | 57 | 0.667 | 0.737 | 0.881 |
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
| E05 Analytical/Diagnostic/Therapeutic Techniques | 10 | 0.200 | 1.000 | 0.200 |
| C18 Nutritional and Metabolic Diseases | 10 | 0.500 | 0.400 | 1.000 |
| C07 Stomatognathic Diseases | 8 | 0.250 | 0.500 | 0.500 |
| B01 Organisms | 6 | 0.167 | 0.167 | 1.000 |
| C25 Chemically-Induced Disorders | 6 | 0.167 | 0.333 | 0.500 |

## Coverage saturation

- mean document coverage: 0.932; share at 1.0: 0.871; mean linked concepts: 1.75

## Cascade: coverage screen in front of the judge

Rule: abstain if coverage <= a; else abstain if judge answer == maybe

| screen | judge calls saved | test coverage | test selective acc |
|---|---|---|---|
| <= 0.00 | 5.6% | 64.2% | 0.782 |
| <= 0.25 | 5.6% | 64.2% | 0.782 |
| <= 0.50 | 14.4% | 58.2% | 0.780 |
| <= 0.75 | 19.4% | 54.6% | 0.773 |
| <= 0.99 | 19.6% | 54.4% | 0.772 |
| <= 1.00 | 96.2% | 1.8% | 0.667 |

## Fused gate weights (dev-fitted)

- **fused_judge_maybe**: {'llm_judge': 0.376088164137, 'judge_answer_maybe': -1.221844105708}
- **fused_judge_maybe_coverage**: {'llm_judge': 0.368963211087, 'judge_answer_maybe': -1.227876947276, 'ontology_coverage': 0.048646435732}
- **fused_all**: {'llm_judge': 0.414088693625, 'judge_answer_maybe': -1.174517702494, 'judge_inconsistent': -0.044351468476, 'ontology_coverage': 0.07703162549, 'similarity': 0.010727465141, 'n_concepts': 0.205611475763}
