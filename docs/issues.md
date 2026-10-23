# Problems faced and how they were solved

A log of the real obstacles in this project, written so that they can be
reported honestly in the paper's "challenges" section and answered in the viva.

---

## 1. We thought the source abstract was leakage. It was the task.

**Symptom.** Early results looked implausibly good, so the source abstract was
excluded from the candidate pool (`--exclude-own`). Results collapsed: the
judge declared the evidence insufficient on 12 out of 12 dry-run questions and
the system answered nothing.

**Cause.** PubMedQA is an open-book task. The corpus is three abstracts per
question: the gold paper and two distractors. Removing the gold paper leaves
only abstracts about related topics, which do not contain the study's result.

**Fix.** Made the open-book setting the primary one, kept exclude-own as a
documented "hard mode" with its zero result, and explained the distinction in
`dataset.md`.

**Lesson.** Before calling something leakage, check what the benchmark defines
as its task. A "fix" that destroys the task is not a fix.

---

## 2. The model was retired mid-project.

**Symptom.** `gemini-2.5-flash-lite` and `gemini-2.0-flash-lite` returned 404.
`gemini-3.5-flash` returned 429 after about six calls.

**Cause.** Model deprecation plus free-tier limits that vary per model. On
`gemini-3.5-flash`, hidden "thinking" tokens are billed against the quota.

**Fix.** Moved to `gemini-3.1-flash-lite` with `thinking_budget=0`, made the
model a single config constant, and recorded the model version in the report.
Earlier numbers collected with `gemini-3.5-flash-lite` are kept and labelled
rather than silently mixed.

**Lesson.** An experiment is only reproducible if the model identifier is part
of the result. Pin it and report it.

---

## 3. Quota exhaustion caused three-minute hangs.

**Symptom.** Once the daily free-tier quota ran out (`429 RESOURCE_EXHAUSTED`,
metric `generate_content_free_tier_requests`), every request retried with a
long backoff. A 50-question run appeared to hang.

**Cause.** A generic retry policy treated quota exhaustion like a transient
network error.

**Fix.** `GenerationClient` now fails fast on 429 after the first attempt,
because waiting cannot help until the quota resets. Disk caching means completed
calls are never repeated, and the sweep is resumable.

**Lesson.** Distinguish *retryable* errors from *terminal* ones. Quota is
terminal for the day.

---

## 4. `thinking_budget` is accepted by some models and rejected by others.

**Symptom.** Passing `thinking_budget=0` raised an API error on some versions.

**Fix.** Try with the parameter, catch the rejection once, retry without it, and
remember the choice for the rest of the process. No hidden retry loop.

---

## 5. Ontology coverage was too slow at first.

**Symptom.** Linking every concept in every passage on every query took long
enough to dominate the sweep.

**Cause.** Re-tokenizing and re-matching the whole corpus per question.

**Fix.** `build_passage_concepts()` precomputes per-passage and per-sentence
concept lists once (3,000 passages, 7,070 concepts, 28,385 sentences, about 31
seconds) and stores them in JSON. Query-time coverage is then a set intersection.

**Lesson.** Move everything that does not depend on the question out of the
query path.

---

## 6. Loading a 683k-triple graph on every run was slow.

**Symptom.** Parsing the TTL took tens of seconds per process.

**Fix.** Serialize the NetworkX graph with `pickle` after the first build
(`graph.pkl`). The TTL remains the source of truth; the cache is disposable.

---

## 7. Parsing the 300 MB MeSH XML could exhaust memory.

**Fix.** Use `xml.etree.ElementTree.iterparse` and call `element.clear()` after
each `DescriptorRecord`. The build then runs comfortably on a 12 GB machine.

---

## 8. Counting abstention as the "maybe" class inflated accuracy.

**Symptom.** Early runs reported accuracy near 0.9, but most of it came from
questions where the system abstained and the gold label was `maybe`.

**Fix.** Abstention is never counted as correct. `accuracy_as_maybe` is reported
as a separate, clearly labelled number for historical comparison only.

**Lesson.** Define the metric before running the experiment, especially for
abstention systems.

---

## 9. Document coverage saturated, which we did not expect.

**Symptom.** Coverage was 1.0 for 82.5% of questions in the interim run (87.1%
on the full test half). The gate had almost no
variance and its AUC was 0.547.

**Cause.** PubMedQA questions name one or two concepts, and ten abstracts
almost always mention them. Term presence is not evidence sufficiency.

**Fix.** Built sentence-level and relation-level coverage features
(`pair_sentence_coverage`, `relation_coverage`) to test whether the *relation*
is present. They did not help either (test AUC 0.493 for coverage /
0.559 for the relation variant), which became a reported
negative result rather than a hidden failure.

**Lesson.** A feature can be conceptually right and empirically useless because
of the dataset's structure. Measure the distribution before trusting the idea.

---

## 10. Ontology query expansion made retrieval worse.

**Symptom.** Expanding the query with graph neighbours lowered recall.

**Cause.** Shared MeSH terms pulled in topically similar but non-answering
abstracts; the dense score already captured the useful semantics.

**Fix.** Dropped expansion from the final system and moved the ontology to the
gate side. Kept the code and the negative result.

---

## 11. The judge occasionally returned non-JSON.

**Symptom.** `json.loads` failed on wrapped or truncated output.

**Fix.** A tolerant parser: strip code fences, take the outermost `{...}`,
validate the fields, and default to `sufficient = "no"` if parsing fails. The
default is deliberately conservative.

---

## 12. PowerShell on Windows has no heredocs.

**Symptom.** `python - <<'EOF'` fails on Windows PowerShell.

**Fix.** All file edits go through the editor tools; inline Python is limited to
one-liners with quoting. All commands run from the repository root with
`uv run python`.

---

## 13. Every MeSH disease specialty was labelled "Diseases".

**Symptom.** The per-specialty table showed C04, C10 and C14 all as "Diseases".

**Cause.** The name was derived from the first tree letter only (`C`), which is
correct for the top level but useless inside category C.

**Fix.** Added `DISEASE_CODE_NAMES`, a table of the specific names extracted
from the MeSH tree itself (C04 Neoplasms, C10 Nervous System Diseases, C14
Cardiovascular Diseases, ...).

---

## 14. The learned gate overfit with too many features.

**Symptom.** `fused_all` had the best dev AUC (0.834, +0.018 over the
two-feature gate) and a worse test AUC (0.772, -0.002). Adding ontology
coverage to the two-feature gate raised dev and lowered test.

**Fix.** Prefer the two-feature gate (dev 0.816 -> test 0.774) and report every
variant with both splits so the gap is visible.

**Lesson.** With 283 dev rows, every extra feature is a lottery ticket.

---

## 15. The always-answer baseline was weaker than a standard RAG baseline.

**Symptom.** The judge prompt answers "maybe" often, so "always answer with the
judge prompt" scores 58.8%, while an earlier plain-prompt RAG run scored 66.0%.

**Fix.** Added `scripts/eg_paired_baseline.py`, which compares both arms on the
same 50 questions and reports the resulting +3.1-point difference with
p = 1.0. The headline is still reported against the same-model baseline, but
the stronger comparison is in the report.

**Lesson.** The baseline is part of the experiment. Choosing a weak one is a
reviewer finding waiting to happen.

---

## 16. Quota limited the dev sweep.

**Symptom.** The free-tier quota allowed enough calls to complete the entire
test half (500 questions) in one sitting, but only 283 of the 500 dev
questions.

**Fix.** Resumable sweep, disk cache, one judge call per question, and an
analysis that refits on whatever dev rows exist. The test CI is reported
explicitly. Extending the run cannot change the protocol, only narrow the
intervals.
