# Viva preparation

Short, defensible answers. Where a number appears, it is the test-split number
from `results.md`.

## The basics

**What problem does this solve?**
Medical question answering systems that always answer will confidently answer
questions their evidence cannot support. This system reads the retrieved
evidence and decides whether it is enough. If it is not, it says so instead of
guessing.

**What is "selective" answering?**
The system may decline to answer. That turns the problem from "be accurate on
everything" into "be accurate on what you choose to answer, and answer as much
as you can". The two numbers that matter are coverage (how many questions it
answers) and selective accuracy (how often those answers are right).

**Why is abstaining useful in medicine?**
A wrong confident answer can cause harm; "the evidence I found is insufficient"
is actionable (order a test, consult a specialist, retrieve more). The system
makes its uncertainty explicit instead of hiding it in fluent text.

**What is the input and output?**
Input: a yes/no research question plus its MeSH terms. Output: `yes`, `no`, or
`insufficient evidence`, together with the retrieved abstracts and the signal
values behind the decision.

## The method

**What are the two gate signals?**
(1) An LLM judge that reads the retrieved abstracts and returns a sufficiency
label, an answer, and a score. (2) Ontology concept coverage: how much of the
question's MeSH/Hetionet concept content the abstracts actually contain.

**Why an LLM judge and not an NLI model?**
The project started with a PubMedBERT-MNLI cross-encoder. It was slow, had to
run on 4 CPU cores, and its raw entailment score was not a good sufficiency
signal for this task. The LLM judge is one call and directly answers the
question "is this evidence enough?".

**Where exactly is the ontology used?**
Four places, all concrete: linking question terms to graph concepts, computing
coverage of those concepts in the evidence, checking whether a *sentence*
relates two question concepts with the right relation cue, and screening
questions before the paid judge call.

**How is the ontology built?**
Script `scripts/eg_build_ontology.py` merges MeSH 2026 (31,110 descriptors,
65,242 hierarchy edges) with Hetionet v1.0 (six clinical relations, 147,591
edges) into 683,340 triples. Node types come from a fixed table of MeSH tree
letters. No LLM is used to build it.

**Is the ontology doing the work?**
No, and the report says so. The judge is the accurate signal (AUC 0.705, 0.747
with self-abstention). Ontology coverage alone is AUC 0.547 and it saturates:
82.5% of questions have coverage 1.0. The ontology's proven contribution is cost
control: it removes 23.5% of judge calls for a 1.9-point accuracy loss.

**Then why keep the ontology?**
Because a negative result with a measured cost/benefit is a result. The project
shows exactly where a curated graph helps (cheap screening, interpretability,
auditability) and where it does not (standalone sufficiency, reranking, query
expansion). It also keeps the system's evidence check inspectable: a human can
see which concepts were found and which were missing.

**What is the most important single finding?**
The judge's own "maybe" answer is a strong abstention signal. Abstaining
whenever the judge answers "maybe" gives 76.9% accuracy at 61.2% coverage with
zero training. A logistic gate on the same signal does not beat it.

**Why does that happen?**
The model is not calibrated on the 0/0.5/1 score, but its three-way answer is
an explicit self-report of uncertainty. When it says "maybe" it is usually
wrong: on test, 29 of 85 questions got "maybe", and keeping them would have
destroyed accuracy. The gate is essentially a well-designed way to trust that
self-report.

## The experiments

**What is the difference between dev and test here?**
Dev (200 judged questions) is used to fit every threshold, screen value and
logistic weight. Test (85) is used once per arm. Thresholds transfer by matched
coverage: the dev threshold that hits a coverage target is applied unchanged.

**Why only 85 test questions?**
The free API tier allows about 200 judge calls per day and the quota was
exhausted. The sweep is resumable by design, so the remaining 415 can be added
without refitting anything. The report states the CI explicitly.

**Why not run every ablation separately?**
Quota. One judge call per question stores the judge output, coverage features,
similarities and passages, so every arm is reconstructed offline from the same
rows. This also makes the comparison paired, which is statistically stronger
than running arms on different samples.

**What is AUC doing here?**
It answers: if I pick a random answerable question and a random unanswerable
one, how often does the gate give the answerable one a higher score? 0.5 is
chance. It measures ranking quality independent of any threshold.

**What is AURC?**
Area under the risk-coverage curve. Lower is better. It summarises accuracy at
every possible abstention rate at once, which is why it is used instead of a
single threshold.

**Did you test statistical significance?**
Yes, where it is meaningful: bootstrap CIs for selective accuracy and McNemar
for paired comparisons. The paired comparison against the stronger plain-prompt
baseline is not significant (p = 1.0), and the report says so.

**What is the retrieval result?**
Dense retrieval is nearly saturated: recall@1 0.885, recall@10 0.970. Ontology
reranking changes one question at rank 1 and nothing else, so there is no
headroom. Query expansion made it worse.

**Why is recall so high?**
The candidate pool is three abstracts per question (the gold one plus two
distractors), so the answer is nearly always in the index. That is the standard
PubMedQA open-book setting, not a modelling achievement.

**What about removing the source abstract?**
That is "hard mode". The judge rejected the evidence in all 12 dry-run
questions. It is reported as a negative result: the pipeline depends on having
the right abstract, which is what PubMedQA's setting provides.

**How do you know the gate is not just memorising the label distribution?**
The majority-class baseline is 55.3% on test. The gate reaches 76.9% on the 61%
it answers. Also, the gate never sees the label; it only sees the judge output
and local features.

**What happens on the questions it abstains on?**
They are harder: the judge found the evidence insufficient or ambiguous. Some
of them are still answerable, so abstention costs coverage. That trade-off is
the whole point and is shown at seven coverage targets.

## Design and engineering

**How did you handle prompt injection / bad model output?**
The judge must return JSON; the parser extracts the object tolerantly and
defaults to "insufficient" if it cannot. The judge output never executes
anything. Passages are truncated to 400 characters when stored for analysis.

**How do you stop the system burning quota?**
A disk cache keyed by the exact prompt and model, a rate limiter, fail-fast on
HTTP 429 instead of retrying for minutes, and the coverage screen that skips
obviously under-supported questions.

**Why is there a `legacy/` folder?**
The project had two earlier designs (a symbolic router with selective
expansion, and an NLI-scored gate). They are kept for reproducibility and for
the "problems faced" write-up, but the final system does not use them.

**What would you change with more compute?**
Three things: finish the test sweep to 500 questions, run a same-model
plain-prompt baseline, and try a relational coverage feature that compares
*claims* (drug-disease pairs) rather than term presence.

## Critical questions

**Is this novel?**
The combination is: an LLM sufficiency judge whose own "maybe" is used as an
abstention signal, plus an ontology coverage screen, evaluated under a strictly
paired, cost-aware protocol on PubMedQA. Individual components exist in prior
work; the self-abstention finding and the negative ontology results are the
specific contributions here.

**Isn't "abstain on maybe" obvious in hindsight?**
It is simple, which is a feature. The value is showing that it matches a
learned gate (76.9% vs 76.9%) while being free and directly interpretable. The
non-obvious part is that the sufficiency *score* alone (0.705) is much weaker
than the three-way answer (0.747), i.e. the label is more informative than the
number.

**Your CI is wide. Is the result real?**
The lower bound of the headline CI is 65.4%, still 6.6 points above the
always-answer baseline. The direction of every major effect is consistent
across dev and test. The ontology results are consistent in the negative
direction. The report does not over-claim: every table includes dev and test.

**Does the ontology really "support" the answer, or is it decoration?**
It is used in the loop, not in the prose: coverage values are computed per
question, the screen changes whether an API call happens, and the per-specialty
analysis comes from the same graph. The honest summary is that its *decision*
contribution is modest and its *cost* contribution is real.

**What is the biggest weakness?**
The evidence pool. With a 3,000-abstract corpus and the gold abstract in the
index, retrieval and coverage both saturate. A realistic evaluation would
retrieve from a much larger pool and use the ontology where it is actually
needed: disambiguating and relating concepts across many candidate papers.
