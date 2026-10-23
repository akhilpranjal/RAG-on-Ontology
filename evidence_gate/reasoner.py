"""Ontology-grounded gap bridging.

When retrieved evidence is only partially sufficient, this module links the
question and the retrieved passages to the OntoGate graph, identifies the
relation family the question is asking about, and appends the labels of
missing related entities to the follow-up query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from evidence_gate.config import MAX_EXPANSION_TERMS
from evidence_gate.ontology import LinkedEntity, OntologyGraph, STOP_LABELS, normalize_label

TREATMENT_CUES = re.compile(
    r"\b(treat|treated|treats|treatment|therapy|therapies|therapeutic|drug|drugs|"
    r"medication|medications|medicine|effective|efficacy|effectiveness|benefit|"
    r"beneficial|improve|improves|improved|reduce|reduces|reduced|lower|lowers|"
    r"management|intervention|prevent|prevents|prevention|prophyla\w*|"
    r"inhibit|inhibitor|agonist|antagonist|statin|aspirin|surgery|transplant)\b",
    re.IGNORECASE,
)
SYMPTOM_CUES = re.compile(
    r"\b(symptom|symptoms|sign|signs|present|presents|presentation|manifest\w*|"
    r"complain\w*|pain|fever|cough|fatigue|nausea|dyspnea|shortness of breath|"
    r"bleeding|rash|headache|dizziness|edema|swelling)\b",
    re.IGNORECASE,
)
HIERARCHY_CUES = re.compile(
    r"\b(subtype|subtypes|type of|types of|class of|classes|variant|variants|"
    r"form of|forms of|subgroup|subgroups|subset|subsets|category|categories|"
    r"comorbid\w*|co-occur\w*|associated condition\w*|related condition\w*)\b",
    re.IGNORECASE,
)
DIAGNOSIS_CUES = re.compile(
    r"\b(diagnos\w*|detect\w*|screen\w*|test|tests|testing|biomarker|marker|"
    r"predict\w*|imaging|ultrasound|mri|ct scan|biopsy|assay|sensitivity|specificity)\b",
    re.IGNORECASE,
)
CAUSE_CUES = re.compile(
    r"\b(cause|causes|caused|causal|risk factor|risk factors|lead to|leads to|"
    r"increase|increases|increased|decrease|decreases|decreased|effect of|"
    r"side effect|side effects|adverse|complication|complications|toxicity)\b",
    re.IGNORECASE,
)

RELATION_PLANS = {
    "treatment": {
        "Disease": ["treatedBy", "palliatedBy"],
        "Compound": ["treats", "palliates"],
        "Chemical": ["treats", "palliates"],
        "Symptom": ["treatedBy"],
    },
    "symptom": {
        "Disease": ["presents"],
        "Symptom": ["presents"],
        "Compound": ["causesSideEffect"],
    },
    "hierarchy": {
        "Disease": ["hasSubclass"],
        "Compound": ["hasSubclass"],
        "Symptom": ["hasSubclass"],
        "Anatomy": ["hasSubclass"],
    },
    "diagnosis": {
        "Disease": ["localizes", "hasSubclass"],
        "Anatomy": ["localizedIn"],
    },
    "cause": {
        "Disease": ["resembles", "hasSubclass"],
        "Compound": ["causesSideEffect", "treatedBy"],
        "Symptom": [],
    },
    "default": {
        "Disease": ["hasSubclass", "presents", "resembles"],
        "Compound": ["treats", "causesSideEffect"],
        "Symptom": ["presents"],
        "Anatomy": ["localizedIn"],
    },
}

# MeSH hierarchy relations are kind-agnostic: every descriptor has a place in
# the tree, so they are the fallback when the intent plan has no clinical edge
# for a node (e.g. a Technique or a generic Concept).
HIERARCHY_RELATIONS = ["hasSubclass"]

# Generic MeSH branches (Concept, Discipline, Humanities, Geography, ...) have
# no useful clinical neighbours; expanding them pulls in unrelated terms.
EXPANDABLE_KINDS = {"Disease", "Compound", "Chemical", "Symptom", "Anatomy", "Technique"}


@dataclass
class OntologyRefinement:
    query: str
    intent: str
    grounded: bool
    entities: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)
    added_terms: list[str] = field(default_factory=list)
    linked: list[LinkedEntity] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "intent": self.intent,
            "grounded": self.grounded,
            "entities": self.entities,
            "relations": self.relations,
            "added_terms": self.added_terms,
        }


def detect_intent(text: str) -> str:
    """Rule-based relation-intent classifier over the question text."""
    if TREATMENT_CUES.search(text):
        return "treatment"
    if HIERARCHY_CUES.search(text):
        return "hierarchy"
    if SYMPTOM_CUES.search(text):
        return "symptom"
    if DIAGNOSIS_CUES.search(text):
        return "diagnosis"
    if CAUSE_CUES.search(text):
        return "cause"
    return "default"


class OntologyReasoner:
    """Constructs structure-grounded follow-up queries from the ontology."""

    def __init__(
        self,
        graph: OntologyGraph,
        max_terms: int = MAX_EXPANSION_TERMS,
    ):
        self.graph = graph
        self.max_terms = max_terms

    def refine(
        self,
        question: str,
        passages: list[str],
        must_not_contain: str | None = None,
    ) -> OntologyRefinement:
        intent = detect_intent(question)
        plan = RELATION_PLANS[intent]

        linked = self.graph.link(question, max_entities=6)
        if not linked:
            # Fall back to topic entities mentioned in the most relevant passages.
            for passage in passages[:2]:
                linked = self.graph.link(passage, max_entities=6)
                if linked:
                    break

        if not linked:
            return OntologyRefinement(
                query=question, intent=intent, grounded=False
            )

        context_norm = normalize_label(
            " ".join([question, must_not_contain or "", *passages[:3]])
        )
        context_tokens = set(context_norm.split())

        added: list[str] = []
        used_relations: list[str] = []
        seen_terms: set[str] = set()

        def add_term(label: str, relation: str) -> bool:
            norm = normalize_label(label)
            if not label or not norm or norm in STOP_LABELS:
                return False
            tokens = norm.split()
            if len(tokens) > 8:
                return False
            if all(token in context_tokens for token in tokens):
                return False
            if norm in seen_terms:
                return False
            if any(norm in normalize_label(existing) for existing in added):
                return False
            seen_terms.add(norm)
            added.append(label)
            if relation and relation not in used_relations:
                used_relations.append(relation)
            return True

        for entity in linked:
            # 1. Surface the canonical label of a node that the question
            #    mentioned only through an alias (e.g. HMO -> Health
            #    Maintenance Organizations). If the canonical label is
            #    already in the context, spelling variants add nothing.
            canonical = normalize_label(entity.label)
            if canonical and not all(t in context_tokens for t in canonical.split()):
                if add_term(entity.label, "synonym") and len(added) >= self.max_terms:
                    break
            if entity.kind not in EXPANDABLE_KINDS:
                continue

            # 2. Intent-specific clinical relations.
            before = len(added)
            for neighbour_uri, relation in self.graph.neighbors(
                entity.uri, plan.get(entity.kind, []), limit=20
            ):
                if add_term(self.graph.label(neighbour_uri), relation):
                    if len(added) >= self.max_terms:
                        break
            if len(added) >= self.max_terms:
                break

            # 3. Hierarchy fallback for nodes without a clinical edge in the
            #    intent plan (common for Techniques and generic Concepts).
            if len(added) == before:
                for neighbour_uri, relation in self.graph.neighbors(
                    entity.uri, HIERARCHY_RELATIONS, limit=12
                ):
                    if add_term(self.graph.label(neighbour_uri), relation):
                        if len(added) >= self.max_terms:
                            break
            if len(added) >= self.max_terms:
                break

        if not added:
            return OntologyRefinement(
                query=question,
                intent=intent,
                grounded=False,
                entities=[e.label for e in linked],
                linked=linked,
            )

        query = question.rstrip(".?! ") + " " + " ".join(added)
        return OntologyRefinement(
            query=query,
            intent=intent,
            grounded=True,
            entities=[e.label for e in linked],
            relations=used_relations,
            added_terms=added,
            linked=linked,
        )
