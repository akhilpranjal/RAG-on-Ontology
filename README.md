# OntoGate-RAG

**Selective biomedical question answering on PubMedQA.** The system retrieves
evidence, links the question to a MeSH + Hetionet knowledge graph, and decides
whether to answer or to say *"the evidence is insufficient"*.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

## Headline result

On the test split (85 judged questions, same model, same passages for every
arm):

| System | Coverage | Accuracy |
|---|---|---|
| Always answer | 100% | 58.8% |
| Ontology coverage gate | 70.6% | 63.3% |
| **Judge + self-abstention gate** | **61.2%** | **76.9%** |

The gate nearly doubles accuracy by declining to answer 39% of the questions.
Abstentions are never counted as correct.

Three findings from the same experiment matter as much as the headline:

1. **The judge's own "maybe" is the best signal.** The numeric sufficiency score
   gives AUC 0.705; adding the fact that the judge answered "maybe" gives 0.747,
   and a zero-training rule matches the fitted gate exactly.
2. **The ontology is a weak accuracy gate but a good cost filter.** Coverage
   alone gives AUC 0.547 and saturates at 1.0 for 82.5% of questions. Used as a
   free pre-screen, it removes **23.5% of judge calls** for a 1.9-point accuracy
   loss.
3. **Ontology reranking and query expansion do not help.** Retrieval is already
   saturated (recall@10 = 0.970), so there is nothing to improve.

Full tables, CIs and threats to validity: [docs/results.md](docs/results.md).

## How it works

```
question
  -> dense retrieval (FAISS, top-10 abstracts)
  -> ontology linking (MeSH 2026 + Hetionet, 683k triples)
  -> concept coverage  --(very low)--> ABSTAIN, no API call
  -> LLM evidence judge (one call: sufficient? answer? score?)
  -> gate: judge says "maybe" -> ABSTAIN
           fused score below dev threshold -> ABSTAIN
           otherwise -> ANSWER
```

The ontology is not decoration. It is used to link question terms to concepts,
to measure whether the evidence covers those concepts, to test whether a single
sentence *relates* two question concepts, and to skip paid judge calls.

Details: [docs/architecture.md](docs/architecture.md).

## Quickstart

```powershell
uv sync
Copy-Item .env.example .env    # add GOOGLE_API_KEY
```

Build the assets (once):

```powershell
uv run python scripts/eg_prepare_data.py       # PubMedQA + splits
uv run python scripts/eg_build_ontology.py     # MeSH + Hetionet -> TTL
uv run python scripts/eg_build_index.py        # FAISS index
uv run python -m evidence_gate.specialty       # MeSH specialty tags
uv run python -c "from evidence_gate.coverage import build_passage_concepts; build_passage_concepts()"
```

Run the experiment (resumable, one judge call per question):

```powershell
uv run python scripts/eg_run_sweep.py --split dev  --include-own
uv run python scripts/eg_run_sweep.py --split test --include-own
```

Analyse (free, deterministic):

```powershell
uv run python scripts/eg_analyze.py
uv run python scripts/eg_eval_retrieval.py --split dev --limit 200
uv run python scripts/eg_paired_baseline.py
```

Demo one question:

```powershell
uv run python scripts/eg_demo.py --split test
uv run python scripts/eg_demo.py --question "Does metformin help Alzheimer's disease?"
```

## Repository layout

```
evidence_gate/          library code (retrieval, ontology, coverage, judge, gate)
scripts/                one entry point per stage (eg_*.py)
docs/                   architecture, dataset, experiments, results, viva, issues
results/metrics/        final_report.{md,json}, questions.csv, retrieval metrics
results/plots/          risk-coverage, gate AUC, coverage saturation
legacy/                 earlier designs (symbolic router, NLI gate), not used
data/                   downloaded/derived assets (git-ignored)
```

## Data sources

* **PubMedQA** - Jin et al., EMNLP 2019. 1,000 expert-labelled questions.
* **MeSH 2026** - U.S. National Library of Medicine, public domain. 31,110
  descriptors, 65,242 hierarchy edges.
* **Hetionet v1.0** - Himmelstein et al., eLife 2017, CC0. Six clinical
  relations, 147,591 edges.

No synthetic ontology content and no LLM-generated graph edges are used.
Provenance and licences are recorded in
`data/ontogate/ontology_provenance.json`.

## Honest limitations

* The test set has **85** judged questions because of free-tier API quotas. The
  sweep is resumable; extending it changes no fitted parameter.
* The headline compares against the *same model's* judge-prompt baseline. Against
  an earlier plain-prompt RAG run on the shared 50 questions the gain is +3.1
  points (p = 1.0), not +18. Both are reported.
* The corpus contains three abstracts per question, so retrieval saturates. This
  is the standard PubMedQA open-book setting, not a modelling achievement.
* One judge model (`gemini-3.1-flash-lite`) and one prompt.

## Documentation

| | |
|---|---|
| [architecture.md](docs/architecture.md) | design, modules, data flow, decisions |
| [dataset.md](docs/dataset.md) | PubMedQA, splits, specialties, the graph |
| [experiments.md](docs/experiments.md) | research questions, protocol, reproduction |
| [results.md](docs/results.md) | every table, interpretation, validity threats |
| [viva.md](docs/viva.md) | likely questions and short answers |
| [issues.md](docs/issues.md) | 16 real problems and their fixes |
| [explainers.md](docs/explainers.md) | every concept in plain language |
| [paper_notes.md](docs/paper_notes.md) | contributions, related work, claims map |
