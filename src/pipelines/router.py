"""Symbolic query router for AdaOnto-RAG (Experiment 2).

Deterministic, zero-API-cost intent classification. Uses ONLY the query text,
ontology labels/structure, and the synonym lay-term list — never relevance
judgments or document annotations.

Pre-registered rule order (see docs/report/architecture_design.md):
  1. PRECISE (both relation sides named, no lay terms) -> no expansion
  2. LAY present -> (+cue -> FULL) else (EQUIV)
  3. HIER cues/pattern (and no treatment cue) -> HIER mask
  4. >=2 distinct cue groups -> FULL (multi-hop)
  5. TREAT cues -> TREAT mask
  6. SYMPTOM label + direction -> SYMP mask
  7. default -> EQUIV
"""

from __future__ import annotations

import json
import re

from rdflib import RDFS

from src.config import SYNONYM_DICT_FILE
from src.ontology.reasoner import OntologyReasoner, MED

# Pre-registered cue lists (exact strings frozen before Experiment 2 runs).
TREAT_CUES = [
    "treat", "medication", "medicine", "drug", "prescrib", "therap",
    "procedure", "surgical", "surgery", "relief", "prevent", "dos",
    "management", "control", "diagnos", "test", "assess", "evaluat",
    "detect", "criteria",
]
HIER_CUES = [
    "types of", "kinds of", "forms of", "fall under", "classified as",
    "categorized under", "categor", "sub-condition", "subcondition",
    "complication", "associated with", "related to", "manifestations",
]
GROUP_PATTERN = re.compile(r"what \w+ (diseases|disorders|conditions|arrhythmias)")
DIRECTION_WORDS = [
    "what", "which", "cause", "present", "produce", "indicate", "sign", "symptom",
]

# Masks as (use_equivalence, use_hierarchy, use_properties).
MASKS = {
    "NONE": (False, False, False),
    "EQUIV": (True, False, False),
    "HIER": (True, True, False),
    "TREAT": (True, False, True),
    "SYMP": (True, False, True),
    "FULL": (True, True, True),
}


class QueryRouter:
    """Routes a query to an intent + expansion mask."""

    def __init__(self, reasoner: OntologyReasoner | None = None):
        self.reasoner = reasoner or OntologyReasoner()
        g = self.reasoner.graph

        with open(SYNONYM_DICT_FILE, "r", encoding="utf-8") as f:
            self.lay_terms = [k.lower() for k in json.load(f)]

        # Symptom vocabulary: labels of Symptom subclasses plus labels of
        # their equivalence partners (lay symptom phrasings like
        # "chest tightness" count as symptom intent).
        self.symptom_labels: set[str] = set()
        symptom_uris = set(self._descendants(MED.Symptom))
        for uri in list(symptom_uris):
            for _, _, partner in g.triples((uri, _owl_equiv(), None)):
                symptom_uris.add(partner)
            for partner, _, _ in g.triples((None, _owl_equiv(), uri)):
                symptom_uris.add(partner)
        for uri in symptom_uris:
            for _, _, label in g.triples((uri, RDFS.label, None)):
                self.symptom_labels.add(str(label).lower())

    def _descendants(self, root):
        """All transitive subclasses of root (BFS, cycle-safe)."""
        g = self.reasoner.graph
        seen, frontier = set(), [root]
        while frontier:
            node = frontier.pop()
            for child, _, _ in g.triples((None, RDFS.subClassOf, node)):
                if child not in seen:
                    seen.add(child)
                    frontier.append(child)
        return seen

    def _is_a(self, uri, root) -> bool:
        """Transitive superclass check (BFS up, depth-capped, cycle-safe)."""
        g = self.reasoner.graph
        seen, frontier, depth = set(), [(uri, 0)], 0
        while frontier:
            node, depth = frontier.pop()
            if node == root:
                return True
            if depth >= 8 or node in seen:
                continue
            seen.add(node)
            for _, _, parent in g.triples((node, RDFS.subClassOf, None)):
                frontier.append((parent, depth + 1))
        return False

    def route(self, query: str) -> dict:
        """Classify query intent; return intent + expansion mask flags."""
        q = query.lower()
        lay = [t for t in self.lay_terms if t in q]
        matches = self.reasoner.match_concepts(query)

        treat_side = any(
            self._is_a(m["uri"], MED.Treatment) or self._is_a(m["uri"], MED.DiagnosticTest)
            for m in matches
        )
        disease_side = any(self._is_a(m["uri"], MED.Disease) for m in matches)

        cue_treat = any(c in q for c in TREAT_CUES)
        cue_hier = any(c in q for c in HIER_CUES) or bool(GROUP_PATTERN.search(q))
        symp_hit = any(s in q for s in self.symptom_labels)
        direction = any(w in q for w in DIRECTION_WORDS)
        groups = {
            "treat": cue_treat,
            "hier": cue_hier,
            "symp": symp_hit and direction,
        }

        if treat_side and disease_side and not lay:
            intent, mask = "precise", "NONE"
        elif lay:
            if cue_treat or cue_hier or (symp_hit and direction):
                intent, mask = "lay_complex", "FULL"
            else:
                intent, mask = "lay", "EQUIV"
        elif cue_hier and not cue_treat:
            intent, mask = "hierarchy", "HIER"
        elif sum(1 for v in groups.values() if v) >= 2:
            intent, mask = "multihop", "FULL"
        elif cue_treat:
            intent, mask = "treatment", "TREAT"
        elif symp_hit and direction:
            intent, mask = "symptom", "SYMP"
        else:
            intent, mask = "default", "EQUIV"

        use_equiv, use_hier, use_props = MASKS[mask]
        return {
            "intent": intent,
            "mask": mask,
            "use_equivalence": use_equiv,
            "use_hierarchy": use_hier,
            "use_properties": use_props,
            "use_expansion": mask != "NONE",
            "lay_terms_found": lay,
            "matched_concepts": [m["concept_id"] for m in matches],
        }


def _owl_equiv():
    from rdflib import OWL

    return OWL.equivalentClass
