# OntoGate-RAG documentation

OntoGate-RAG decides **whether to answer** a biomedical question, and if it
answers, **tells you how much evidence it had**. The gate is built from two
signals: an LLM evidence judge and a concept-coverage score computed over a
curated MeSH + Hetionet knowledge graph.

Start here:

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | System design, modules, data flow, key decisions |
| [dataset.md](dataset.md) | PubMedQA, the corpus, splits, specialties, the ontology |
| [experiments.md](experiments.md) | Research questions, protocol, how to reproduce everything |
| [results.md](results.md) | Every table, plus what the numbers mean and do not mean |
| [viva.md](viva.md) | Likely questions with short, defensible answers |
| [issues.md](issues.md) | Real problems hit during the project and how they were solved |
| [explainers.md](explainers.md) | Plain-language explanations of every concept used |
| [paper_notes.md](paper_notes.md) | Contributions, related-work outline, claims-to-evidence map |

## TL;DR

* Selective accuracy on the test split rises from **58.8%** (always answer) to
  **76.9%** at **61.2% coverage** (+18.1 points). Same model, same questions,
  same retrieved passages: a fully paired comparison.
* The signal that does the work is the LLM judge's **own "maybe" answer**.
  Simply abstaining whenever the judge says "maybe" reproduces the learned
  gate without training.
* The ontology is a **weak standalone gate** (AUC 0.55) and its document-level
  coverage **saturates** (82.5% of questions are at 1.0). Its real value is
  cheaper: as a **free pre-screen** it removes 23.5% of judge calls at a cost
  of 1.9 accuracy points.
* Ontology-based **reranking does not help** retrieval (recall@10 is already
  0.970) and ontology-based query expansion **hurts**.

The negative results are part of the contribution: they show exactly where a
knowledge graph is and is not worth its cost in a selective RAG pipeline.
