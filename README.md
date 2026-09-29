# RAG-on-Ontology

**Ontology-Enhanced Retrieval-Augmented Generation for Medical Question Answering.**

A controlled experimental evaluation of whether ontology-based query expansion improves
retrieval and answer quality over (1) standard semantic retrieval and (2) a simple synonym
dictionary expansion, on a purpose-built medical corpus (Cardiovascular + Metabolic).

---

## Research Question

> Under what conditions (query types and relation types) does ontology-based query expansion
> improve retrieval and answer quality over standard semantic retrieval and simple dictionary
> expansion?

### Pipelines (differ only in query-expansion strategy)

| # | Pipeline | Expansion strategy |
|---|---|---|
| 1 | **Baseline** | No expansion — semantic (embedding) retrieval only |
| 2 | **Dictionary** | Synonym-dictionary expansion (`data/synonyms/synonym_dict.json`) |
| 3 | **Ontology** | Ontology traversal — equivalence, hierarchy (subclass), properties (symptom/treatment/diagnosis/related-condition) |
| 4–6 | Ablations | Ontology variants: equivalence-only, hierarchy-only, properties-only |

All pipelines share one retrieval node and one generation node, unified in a single
[LangGraph](https://langchain-ai.github.io/langgraph/) orchestration graph
(`src/orchestration/`).

---

## Key Results

### Retrieval (6 pipelines × 66 queries, Recall@5)

| Pipeline | Recall@5 | Recall@10 | Precision@5 | Hit@5 | nDCG@5 |
|---|---|---|---|---|---|
| 1 Baseline | 0.352 | 0.470 | 0.479 | 0.985 | 0.650 |
| 2 Dictionary | 0.342 | 0.480 | 0.476 | 1.000 | 0.639 |
| **3 Ontology (full)** | **0.364** | **0.495** | **0.512** | 1.000 | **0.658** |
| 4 Equivalence-only | 0.371 | — | — | — | — |
| 5 Hierarchy-only | 0.347 | — | — | — | — |
| 6 Properties-only | 0.367 | — | — | — | — |

- **Ontology vs Dictionary: p = 0.015 (significant), Cohen's d = 0.295** — ontology expansion
  significantly outperforms dictionary expansion on Recall@5.
- Ontology vs Baseline: p = 0.173 (n.s.), small positive effect (d = 0.10).
- **Category gains** (Ontology − Baseline, Recall@5): treatment_reasoning **+0.042**,
  disease_hierarchy **+0.040**, lay_terminology +0.012, symptom_reasoning +0.010, multi_hop +0.010;
  control_exact_clinical **−0.038** (expected harm on the control category).

### Answer quality (3 pipelines × 66 queries)

| Pipeline | Concept-F1 | Recall | Judge correct |
|---|---|---|---|
| 1 Baseline | 0.572 | 0.807 | 0.667 |
| 2 Dictionary | 0.573 | 0.806 | 0.682 |
| **3 Ontology** | 0.572 | **0.881** | **0.788** |

Ontology expansion raises answer concept-recall (+0.074) and LLM-judge correctness (+0.121)
while keeping F1 flat — answers become more complete at a small precision cost.

---

## Repository Layout

```
data/
  corpus/real/           68 PubMed abstracts
  corpus/synthetic/      12 gap-filling docs
  ontology/              medical_ontology.ttl (347 triples)
  synonyms/              synonym_dict.json (52 pairs)
  evaluation/            queries.json (66), relevance_judgments.json
  vectorstore/           ChromaDB persist dir + embedding cache
src/
  config.py              all configuration + model names
  rate_limiter.py        shared per-model API rate limiting
  corpus/                loading, chunking, embedding, vector store
  ontology/              builder, reasoner (+ reasoning traces), synonym expander
  pipelines/             baseline / dictionary / ontology-enhanced modules
  orchestration/         LangGraph: state, nodes, graph
  generation/            generator (Gemini)
  evaluation/            retrieval metrics, statistical tests, answer metrics
scripts/
  collect_pubmed.py      download & clean PubMed abstracts
  generate_synthetic_docs.py
  annotate_corpus.py     concept annotations (idempotent)
  build_vectorstore.py   chunk + embed + index
  create_evaluation_set.py
  run_experiments.py     retrieval experiments (resumable)
  run_answer_eval.py     answer-quality evaluation (resumable, judge backfill)
  generate_plots.py      plots (incl. trace_breakdown)
  generate_trace_report.py  reasoning-trace exhibit (results/trace_exhibits.md)
  orchestrate_demo.py    LangGraph demo
  live_demo.py           panel demo: 1 query × 3 pipelines, ground-truth verdict
results/
  metrics/               per-pipeline + summary JSON
  plots/                 overall_comparison, category_breakdown, ablation, answer_quality, trace_breakdown
  reasoning_logs/        ontology reasoning traces
  trace_exhibits.md      worked reasoning-trace examples per query category
docs/
  PROJECT_STATUS.md      status & execution plan
```

---

## Setup

```bash
# 1. Install with uv (or pip)
uv sync                 # Python >= 3.11

# 2. Configure API key (optional for retrieval-only demos)
cp .env.example .env    # set GOOGLE_API_KEY=<your Gemini API key>
```

**Running without an API key:** the built vector store (263 chunks) and the embedding
cache for all 66 evaluation queries are committed, so a fresh clone works out of the box:

```bash
uv run python -m scripts.live_demo --no-generate   # retrieval + verdict, zero API calls
```

A `GOOGLE_API_KEY` is required only for answer generation (the default `live_demo`
mode), the answer evaluation, and embedding **new** query texts — queries are embedded
with `gemini-embedding-2` (cache-first: `src/corpus/embedder.py`).

> ChromaDB rewrites `data/vectorstore/chroma.sqlite3` whenever it opens the store.
> If `git status` shows it modified after a run you didn't rebuild from, restore it
> with `git checkout -- data/vectorstore` before committing.

Models (see `src/config.py`): `gemini-embedding-2` (embeddings),
`gemini-3.1-flash-lite` (generation + judge). Free-tier quotas are per-model and
**~20 req/day for the newest Flash models**; `gemini-3.1-flash-lite` has a ~1000 req/day
budget. All runs are cached/resumable and a shared per-model rate limiter
(`src/rate_limiter.py`) prevents 429 bursts.

---

## Running

```bash
# Build corpus index (idempotent; caches embeddings)
uv run python -m scripts.build_vectorstore

# Retrieval experiments: 6 pipelines × 66 queries → results/metrics/experiment_summary.json
uv run python -m scripts.run_experiments

# Answer-quality evaluation: 3 pipelines × 66 queries → results/metrics/answer_summary.json
uv run python -m scripts.run_answer_eval          # judge ON (default)
uv run python -m scripts.run_answer_eval --no-judge

# Plots → results/plots/
uv run python -m scripts.generate_plots

# Live demo: 1 query through all 3 pipelines with ground-truth scoring,
# ontology reasoning trace, and generated answers
uv run python -m scripts.live_demo              # retrieval + generation (3 API calls)
uv run python -m scripts.live_demo --no-generate  # offline: retrieval + verdict only

# Quick demo through the unified LangGraph
uv run python -m scripts.orchestrate_demo
```

Every runner saves per-query results incrementally and **resumes automatically**, so a
quota/rate-limit interruption never loses progress.

---

## Methods (short version)

1. **Corpus:** 80 medical documents (68 PubMed abstracts + 12 synthetic), chunked to
   500 chars / 100 overlap → 263 chunks, embedded with `gemini-embedding-2`.
2. **Ontology:** purpose-built Cardiovascular + Metabolic ontology (347 triples) covering
   equivalence, subclass hierarchy, symptoms, treatments, diagnoses, related conditions.
3. **Query expansion:** each pipeline expands the query differently; retrieval uses the
   expanded query embedding; generation is identical across pipelines (temperature 0.0).
4. **Evaluation:** 66 queries in 6 categories (lay terminology, disease hierarchy, symptom
   reasoning, treatment reasoning, multi-hop, control-exact-clinical) with manual relevance
   judgments. Retrieval: Recall@5/@10, Precision@5, Hit@5, MRR, nDCG@5. Answer quality:
   objective concept-coverage F1 + an LLM judge (blinded rubric). Statistics: paired
   Wilcoxon tests, Cohen's d, Cliff's delta.

---

## Limitations

- LLM judge uses the same model family as the generator (quota constraint); the rubric is
  blinded and the primary answer metric (concept F1) is objective.
- Free-tier quota (~20 req/day/model on newest Flash) forced generation/judging onto
  `gemini-3.1-flash-lite`; results are per-pipeline-comparative and not absolute.
- Corpus and ontology are domain-scoped (Cardiovascular + Metabolic); results may not
  generalise to other medical domains.

See `docs/PROJECT_STATUS.md` for the full execution plan, results tables, and status.