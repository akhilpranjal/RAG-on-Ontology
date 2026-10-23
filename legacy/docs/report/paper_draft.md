# AdaOnto-RAG: Adaptive Ontology-Gated Retrieval with Diversity Reranking for Medical Question Answering

**Paper draft — all numbers are measured results from this repository (Experiment 2).**

---

## Title (proposed)

**AdaOnto-RAG: Adaptive Ontology-Gated Retrieval with Diversity Reranking
for Medical Question Answering**

## Abstract

Standard retrieval-augmented generation (RAG) struggles with the vocabulary gap
between lay medical questions and clinical documents, and naive synonym
expansion can degrade retrieval. Ontology-based query expansion helps, but
uniformly expanding every query is suboptimal: expansion benefits queries that
require relational reasoning while harming already-precise clinical queries.
We propose **AdaOnto-RAG**, a novel adaptive architecture with three components:
(1) a deterministic symbolic **query router** that classifies intent
(lay / hierarchy / treatment / symptom / multi-hop / precise) from query text
alone; (2) **intent-conditioned selective expansion** over a medical knowledge
graph, applying only the relation families each intent requires (or none);
(3) **redundancy-aware MMR reranking** (λ = 0.5) with hard document dedup.
On a self-built Cardio+Metabolic benchmark (80 documents, 347-triple ontology,
66 queries in 6 categories), AdaOnto-RAG achieves **Recall@5 of 0.392** vs
0.352 (semantic baseline), 0.342 (dictionary expansion), and 0.364 (full
ontology expansion) — significant against all three (Wilcoxon p = 0.0016,
p < 0.0001, p = 0.0019). Answer correctness judged by a blinded LLM rubric
rises from 66.7% to **84.8%** (McNemar p = 0.004 vs baseline). Component
ablations show neither selective expansion nor reranking alone is significant,
while their combination is — the integration is the contribution.

## 1. Introduction

- Medical QA needs grounding (hallucination risk) → RAG [Lewis et al. 2020].
- The bottleneck is retrieval: vocabulary mismatch (lay vs clinical), and in
  medicine most retrieved passages are irrelevant [Kim et al. 2025: only 22%
  of top-16 passages relevant].
- Query expansion with biomedical vocabularies helps recall but can cost
  precision [Lu et al. 2009, MeSH/ATM]; flat synonym lists underperform
  structured expansion (our Experiment 1: dictionary 0.342 < baseline 0.352).
- **Gap:** existing ontology-RAG systems expand every query identically.
- **Contribution:** an adaptive architecture that expands selectively by
  intent and diversifies results — evaluated under a pre-registered protocol
  (design frozen in `docs/report/architecture_design.md` before any run).

## 2. Related Work

- RAG paradigms and query optimization as a first-class component
  [Gao et al. 2023]; biomedical RAG survey [2025, arXiv:2505.01146].
- Graph/KG-RAG: GraphRAG surveys [Han et al. 2024; Peng et al. 2024],
  KG-guided chunk expansion [Zhu et al., NAACL 2025].
- Ontology-driven biomedical expansion: MeSH ATM [Lu et al. 2009];
  BMQExpander (UMLS + LLM) [Al Nazi et al. 2025] — closest prior system.
- Biomedical ontologies: UMLS [Bodenreider 2004]; OBO Foundry [Smith et al. 2007].
- Evaluation: LLM-as-a-judge validity and biases [Zheng et al. 2023];
  medical QA benchmarks [MedQA, PubMedQA].
- Selective expansion precedent: expansion helps recall but hurts precision on
  precise queries — the standard justification for gating (cf. [Lu et al.]).
- **Difference from prior work:** BMQExpander/KG²RAG expand uniformly; AdaOnto-RAG
  routes per-query intent → relation-family masks, fused with diversity reranking.

## 3. Method: AdaOnto-RAG

### 3.1 Knowledge graph
Purpose-built Cardio+Metabolic ontology (RDF/Turtle, 347 triples, 77 classes):
12 `equivalentClass` (lay↔clinical), 61 `subClassOf`, 42 `treatedBy`,
37 `hasSymptom`, 14 `diagnosedBy`, 12 `relatedCondition` (+1 declared property).

### 3.2 Symbolic query router (zero API calls, no training)
Ordered rules over query text + ontology labels + 52-term lay dictionary:
1. **precise** — query names both relation sides (intervention + disease), no lay
   terms → NO expansion.
2. **lay (+cue)** — lay term alone → equivalence-only; lay + intent cue → full.
3. **hierarchy** — "types/kinds/forms of…", enumeration patterns → equivalence+hierarchy.
4. **multi-hop** — ≥2 cue groups → full.
5. **treatment** — drug/therapy/diagnosis cues → equivalence+properties.
6. **symptom** — symptom label + direction word → equivalence+properties.
7. **default** — equivalence-only (safest single family).
Measured routing on 66 queries: treatment 15, lay_complex 12, hierarchy 10,
lay 8, default 6, precise 6, symptom 5, multihop 4.

### 3.3 Selective expansion
Shared `OntologyReasoner` traversal with per-intent family flags
(equivalence / hierarchy / properties); every hop logged (explainability).

### 3.4 Diversity reranking
Dense top-20 pool → greedy MMR (λ = 0.5, fixed) on min-max normalized
relevance vs max chunk-embedding cosine redundancy, hard same-document dedup.
Uses only scores/embeddings/IDs — no judgment or annotation signals
(fairness guardrail; judgments derive from concept tags, so tag-based
reranking would be circular and is excluded by design).

### 3.5 Generation
Shared Gemini generator (temp 0.0) + ontology reasoning context when expanded —
identical across pipelines, so gains are attributable to retrieval.

## 4. Experiments

- **Dataset (self-built):** 80 docs (68 PubMed + 12 synthetic) → 263 chunks,
  ChromaDB + `gemini-embedding-2`; 66 queries × 6 categories with
  concept-derived relevance judgments; 6-relation ontology above.
- **Baselines:** P1 semantic RAG, P2 dictionary expansion (52 pairs),
  P3 full ontology expansion (+ its 3 family ablations).
- **Protocol:** same metrics code (Recall@5 primary, P@5, MRR, nDCG),
  same stats (`full_comparison`: Wilcoxon α=0.05, Cohen's d, Cliff's delta),
  same blinded LLM judge + objective concept-F1. Pre-registered before runs.
- **Pre-registration deviations (logged):** `prevent` added to treatment cues;
  symptom vocabulary extended to equivalence-partners of symptoms; both before
  any Experiment-2 run. Cosmetic runner print fix after.

## 5. Results

### Retrieval (Recall@5, n = 66)

| System | R@5 | Δ vs baseline |
|---|---|---|
| P1 Baseline | 0.3520 | — |
| P2 Dictionary | 0.3419 | −0.010 |
| P3 Ontology-full | 0.3637 | +0.012 |
| AdaOnto selective-only | 0.3657 | +0.014 (n.s., p = 0.11) |
| AdaOnto mmr-only | 0.3746 | +0.023 (n.s., p = 0.052) |
| **AdaOnto full** | **0.3918** | **+0.040** |

Significance (paired Wilcoxon, Recall@5):
- full vs baseline: **p = 0.0016**, d = 0.35, mean diff +0.040
- full vs dictionary: **p < 0.0001**, d = 0.60, diff +0.050
- full vs ontology-full: **p = 0.0019**, d = 0.36, diff +0.028
- Neither component alone is significant — **the combination is the contribution.**

### Per-category Recall@5 (full − baseline, percentage points)
treatment **+6.4**, hierarchy **+6.3**, multi-hop **+5.2**, lay +2.4,
symptom +1.5, control **+2.4** (the control harm of uniform expansion is reversed).

### Answer quality (66 answers/system)

| System | Concept-F1 | Concept-R | Judge correct | Judge score |
|---|---|---|---|---|
| Baseline | 0.572 | 0.807 | 0.667 | 7.82 |
| Dictionary | 0.573 | 0.806 | 0.682 | 7.86 |
| Ontology | 0.572 | 0.881 | 0.788 | 8.62 |
| **AdaOnto** | 0.565 | **0.893** | **0.848** | **8.95** |

- McNemar (judge correct): AdaOnto vs baseline **p = 0.004** (14 flips for, 2 against);
  vs dictionary **p = 0.007**; vs ontology p = 0.34 (7 for, 3 against — directional).
- Judge-score Wilcoxon: vs baseline **p = 0.002**, vs dictionary **p = 0.002**,
  vs ontology p = 0.18.
- F1 differences n.s. (as in prior work): answers are more complete
  (recall +8.6pp over baseline) at a small precision cost.

### Figures
`results/plots/adaptive_comparison.png` — Panel A: R@5 across all six
configurations; Panel B: judge correctness across four systems.

## 6. Limitations
Single 66-query set, no held-out split (mitigated by frozen pre-registration);
concept-derived (not human) relevance judgments; shared generator/judge model;
substring matcher quirks; single-hop expansion; single Cardio+Metabolic domain.

## 7. Future Work
Held-out validation on a second query set; BEIR out-of-domain robustness check
(router should abstain → no harm); learned router vs symbolic comparison;
chained multi-hop traversal; cross-model judge.

## 8. Conclusion
Selective expansion by intent plus diversity reranking beats uniform ontology
expansion (+2.8pp, p = 0.002), flat synonyms (+5.0pp, p < 0.0001), and pure
semantic retrieval (+4.0pp, p = 0.002) on the same testbed — with gains in
every query category and significantly more correct answers. Expansion in
medical RAG should be adaptive, not universal.

## References
See `docs/report/references.md` (§1–§8). Key additions for this paper:
selective-expansion precedent [Lu et al. 2009]; closest systems
[Al Nazi et al. 2025; Zhu et al. 2025]; medical-RAG motivation [Kim et al. 2025].
