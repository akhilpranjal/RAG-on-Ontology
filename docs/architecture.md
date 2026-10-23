# Architecture

## One-paragraph summary

A user asks a biomedical yes/no question. The system retrieves ten candidate
abstracts from the PubMedQA corpus with a dense retriever. It then links the
question to concepts in a MeSH + Hetionet knowledge graph and measures how much
of the question's concept content those abstracts actually cover. If the
coverage is very low, the system abstains immediately **without paying for an
LLM call**. Otherwise it asks a single LLM judge to read the abstracts and
return three things: whether the evidence is sufficient, a yes/no/maybe answer,
and a sufficiency score. Finally a small gate decides whether to answer or
abstain. The gate is a logistic regression fitted on the development split and
uses two signals: the judge's sufficiency score and whether the judge itself
answered "maybe".

## Data flow

```
question
   |
   |-- DenseRetriever (multi-qa-MiniLM-L6-cos-v1, FAISS, top-10)
   |        -> passages with similarity scores
   |
   |-- OntologyGraph (MeSH 2026 + Hetionet v1.0, 683k triples)
   |        -> linked question concepts (uri, label, kind)
   |
   |-- ConceptCoverageScorer (local, zero API)
   |        -> coverage, coverage_top3, idf-weighted, relation coverage,
   |           heading coverage, sentence-level pair coverage
   |
   |-- GATE STAGE 1: ontology screen
   |        coverage_top3 <= 0.5  ->  ABSTAIN (no API call)
   |
   |-- LLMEvidenceJudge (one Gemini call per question)
   |        -> sufficient: yes/no/partial
   |           answer: yes/no/maybe
   |           sufficiency_score: 0 / 0.5 / 1
   |
   |-- GATE STAGE 2: decision
   |        judge answer == "maybe"          -> ABSTAIN (self-abstention)
   |        fused score < dev threshold      -> ABSTAIN
   |        otherwise                        -> ANSWER
   |
   `-- answer or explicit abstention
```

## Modules

| Module | Responsibility |
|---|---|
| `evidence_gate/config.py` | Paths, model names, retrieval settings, API settings |
| `evidence_gate/api.py` | Gemini client: disk cache, rate limiting, fail-fast on quota errors |
| `evidence_gate/retriever.py` | Sentence-transformers + FAISS dense retrieval |
| `evidence_gate/ontology.py` | TTL graph, alias-aware label linking, one-hop relations |
| `evidence_gate/reasoner.py` | Intent detection (treatment/cause/diagnosis/...) from cue patterns |
| `evidence_gate/coverage.py` | Question-concept coverage of retrieved passages; offline passage concept index |
| `evidence_gate/specialty.py` | MeSH tree classification of each question (analysis only) |
| `evidence_gate/llm_judge.py` | The evidence judge prompt and JSON parser |
| `evidence_gate/selective.py` | Risk-coverage metrics, AURC, thresholding, logistic selector, bootstrap CIs |
| `evidence_gate/evaluate.py` | JSONL I/O, accuracy, AUC, McNemar, bootstrap |

Scripts:

| Script | Purpose | API calls |
|---|---|---|
| `scripts/eg_prepare_data.py` | Download PubMedQA, build the 3000-abstract corpus and splits | 0 |
| `scripts/eg_build_ontology.py` | Build `ontology.ttl` from MeSH XML + Hetionet | 0 |
| `scripts/eg_build_index.py` | Embed the corpus, build the FAISS index | 0 |
| `scripts/eg_run_sweep.py` | One judge call per question; stores all signals; resumable | 1/question |
| `scripts/eg_backfill_sweep.py` | Convert an archived run into sweep rows | 0 |
| `scripts/eg_eval_retrieval.py` | Dense vs ontology-reranked retrieval metrics | 0 |
| `scripts/eg_analyze.py` | Fit gates on dev, evaluate on test, write report and plots | 0 |
| `scripts/eg_paired_baseline.py` | Paired comparison against the plain-prompt baseline | 0 |
| `scripts/eg_demo.py` | End-to-end demo of one question | 0 or 1 |

## The key design decision: one API call buys every comparison

The free-tier LLM quota is the binding constraint. A conventional ablation
matrix (five gates times two splits times 500 questions) would need thousands of
calls. Instead `eg_run_sweep.py` makes **one** judge call per question and stores
everything needed to reconstruct every arm:

* the judge's sufficiency label, answer and score,
* the ontology coverage features,
* the retrieval similarities,
* the retrieved passages.

Every comparison in `eg_analyze.py` is therefore **paired**: the same questions,
the same passages, the same model response. Differences between gates cannot be
explained by different samples or different prompts. The gates themselves are
deterministic functions of the stored signals.

The cost is that the system cannot compare two *different prompts* on the same
budget. That limitation is stated in the results.

## Why these two signals

**LLM judge.** Asking a model "is this evidence enough to answer?" is a strong
and cheap sufficiency signal. The sweep shows it is the best single gate
(AUC 0.70 on test) and that its answer field carries extra information: when the
judge answers "maybe" it is telling you it does not know, which is exactly the
quantity the gate is trying to estimate.

**Ontology coverage.** The judge costs money and can hallucinate. The ontology
is free, auditable and grounded in curated vocabulary. In principle, measuring
how much of the question's concept content the evidence covers is a model-free
proxy for sufficiency. In practice it is a *weak* proxy (AUC 0.55) because
document coverage saturates: the question's terms almost always appear somewhere
in ten abstracts. It remains useful as a pre-screen, where it removes a quarter
of the judge calls with almost no accuracy loss.

## What the ontology is used for, precisely

The user-facing question "where is the ontology actually used?" has four
concrete answers in this codebase:

1. **Question linking** (`OntologyGraph.link`): multi-word alias matching over
   161,041 normalized labels from MeSH descriptors and Hetionet entities.
2. **Coverage** (`ConceptCoverageScorer`): whether the question's linked
   concepts appear in the retrieved passages, weighted by inverse document
   frequency so that common concepts count less.
3. **Relational sufficiency**: does any sentence contain *two* question concepts
   at once, and does it contain an intent cue (e.g. "treats")? This tests
   whether the evidence *relates* the concepts rather than merely mentioning
   them.
4. **Cost control**: the coverage score is a free screen in front of the paid
   judge.

The ontology is **not** used for query expansion or reranking in the final
system, because experiments showed both hurt (see `results.md`).

## Graph construction

* **MeSH 2026** (`desc2026.xml`): 31,110 descriptors, 65,242 hierarchy edges.
  Each descriptor becomes a node typed by its tree letter (Disease, Chemical,
  Anatomy, ...). Tree numbers become `rdfs:subClassOf` edges.
* **Hetionet v1.0**: six relation types kept (`presents`, `localizes`,
  `treats`, `resembles`, `palliates`, `causesSideEffect`), 147,591 edges.
  `causesSideEffect` alone is 138,944 edges, which is why it dominates the
  triple count.
* Total: 683,340 triples, 36,840 nodes with edge data, 36,557 edge sources.
* No LLM is used anywhere in graph construction. Every node and edge comes from
  a published, citable source with a recorded licence in
  `data/ontogate/ontology_provenance.json`.

## Reproducibility

All randomness is seeded (`SPLIT_SEED = 42`). The judge client caches every
response on disk, keyed by the exact prompt and model. Re-running the analysis
is free. Re-running the sweep after a quota reset resumes where it stopped.
