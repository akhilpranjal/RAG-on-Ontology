# OntoGate-RAG results (dev)

| System | n | Accuracy | 95% CI | Macro-F1 | Maybe recall | Abstain (n) | Abstain precision | ESS AUC | Latency (s) |
|---|---|---|---|---|---|---|---|---|---|
| Standard RAG | 50 | 0.66 | [0.52, 0.8] | 0.5676 | 0.375 | 0 | None | None | 0.05 |
| Gate only | 50 | 0.56 | [0.42, 0.7] | 0.5142 | 0.75 | 25 | 0.24 | 0.5 | 0.04 |
| OntoGate (full) | 50 | 0.54 | [0.4, 0.68] | 0.491 | 0.625 | 22 | 0.1818 | 0.5 | 0.07 |

## Significance (OntoGate vs standard RAG)

- McNemar: b=3 (OntoGate only), c=9 (RAG only), p=0.146 (exact_binomial)

## Gate and ontology behaviour

- Decisions: {'GENERATE': 28, 'ABSTAIN': 22}
- Refinement attempts: 12 (grounded 4, ungrounded 8)
- Intents: {'default': 7, 'cause': 1, 'treatment': 4}
- Mean sufficiency change after grounded re-retrieval: +0.0000 (n=4)
- Most frequent added terms: [('Esotropia', 1), ('Exotropia', 1), ('Pathology', 1), ('Transplants', 1), ('Heterografts', 1), ('Autografts', 1), ('Isografts', 1), ('Allografts', 1), ('Bone-Patellar Tendon-Bone Grafts', 1), ('Composite Tissue Allografts', 1)]
