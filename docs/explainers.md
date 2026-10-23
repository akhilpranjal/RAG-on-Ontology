# Plain-language explainers

Every technical term used in this project, explained without jargon. Useful for
the report's background section and for explaining the work to a non-specialist
examiner.

---

## RAG (retrieval-augmented generation)

A language model alone answers from memory. RAG first *finds* relevant documents
and gives them to the model, so the answer can be traced to a source.

Analogy: an open-book exam. The retriever is the index at the back of the book;
the model is the student reading the pages you hand them.

## Why an open-book analogy matters for PubMedQA

PubMedQA gives the model one abstract and asks for the paper's conclusion. In
the 1,000-question split, three abstracts are offered per question: the right
one and two related ones. If you take the right one away, the remaining
abstracts are "about the topic" but do not contain the answer. That is why
"hard mode" collapses: the student is asked to answer without the page.

## Selective prediction (abstention systems)

Normal accuracy assumes the system answers everything. A selective system may
say "I don't know". It is judged by two numbers at once:

* **coverage**: the fraction of questions it answers;
* **selective accuracy**: how often those answers are right.

Reporting only one is meaningless. Answering one easy question can give 100%
accuracy at 0.1% coverage.

## Risk-coverage curve and AURC

Plot coverage on the x-axis and error rate on the y-axis. A good gate's error
rate rises slowly as you force it to answer more. The area under that curve
(AURC) compresses the whole curve into one number; lower is better.

## AUC

If you pick one question the system gets right and one it gets wrong, the AUC is
the chance that the gate gives the correct one the higher score. 0.5 is a coin
flip, 1.0 is a perfect ranking. AUC does not depend on any threshold.

## Calibration

A score is calibrated if "0.8" really means 80% likely. The judge's 0/0.5/1
sufficiency score is not calibrated; that is one reason the three-way answer is
a better signal than the score.

## Precision, recall, @k

* **Recall@k**: of all the questions whose answer is in the corpus, how many
  have it in the top k retrieved passages.
* **Recall@1 = 0.885** means the correct abstract is the top hit 88.5% of the
  time.
* **MRR** (mean reciprocal rank): 1/rank of the correct abstract, averaged. A
  correct abstract at rank 1 contributes 1.0; at rank 2, 0.5.

## Saturation

A metric saturates when it is almost always at its maximum. Recall@10 = 0.970
means retrieval cannot improve much: there is no room. Coverage = 1.0 for 87.1%
of questions means the coverage gate has little to discriminate on.

## Ontology, MeSH, Hetionet

* An **ontology** is a machine-readable map of concepts and the relations
  between them.
* **MeSH** is the US National Library of Medicine's controlled vocabulary:
  terms like "Neoplasms", arranged in a hierarchy (a brain tumour is-a tumour
  is-a disease). It also provides synonyms, which is how "heart attack" links to
  "Myocardial Infarction".
* **Hetionet** is a graph of biomedical facts: drug X *treats* disease Y,
  disease Y *presents* symptom Z. It is built from public databases and released
  under CC0.

Together they let the system know that two different strings mean the same
concept, and how concepts usually relate.

## Triples, RDF, Turtle

An ontology is stored as facts of the form (subject, predicate, object), called
triples. "Metformin treats Diabetes" is one triple. `ontology.ttl` is a text
file of such triples in the Turtle format. 683,340 triples is large but normal.

## Concept coverage

For each question, find its concepts ("metformin", "Alzheimer's disease"). Then
ask: do the retrieved abstracts mention them? Coverage is the fraction of the
question's concepts that appear. Weighted coverage gives rare concepts more
weight (see IDF).

## IDF (inverse document frequency)

Common words carry little information. IDF weights each concept by how rare it is
across the corpus: `log((N+1)/(df+1)) + 1`. A concept in every abstract counts
almost nothing; a rare concept counts a lot.

## Relation coverage

Mentioning "metformin" and "Alzheimer's" in *different* abstracts is not
evidence that metformin helps Alzheimer's. Relation coverage checks whether a
single sentence contains both concepts together, and whether an intent cue
("treats", "causes", "diagnosed with") is present.

## LLM judge

A language model prompted to read the evidence and answer: is it sufficient?
what is the answer? how sure are you? One call per question. It is more flexible
than a classifier but costs money and can be wrong.

## Self-abstention signal

The judge can answer "maybe". That is the model saying "I cannot tell". In this
project that single bit of information is a better gate signal (AUC 0.770) than
the numeric sufficiency score (AUC 0.736).

## Logistic regression

A small model that combines features into a probability:
`p = 1 / (1 + exp(-(w1*x1 + w2*x2 + b)))`. With two features and 200 training
examples it is about the largest model the data can support. The L2 penalty
keeps the weights small to avoid overfitting.

## Overfitting

Learning the training set instead of the pattern. The tell is a good dev score
and a worse test score. `fused_all` shows it: 0.776 dev, 0.704 test.

## Bootstrap confidence interval

Resample the test questions with replacement a thousand times, recompute the
metric each time, and take the middle 95% of the results. It says how much the
number would wobble if the test set were a different sample of questions.

## McNemar test

A paired test for two systems on the same questions. It looks only at the
questions where the systems disagree and asks whether one wins those
disagreements more often than chance. With 32 questions and a 0-vs-1 split, it
cannot be significant; that is why the paired result is reported as
"not significant" rather than as a win.

## API quota

The free tier of the Gemini API allows a limited number of requests per day. The
number differs per model. It is the reason the test sweep has 85 questions
instead of 500, and the reason the system makes exactly one judge call per
question.

## Why the expensive part is the judge

Coverage is a set intersection over a precomputed index: microseconds, local,
free. The judge is a network round trip to a large model: seconds, metered,
rate-limited. So the architecture puts the free signal first and uses it to
avoid the paid one.
