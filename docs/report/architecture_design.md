# AdaOnto-RAG — Pre-registered Architecture Design (Experiment 2)

**Status: DESIGN FROZEN — written before any Experiment-2 run.**
This document fixes the architecture, router rules, and constants *before* the new
pipelines are executed, so the comparison against Pipelines 1–3 cannot be tuned
on the test queries. Any deviation must be logged in the results section.

## 1. Name and one-line claim

**AdaOnto-RAG: Adaptive Ontology-Gated Retrieval with Diversity Reranking.**
A RAG pipeline that (a) classifies each query's intent with a deterministic
symbolic router, (b) applies only the ontology relation families that intent
requires (or no expansion at all), and (c) reranks candidates with a
redundancy-aware MMR filter. It is evaluated on the *same* 66-query dataset
against Pipelines 1–3 with the *same* metrics and statistics — the architecture
is new, the testbed is fixed.

## 2. Motivation (evidence from Experiment 1)

| Observation (measured) | Architectural consequence |
|---|---|
| Ontology helps treatment (+4.2pp R@5) and hierarchy (+4.0pp) but hurts precise control queries (−3.8pp) | Expansion must be **selective**, gated by query intent |
| Equivalence-only ablation is best single family (37.1% R@5); hierarchy-only is noisy (34.7%) | Intent should select **relation families**, never blanket traversal |
| Top-5 lists contain duplicate chunks of the same doc (e.g. beta-blocker query → 5 chunks, 2 unique docs) | Retrieval must enforce **diversity** (doc dedup + MMR) |
| Dictionary (flat synonyms) underperforms (34.2%) | Keep **typed relations**, not word lists |

## 3. Architecture

```
query
  │
  ▼
┌──────────────┐   query text + ontology labels + synonym lay terms
│    ROUTER    │   (deterministic, zero API calls, no training)
│ (intent →    │
│  mask)       │
└──────┬───────┘
       │  mask ∈ {NONE, EQUIV, HIER, TREAT, SYMP, FULL}
       ▼
┌──────────────────┐
│ SELECTIVE        │  reasoner.expand_query with per-family flags
│ EXPANSION        │  (same OntologyReasoner as Pipeline 3)
└──────┬───────────┘
       │  expanded query string
       ▼
┌──────────────────┐
│ DENSE RETRIEVE   │  top-20 chunks (POOL_SIZE = 20), cosine
│ (ChromaDB)       │
└──────┬───────────┘
       │  20 candidates + distances
       ▼
┌──────────────────┐
│ MMR DIVERSITY    │  λ = 0.5, hard doc_id dedup
│ RERANK → top-k   │  (embeddings + IDs only — no label signals)
└──────┬───────────┘
       ▼
┌──────────────────┐
│ TRACE-GROUNDED   │  same generator as all pipelines (temp 0.0)
│ GENERATION       │  + ontology reasoning context when expanded
└──────────────────┘
```

## 4. Router rules (FROZEN, evaluated in order)

Signals (case-insensitive substring on query text):
- **LAY**: any lay term from `data/synonyms/synonym_dict.json` present.
- **HIER**: regex/word cues `types of|kinds of|forms of|fall under|classified as|categorized
  under|categor|sub-condition|subcondition|complication|associated with|related to|
  manifestations` OR group pattern `what <word> (diseases|disorders|conditions|arrhythmias)`.
- **TREAT** (treatment/diagnosis cues): `treat|medication|medicine|drug|prescrib|therap|
  procedure|surgical|surgery|relief|dos|management|control|diagnos|test|assess|evaluat|
  detect|criteria`.
- **SYMP**: an ontology Symptom-subclass label present AND a direction word
  (`what|which|cause|present|produce|indicate|sign|symptom`) present.
- **PRECISE**: matched ontology concepts include ≥1 Treatment/DiagnosticTest-class
  concept AND ≥1 Disease-class concept (transitive subClassOf), AND no LAY token.
  Rationale: the query already names both sides of the relation — expansion adds noise
  (standard selective-expansion finding; cf. MeSH/ATM literature).

Order and masks (`(equiv, hier, props)` flags to the shared reasoner):
1. PRECISE → **NONE** `(F,F,F)` — raw query, pure dense retrieval.
2. LAY present → +any cue-group → **FULL** `(T,T,T)`; else **EQUIV** `(T,F,F)`.
3. HIER cues/pattern → **HIER** `(T,T,F)`.
4. ≥2 distinct cue-groups among {TREAT, SYMP, HIER} → **FULL** `(T,T,T)` (multi-hop).
5. TREAT cues → **TREAT** `(T,F,F→props)` = `(equiv=T, hier=F, props=T)`.
6. SYMP → **SYMP** `(equiv=T, hier=F, props=T)`.
7. Default → **EQUIV** `(T,F,F)` (safest single family per ablations).

Rationale for each mapping (mechanism matches intent by definition):
lay≈equivalence bridging; types-of≈downward hierarchy; treatment/diagnosis≈treatedBy/
diagnosedBy properties; symptom→disease≈inverse hasSymptom; precise≈no expansion.

## 5. MMR rerank (FROZEN constants)

- Candidate pool: **POOL_SIZE = 20** chunks.
- Relevance: min-max normalized negative cosine distance over the pool.
- Similarity: cosine between stored chunk embeddings (local fetch, no API).
- **λ = 0.5** (standard MMR default; fixed, not tuned).
- Hard constraint: skip chunks whose `doc_id` is already selected.
- Greedy select until `top_k`; if the pool exhausts first, fill remainder ignoring
  dedup (documented fallback; expected to never trigger with pool 20 → 10).

## 6. Experiment-2 protocol (FROZEN)

- Same 66 queries, same judgments, same metrics code, same stats code
  (`full_comparison`: Wilcoxon + Cohen's d + Cliff's delta, α = 0.05).
- **Primary metric: Recall@5.** Comparisons: adaptive-full vs P1, vs P2, vs P3.
- Component ablations (same protocol):
  - `selective-only` (router + selective expansion, no MMR),
  - `mmr-only` (no expansion, dense + MMR),
  - `full` (router + selective + MMR).
- Fairness guardrails: NO annotation-tag or judgment signals anywhere in the
  retrieval path (provenance: judgments derive from concept tags —
  `create_evaluation_set.py:113-141` — so tag-based reranking would be circular
  and is explicitly excluded). Router uses query text + ontology/dictionary only.
- Result files: `pipeline_4_adaptive_{full,selective,mmr}_results.json`,
  `pipeline_4_adaptive_full_answers.json`, summary `adaptive_summary.json`.
  `experiment_summary.json` (Experiment 1) is NOT modified.
- Answer eval for `full` only, and only if retrieval wins (same generator +
  judge + concept-F1 protocol as Experiment 1).

## 7. Known limitations (to report honestly)

- Single 66-query set, no held-out split (design frozen a priori as mitigation).
- Substring concept matcher quirks (e.g. generic words can match root classes).
- Same-model judge limitation inherited from Experiment 1.
- Reasoner expansion is single-hop from matched concepts (no chaining).
