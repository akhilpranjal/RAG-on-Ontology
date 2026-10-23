"""Ontology-grounded concept coverage: a model-free evidence-sufficiency signal.

The gate needs to know whether the retrieved evidence actually *covers* what the
question asks about. An LLM judge answers that question with one call per
question. This module answers it with the curated MeSH + Hetionet vocabulary
instead, using zero model calls:

1. link the question to graph concepts (labels and synonyms, longest match),
2. look up the same concepts in the retrieved passages,
3. report how much of the question's concept content is covered.

Document-level coverage saturates quickly: in a ten-passage evaluation set, the
question's key terms almost always appear *somewhere*. That is why the module
also measures the relational reading of sufficiency:

* ``pair_sentence_coverage`` -- do two question concepts occur in the *same
  sentence* of some passage? A question about a chemical and a disease needs a
  passage that relates them, not two passages that mention them separately.
* ``pair_rank_score`` -- how high in the ranking the first such related passage
  appears (``1 / rank``).

Two surface views are produced as well, because they cost nothing:

* ``coverage`` (text) -- any label or alias of the concept occurs in the set.
* ``heading_coverage`` -- the passages' curated MeSH headings contain the
  concept, using the indexer's own annotation rather than string matching.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from evidence_gate.config import PASSAGE_CONCEPTS_PATH, PUBMEDQA_DIR
from evidence_gate.ontology import LinkedEntity, OntologyGraph
from evidence_gate.reasoner import (
    CAUSE_CUES,
    DIAGNOSIS_CUES,
    HIERARCHY_CUES,
    SYMPTOM_CUES,
    TREATMENT_CUES,
    detect_intent,
)

INTENT_CUES = {
    "treatment": TREATMENT_CUES,
    "symptom": SYMPTOM_CUES,
    "hierarchy": HIERARCHY_CUES,
    "diagnosis": DIAGNOSIS_CUES,
    "cause": CAUSE_CUES,
}
ANY_RELATION_CUES = re.compile(
    "|".join(
        pattern.pattern
        for pattern in (
            TREATMENT_CUES,
            CAUSE_CUES,
            DIAGNOSIS_CUES,
            SYMPTOM_CUES,
            HIERARCHY_CUES,
        )
    ),
    re.IGNORECASE,
)

FOCUS_KINDS = (
    "Disease",
    "Compound",
    "Chemical",
    "Symptom",
    "Anatomy",
    "Technique",
)

MAX_QUESTION_CONCEPTS = 12
MAX_PASSAGE_CONCEPTS = 64
MAX_SENTENCES = 14

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class CoverageResult:
    n_concepts: int
    n_covered: int
    n_focus_concepts: int
    coverage: float
    coverage_top1: float
    coverage_top3: float
    coverage_weighted: float
    coverage_mean_passage: float
    heading_coverage: float
    pair_coverage: float
    pair_sentence_coverage: float
    pair_rank_score: float
    intent: str
    relation_coverage: float
    relation_rank_score: float
    concepts: list[dict] = field(default_factory=list)

    @property
    def has_concepts(self) -> bool:
        return self.n_concepts > 0

    def to_dict(self) -> dict:
        return {
            "n_concepts": self.n_concepts,
            "n_covered": self.n_covered,
            "n_focus_concepts": self.n_focus_concepts,
            "coverage": _round(self.coverage),
            "coverage_top1": _round(self.coverage_top1),
            "coverage_top3": _round(self.coverage_top3),
            "coverage_weighted": _round(self.coverage_weighted),
            "coverage_mean_passage": _round(self.coverage_mean_passage),
            "heading_coverage": _round(self.heading_coverage),
            "pair_coverage": _round(self.pair_coverage),
            "pair_sentence_coverage": _round(self.pair_sentence_coverage),
            "pair_rank_score": _round(self.pair_rank_score),
            "intent": self.intent,
            "relation_coverage": _round(self.relation_coverage),
            "relation_rank_score": _round(self.relation_rank_score),
            "concepts": self.concepts,
        }


def _round(value: float) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), 4)


def split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]
    return sentences[:MAX_SENTENCES]


def build_passage_concepts(
    corpus_path: Path | str | None = None,
    out_path: Path | str | None = None,
    graph: OntologyGraph | None = None,
) -> dict:
    """Link every corpus abstract (and its sentences) to graph concepts."""
    corpus_path = Path(corpus_path or PUBMEDQA_DIR / "corpus.jsonl")
    out_path = Path(out_path or PASSAGE_CONCEPTS_PATH)
    graph = graph or OntologyGraph()

    passages: dict[str, list[str]] = {}
    sentences: dict[str, list[list[str]]] = {}
    df: dict[str, int] = {}
    with open(corpus_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            linked = graph.link(row["text"], max_entities=MAX_PASSAGE_CONCEPTS)
            uris = sorted({entity.uri for entity in linked})
            passages[row["id"]] = uris
            for uri in uris:
                df[uri] = df.get(uri, 0) + 1
            sentence_uris = []
            for sentence in split_sentences(row["text"]):
                found = graph.link(sentence, max_entities=MAX_PASSAGE_CONCEPTS)
                sentence_uris.append(sorted({entity.uri for entity in found}))
            sentences[row["id"]] = sentence_uris
    payload = {
        "n_passages": len(passages),
        "df": df,
        "passages": passages,
        "sentences": sentences,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


class ConceptCoverageScorer:
    """Coverage of question concepts in a retrieved passage set."""

    def __init__(
        self,
        graph: OntologyGraph | None = None,
        index: dict | None = None,
        focus_kinds: tuple[str, ...] = FOCUS_KINDS,
    ):
        self.graph = graph or OntologyGraph()
        if index is None:
            path = Path(PASSAGE_CONCEPTS_PATH)
            index = (
                json.loads(path.read_text(encoding="utf-8"))
                if path.exists()
                else build_passage_concepts(graph=self.graph)
            )
        self.n_passages = int(index.get("n_passages", 0))
        self.df: dict[str, int] = index.get("df", {})
        self.passage_concepts: dict[str, list[str]] = index.get("passages", {})
        self.sentence_concepts: dict[str, list[list[str]]] = index.get("sentences", {})
        self._passage_sets: dict[str, set[str]] = {}
        self._sentence_sets: dict[str, list[set[str]]] = {}
        self.focus_kinds = set(focus_kinds)

    # ------------------------------------------------------------------
    def _passage_set(self, passage_id: str) -> set[str]:
        cached = self._passage_sets.get(passage_id)
        if cached is None:
            cached = set(self.passage_concepts.get(passage_id, ()))
            self._passage_sets[passage_id] = cached
        return cached

    def _sentence_sets_for(self, passage_id: str) -> list[set[str]]:
        cached = self._sentence_sets.get(passage_id)
        if cached is None:
            cached = [set(group) for group in self.sentence_concepts.get(passage_id, ())]
            self._sentence_sets[passage_id] = cached
        return cached

    def idf(self, uri: str) -> float:
        df = self.df.get(uri, 0)
        return math.log((self.n_passages + 1.0) / (df + 1.0)) + 1.0

    def question_concepts(self, question: str) -> list[LinkedEntity]:
        linked = self.graph.link(question, max_entities=MAX_QUESTION_CONCEPTS)
        focus = [entity for entity in linked if entity.kind in self.focus_kinds]
        return focus or linked

    def heading_uris(self, heading: str) -> set[str]:
        return {entity.uri for entity in self.graph.link(heading, max_entities=8)}

    # ------------------------------------------------------------------
    def score(self, question: str, passages) -> CoverageResult:
        concepts = self.question_concepts(question)
        if not concepts:
            nan = float("nan")
            return CoverageResult(
                0, 0, 0, nan, nan, nan, nan, nan, nan, nan, nan, nan, "default", nan, nan
            )

        intent = detect_intent(question)
        cue_pattern = INTENT_CUES.get(intent) or ANY_RELATION_CUES

        passage_sets = [self._passage_set(p.id) for p in passages]
        union: set[str] = set()
        for item in passage_sets:
            union |= item
        top1 = passage_sets[0] if passage_sets else set()
        top3: set[str] = set()
        for item in passage_sets[:3]:
            top3 |= item

        weights = [self.idf(entity.uri) for entity in concepts]
        covered_flags = [entity.uri in union for entity in concepts]
        n_covered = sum(covered_flags)
        total_weight = sum(weights) or 1.0

        per_passage = [
            sum(1 for entity in concepts if entity.uri in item) / len(concepts)
            for item in passage_sets
        ] or [0.0]

        pair_total = 0
        pair_cov = 0
        pair_sentence_cov = 0
        pair_rank = 0
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                pair_total += 1
                left, right = concepts[i].uri, concepts[j].uri
                if any(left in item and right in item for item in passage_sets):
                    pair_cov += 1
                matched_rank = 0
                for rank, (document, groups) in enumerate(
                    zip(passage_sets, [self._sentence_sets_for(p.id) for p in passages]),
                    start=1,
                ):
                    if left not in document or right not in document:
                        continue
                    if any(left in group and right in group for group in groups):
                        pair_sentence_cov += 1
                        matched_rank = rank
                        break
                if matched_rank and (pair_rank == 0 or matched_rank < pair_rank):
                    pair_rank = matched_rank
        pair_coverage = pair_cov / pair_total if pair_total else float("nan")
        pair_sentence_coverage = pair_sentence_cov / pair_total if pair_total else float("nan")
        pair_rank_score = 1.0 / pair_rank if pair_rank else 0.0

        sentence_texts = [split_sentences(p.text) for p in passages]
        sentence_groups = [self._sentence_sets_for(p.id) for p in passages]
        relation_total = 0
        relation_cov = 0
        relation_rank = 0
        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                relation_total += 1
                left, right = concepts[i].uri, concepts[j].uri
                for rank, (texts, groups) in enumerate(
                    zip(sentence_texts, sentence_groups), start=1
                ):
                    hit = any(
                        left in group
                        and right in group
                        and k < len(texts)
                        and cue_pattern.search(texts[k])
                        for k, group in enumerate(groups)
                    )
                    if hit:
                        relation_cov += 1
                        if relation_rank == 0 or rank < relation_rank:
                            relation_rank = rank
                        break
        relation_coverage = (
            relation_cov / relation_total if relation_total else float("nan")
        )
        relation_rank_score = 1.0 / relation_rank if relation_rank else 0.0

        heading_union: set[str] = set()
        for passage in passages:
            for heading in passage.metadata.get("meshes") or []:
                heading_union |= self.heading_uris(str(heading))
        heading_coverage = (
            sum(1 for entity in concepts if entity.uri in heading_union) / len(concepts)
        )

        return CoverageResult(
            n_concepts=len(concepts),
            n_covered=n_covered,
            n_focus_concepts=sum(
                1 for entity in concepts if entity.kind in self.focus_kinds
            ),
            coverage=n_covered / len(concepts),
            coverage_top1=sum(1 for e in concepts if e.uri in top1) / len(concepts),
            coverage_top3=sum(1 for e in concepts if e.uri in top3) / len(concepts),
            coverage_weighted=sum(w for w, flag in zip(weights, covered_flags) if flag)
            / total_weight,
            coverage_mean_passage=sum(per_passage) / len(per_passage),
            heading_coverage=heading_coverage,
            pair_coverage=pair_coverage,
            pair_sentence_coverage=pair_sentence_coverage,
            pair_rank_score=pair_rank_score,
            intent=intent,
            relation_coverage=relation_coverage,
            relation_rank_score=relation_rank_score,
            concepts=[
                {
                    "uri": entity.uri,
                    "label": entity.label,
                    "kind": entity.kind,
                    "weight": round(weight, 3),
                    "covered": flag,
                }
                for entity, weight, flag in zip(concepts, weights, covered_flags)
            ],
        )
