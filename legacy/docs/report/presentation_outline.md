# Presentation Outline — Ontology-Enhanced RAG for Medical QA

*Minor project presentation · ~15 min · 16 slides · narrative arc: **Problem → Fault → Solution → Results → Conclusion***

Numbers cited are the committed experimental results (`results/metrics/`, git `248381a`).

---

## Slide 1 — Title
**Title:** Ontology-Enhanced Retrieval-Augmented Generation for Medical Question Answering
**Subtitle:** When documents don't speak the patient's language — a controlled study of knowledge-graph query expansion
**Byline:** [Your name] · Minor Project · [Date]

**Speaker notes (30 s):**
- Hello everyone. Today I'll present my minor project: an ontology-enhanced RAG system for medical QA.
- One-line summary: I built a medical knowledge graph and used it to expand user queries, so the retriever can match lay language ("blood pressure pill") to clinical literature ("ACE inhibitor").
- The presentation follows four stages: the problem, the root-cause fault, my solution, and the measured results.

---

## Slide 2 — Agenda
**Bullets:**
1. Motivation & The Problem
2. Root-Cause: Why plain RAG fails
3. The Solution: Ontology-based query expansion
4. Experimental setup (controlled comparison)
5. Results (retrieval + answers)
6. Limitations, Conclusion, Future work

**Speaker notes (30 s):**
- Quick map of the talk. The core message is on slides on Results — but the reason the numbers matter depends on the first three sections, so please bear with the setup.

---

## Slide 3 — The Problem: Medical QA at Scale
**Bullets:**
- Users ask in **lay language**: "blood pressure pill", "sugar in blood", "heart attack"
- Medical literature answers in **clinical terms**: "antihypertensive", "hyperglycemia", "myocardial infarction"
- Plain retrieval (RAG) is the standard way to ground answers in documents — but it fails on this **lexical gap**
- Two naive fixes also fail (we measured this): no expansion → misses clinical docs; blanket synonym expansion → introduces noise

**Speaker notes (1 min):**
- Frame the scenario: a patient asks a health assistant "What are the emergency signs of a heart attack?".
- The underlying documents talk about "myocardial infarction". A standard embedding search can still miss this if it doesn't know the terms are the same thing.
- This is the core of the problem: the *language* of the question and the *language* of the answer live in different vocabularies.

---

## Slide 4 — The Problem: Why this is hard (background)
**Bullets:**
- RAG = Retrieve-then-Generate: retriever finds relevant chunks, LLM writes an answer grounded in them
- Quality ceiling is set by **retrieval**: if the right document isn't retrieved, no generator can save the answer
- Medical synonyms, abbreviations, hierarchy ("hypertension ⊂ cardiovascular disease") and properties ("hypertension → treatedBy ACE inhibitor") are not obvious to a pure embedding model
- This motivates: can a **structured medical knowledge base** close the vocabulary gap?

**Speaker notes (1 min):**
- Briefly explain RAG for the non-specialists in the room.
- Emphasise the key idea: garbage-in-garbage-out applies to RAG — the answer can only be as good as the documents retrieved.
- Set up the question we will answer experimentally.

---

## Slide 5 — The Fault: Root-Cause Analysis of Baseline RAG
**Bullets:**
- **Fault 1 — No lexical bridging:** embedding-only retrieval doesn't reliably equate synonyms ("hypertension" vs "high blood pressure"); similarity is fuzzy, not semantic-exact
- **Fault 2 — No relational knowledge:** the system doesn't know hierarchies (stroke ⊂ CVD), symptoms, treatments — so it can't *reason* about related terms
- **Fault 3 — Naive expansion backfires:** dictionary expansion adds terms with no relevance filter, so precise clinical queries get *diluted* (we measured −5.0pp on control queries)

**Speaker notes (1.5 min):**
- This is the "diagnosis" slide — be explicit about the three defects.
- Fault 1: embeddings map words to vectors; two very different words can be near each other, and true synonyms can be far apart. Fuzzy, not exact.
- Fault 2: even if you solve synonyms, there's no *structure* — you can't traverse "disease → symptom → test" the way a clinician reasons.
- Fault 3: and the obvious fix (just add synonyms) introduces noise, which hurts the queries that were already precise.
- Key phrase to land: *"The baseline has no structured medical knowledge — it sees words, not concepts."*

---

## Slide 6 — The Fault: Evidence the baseline is limited
**Bullets:**
- Baseline Recall@5: **35.2%** — the correct document is missed ~2/3 of the time
- Dictionary expansion does **not** fix it: **34.2%** (slightly worse overall)
- Hierarchy-reasoning queries (disease taxonomy) are worst for baseline: **22.7%**
- Conclusion: the *approach* (no structured knowledge) is the defect, not the data

**Speaker notes (1 min):**
- Show that the problem is not bad data but bad *approach*.
- On hierarchy queries the baseline retrieves the right material only ~1 in 4 times.
- Dictionary expansion, the "easy fix", doesn't help and can hurt — this justifies building something more principled.

---

## Slide 7 — The Solution: Overview
**Bullets:**
- **What:** a purpose-built medical ontology (Cardiovascular + Metabolic) used to expand queries before retrieval
- **How:** three controlled pipelines that differ *only* in expansion strategy — baseline, dictionary, ontology
- **Key design choices:**
  - One shared LangGraph orchestration (same retrieval + generation nodes)
  - Deterministic, explainable expansion traces (query → concept → relation → terms)
  - Blinded LLM judge + objective concept-coverage metric for answers
- **Why it fixes the fault:** expansion now encodes *structured clinical relationships*, not just word lists

**Speaker notes (1.5 min):**
- Transition slide: Problem → Solution.
- The core idea: instead of hoping the embedding model "just knows" that hypertension = high blood pressure, we *tell* the system through a knowledge graph.
- Stress the controlled design — three pipelines differ in only one component. That is what makes the experiment trustworthy.
- Preview the explainability angle: we can show exactly why a query was expanded.

---

## Slide 8 — The Solution: The Medical Ontology
**Bullets:**
- RDF/Turtle knowledge graph, **347 triples**
- Six relation types:
  - **Equivalence** (12) — Hypertension ≡ High Blood Pressure
  - **Hierarchy** (61) — Myocardial Infarction ⊂ Acute Coronary Syndrome
  - **hasSymptom** (37) · **treatedBy** (42) · **diagnosedBy** (14) · **relatedCondition** (12)
- 80-document corpus (68 PubMed abstracts + 12 synthetic) → 263 chunks
- Ontology and corpus are domain-scoped: Cardiovascular + Metabolic

**Speaker notes (1 min):**
- This is the knowledge asset at the heart of the project.
- Give two concrete examples with the relation arrows — they make the ontology tangible.
- Note it's purpose-built and hand-verified — this is "my own work" territory, good for Q&A.

---

## Slide 9 — The Solution: System Architecture (LangGraph)
**Bullets:**
- Single LangGraph state machine, conditional routing
- START → [expansion node] → shared retrieve → shared generate → END
  - Pipeline 1: **no expansion**
  - Pipeline 2: **dictionary expansion** (52 synonym pairs)
  - Pipeline 3: **ontology traversal** (equivalence + hierarchy + properties)
- Ablations toggle individual relation types on Pipeline 3
- Result: identical retrieval/generation for every pipeline → clean controlled comparison

**Speaker notes (1.5 min):**
- Show the flow. Emphasise: three pipelines share the SAME retrieve and generate nodes — only expansion differs.
- This single graph is what lets us attribute any difference in results to the expansion strategy and nothing else.
- Mention the ablation switches as a bonus: we can turn off just equivalence, just hierarchy, just properties.

---

## Slide 10 — The Solution: From Query to Expansion (Trace)
**Bullets (example — real system output):**
- Query: "What causes **high blood pressure**?"
- Match: high blood pressure → **HighBloodPressure**
- Expansion (equivalentClass): HighBloodPressure → **Hypertension**
- Expanded terms used for retrieval: `Hypertension`
- Same pipeline on a hierarchy query fires subclass/ancestor/symptom/treatment relations with full trace logged

**Speaker notes (1 min):**
- Walk one example trace so the audience sees the mechanism concretely.
- This trace is logged per query (`results/trace_exhibits.md`) — full explainability.
- Contrast: the baseline would search the literal phrase and hope; the ontology *knows* the two phrases denote the same concept.

---

## Slide 11 — Evaluation Setup (controlled)
**Bullets:**
- **66 queries, 6 categories** (12/12/12 + 10×3): lay terminology, disease hierarchy, symptom reasoning, treatment reasoning, multi-hop, exact-clinical control
- **Manual relevance judgments** for all 66 queries (ground truth)
- Retrieval metrics: Recall@5/@10, Precision@5, Hit@5, MRR, nDCG@5
- Answer metrics: **objective concept-coverage F1** + **blinded LLM judge** (correctness + score)
- Statistics: paired Wilcoxon signed-rank, Cohen's d, Cliff's delta
- Models: Gemini embeddings + `gemini-3.1-flash-lite` generation (temperature 0, identical for all pipelines)

**Speaker notes (1 min):**
- Emphasise the scientific hygiene: paired design (same 66 queries per pipeline), manual ground truth, two families of answer metrics (one fully objective).
- The control category (exact-clinical) is deliberate: expansion *should* help relational queries and ideally not harm precise ones — we test both directions.

---

## Slide 12 — Results 1: Retrieval (overall)
**Bullets (Recall@5):**
| Pipeline | Recall@5 | Recall@10 | Precision@5 | nDCG@5 |
|---|---|---|---|---|
| Baseline | 35.2% | 47.0% | 47.9% | 65.0% |
| Dictionary | 34.2% | 48.0% | 47.6% | 63.9% |
| **Ontology** | **36.4%** | **49.5%** | **51.2%** | **65.8%** |
- **Ontology vs Dictionary: p = 0.015 (significant), Cohen's d = 0.295**
- Ontology vs Baseline: p = 0.173 (positive, not significant at α=0.05)

**Speaker notes (1.5 min):**
- Present the table left-to-right.
- The headline: ontology expansion significantly beats dictionary expansion on Recall@5, with a medium effect size (d ≈ 0.3).
- Be honest: vs baseline it's positive but not significant — explain that the pooled number hides a strong conditional pattern (next slide).
- Also note Precision@5 improves (+3.3pp vs baseline) — the ontology isn't just adding recall, it sharpens precision too.

---

## Slide 13 — Results 2: The "When" story (category analysis)
**Bullets (Recall@5, Ontology − Baseline):**
- Treatment reasoning: **+4.2pp**
- Disease hierarchy: **+4.0pp**
- Lay terminology: +1.2pp · Symptom reasoning: +1.0pp · Multi-hop: +1.0pp
- **Control (exact clinical): −3.8pp** (expansion hurts precise queries — expected, by design)

**Speaker notes (1.5 min):**
- This is the most important slide: *when* does the solution help?
- The ontology helps exactly where relational knowledge is needed (taxonomy, treatment chains) and — as hypothesised — hurts where the query is already precise.
- This turns "is it better?" into "it's better under these conditions, and we can prove it".
- Practical implication: use expansion selectively.

---

## Slide 14 — Results 3: Ablations + Answer Quality
**Bullets:**
- **Ablations (Recall@5):** Equivalence-only **37.1%** · Properties-only 36.7% · Full ontology 36.4% · Hierarchy-only 34.7% · Baseline 35.2%
  - *Equivalence is the workhorse; hierarchy needs guarding (over-expansion noise)*
- **Answer quality (66 judged per pipeline):**
  | Pipeline | Concept-F1 | Concept-Recall | Judge correct |
  |---|---|---|---|
  | Baseline | 57.2% | 80.7% | 66.7% |
  | Dictionary | 57.3% | 80.6% | 68.2% |
  | **Ontology** | **57.2%** | **88.1%** | **78.8%** |
- Ontology answers are **more complete** (+7.4pp concept-recall) and **judged correct more often** (+12.1pp), with no loss in F1

**Speaker notes (2 min):**
- Two messages: (1) which mechanism drives the gain, (2) does retrieval translate to better answers?
- Ablations: equivalence expansion alone is the single best configuration — it directly fixes the synonym fault. Hierarchy alone is noisy.
- Answers: concept-F1 is flat, but recall and judge-correctness jump. Interpretation: the ontology yields more complete, more correct answers — F1 alone understates the win.
- Land the punchline: *"Expansion trades a little precision for a lot of completeness, and the judge prefers the ontology answers."*

---

## Slide 15 — Limitations
**Bullets:**
- Domain-scoped: Cardiovascular + Metabolic only; 80 documents is a small corpus
- LLM judge uses the same model family as the generator (free-tier quota ~20 req/day on newer Flash models) — mitigated by blinded rubric + objective concept-F1
- Absolute metrics are model-dependent; conclusions are comparative (pipeline vs pipeline)
- Hierarchy expansion adds noise — needs a relevance filter in future
- Free-tier quotas shaped model choices (documented in report)

**Speaker notes (45 s):**
- Honesty builds credibility — list the limits before the conclusion.
- Reassure: the controlled design and objective metric mean the *comparative* claims hold.

---

## Slide 16 — Conclusion & Future Work
**Bullets:**
- **Conclusion:**
  - Ontology expansion **significantly** outperforms dictionary expansion (p = 0.015, Recall@5)
  - Helps relational-reasoning queries (+4pp hierarchy/treatment), hurts exact-clinical queries (−3.8pp) — expansion should be **selective**
  - Answers are more complete and judged more correct (+12.1pp) at no F1 cost
- **Future work:**
  - Route queries by predicted category → selective expansion
  - Relevance filter on expanded terms to tame hierarchy noise
  - Larger multi-domain corpus · cross-model judge

**Speaker notes (1 min):**
- Recap the three claims with the headline numbers.
- Future work is short and actionable — signals the project is a foundation, not a dead-end.
- Thank the audience; invite questions.

---

## Backup slides (optional, only if asked)
- **B1 — Full metric table** (all 6 pipelines × all metrics)
- **B2 — Reasoning-trace exhibit** (per-category worked examples, `results/trace_exhibits.md`)
- **B3 — Reproducibility** (commands: build_vectorstore → run_experiments → run_answer_eval → generate_plots)
- **B4 — Quota/engineering notes** (rate limiter, resumable runners, embedding cache)

---

## Delivery tips
- Keep slides 3–6 (Problem/Fault) tight — the audience's key takeaways live in slides 12–14.
- Use the real trace example (Slide 10) as a "show, don't tell" moment.
- For Q&A, be ready with: why overall gain isn't significant (conditional effect + control drag), why dictionary underperforms, judge/generator model choice, and what "selective expansion" would look like.
