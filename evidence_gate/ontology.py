"""Ontology loading and entity linking for OntoGate-RAG.

The graph is built by scripts/eg_build_ontology.py from MeSH 2026
(hierarchy and synonyms) and Hetionet v1.0 (clinical relations).
"""

from __future__ import annotations

import pickle
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from evidence_gate.config import GRAPH_CACHE_PATH, MAX_EXPANSION_TERMS

# Generic clinical words that match thousands of MeSH descriptors and add
# no retrieval signal on their own.
STOP_LABELS = {
    "human",
    "humans",
    "male",
    "female",
    "adult",
    "adults",
    "aged",
    "middle aged",
    "adolescent",
    "child",
    "children",
    "infant",
    "pregnancy",
    "treatment",
    "therapy",
    "disease",
    "diseases",
    "patient",
    "patients",
    "study",
    "studies",
    "risk",
    "risk factors",
    "prognosis",
    "diagnosis",
    "symptom",
    "symptoms",
    "clinical trial",
    "randomized controlled trial",
    "retrospective studies",
    "prospective studies",
    "follow up studies",
    "treatment outcome",
    "time factors",
    "surveys and questionnaires",
    "cross sectional studies",
    "cohort studies",
    "sensitivity and specificity",
    "predictive value of tests",
    "united states",
    "methods",
    "results",
    "conclusion",
    "background",
    "objective",
    "aim",
    "purpose",
    "outcome",
    "outcomes",
    "effect",
    "effects",
    "association",
    "associated",
    "levels",
    "level",
    "group",
    "groups",
    "data",
    "mortality",
    "morbidity",
    "incidence",
    "prevalence",
    "survival",
    "survival rate",
    "recurrence",
    "age factors",
    "sex factors",
    "logistic models",
    "multivariate analysis",
    "odds ratio",
    "confidence interval",
    "cohort",
    "treatment failure",
    "quality of life",
    "severity of illness index",
}


def normalize_label(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class LinkedEntity:
    uri: str
    label: str
    kind: str
    n_tokens: int


class OntologyGraph:
    """Compact adjacency graph backed by a pre-built pickle cache."""

    def __init__(
        self,
        cache_path: Path | str = GRAPH_CACHE_PATH,
        max_expansion_terms: int = MAX_EXPANSION_TERMS,
    ):
        cache_path = Path(cache_path)
        if not cache_path.exists():
            raise FileNotFoundError(
                f"Ontology cache not found: {cache_path}\n"
                "Run: uv run python scripts/eg_build_ontology.py"
            )
        with open(cache_path, "rb") as fh:
            payload = pickle.load(fh)
        self.nodes: dict[str, dict] = payload["nodes"]
        self.edges: dict[str, dict[str, list[str]]] = payload["edges"]
        self.max_expansion_terms = max_expansion_terms

        self._by_first: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
        self._max_tokens = 1
        for uri, info in self.nodes.items():
            labels = [info.get("label", "")]
            labels.extend(info.get("aliases", []) or [])
            seen_norms: set[str] = set()
            for label in labels:
                norm = normalize_label(label)
                if (
                    not norm
                    or norm in seen_norms
                    or norm in STOP_LABELS
                    or len(norm) < 3
                ):
                    continue
                seen_norms.add(norm)
                tokens = norm.split()
                if len(tokens) > self._max_tokens:
                    self._max_tokens = len(tokens)
                self._by_first[tokens[0]].append((len(tokens), norm, uri))
        for candidates in self._by_first.values():
            candidates.sort(key=lambda item: item[0], reverse=True)

    # ------------------------------------------------------------------
    # Entity linking
    # ------------------------------------------------------------------
    def link(self, text: str, max_entities: int = 8) -> list[LinkedEntity]:
        """Find ontology nodes explicitly mentioned in ``text``.

        Longest matches win; matches may not overlap. Very short and generic
        labels are ignored.
        """
        norm = normalize_label(text)
        tokens = norm.split()
        if not tokens:
            return []

        found: list[LinkedEntity] = []
        seen_uris: set[str] = set()
        i = 0
        while i < len(tokens):
            best: LinkedEntity | None = None
            for n_tokens, label, uri in self._by_first.get(tokens[i], ()):  # longest first
                if i + n_tokens > len(tokens):
                    continue
                if " ".join(tokens[i : i + n_tokens]) != label:
                    continue
                if uri in seen_uris:
                    continue
                best = LinkedEntity(
                    uri=uri,
                    label=self.nodes[uri].get("label") or label,
                    kind=self.nodes[uri].get("kind", "Concept"),
                    n_tokens=n_tokens,
                )
                break
            if best is not None:
                found.append(best)
                seen_uris.add(best.uri)
                i += best.n_tokens
                if len(found) >= max_entities:
                    break
            else:
                i += 1
        return found

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------
    def neighbors(self, uri: str, relations: list[str], limit: int = 50) -> list[tuple[str, str]]:
        """Return ``(uri, relation)`` neighbours reachable through ``relations``."""
        out: list[tuple[str, str]] = []
        rel_edges = self.edges.get(uri, {})
        for relation in relations:
            for target in rel_edges.get(relation, ())[:limit]:
                out.append((target, relation))
        return out

    def label(self, uri: str) -> str:
        return self.nodes.get(uri, {}).get("label", "")

    def kind(self, uri: str) -> str:
        return self.nodes.get(uri, {}).get("kind", "Concept")
