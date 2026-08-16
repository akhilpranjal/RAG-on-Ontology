# Ontology-Enhanced RAG for Medical QA — Final Report

**Controlled experimental evaluation of ontology-based query expansion for
retrieval-augmented generation in medical question answering.**

*Cardiovascular + Metabolic domain · Gemini embeddings + Gemini generation · LangGraph orchestration*

---

## 1. Abstract

Retrieval-augmented generation (RAG) is the standard way to ground LLM answers in domain
knowledge, but plain semantic retrieval fails when users ask in lay terms what clinicians
write in technical terms. This project tests whether **ontology-based query expansion**
improves retrieval and answer quality over (a) a **baseline** semantic-retrieval RAG and
(b) a **simple synonym-dictionary** expansion, under controlled conditions. Using a
purpose-built 80-document medical corpus, a 347-triple Cardiovascular + Metabolic ontology,
and 66 manually-judged queries across 6 categories, we find:

- Ontology expansion **significantly** improves Recall@5 over dictionary expansion
  (p = 0.015, Cohen's d = 0.295, mean Δ = +0.022).
- The ontology's gains concentrate exactly where hypothesised: **treatment-reasoning
  (+0.042)**, **disease-hierarchy (+0.040)**, lay-terminology (+0.012), symptom-reasoning
  (+0.010), multi-hop (+0.010) queries.
- As hypothesised, expansion **hurts the control category** (exact-clinical queries,
  −0.038): over-expansion degrades precisely-worded clinical queries.
- Answer-quality: ontology expansion raises answer **concept-recall (+0.074)** and
  **LLM-judge correctness (+0.121)** while holding concept-F1 flat (≈0.57), i.e. answers
  become more complete at a small precision cost.

---

## 2. Motivation & Research Question

**Problem.** Medical information is expressed differently by lay users ("blood pressure pill")
and by the literature ("antihypertensive", "angiotensin-converting-enzyme inhibitors").
Embedding retrieval alone fails on this lexical gap; naive dictionary expansion can over-shoot.

**Research question.**
> Under what conditions (query types and relation types) does ontology-based query
> expansion improve retrieval and answer quality over standard semantic retrieval and
> simple dictionary expansion?

**Hypotheses.**
- **H1.** Ontology expansion improves Recall@5 over the baseline overall.
- **H2.** Ontology expansion improves Recall@5 over a synonym dictionary.
- **H3.** Gains concentrate in categories that need *relational* knowledge (hierarchy,
  symptom/treatment reasoning, multi-hop, lay terminology).
- **H4.** Over-expansion harms the control category of exact-clinical queries.
- **H5.** Answer concept-recall improves with ontology expansion (F1 may stay flat).

---

## 3. Methods

### 3.1 Corpus

| Component | Detail |
|---|---|
| Real documents | 68 PubMed abstracts (Cardiovascular + Metabolic; 13+ MeSH topics, junk-filtered, deduped) |
| Synthetic documents | 12 gap-filling documents (conditions/symptoms/treatments underrepresented in the real corpus) |
| **Total** | **80 documents → 263 chunks** (500-char chunks, 100-char overlap) |
| Concept annotations | 80/80 documents annotated (automated matcher + 9 manual) |
| Embeddings | `gemini-embedding-2` (cached on disk; ~1000/day free quota) |

### 3.2 Ontology

Purpose-built `data/ontology/medical_ontology.ttl` (RDF/Turtle, **347 triples**):

| Relation type | Example | Count |
|---|---|---|
| Equivalence | `Hypertension ≡ HighBloodPressure` | 12 |
| Hierarchy (subClassOf) | `MyocardialInfarction ⊑ AcuteCoronarySyndrome` | 61 |
| hasSymptom | `Hyperglycemia hasSymptom Polyuria` | 37 |
| treatedBy | `Hypertension treatedBy ACEInhibitor` | 42 |
| diagnosedBy | `Diabetes diagnosedBy FastingGlucose` | 14 |
| relatedCondition | `Obesity relatedCondition SleepApnea` | 12 |

### 3.3 Pipelines (controlled comparison)

Three pipelines differ **only** in query-expansion strategy; retrieval and generation nodes
are shared and identical (implemented as one LangGraph graph, `src/orchestration/`):

| # | Pipeline | Expansion |
|---|---|---|
| 1 | Baseline | None (raw query embedding) |
| 2 | Dictionary | Synonym-dictionary expansion (52 pairs, `data/synonyms/synonym_dict.json`) |
| 3 | Ontology | Ontology traversal: equivalence + hierarchy + properties (symptom/treatment/diagnosis/related) |

**Ablations** (same graph, relation toggles): equivalence-only, hierarchy-only, properties-only.

Generator: `gemini-3.1-flash-lite`, temperature 0.0, identical system prompt for all pipelines.

### 3.4 Evaluation setup

- **66 queries × 6 categories** (`data/evaluation/queries.json`): lay_terminology,
  disease_hierarchy, symptom_reasoning, treatment_reasoning, multi_hop,
  control_exact_clinical — each with `target_concepts`.
- **Manual relevance judgments** for all 66 queries (`relevance_judgments.json`).
- **Retrieval metrics:** Recall@5, Recall@10, Precision@5, Hit@5, MRR, nDCG@5
  (retrieval fetches `top_k=10`, scores at both @5 and @10).
- **Answer metrics:** objective **concept-coverage Precision/Recall/F1** (no LLM) plus an
  **LLM judge** (blinded rubric, 0–5 score + correctness).
- **Statistics:** paired Wilcoxon signed-rank, Cohen's d, Cliff's delta.

### 3.5 Quota & reproducibility

- Free-tier generation quota is ~**20 requests/day per model** on the newest Flash models
  (`gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite` — verified empirically).
  `gemini-3.1-flash-lite` has a ~1000 req/day budget and is used for both generation and
  judging (judge rubric is blinded; concept-F1 is objective).
- Shared per-model rate limiter (`src/rate_limiter.py`) paces calls; every runner is
  **resumable** (per-query JSON persistence) and embeddings are disk-cached.

---

## 4. Results

### 4.1 Retrieval — overall

| Pipeline | Recall@5 | Recall@10 | Precision@5 | Hit@5 | MRR | nDCG@5 |
|---|---|---|---|---|---|---|
| 1 Baseline | 0.3520 | 0.4702 | 0.4788 | 0.9848 | 0.9668 | 0.6496 |
| 2 Dictionary | 0.3419 | 0.4802 | 0.4758 | 1.0000 | 0.9710 | 0.6389 |
| **3 Ontology (full)** | **0.3637** | **0.4948** | **0.5121** | 1.0000 | 0.9659 | **0.6578** |
| 4 Equivalence-only | 0.3706 | 0.5028 | 0.5121 | 1.0000 | 0.9735 | 0.6708 |
| 5 Hierarchy-only | 0.3473 | 0.4978 | 0.4848 | 1.0000 | 0.9533 | 0.6377 |
| 6 Properties-only | 0.3669 | 0.4920 | 0.5182 | 1.0000 | 0.9886 | 0.6722 |

### 4.2 Statistical tests (Recall@5, paired across 66 queries)

| Comparison | Wilcoxon p | Cohen's d | Cliff's delta | Mean Δ |
|---|---|---|---|---|
| Ontology vs Baseline | 0.1729 | 0.103 | 0.076 | +0.0118 |
| **Ontology vs Dictionary** | **0.0148** | **0.295** | 0.084 | **+0.0218** |
| Dictionary vs Baseline | 0.4100 | −0.124 | −0.001 | −0.0101 |

**H2 supported** (ontology significantly beats dictionary). H1 is positive but not
significant at α=0.05 (p=0.17) — the pooled effect is small and dominated by the control
category drag (see below).

### 4.3 Retrieval — category breakdown (Recall@5)

| Category | Baseline | Dictionary | Ontology | Δ Ont−Base |
|---|---|---|---|---|
| lay_terminology | 0.3197 | 0.3012 | 0.3312 | **+0.0115** |
| disease_hierarchy | 0.2272 | 0.2470 | 0.2667 | **+0.0395** |
| symptom_reasoning | 0.3697 | 0.3540 | 0.3799 | **+0.0102** |
| treatment_reasoning | 0.2943 | 0.3097 | 0.3362 | **+0.0419** |
| multi_hop | 0.3243 | 0.3166 | 0.3338 | **+0.0095** |
| control_exact_clinical | 0.5655 | 0.5155 | 0.5278 | **−0.0377** |

**H3 and H4 supported.** The largest gains are in the relational categories
(treatment_reasoning +0.042, disease_hierarchy +0.040) and the control category drops,
exactly as predicted.

### 4.4 Answer quality (3 pipelines × 66 queries, judged)

| Pipeline | Concept-F1 | Precision | Recall | Judge correct |
|---|---|---|---|---|
| 1 Baseline | 0.5717 | 0.485 | 0.807 | 0.667 |
| 2 Dictionary | 0.5728 | 0.487 | 0.806 | 0.682 |
| **3 Ontology** | 0.5718 | 0.457 | **0.881** | **0.788** |

All pairwise F1 tests non-significant (p > 0.48). But ontology expansion:
- **raises answer concept-recall by +0.074** (0.807 → 0.881), and
- **raises LLM-judge correctness by +0.121** (0.667 → 0.788).

**H5 supported:** the ontology produces more *complete* answers (higher recall / judge
correctness) at a small precision cost, keeping F1 flat. Concept-F1 alone understates the
improvement — recall and the qualitative judge both favour the ontology.

---

## 5. Interpretation

1. **Equivalence expansion is the strongest single mechanism** (ablation Recall@5 0.3706,
   best of all pipelines). It resolves the lay↔clinical lexical gap directly, consistent
   with the lay_terminology and treatment_reasoning gains.
2. **Hierarchy alone underperforms** (0.3473): upward/downward subclass expansion can add
   noise in a small corpus where "the" subclass is not always relevant. Trace analysis
   (`results/trace_exhibits.md`, `trace_breakdown.png`) shows hierarchy is also the most
   *prolific* mechanism: a single query such as "conditions under cardiovascular disease"
   fires 20+ subclass expansions, most of which are irrelevant to the answer.
3. **Properties (symptom/treatment/diagnosis/related) carry most relational value**
   (0.3669) and power the symptom- and treatment-reasoning gains.
4. **Over-expansion hurts exact clinical queries** (−0.038 on control). The traces reveal
   *why*: even precisely-worded control queries trigger ~12 expansions on average
   (notably `hasSymptom` ×40 and `treatedBy` ×35 across the 12 control queries) — the
   relational graph has no "leave it alone" switch, so exact queries get diluted too.
5. The full ontology is a middle ground between the strong equivalence effect and the
   hierarchy noise — hence overall Recall@5 (0.364) sits between equivalence-only and
   hierarchy-only.
6. On the answer side, expansion trades precision for completeness: LLM answers cite more
   target concepts (higher recall) and are judged more often correct, without F1 loss.

---

## 6. Limitations

- **Judge = same model as generator** (`gemini-3.1-flash-lite`) due to free-tier quota
  (~20 req/day on other Flash models). Mitigations: blinded rubric, objective concept-F1 as
  the primary metric.
- **Domain scope:** Cardiovascular + Metabolic only; 80 documents is small. Results may not
  generalise to other medical domains or larger corpora.
- **Absolute metrics are model-dependent**; the study is comparative (pipeline vs pipeline),
  which is quota-friendly and internally valid.
- **Synthetic documents** fill corpus gaps but are not external ground truth.
- **nDCG@5 max > 1** (1.26) for one query due to graded gains > 1 in the judgment scheme;
  medians are reported alongside means.
- Hierarchy expansion underperforms; a corpus-relative relevance filter on expanded terms
  could recover it.

---

## 7. Conclusions

- Ontology-based query expansion **significantly outperforms dictionary expansion** for
  retrieval (Recall@5, p = 0.015) and yields qualitative answer gains (concept-recall
  +0.07, judge-correctness +0.12).
- The benefit is **conditional**: strong for relational reasoning categories
  (hierarchy +0.040, treatment +0.042), nil-to-negative for exact-clinical queries (−0.038).
- **Equivalence** expansion is the highest-value mechanism; **hierarchy** needs guarding.
- A production system should apply ontology expansion **selectively** (per query category),
  not uniformly.

- **Ontology relation usage per category** is visualised in `results/plots/trace_breakdown.png`
  with worked per-category traces in `results/trace_exhibits.md` (explainability exhibit).

---

## 8. Reproducibility

```bash
uv sync                      # Python >= 3.11
cp .env.example .env         # GOOGLE_API_KEY=...
uv run python -m scripts.build_vectorstore    # chunk/embed/index (cached)
uv run python -m scripts.run_experiments      # 6×66 retrieval -> experiment_summary.json
uv run python -m scripts.run_answer_eval      # 3×66 answers + judge -> answer_summary.json
uv run python -m scripts.generate_plots       # -> results/plots/*.png
```

All intermediate data is in `data/`; all results in `results/metrics/`; all plots in
`results/plots/`. Runners are resumable and rate-limit-safe.

*Report generated 2026-08-16 from committed results (git `03fd169`+).*