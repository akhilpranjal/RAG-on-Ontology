# References

Grouped by how they are used in this project. All links verified.

## 1. Foundational: Retrieval-Augmented Generation

1. **Lewis et al. (2020), "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", NeurIPS 2020.**
   https://arxiv.org/abs/2005.11401
   *Cite for:* the RAG paradigm itself (retrieve → generate, parametric + non-parametric memory).

2. **Gao et al. (2023), "Retrieval-Augmented Generation for Large Language Models: A Survey".**
   https://arxiv.org/abs/2312.10997
   *Cite for:* Naive/Advanced/Modular RAG framing; "query optimization" (your expansion step) as a standard RAG component.

## 2. Graph / Knowledge-Graph RAG (closest related work)

3. **Han et al. (2024), "Retrieval-Augmented Generation with Graphs (GraphRAG)".**
   https://arxiv.org/abs/2501.00309
   *Cite for:* survey position of GraphRAG — retrieving over structured relational knowledge instead of flat chunks.

4. **Peng et al. (2024), "Graph Retrieval-Augmented Generation: A Survey".**
   https://arxiv.org/abs/2408.08921
   *Cite for:* formalization of graph-based RAG workflows.

5. **Zhu et al. (2025), "Knowledge Graph-Guided Retrieval Augmented Generation", NAACL 2025.**
   https://aclanthology.org/2025.naacl-long.449.pdf
   *Cite for:* graph-guided expansion of retrieved chunks vs. plain semantic retrieval.

## 3. Medical / Biomedical RAG (your domain)

6. **(2025), "Retrieval-Augmented Generation in Biomedicine: A Survey of Technologies, Datasets, and Clinical Applications".**
   https://arxiv.org/abs/2505.01146
   *Cite for:* state of biomedical RAG; knowledge-graph RAG in medicine; medically grounded evaluation.

7. **Kim et al. (2025), "Rethinking Retrieval-Augmented Generation for Medicine: A Large-Scale, Systematic Expert Evaluation and Practical Insights".**
   https://arxiv.org/abs/2511.06738
   *Cite for:* **motivation** — only 22% of top-16 passages relevant; retrieval is the failure point in medical RAG; evidence filtering and *query reformulation* improve results. Directly justifies your focus on query expansion.

## 4. Ontology-Based Query Expansion (your core method)

8. **Lu, Kim, Raghavan, Wilbur, Zahm (2009), "Evaluation of Query Expansion Using MeSH in PubMed", Journal of Biomedical Informatics 42(2).**
   https://pmc.ncbi.nlm.nih.gov/articles/PMC2747526
   *Cite for:* the classic result that ontology/thesaurus expansion (MeSH) improves biomedical retrieval — and that gains are recall-favoring with possible precision costs (mirrors your control-category drop).

9. **Al Nazi et al. (2025), "Ontology-Guided Query Expansion for Biomedical Document Retrieval using Large Language Models" (BMQExpander).**
   https://arxiv.org/abs/2508.11784
   *Cite for:* most recent direct prior work — UMLS-driven ontology-aware expansion; report your controlled comparison against its philosophy (your dictionary baseline ≈ synonym-only expansion).

## 5. Biomedical Ontologies (lineage of your ontology)

10. **Bodenreider (2004), "The Unified Medical Language System (UMLS): integrating biomedical terminology", Nucleic Acids Research 32(suppl_1).**
    https://academic.oup.com/nar/article/32/suppl_1/D267/2505235
    *Cite for:* concept/relation integration (synonyms ↔ concepts) — the model your 347-triple ontology follows.

11. **Smith et al. (2007), "The OBO Foundry: coordinated evolution of ontologies to support biomedical data integration", Nature Biotechnology 25(11).**
    https://pmc.ncbi.nlm.nih.gov/articles/PMC2814061 (DOI: 10.1038/nbt1346)
    *Cite for:* principles of well-formed biomedical ontologies (typed relations, hierarchy) — when asked how your ontology "should" be designed.

## 6. Medical QA datasets (framing / benchmarking)

12. **Jin et al. (2020), "What Disease does this Patient Have? A Large-scale Open Domain Question Answering Dataset from Medical Exams" (MedQA).**
    https://arxiv.org/abs/2009.13081 — published version: https://www.mdpi.com/2076-3417/11/14/6421
    *Cite for:* medical QA benchmark landscape; retrieval-then-comprehension baselines.

13. **Jin et al. (2019), "PubMedQA: A Dataset for Biomedical Research Question Answering", EMNLP-IJCNLP 2019.**
    https://arxiv.org/abs/1909.06146 — ACL Anthology: https://aclanthology.org/D19-1259/
    *Cite for:* PubMed-abstract-grounded QA and human-vs-model accuracy gaps.

## 7. Evaluation methodology (your LLM judge + metrics)

14. **Zheng et al. (2023), "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", NeurIPS 2023 Datasets & Benchmarks.**
    https://arxiv.org/abs/2306.05685
    *Cite for:* LLM-as-a-judge validity (>80% agreement with humans) **and** its known biases (position, verbosity, self-enhancement) — use it to justify your blinded rubric + objective concept-F1 metric.

## 8. Statistics (your significance testing)

15. **Wilcoxon, F. (1945), "Individual comparisons by ranking methods", Biometrika 32(3–4), pp. 248–260.**
    *Cite for:* the paired Wilcoxon signed-rank test (p-values in `src/evaluation/statistical_tests.py`). No open-access URL verified — include via DOI/JSTOR through your library.
16. **Cohen, J. (1988), *Statistical Power Analysis for the Behavioral Sciences*, 2nd ed.**
    *Cite for:* Cohen's d effect-size thresholds (0.2/0.5/0.8).

---

### Suggested citation clusters for the report
- **Related work — RAG:** [1], [2], [6]
- **Related work — Graph/ontology expansion:** [3], [4], [5], [8], [9]
- **Motivation (retrieval is the bottleneck in medicine):** [7], [8]
- **Ontology design:** [10], [11]
- **Benchmarks:** [12], [13]
- **Evaluation protocol:** [14], [15], [16]
