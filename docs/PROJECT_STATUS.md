# Project Status & Execution Plan — Ontology-Enhanced RAG for Medical QA

> **Generated:** 2026-08-14 · Based on live repo inspection + `implementation_plan.md`
>
> This document records the **target**, **what is completed (verified)**, and **what remains**,
> together with plan changes I recommend and the split of work between **me (automated)**
> and **you (manual review only)**.

---

## 1. Target

### 1.1 Research Question
> Under what conditions (query types and relation types) does ontology-based query expansion
> improve retrieval and answer quality over standard semantic retrieval and simple dictionary expansion?

### 1.2 Deliverables (a "great project")
1. A purpose-built medical ontology (Cardiovascular + Metabolic domain) — **built, 347 triples**.
2. Three **controlled pipelines** differing only in retrieval-expansion method — **built + orchestrated in LangGraph**.
3. Category-wise evaluation (6 query types) showing *when* ontology reasoning helps vs. hurts.
4. An **ablation study** isolating relation-type contributions.
5. **Retrieval metrics + answer-quality metrics** + interpretable reasoning traces.
6. **Statistical analysis** (Wilcoxon, effect sizes, CIs).
7. Final report, plots, README, and viva-ready artifacts.

### 1.3 Success Criteria
| Metric | Aspiration |
|---|---|
| Recall@5 gain, Ontology vs Baseline (overall) | **+5–15%** |
| Gain on lay-term & hierarchy categories | **+10–20%** |
| Gain on control (exact clinical) category | **±0–2%** (no harm) |
| Answer Concept-Coverage F1 gain | positive & significant |
| All numbers statistically tested (Wilcoxon + effect sizes) | ✓ |

---

## 2. Live Repo Snapshot (verified 2026-08-14)

| Asset | Status | Detail |
|---|---|---|
| Real corpus | ✅ | 38 PubMed abstracts (`data/corpus/real/`) |
| Synthetic corpus | ✅ | 12 gap-filling docs (`data/corpus/synthetic/`) |
| Chunks indexed | ✅ | 116 chunks in ChromaDB (`gemini-embedding-2`) |
| Concept annotations | ⚠️ 45/50 | 3 good docs unannotated; 2 junk docs to drop |
| Ontology | ✅ | 347 triples, `.ttl` — 12 equiv, 61 subclass, 37 hasSymptom, 42 treatedBy, 14 diagnosedBy, 12 relatedCondition |
| Synonym dictionary | ✅ | 52 pairs (`data/synonyms/synonym_dict.json`) |
| Evaluation queries | ✅ | 66 queries, 6 categories, with `target_concepts` |
| Relevance judgments | ✅ | 66 entries (manual ground truth) |
| Pipelines 1–3 | ✅ | `baseline`, `dictionary`, `ontology_enhanced` |
| LangGraph orchestration | ✅ | `src/orchestration/` — shared retrieve/generate nodes, conditional expansion routing |
| Retrieval metrics | ✅ | Recall@5/10, Precision@5, Hit@5, MRR, nDCG@5 |
| Statistical tests | ✅ | Wilcoxon, Cohen's d, Cliff's δ, paired t, bootstrap CI |
| Reasoning trace logs | ✅ | saved for all 4 ontology variants (from the completed run) |
| **Experiments (real runs)** | ❌ | **blocked: Gemini free-tier quota exhausted** |
| **Answer-quality metrics** | ❌ | **not implemented** (biggest build gap) |
| Plots | ❌ | script ready, no data yet |
| README / report / viva | ❌ | not started |
| Git | ❌ | **0 commits, everything untracked** |

---

## 3. Completed (verified)

**Phase 1–6 & most of Phase 7 (code) are complete and working:**

- Corpus pipeline: download → generate → annotate → chunk → embed → index. ✓
- Ontology builder + reasoner (rdflib traversal, reasoning traces, ablation toggles). ✓
- All 3 pipelines, plus **LangGraph orchestration** (`src/orchestration/`) added this session —
  verified live end-to-end: routing, retrieval, generation, and ablation config all work. ✓
- Full evaluation harness code (metrics, stats, experiment runner with **per-pipeline resume**,
  plots). ✓
- **Embedding cache** (disk-backed) added this session — prevents re-burning the 1000/day free-tier
  quota. ✓
- Two latent bugs fixed this session: `ReasoningTrace.get_all_terms()` and
  `OntologyReasoner.expand_query()` were referenced but never defined (would have crashed Pipeline 3);
  plus a numpy-bool JSON serialization bug in `statistical_tests.py`. ✓

---

## 4. What Is To Be Done (prioritised)

### P0 — Blocking
| # | Task | Who | Notes |
|---|---|---|---|
| 1 | **Run the full experiment** (6 pipeline runs × 66 queries) | me | Needs **~396 embed calls**; quota resets daily. Run tomorrow morning. Cache + resume already built in. |
| 2 | Generate plots | me | `generate_plots.py` reads `experiment_summary.json`. |
| 3 | Git: initial commit of the working baseline | me | Repo has zero commits. Important safety + deliverable. |

### P1 — Build the missing answer-quality layer
| # | Task | Who | Notes |
|---|---|---|---|
| 4 | **`src/evaluation/answer_metrics.py`** — Concept-Coverage F1 (parse generated answers, match against query `target_concepts` + doc concepts) | me | Fully automatable; queries already carry `target_concepts`. |
| 5 | **LLM-as-judge** binary correctness — judge with a *different* Gemini variant (`gemini-2.0-flash` judges `gemini-3.6-flash` answers) | me | Config already has `LLM_JUDGE_MODEL`. Needs ~198 generation + ~198 judge calls (separate quota from embedding). |
| 6 | Wire answer metrics into the experiment runner + plots | me | Reuse existing `full_comparison` stats. |
| 7 | Generate answers for all 66 × 3 pipelines | me | Same P0 run; can be batched with retrieval runs. |

### P2 — Strengthen data quality (recommended before the final runs)
| # | Task | Who | Notes |
|---|---|---|---|
| 8 | **Drop 2 junk docs** (`pubmed_42177087` "Pediatric.", `pubmed_42536866` "[Not Available]") and **annotate 3 good unannotated docs** (PCSK9, Piezo1, BP-lowering) | me | `annotate_corpus.py` exists; quick manual pass for accuracy. |
| 9 | **Expand corpus 50 → ~80 docs** — fetch ~20–30 more PubMed abstracts across extra MeSH terms (`collect_pubmed.py`, free E-utilities, no API key) + a few synthetic gap-fillers | me | Bigger pool → stronger, more defensible statistics; also makes top-5 retrieval a fairer test. **Run on a separate day from experiments** (indexing burns embed quota). |
| 10 | **Clean/standardise concept annotation names** to OWL local names (some docs carry generic `Disease`/`Treatment` — fine, but verify mapping) | me + you review | Viva-defensible accuracy. |

### P3 — Optional scope expansion
| # | Task | Who | Notes |
|---|---|---|---|
| 11 | Expand 66 → ~81 queries to match the plan's per-category minimums | me | Auto-derive relevance from concept overlap, clearly marked "weak supervision"; keep the original 66 as curated core. |
| 12 | Reasoning-trace visualisation (one per query category) for the report | me | Nice explainability exhibit. |

### P4 — Reporting
| # | Task | Who | Notes |
|---|---|---|---|
| 13 | README (setup, architecture, how-to-run) | me | Currently empty. |
| 14 | Final report (`docs/report/`): framing, methods, results, ablations, stats, limitations | me | After experiments. |
| 15 | Viva presentation (slides outline + talking points) | me + you present | I draft; you rehearse. |

---

## 5. Plan Changes I Recommend (full authority taken)

1. **Answer-quality is the missing differentiator.** The original plan listed it, but no code exists.
   I will implement concept-coverage F1 **and** a cross-model LLM judge (Gemini-variant, per the plan's
   own fallback since no OpenAI/Anthropic keys are configured). This makes the "great results" claim
   answer-level, not just retrieval-level.

2. **Corpus expansion is worthwhile but must be quota-scheduled.** 50 docs works but is thin.
   Target ~80: more PubMed abstracts (free, no key) + synthetic fillers. **Indexing on day A,
   experiments on day B** — each fits inside the 1000 embed-calls/day budget with the new cache.

3. **Drop two junk corpus entries.** Two downloaded abstracts are placeholders ("[Not Available]",
   "Pediatric.") that only add retrieval noise. Removing them is strictly a quality improvement.

4. **Keep 66 curated queries as the primary set.** Quality over quantity for a controlled study;
   optionally add auto-judged queries later. Do not rush weak-supervision queries into the headline numbers.

5. **Protégé validation is optional.** `rdflib` parsing + triple-count checks are sufficient for this
   study; the ontology is programmatic and self-consistent. Skip Protégé unless you want it for viva theatre.

6. **LangGraph lives at `src/orchestration/`** (not `src/pipelines/graph.py` as the plan sketched) —
   a cleaner home given the three pipeline modules stay importable for the experiment runner.

7. **Git hygiene first.** Baseline commit now (P0) so every later change is reviewable — standard
   practice and protects the viva artifact.

---

## 6. What YOU Must Do (manual, cannot/should not be automated)

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | **Review the ontology triples** for clinical accuracy (skim `data/ontology/medical_ontology.ttl` or a rendered view) | ~30 min | Viva-defensible: "I built it, but I verified every triple." |
| 2 | **Spot-check relevance judgments** (≈10–15 of the 66) | ~30 min | This is your ground truth; a wrong label distorts every metric. |
| 3 | **Spot-check concept annotations** on the newly collected/expanded docs | ~20 min | Same reasoning as above. |
| 4 | Confirm API budget: the Google key is present ✅; experiments need ~400 embed + ~400 generate/judge calls over 1–2 days | — | Free tier handles it if spaced. If you have OpenAI/Claude keys, judge quality improves (optional). |
| 5 | Nothing else. **All downloading, scripting, experiment runs, metrics, stats, plots, README and report drafting are handled by me.** | — | — |

---

## 7. Execution Roadmap

| Day | Work | Depends on |
|---|---|---|
| **Today** | (1) P0 commit baseline · (2) build answer-metrics layer (concept F1 + LLM judge, code) · (3) corpus cleanup (drop junk, annotate 3 docs) · (4) expand queries? (decide after cleanup) | — |
| **Tomorrow (AM, quota reset)** | Run retrieval experiments (all 6 pipelines, ~396 embed calls, cached + resumable) → `experiment_summary.json` | quota |
| **Day after / same day** | Run answer generation + LLM judge (66×3) · compute answer metrics · statistical tests | experiments |
| **Day after** | Corpus expansion (new PubMed abstracts + synthetic) → re-index **on its own day** | quota scheduling |
| **Then** | Full re-run (clean corpus) → plots → README → final report → viva outline | all above |

> ⚠️ **Quota reality check:** `gemini-embedding-2` free tier = **1000 requests/day**.
> A full experiment = ~400 (retrieval) + ~150 (re-index after corpus expansion) → **one run per day**.
> Generation/judge calls draw from a *separate* quota. All runs are now cached + resumable, so a
> mid-run quota error no longer loses progress.

---

## 8. Blockers & Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Embedding daily quota (1000/day) | Can't run experiments repeatedly same-day | Cache + resume; schedule one pipeline batch/day; run retrieval and answer-generation on separate days |
| Generation rate limits (Gemini free tier) | 198 answers + 198 judge calls may throttle | Built-in SDK retries; batch with sleeps; resumable saving of answers |
| Small corpus (50 docs) | Weak statistical power; lenient retrieval | Corpus expansion (P2) before final runs |
| Ground-truth errors | Distorted metrics | Your manual spot-checks (§6) |
| LLM judge self-bias | Judge = different Gemini variant (not generator) | Documented limitation; concept-F1 is the objective complement |

---

## 9. Immediate Next Action

Say **"go"** and I will execute **today's block**: git baseline commit → answer-metrics
implementation → corpus cleanup (drop 2 junk docs, annotate 3) → verify everything imports,
then prepare the experiment run for tomorrow's quota window.