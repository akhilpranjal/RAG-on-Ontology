# OntoGate-RAG - final report

## Data

| split | n | judge model | retrieval |
|---|---|---|---|
| dev | 200 | gemini-3.1-flash-lite | multi-qa-MiniLM-L6-cos-v1 (top-10) |
| test | 85 | gemini-3.1-flash-lite | multi-qa-MiniLM-L6-cos-v1 (top-10) |

## Headline

Always-answer accuracy is **58.8%** on the test split. The dev-fitted fused gate (threshold fitted for 60% coverage) reaches **76.9%** selective accuracy at **61.2%** coverage (+18.1% absolute). That gate simplifies exactly to a deterministic rule - answer only when the judge is fully confident (sufficiency 1) and did not answer 'maybe' - which reaches 76.9% at 61.2% coverage with no training.

## Always-answer baselines

| split | accuracy | accuracy forced (maybe->yes) | accuracy if abstain=maybe | predicted |
|---|---|---|---|---|
| dev | 0.600 | 0.675 | 0.060 | {'no': 36, 'yes': 103, 'maybe': 61} |
| test | 0.588 | 0.624 | 0.094 | {'yes': 40, 'maybe': 29, 'no': 16} |

## Gate quality (AUC / AURC)

| gate | dev AUC | test AUC | dev AURC | test AURC |
|---|---|---|---|---|
| similarity | 0.561 | 0.552 | 0.3355 | 0.3529 |
| ontology_coverage | 0.530 | 0.547 | 0.3493 | 0.4062 |
| ontology_coverage_doc | 0.519 | 0.495 | 0.3583 | 0.4209 |
| ontology_relation | 0.506 | 0.442 | 0.4118 | 0.4688 |
| ontology_heading | 0.528 | 0.514 | 0.3464 | 0.3853 |
| llm_judge | 0.700 | 0.705 | 0.2564 | 0.3277 |
| judge_self_abstain | 0.757 | 0.737 | 0.2261 | 0.2602 |
| judge_confident | 0.750 | 0.729 | 0.2284 | 0.2652 |
| fused_judge_maybe | 0.758 | 0.747 | 0.2265 | 0.2542 |
| fused_judge_maybe_coverage | 0.769 | 0.738 | 0.2124 | 0.2709 |
| fused_all | 0.776 | 0.704 | 0.2237 | 0.3488 |

## Selective accuracy at matched coverage (test)

| gate | cov 100% | cov 80% | cov 70% | cov 60% | cov 50% | cov 40% | cov 30% |
|---|---|---|---|---|---|---|---|
| similarity | 0.583@99% | 0.612@79% | 0.623@72% | 0.612@58% | 0.579@45% | 0.621@34% | 0.667@32% |
| ontology_coverage | 0.613@94% | 0.645@73% | 0.633@71% | 0.633@71% | 0.633@71% | 0.633@71% | 0.633@71% |
| ontology_coverage_doc | 0.613@94% | 0.606@78% | 0.606@78% | 0.606@78% | 0.606@78% | 0.606@78% | 0.606@78% |
| ontology_relation | 0.561@48% | 0.561@48% | 0.561@48% | 0.561@48% | 0.561@48% | 0.561@48% | 0.474@22% |
| ontology_heading | 0.613@94% | 0.613@94% | 0.610@69% | 0.611@64% | 0.649@44% | 0.639@42% | 0.639@42% |
| llm_judge | 0.588@100% | 0.653@85% | 0.729@69% | 0.729@69% | 0.729@69% | 0.729@69% | 0.729@69% |
| judge_self_abstain | 0.588@100% | 0.588@100% | 0.588@100% | 0.769@61% | 0.769@61% | 0.769@61% | 0.769@61% |
| judge_confident | 0.588@100% | 0.588@100% | 0.588@100% | 0.769@61% | 0.769@61% | 0.769@61% | 0.769@61% |
| fused_judge_maybe | 0.588@100% | 0.640@88% | 0.714@74% | 0.769@61% | 0.769@61% | 0.769@61% | 0.769@61% |
| fused_judge_maybe_coverage | 0.588@100% | 0.662@84% | 0.714@74% | 0.766@55% | 0.756@48% | 0.756@48% | 0.756@48% |
| fused_all | 0.588@100% | 0.697@78% | 0.737@67% | 0.775@58% | 0.775@47% | 0.750@42% | 0.692@31% |

## Per-specialty (test, judge gate at dev 50% coverage)

| MeSH | n | always | coverage | selective |
|---|---|---|---|---|
| C04 Neoplasms | 22 | 0.591 | 0.500 | 0.727 |
| C14 Cardiovascular Diseases | 10 | 0.600 | 0.700 | 0.857 |
| C10 Nervous System Diseases | 6 | 0.333 | 0.667 | 0.500 |
| C01 Infections | 6 | 0.667 | 0.333 | 1.000 |

## Coverage saturation

- mean document coverage: 0.916; share at 1.0: 0.825; mean linked concepts: 1.72

## Cascade: coverage screen in front of the judge

Rule: abstain if coverage <= a; else abstain if judge answer == maybe

| screen | judge calls saved | test coverage | test selective acc |
|---|---|---|---|
| <= 0.00 | 5.9% | 63.5% | 0.759 |
| <= 0.25 | 5.9% | 63.5% | 0.759 |
| <= 0.50 | 15.3% | 58.8% | 0.760 |
| <= 0.75 | 23.5% | 51.8% | 0.750 |
| <= 0.99 | 23.5% | 51.8% | 0.750 |
| <= 1.00 | 94.1% | 2.4% | 0.500 |

## Fused gate weights (dev-fitted)

- **fused_judge_maybe**: {'llm_judge': 0.1163, 'judge_answer_maybe': -1.0733}
- **fused_judge_maybe_coverage**: {'llm_judge': 0.0801, 'judge_answer_maybe': -1.0992, 'ontology_coverage': 0.1463}
- **fused_all**: {'llm_judge': 0.1033, 'judge_answer_maybe': -1.0666, 'judge_inconsistent': -0.0374, 'ontology_coverage': 0.1525, 'similarity': 0.0633, 'n_concepts': 0.1074}
