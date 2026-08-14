# Project Status & Execution Plan — Ontology-Enhanced RAG for Medical QA

> **Last updated:** 2026-08-14 (session 2 — corpus expansion + answer-quality layer built)
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
| Quota resilience | ✅ | embed cache + per-pipeline resume + auto corpus re-index |
| **Experiments (real runs)** | ❌ | **blocked: embedding quota exhausted today; run tomorrow AM** |
| Plots | ❌ | script ready, no data yet |
| README / report / viva | ❌ | not started |
| Git | ✅ | **2 commits** (baseline + this session) |

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
- **Model config:** generator `gemini-3.6-flash` ✓; judge moved from deprecated `gemini-2.0-flash`
  /restricted `gemini-2.5-flash` to **`gemini-3.1-flash-lite`** (available + truly cross-model).

---

## 4. What Is To Be Done (prioritised)

### P0 — Blocking (quota-scheduled)
| # | Task | Who | Notes |
|---|---|---|---|
| 1 | **Run retrieval experiments** (6 runs × 66 queries) | me | ~396 embed calls + ~263 to re-index corpus. Run **tomorrow AM**. Cache + resume + auto re-index built in. |
| 2 | **Run answer evaluation** (66×3 generate + judge) | me | Reuses cached retrieval texts → **zero embed calls**, only generation quota. Can run same/next day. |
| 3 | Generate plots | me | `generate_plots.py` (retrieval + answer-quality). |
| 4 | Commit each completed step | me | Git hygiene. |

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

| Day | Work | Depends on |
|---|---|---|
| ✅ Done (this session) | Baseline commit · corpus cleanup + expansion (80 docs) · answer-metrics layer · quota hardening · 3 bug fixes · model config fix | — |
| **Tomorrow AM** | Retrieval experiments (~660 embed calls: re-index 263 + 6×66 queries) → `experiment_summary.json` | quota reset |
| **Tomorrow** | Answer eval (198 gen + 198 judge) → `answer_summary.json` · generate plots | experiments |
| **Then** | README → final report → viva outline · commit all | results |

> ⚠️ **Quota reality:** `gemini-embedding-2` free tier ≈ **1000 requests/day**. Tomorrow's plan
> (~660 embed calls + up to 396 generation calls on separate quota) fits comfortably. Every step is
> cached/resumable so a mid-run quota error no longer loses progress.

---

## 7. Blockers & Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Embedding daily quota | Can't run repeatedly same day | Cache + resume + one-day scheduling; decoupled answer eval (no embeds) |
| Generation rate limits | 198 answers + 198 judge calls may throttle | SDK retries + `retry_call` backoff + per-query persistence |
| Model availability drift (2.x deprecated) | 404s | Judge moved to `gemini-3.1-flash-lite` (verified available) |
| Ground-truth errors | Distorted metrics | Your manual spot-checks (§5) |
| LLM judge bias (same vendor) | Documented limitation | Judge = different Gemini family than generator; concept-F1 is objective complement |

---

## 8. Immediate Next Action

Say **"run"** tomorrow morning and I will execute the full experiment pipeline:
`run_experiments` → `run_answer_eval` → `generate_plots`, commit results, then draft README + report.