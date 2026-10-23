# Dataset and knowledge graph

## PubMedQA

[PubMedQA](https://pubmedqa.github.io/) (Jin et al., EMNLP 2019) is a
biomedical question-answering dataset built from PubMed abstracts. Each
instance is a research question, the abstract of one paper that answers it, and
a three-way label (`yes`, `no`, `maybe`) taken from the paper's own conclusion.

The `qiaojin/PubMedQA` release has 1,000 expert-labelled questions. They are
the evaluation set here.

| Property | Value |
|---|---|
| Labelled questions | 1,000 |
| Labels | 552 yes, 338 no, 110 maybe |
| Candidate abstracts in the corpus | 3,000 (three per question: the gold paper plus two distractors) |
| Unique abstracts available | 212,269 |
| Mean abstract length | 1,390 characters |
| Dev / test split | 500 / 500 (`seed = 42`) |

The `maybe` label is important: it is a *gold* label, not an abstention. The
system never gets credit for abstaining. `row_answer()` in `selective.py`
returns the system's answer, and abstention is simply not counted as correct.
Because the judge can output "maybe" as an answer, a separate
`accuracy_as_maybe` metric is reported so that earlier runs, which counted
abstention as the "maybe" class, remain comparable.

### Why the source abstract is in the retrieval pool

In the standard PubMedQA setup the model is given the abstract and asked for the
label. Our retrieval pool is built from the gold abstract plus two distractors
per question, so the gold abstract is *in* the index. Retrieval recall@1 is
therefore 0.885 and recall@10 is 0.970.

An earlier version of this project treated that as leakage and removed the
source abstract (`--exclude-own`). That converts the task into "answer a
biomedical question using only *other* papers", which the evidence judge fails
almost every time: on the twelve-question dry run, 12/12 were judged
insufficient and the system abstained on all of them. The setting is kept as
**hard mode** (`results/runs/dryrun/dev_sweep.jsonl`) and is reported as a
negative result, but the primary setting retrieves from the full pool.

## Specialties

`evidence_gate/specialty.py` parses the MeSH tree structure and maps every
question's MeSH headings to top-level tree categories. This is used **only for
analysis**, never by the gate, so that the results can be broken down by medical
domain without contaminating the system.

Distribution over all 1,000 questions by primary category (the category with
the most assigned headings):

| Code | Category | Questions |
|---|---|---|
| C04 | Neoplasms | 178 |
| C23 | Pathological Conditions, Signs and Symptoms | 117 |
| C14 | Cardiovascular Diseases | 89 |
| C01 | Infections | 65 |
| C10 | Digestive System Diseases | 62 |
| C12 | Urogenital Diseases | 50 |
| C06 | Endocrine Diseases | 48 |
| M01 | Persons | 41 |
| C05 | Musculoskeletal Diseases | 39 |
| C26 | Wounds and Injuries | 29 |
| C08 | Respiratory Tract Diseases | 29 |
| N05 | Health Care Facilities, Manpower, and Services | 28 |

Specialization by restricting the *graph* to one category was considered and
rejected: restricting the questions would have cut the main evaluation set from
1,000 to between 120 and 193, and the user's requirement was a main table on
the full set. The per-specialty view is reported instead, and the test split is
too small for reliable per-category estimates below about 10 questions (see
`results.md`).

## The OntoGate graph

Built by `scripts/eg_build_ontology.py` into
`data/ontogate/ontology.ttl` (683,340 triples).

### MeSH 2026

* Source: `https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.xml`
* Licence: public domain (US Government work)
* 31,110 descriptors, 65,242 hierarchy edges
* Node kinds are assigned from the descriptor's tree letter using an explicit
  table (`MESH_KIND_BY_TREE_LETTER`): `C` -> Disease, `D` -> Chemical,
  `A` -> Anatomy, `E` -> Technique, `F` -> Psychiatry, and so on. No model
  decides the kinds.
* Labels and synonyms feed a normalized alias index of 161,041 entries, which
  is what makes multi-word linking practical.

### Hetionet v1.0

* Source: `https://het.io/`, Himmelstein et al., eLife 2017
* Licence: CC0 1.0
* Relations kept: `presents` (3,357), `localizes` (3,602), `treats` (755),
  `resembles` (543), `palliates` (390), `causesSideEffect` (138,944)
* Total: 147,591 edges.

`causesSideEffect` is 40% of all triples. It is kept because side-effect
questions are common in PubMedQA, but it also inflates the graph size and slows
loading. The serialized NetworkX cache (`graph.pkl`) is used at runtime, so the
TTL is only parsed when the cache is missing.

## Passage concept index

`build_passage_concepts()` runs once over the 3,000-abstract corpus and produces
`data/ontogate/passage_concepts.json`:

* 3,000 passages, 7,070 unique linked concepts, 28,385 sentences, about 31
  seconds on 4 CPU cores.
* For each passage: a list of concept URIs, a sentence-level list of concept
  URIs, and the curated MeSH headings.
* The index is what allows coverage to be computed in milliseconds during the
  sweep, and it is why the ontology screen costs no API calls.

## Honest limitations of the data

* The 3,000-abstract pool is small and each question's distractors are not
  adversarially chosen, which is why retrieval is nearly saturated.
* The test half (500 questions) was judged completely. The dev half has 283 of
  500 judged; the run is resumable over the daily free-tier quota and the
  sweep's skip-on-existing logic continues where it stopped.
* `maybe` is only 11% of the gold labels, so per-class metrics for `maybe` are
  noisy.
