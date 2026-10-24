# Viva Presentation Outline & Talking Points

*Ontology-Enhanced RAG for Medical QA — 10–12 min presentation + Q&A*

---

## Slide 0 — Title
- "Ontology-Enhanced Retrieval-Augmented Generation for Medical Question Answering"
- One-line hook: *"RAG grounds LLMs in documents, but documents don't speak the patient's
  language — can a medical ontology bridge that gap?"*

## Slide 1 — Motivation (2 min)
- The problem: lay user asks "blood pressure pill" → literature says "ACE inhibitor".
- Embedding retrieval fails on this lexical gap; naive synonym expansion over-shoots.
- Contribution: a **controlled experiment** isolating *when* ontology expansion helps vs hurts.
- Show one real example query + the ontology reasoning trace behind it
  (`results/reasoning_logs/`).

## Slide 2 — Research question & hypotheses (1 min)
- RQ: Under what conditions does ontology query expansion improve retrieval and answer
  quality over baseline RAG and dictionary expansion?
- H1 overall gain · H2 beats dictionary · H3 gains in relational categories ·
  H4 harms control category · H5 answers more complete.

## Slide 3 — System (2 min)
- Corpus: 80 docs (68 PubMed + 12 synthetic) → 263 chunks, `gemini-embedding-2`.
- Ontology: 347 triples (equiv / hierarchy / symptom / treatment / diagnosis / related).
- Three pipelines, **identical except expansion**, one shared LangGraph
  (`src/orchestration/`): baseline → dictionary → ontology.
- Evaluation: 66 manual-judged queries, 6 categories; Recall@5/@10, P@5, Hit@5, MRR, nDCG@5;
  concept-F1 + blinded LLM judge; Wilcoxon / d / Cliff's.

## Slide 4 — Headline results (2 min)
- Retrieval table (6 pipelines × 6 metrics) — point to **Ontology Recall@5 0.364**.
- **Ontology vs Dictionary: p = 0.015, d = 0.295** (significant). vs Baseline: p = 0.17 (n.s.).
- Ablations: equivalence 0.371 > properties 0.367 > full 0.364 > hierarchy 0.347.
- Answer quality: concept-recall 0.81 → 0.88; judge-correctness 0.67 → 0.79.

## Slide 5 — The "when" story (category analysis) (2 min)
- Bar chart (`category_breakdown.png`): Δ per category.
- Gains: treatment_reasoning +0.042, disease_hierarchy +0.040, lay +0.012, symptom +0.010,
  multi-hop +0.010.
- **Control: −0.038** — expansion harms exact-clinical queries.
- Takeaway: *ontologies help relational reasoning, hurt precision questions.*

## Slide 6 — Ablations & interpretation (1.5 min)
- Equivalence = the workhorse; hierarchy = noisy; properties = relational value.
- Full system is a middle ground → explains modest overall effect.

## Slide 7 — Answer quality (1.5 min)
- Concept-F1 flat (0.57) but **recall +0.074 and judge +0.121** → answers more complete.
- Why F1 hides it: expansion trades precision for coverage.

## Slide 8 — Limitations (1 min)
- Same judge/generator model (free-tier quota ~20 req/day on newest Flash).
- Small, single-domain corpus; comparative rather than absolute claims.

## Slide 9 — Conclusions (1 min)
- Ontology expansion **beats dictionary** significantly; helps relational reasoning,
  hurts exact-clinical queries.
- Recommendation: **selective** expansion per query category; equivalence-first.

---

## Likely Q&A + short answers

**Q: Why is the overall ontology-vs-baseline gain not significant?**
A: The pooled effect is small (d=0.10) because the large relational gains are dragged down
by the control category (−0.038) and hierarchy noise. The effect is real but conditional —
which is exactly the research finding.

**Q: How do you know it's not just better embedding luck?**
A: Controlled pipelines — identical retrieval/generation nodes, only expansion differs;
paired stats across the same 66 queries; temperature 0.0; deterministic expansion traces.

**Q: Why does dictionary expansion underperform?**
A: It adds terms without relational semantics and without per-query relevance, so it
dilutes precise queries (control −0.05) without the relational lift the ontology provides.

**Q: Is using the same model for judge and generator a problem?**
A: It reduces independence; mitigated by a blinded rubric and by concept-F1 being fully
objective. Full cross-model judging needs more quota than the free tier allows
(~20 req/day on other Flash models; ~1000 on the lite model).

**Q: What would you do next?**
A: Selective expansion (route by predicted category); corpus-relative relevance filter on
expanded terms to fix hierarchy noise; a larger multi-domain corpus; cross-model judge.

**Q: How much of this is your own work?**
A: All data pipelines, the ontology, the LangGraph orchestration, the eval harness,
experiments, and analysis. I hand-built/verified the ontology triples, the queries, and the
relevance judgments (spot-checked), and I can walk through any component live.

---

## Cheat sheet — numbers to remember
- 80 docs · 263 chunks · 347 triples · 66 queries · 6 categories · 6 pipelines
- Recall@5: Baseline 0.352, Dictionary 0.342, **Ontology 0.364**
- Ontology vs Dictionary: **p=0.015, d=0.295**; vs Baseline p=0.173
- Category Δ (Ont−Base): treatment +0.042, hierarchy +0.040, control **−0.038**
- Ablations R@5: equiv 0.371, props 0.367, full 0.364, hier 0.347
- Answers: concept-recall 0.807→0.881, judge-correct 0.667→0.788, F1≈0.572