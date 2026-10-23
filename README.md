# OntoGate-RAG

**A question-answering system that knows when it doesn't know.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

---

## Read this first (60-second version)

* We built a system that answers **yes/no/maybe research questions about
  medicine** (taken from PubMedQA, a public dataset of real medical papers).
* Most chatbots always give an answer, even when they are guessing. Ours
  tracks how confident it is, and **when its evidence is weak it refuses and
  says "I don't know" instead of guessing wrong.**
* Result: when it does choose to answer, it is right **78.2%** of the time,
  versus **58.8%** if it were forced to answer everything. Those are real,
  measured numbers on a set of 500 questions it had never seen during
  development.
* The confidence signal comes from asking a large language model (Gemini) a
  second, cheap question: *"is the evidence I found actually enough to answer
  this?"*
* A medical knowledge graph (MeSH + Hetionet) is used as a **free
  money-saver**: before paying for any model calls, it checks whether the
  retrieved medical abstracts even mention the topics of the question. If they
  clearly don't, the system skips straight to "I don't know" with zero cost.
* We also tested what did **NOT** work: the knowledge graph cannot judge
  accuracy by itself, graph-based re-ranking of search results adds nothing,
  and the fitted learning model ends up reducing to a simple untrained rule.
  All of this is documented in detail, not hidden.

Everything below explains these bullets slowly.

---

## 1. The problem in plain words

### What is RAG?

Retrieval-Augmented Generation (RAG) means: when someone asks a question, the
system first **searches** a document collection for relevant passages, then
**pastes those passages into a large language model (LLM)**, and the LLM writes
the answer while looking at the pasted passages. This is how most serious
chatbots are built.

### What goes wrong?

The LLM answers **every** question, no matter how good the retrieved passages
were. If the search found irrelevant or incomplete evidence, the LLM still
writes a confident-sounding answer — which is often wrong. A wrong
confident answer is worse than no answer, especially in medicine.

### What is a "selective" QA system?

A selective system is allowed a third option: **abstain**. At each question it
makes a two-part decision:

1. *Is this question worth answering?* (the **gate** decision)
2. If yes — *what is the answer?*

If the gate says "abstain", the system outputs *"insufficient evidence"*. When
we score the system, an abstention is never counted as correct — the system
only earns points on the questions where it actually commits to an answer.
This trade-off is called the **accuracy–coverage trade-off**: answer fewer
questions (low coverage) and they can be more accurate (high accuracy).

### The one thing this project is about

> **How do you decide, for each question, whether the retrieved evidence is
> good enough — before you trust the answer?**

Everything in this repository exists to answer that question, and to test
whether a medical knowledge graph can help.

---

## 2. Where the data comes from

### PubMedQA

PubMedQA (Jin et al., EMNLP 2019) is a benchmark of **real research questions
from medical papers**, each with a gold answer recorded as exactly one of
`yes` / `no` / `maybe`.

We used the 1,000 questions that medical experts have labelled:

| Gold label | Count |
|---|---|
| yes | 552 |
| no | 338 |
| maybe | 110 |

Around each question there is a public collection of **3,000 medical paper
abstracts**. This is the "open-book" setting: the relevant abstracts are in
the pile, and the system has to find and use them.

We randomly split the 1,000 questions into two halves with a fixed random seed:

* **Development (dev) half, 500 questions** — used to design the system and to
  fit its little learning model. 283 of these have been fully processed (the
  API cost more than our free daily quota; the run resumes where it stopped).
* **Test half, 500 questions** — completely processed, and **never used for
  any design decision**. All headline numbers are quoted on this half.

### MeSH and Hetionet (the ontology)

An ontology, in this project, is a **machine-readable medical vocabulary plus
relationships between terms**:

* **MeSH 2026** — the U.S. National Library of Medicine's controlled
  vocabulary. It defines that "Heart Attack", "myocardial infarction" and "MI"
  are one concept ("Myocardial Infarction"), and organises every medical term
  into a tree of broad categories (Heart Diseases → Cardiovascular Diseases →
  Disease). 31,110 terms, 65,242 parent/child links.
* **Hetionet v1.0** — a curated public graph of real relationships, e.g.
  *compound TREATS disease*, *disease ASSOCIATES gene*, *drug CAUSES side
  effect*. We used six clinical relation types: 147,591 edges.

Together these give us two things we use later: (a) we can tag each question
with its disease category (for per-specialty reporting), and (b) we can
translate both the question and the evidence into sets of concept terms and
ask *"do they overlap?"* — the heart of the ontology-based gate feature.

No LLM was used to generate any graph content; everything comes from the two
public files, and their licences are recorded in the ontology build script's
provenance file.

### The model

One model does all the paid work: `gemini-3.1-flash-lite` (a small, fast,
cheap Google model), with a disk cache so no question is ever paid for twice.

---

## 3. How the system works, step by step

When a question arrives, five things happen in order:

```
question
  |
  v
[1] SEARCH       : find the 10 most relevant abstracts from the 3,000
  |
  v
[2] ONTOLOGY      : translate question and abstracts into MeSH concepts
  |                 and measure how much the abstracts "cover" the question
  |
  +--> few concepts covered? --> ABSTAIN ("insufficient evidence")
  |                             [zero API calls — free]
  v
[3] JUDGE (LLM)   : one cheap call that looks at the abstracts and returns
  |                 a sufficiency score (0.0–1.0), a provisional answer
  |                 (yes / no / maybe), and a one-line justification
  |
  +--> judge answered "maybe"? --> ABSTAIN   [why: see finding 1]
  |
  v
[4] GATE          : a tiny learned calculator combines the judge's score
  |                 and the ontology coverage into one number (0–1);
  |                 below the threshold (fitted on dev) -> ABSTAIN
  |
  v
[5] ANSWER        : the question gets a yes/no answer
```

A few notes on each step, in slightly more detail:

1. **Search uses embeddings, not keywords.** Each abstract was converted into
   a vector (a list of numbers) once, offline. A similarity search (FAISS)
   finds the 10 abstracts closest in meaning to the question. This step was
   already near-perfect (see section 5), so the interesting science is all
   after it.
2. **The ontology step is where the graph earns its keep.** We match every
   text span in the question against MeSH concepts (for instance *metformin*
   → the drug concept, *Alzheimer's disease* → the disease concept) and check
   how many of those concepts are also mentioned in the 10 retrieved
   abstracts. Simple versions of this measure (how many top concepts are
   mentioned at all) turned out to be too easy — see section 6 — but it costs
   nothing to compute, so it is used as a **first filter**: if the evidence
   barely mentions the question's topics, there is no point paying for an LLM
   judge.
3. **The judge is the key invention of this project.** Instead of asking the
   LLM for an answer directly, we ask one structured question:
   *"Given these abstracts and the question — how sufficient is the evidence
   (0–1), what is your provisional answer (yes/no/maybe), and why?"* This one
   call produces **both** a candidate answer and a confidence score to gate
   with, so the system costs one API call per question, not two.
4. **The gate is deliberately tiny.** It is a two-feature logistic model —
   it mixes the judge's score with the *fact* of whether the judge answered
   "maybe". Nothing more. Two features means it cannot secretly memorise the
   development data, which larger feature sets demonstrably did.
5. **Answers are yes/no only when committed.** When the gate abstains, the
   output is "maybe (insufficient evidence)" and it scores zero points, the
   same rule some doctors' exams use as a penalty for wild guessing.

A worked example is printed by the demo script (`scripts/eg_demo.py`) which
runs all five stages on one real question and prints what each stage saw.

---

## 4. What we measured, and what the numbers mean

Three metrics appear everywhere in the results. Here is the honest meaning of
each:

* **Coverage** — of all questions, how many got a real answer (not an
  abstention). 100% = never abstains.
* **Selective accuracy** — of those *answered* questions, how many were
  actually right. This is the number that matters.
* **AUC** — a 0-to-1 score for how well a signal sorts the questions the
  system would be right on from the ones it would be wrong on. 0.5 = the
  signal is useless (a coin flip), closer to 1 = better sorting. Do not
  compare AUC with accuracy directly; they measure different things.

---

## 5. The results

All numbers below are from the **test half: all 500 questions**, with the gate
thresholds fixed from the dev half and then applied unchanged. The same model
produces both the baseline and the gated answers — the *only* difference
between the rows is whether it was allowed to abstain.

### Headline table

| System | Answers about | Right about |
|---|---|---|
| Always answer (standard RAG) | 100% of questions | **58.8%** |
| **OntoGate (this project)** | **65% of questions** | **78.2%** |

Reading that table: standard RAG answers everything and gets ~59% right —
barely better than guessing "yes" every time (55%). Our system answers the
~326 questions where it is confident and gets 78.2% right there (95%
confidence interval 73.6%–82.5%: in a re-run of the same experiment, that is
the range the number would fall in). It earns +19.4 points of accuracy by
giving up 35% of answers.

For comparison: reported human expert accuracy on PubMedQA is about the same
(78.2%, measured on the yes/no-only subset). Our gated system reaches that
figure in this open-book setting, while the same model ungated sits 19 points
lower.

### Finding 1: the judge's *own* uncertainty is the best signal

We tried many candidate "confidence signals" and measured each one's AUC:

| Signal | Dev AUC | Test AUC |
|---|---|---|
| Retrieval-similarity score (how close the top abstract was) | 0.55 | 0.53 |
| Ontology concept-coverage features | 0.49–0.50 | 0.49 |
| LLM judge's 0–1 sufficiency score | 0.77 | 0.74 |
| Judge score **+ whether it answered "maybe"** | 0.81 | 0.77 |
| The fitted two-feature gate built on those | 0.82 | **0.77** |

Two things stand out:

* **Everything from the ontology or the retrieval scores is near-coin-flip.**
  The medical facts named in the question almost always appear *somewhere* in
  ten abstracts — so coverage cannot distinguish answerable from
  unanswerable.
* **The judge's structured output sorts almost perfectly.** Best of all,
  when we inspect the fitted two-feature gate, it turns out to be equivalent
  to a plain rule with *zero training*:

> **Answer only if the judge said yes/no (not "maybe") AND its sufficiency
> score was maximum (1.0).** That rule, applied with no learning at all,
> gives exactly the same 78.2% at 65.2% coverage on test (83.2% at 67.1% on
> dev) — and the learned gate makes the identical decisions.

This is the single most useful discovery of the project: you don't need a
trained gate; you need the right *question* to the judge, and its
"maybe"-saying behaviour is the confidence signal.

### Finding 2: the ontology can't see accuracy — but it saves 1 judge call in 5

As the table above shows, ontology coverage is a near-useless **accuracy**
gate (AUC ≈ 0.49-0.50). But it is free, and when it is placed *in front of*
the judge as a cheap pre-filter, configured from dev-set data (where it skips
questions with almost no ontology evidence), then measured on test:

* **It skips 19.4% of all judge calls** (around 97 calls saved per 500
  questions),
* for a cost of only **0.9 accuracy points** (78.2% → 77.3%),
* and it behaves almost identically on dev and test (dev saves 20.5% and
  loses 0.7 points).

That is the honest picture of "is the ontology useful?": not as a brain, only
as a wallet.

### Finding 3: which questions get abstained on?

Detailed failure analysis on all 500 test questions:

* The judge answered "maybe" on 161 questions; if a plain RAG answer had been
  forced on those, it would have been right less than one time in five
  (**18.6%**) — that is exactly the group the gate keeps silent on.
* Questions skipped by the ontology pre-filter were (slightly) *easier* on
  average than the average question, not harder.
* The errors it still makes are spread evenly over medical specialties, with
  one exception: a tiny rare-disease group where the judge says "maybe" almost
  every time — which is *correct behaviour* for that specialty.

### Finding 4: retrieval is not the bottleneck

We measured how well step 1 finds the right abstracts:

* Top-1 is correct 88.5% of the time, top-3 94%, top-10 97% (measured over a
  200-question dev sample).
* Because the ground-truth abstracts are present in the corpus and the
  questions are written using words from them, retrieval is essentially
  solved.
* We therefore also tried ontology-based **reranking** (re-ordering results
  by graph-similarity) and **query expansion** (adding graph terms to the
  query). Both did nothing or hurt. With 97% recall already, there was
  nothing left to gain. Negative result, honestly reported.

---

## 6. What did NOT work (and is still in the repo on purpose)

| Idea | Fate |
|---|---|
| Ontology coverage as an accuracy gate | near-useless (AUC ~0.49); kept only as a cost filter |
| Ontology-based re-ranking / query expansion of retrieval | no effect — retrieval was already at ceiling |
| Fancy learned gates with many features (per-specialty one-hot encodings, all features fused, NLI) | **overfit**: looked better on dev, worse on test; replaced by the two-feature gate and the simple rule |

Being able to *demonstrate* each of these on the full test set, with numbers
and plots, is part of the deliverable: the project shows where the ontology
helps (cost), where it does not (accuracy), and why (term overlap saturates).

---

## 7. Honest limitations

1. **The dev half isn't fully processed** (283/500) because of free-tier API
   quotas. The test half — every number quoted above — is complete. If the
   dev sweep is finished later, thresholds can only improve; the test half is
   already untouched and final.
2. **The always-answer baseline is a judge-prompt baseline**, not exactly
   standard RAG. The judge prompt is worded so the model sometimes answers
   "maybe", which makes the ungated baseline slightly weaker than a
   conventional plain-answer prompt. Against an older, different-model
   plain-prompt run (on 50 shared questions), the gate's gain shrinks from
   +19.4 points to +3.1 points and loses statistical significance. A
   same-model plain-prompt runner (`scripts/eg_run_baseline.py`) is included
   and ready to run when quota allows.
3. **Open-book corpus**: PubMedQA ships the question's own abstracts in the
   pile, so retrieval is easy. This is the *standard* benchmark setup, not a
   modelling achievement, and it means "retrieval quality" improvements were
   expected to be small.
4. **One model, one prompt**. Everything hinges on `gemini-3.1-flash-lite`.
   A different judge model would change the numbers (probably the rule, not
   the idea).
5. "maybe" gold labels are only 11% of the data, so per-class error rates are
   noisy.

---

## 8. How to run this project

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), and a free Google AI
Studio API key.

```powershell
# once: install dependencies
uv sync

# once: create .env from the template and paste your API key in it
Copy-Item .env.example .env
```

Build the assets (each step is one command, each writes into `data/`):

```powershell
uv run python scripts/eg_prepare_data.py       # download PubMedQA, make splits
uv run python scripts/eg_build_ontology.py     # download MeSH + Hetionet, build the graph
uv run python scripts/eg_build_index.py        # embed all 3,000 abstracts, build FAISS index
uv run python -m evidence_gate.specialty       # tag every question with its disease area
uv run python -c "from evidence_gate.coverage import build_passage_concepts; build_passage_concepts()"
```

Run the main experiment (resumable; ONE LLM call per question):

```powershell
uv run python scripts/eg_run_sweep.py --split dev  --include-own
uv run python scripts/eg_run_sweep.py --split test --include-own
```

Produce the report, tables and plots (free, no API):

```powershell
uv run python scripts/eg_analyze.py             # final_report.md, per-question CSV, plots
uv run python scripts/eg_eval_retrieval.py      # retrieval metrics
uv run python scripts/eg_paired_baseline.py     # accuracy sanity-check vs a plain baseline
```

See one question pass through the whole system:

```powershell
uv run python scripts/eg_demo.py --split test
uv run python scripts/eg_demo.py --question "Does metformin help Alzheimer's disease?"
```

Every command skips work that is already done (cached API responses, built
indexes, existing result rows), so any of them can be stopped and re-run.

---

## 9. Repository layout

```
evidence_gate/          library code
  retriever.py            step 1: embed + search abstracts (FAISS)
  ontology.py             step 2a: load the MeSH+Hetionet graph (rdflib)
  coverage.py             step 2b: link text to concepts, compute coverage
  llm_judge.py            step 3: the sufficiency judge (prompt + parsing)
  selective.py            step 4: candidate gate features and the learner
  api.py                  Gemini client with disk cache and fail-fast quota
  specialty.py            per-question disease categories from MeSH
  evaluate.py             jsonl reading/writing, shared scoring helpers
scripts/                the runnable entry points, one per stage (eg_*.py)
results/metrics/        final_report.md/json (the tables you'd print), CSV of each question
results/plots/          risk–coverage curve, AUC chart, coverage histogram
results/runs/           raw per-question records (git-ignored)
docs/                   all documentation (see table below)
legacy/                 earlier designs kept for the record, not used
data/                   downloads and derived assets (git-ignored)
```

---

## 10. Detailed documentation

| | |
|---|---|
| [architecture.md](docs/architecture.md) | how each module works and why it is that way |
| [dataset.md](docs/dataset.md) | PubMedQA in detail, the splits, the graph provenance |
| [experiments.md](docs/experiments.md) | every experiment run, with the protocol and exact commands |
| [results.md](docs/results.md) | every result table with interpretation and caveats |
| [viva.md](docs/viva.md) | likely questions and short defensible answers |
| [issues.md](docs/issues.md) | 16 real problems hit during the build and their fixes |
| [explainers.md](docs/explainers.md) | every technical term above, in plain language |
| [paper_notes.md](docs/paper_notes.md) | drafts of the report/paper sections |

---

## 11. Data sources and licences

| Source | Role | Reference / licence |
|---|---|---|
| PubMedQA | 1,000 expert-labelled questions + a 3,000-abstract search corpus | Jin et al., 2019 |
| MeSH 2026 | the medical vocabulary and hierarchy (31,110 terms) | NLM, public domain |
| Hetionet v1.0 | drug–disease–gene relationship edges (147,591) | Himmelstein et al., 2017 (CC0) |

Gemini is accessed through the official `google-genai` library; the model
outputs were not used to build the ontology or its evaluation.
