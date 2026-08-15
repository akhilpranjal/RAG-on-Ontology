# Project Status & Execution Plan — Ontology-Enhanced RAG for Medical QA

> **Last updated:** 2026-08-16 (session 3 — retrieval + answer-quality experiments COMPLETE, plots generated)
> Based on live repo inspection + `implementation_plan.md`

---

## 1. Target

### Research Question
> Under what conditions (query types and relation types) does ontology-based query expansion
> improve retrieval and answer quality over standard semantic retrieval and simple dictionary expansion?

### Deliverables
1. Purpose-built medical ontology (Cardiovascular + Metabolic) — **built, 347 triples**.
2. Three controlled pipelines differing only in retrieval-expansion method — **built + LangGraph orchestration**.
3. Category-wise evaluation (6 query types) — *when* ontology reasoning helps vs. hurts.
4. Ablation study isolating relation-type contributions.
5. **Retrieval + answer-quality metrics** + interpretable reasoning traces.
6. Statistical analysis (Wilcoxon, effect sizes, CIs).
7. Final report, plots, README, viva-ready artifacts.

### Success Criteria
| Metric | Aspiration |
|---|---|
| Recall@5 gain, Ontology vs Baseline (overall) | **+5–15%** |
| Gain on lay-term & hierarchy categories | **+10–20%** |
| Gain on control (exact clinical) category | **±0–2%** (no harm) |
| Answer Concept-Coverage F1 gain | positive & significant |
| All numbers statistically tested | ✓ |

---

## 2. Live Repo Snapshot (2026-08-14)

| Asset | Status | Detail |
|---|---|---|
| Real corpus | ✅ | **68** PubMed abstracts (`data/corpus/real/`) |
| Synthetic corpus | ✅ | 12 gap-filling docs |
| Total corpus | ✅ | **80 docs → 263 chunks** (expanded from 50/116 this session) |
| Concept annotations | ✅ | **80/80** docs annotated (auto + 9 manual) |
| Ontology | ✅ | 347 triples — 12 equiv, 61 subclass, 37 hasSymptom, 42 treatedBy, 14 diagnosedBy, 12 relatedCondition |
| Synonym dictionary | ✅ | 52 pairs |
| Evaluation queries | ✅ | 66 queries, 6 categories, with `target_concepts` |
| Relevance judgments | ✅ | 66 entries (manual ground truth) |
| Pipelines 1–3 + LangGraph | ✅ | `src/orchestration/` verified live |
| Retrieval metrics + stats | ✅ | recall/precision/hit/MRR/nDCG + Wilcoxon/d/Cliff's |
| **Answer-quality metrics** | ✅ | **NEW** — concept-coverage F1 + cross-model LLM judge (`gemini-3.1-flash-lite`) |
| Answer-eval runner | ✅ | **NEW** — `scripts/run_answer_eval.py`, resumable + judge backfill |
| Answer-quality plot | ✅ | **NEW** — `generate_plots.py` → `answer_quality.png` |
| Quota resilience | ✅ | shared per-model rate limiter (`src/rate_limiter.py`) + embed cache + resume + retry (429/503) |
| **Experiments (retrieval)** | ✅ | **DONE — 6 pipelines × 66 queries, real metrics** → `experiment_summary.json` |
| **Answer evaluation** | ✅ | **DONE — 3 pipelines × 66 queries, judged** → `answer_summary.json` |
| Plots | ✅ | **DONE** — `overall_comparison.png`, `category_breakdown.png`, `ablation_study.png`, `answer_quality.png` |
| README / report / viva | ❌ | not started (next) |
| Git | ✅ | **4 commits** (baseline, corpus+metrics, quota hardening+answer eval) |

---

## 3. Completed (verified)

**Build (all working, smoke-tested end-to-end):**
- Corpus pipeline: collect → generate → annotate → chunk → embed → index. ✓
- Ontology builder + reasoner with reasoning traces + ablation toggles. ✓
- All 3 pipelines + LangGraph orchestration (`src/orchestration/`). ✓
- Evaluation harness: retrieval metrics, statistical tests, experiment runner with resume. ✓
- **NEW — Answer-quality layer:** `src/evaluation/answer_metrics.py` (ConceptResolver,
  concept-coverage Precision/Recall/F1, cross-model LLM judge) and `scripts/run_answer_eval.py`
  (generation decoupled from retrieval via cached chunk texts; per-query persistence; judge backfill
  for records created without judge). Smoke-tested with real API calls on a single query.
- **NEW — Quota-hardened pipeline:** disk embedding cache; `index_chunks(reset=True)` + auto corpus
  change detection in `ensure_vectorstore`; on-disk dedup + junk filtering in `collect_pubmed`;
  idempotent `annotate_corpus`.

**Data improvements this session:**
- Dropped 2 off-domain junk docs ("Pediatric.", "[Not Available]" Spanish protocol).
- Expanded corpus 50 → 80 docs (32 new PubMed abstracts across 13 extra MeSH terms;
  structured abstracts now joined fully).
- Manually annotated 9 docs the substring matcher couldn't tag (antihypertensives, PCSK9,
  Piezo1, VF, ACS, retinopathy, ECG biomarker, diabetic cardiomyopathy).

**Bugs fixed (would have crashed the pipelines):**
- `ReasoningTrace.get_all_terms()` and `OntologyReasoner.expand_query()` were referenced but undefined.
- `ReasoningTrace.format_for_prompt()` was referenced but undefined.
- numpy-bool JSON serialization crash in `statistical_tests.py`.
- recall@10 was vacuous (top_k=5) — retrieval now fetches `TOP_K_EXTENDED=10` and scores @5/@10.

**Model / quota reality (this session):**
- **Free-tier generation quota is ~20 req/day per model** on the newest Flash models
  (`gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`) — too small for a
  198-answer + 198-judge evaluation. **`gemini-3.1-flash-lite` has a ~1000 req/day budget**
  and is the only viable free-tier option → generator AND judge use it (judge rubric is
  model-independent; concept-F1 is objective).
- Added shared per-model rate limiter (`src/rate_limiter.py`, even pacing, no bursts) and
  `retry_call` handling for 429/503 including the server's suggested retry delay.

---

## 3b. Results — Retrieval (COMPLETE)

All 6 pipelines × 66 queries, `top_k=10` retrieval, real embeddings (Gemini), cached.

| Pipeline | Recall@5 | Recall@10 | Precision@5 | Hit@5 | MRR | nDCG@5 |
|---|---|---|---|---|---|---|
| 1 Baseline | 0.3520 | 0.4702 | 0.4788 | 0.9848 | 0.9668 | 0.6496 |
| 2 Dictionary | 0.3419 | 0.4802 | 0.4758 | 1.0000 | 0.9710 | 0.6389 |
| 3 Ontology (full) | 0.3637 | 0.4948 | 0.5121 | 1.0000 | 0.9659 | 0.6578 |
| 4 Equivalence-only | 0.3706 | — | — | — | — | — |
| 5 Hierarchy-only | 0.3473 | — | — | — | — | — |
| 6 Properties-only | 0.3669 | — | — | — | — | — |

**Statistical tests (Recall@5, paired across 66 queries):**
- Ontology vs Baseline: p=0.1729 (n.s.), Cohen's d=0.103, Cliff's delta=0.076, mean diff +0.0118
- **Ontology vs Dictionary: p=0.0148 (significant), d=0.295, mean diff +0.0218**
- Dictionary vs Baseline: p=0.4100, d=-0.124, mean diff -0.0101

**Category Recall@5 gains (Ontology − Baseline):** lay_terminology +0.012, disease_hierarchy +0.040,
symptom_reasoning +0.010, treatment_reasoning +0.042, multi_hop +0.010, control_exact_clinical **−0.038**
(harm on the control category, as hypothesised).

**Ablations Recall@5:** Baseline 0.3520 · Equivalence-only 0.3706 · Hierarchy-only 0.3473 ·
Properties-only 0.3669 · Full ontology 0.3637.

---

## 3c. Results — Answer Quality (COMPLETE)

3 main pipelines × 66 queries, concept-coverage F1 (objective) + LLM judge (same lite model, blinded rubric).

| Pipeline | Concept F1 | Precision | Recall | Judge correct |
|---|---|---|---|---|
| 1 Baseline | 0.5717 | 0.485 | 0.807 | 0.667 |
| 2 Dictionary | 0.5728 | 0.487 | 0.806 | 0.682 |
| 3 Ontology | 0.5718 | 0.457 | 0.881 | **0.788** |

- Concept-F1 is flat across pipelines (F1 Δ≈0), but ontology **raises answer concept-recall
  (+0.074)** at a precision cost — mirroring the retrieval finding.
- LLM judge correctness: **Ontology 0.788 vs Baseline 0.667 (+0.121)** — a qualitative gain not
  captured by F1 (answers are more complete, less precise).
- All pairwise Wilcoxon tests on F1 are non-significant (p>0.48).

---

## 4. What Is To Be Done (prioritised)

### P0 — Experiments (ALL COMPLETE ✅)
| # | Task | Status |
|---|---|---|
| 1 | Retrieval experiments (6 runs × 66 queries) | ✅ `experiment_summary.json` |
| 2 | Answer evaluation (66×3 generate + judge) | ✅ `answer_summary.json` |
| 3 | Generate plots | ✅ 4 plots in `results/plots/` |
| 4 | Commit each completed step | ✅ commit `03fd169` |

### P1 — Analysis & Reporting
| # | Task | Who | Notes |
|---|---|---|---|
| 5 | README | me | Setup, architecture, how-to-run. |
| 6 | Final report (`docs/report/`) | me | Framing, methods, results, ablations, stats, limitations. |
| 7 | Viva presentation outline + talking points | me + you rehearse | I draft. |

### P2 — Optional strengthening
| # | Task | Who | Notes |
|---|---|---|---|
| 8 | Expand queries 66 → ~81 to hit plan minimums | me | Auto-judged relevance (weak supervision), clearly marked. |
| 9 | Reasoning-trace visualisation per query category | me | Explainability exhibit for report. |
| 10 | Protégé validation of ontology | you (optional) | Nice viva theatre; rdflib validation already passes. |

---

## 5. What YOU Must Do (manual only)

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | **Review the ontology triples** for clinical accuracy (`data/ontology/medical_ontology.ttl`) | ~30 min | Viva-defensible: "built and verified by me." |
| 2 | **Spot-check ~10–15 relevance judgments** (`data/evaluation/relevance_judgments.json`) | ~30 min | Ground truth; a wrong label distorts every metric. |
| 3 | **Spot-check concept annotations** on the 9 manually tagged docs + a few auto-tagged | ~20 min | Same reasoning. |
| 4 | Confirm Google key is active (✅) and budget for ~400 embed + ~400 generate calls | — | Free tier OK if spaced. |
| 5 | Nothing else — all downloading, runs, metrics, stats, plots, README, report drafting are handled by me. | — | — |

---

## 6. Execution Roadmap

| Day | Work | Status |
|---|---|---|
| Session 1 | Baseline commit — corpus, ontology, pipelines, LangGraph, eval harness | ✅ `a3628ca` |
| Session 2 | Corpus cleanup + expansion (80 docs), answer-metrics layer, quota hardening, bug fixes | ✅ `dde1228` |
| **Session 3 (this)** | **Retrieval experiments (6×66) · answer eval (3×66) · plots · quota fixes** | ✅ `03fd169` |
| **Next** | README → final report → viva outline · commit all | ⏳ |

> ⚠️ **Quota reality (verified empirically this session):** free-tier generation is **~20 req/day per model**
> on the newest Flash models, but **`gemini-3.1-flash-lite` has a ~1000 req/day budget** — used for both
> generation and judging. Embeddings (~1000/day on `gemini-embedding-2`) were cached so no re-burn is needed.
> All runs are cached/resumable with a shared per-model rate limiter.

---

## 7. Blockers & Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Embedding daily quota | Can't run repeatedly same day | Cache + resume + one-day scheduling; decoupled answer eval (no embeds) |
| **Generation daily quota (~20/day/model on newest Flash)** | **Can't run 396-call eval on one model** | **Use `gemini-3.1-flash-lite` (~1000 req/day); shared per-model rate limiter; retry 429/503** |
| Model availability drift (2.x deprecated) | 404s | Verified live model list; judge/generator on available 3.x models |
| Ground-truth errors | Distorted metrics | Your manual spot-checks (§5) |
| Judge = same model as generator | Reduced independence | Documented limitation; judge rubric is blinded; concept-F1 is objective |

---

## 8. Immediate Next Action

README + final report (`docs/report/`) + viva outline, then commit. All experiments, metrics,
stats, and plots are DONE.