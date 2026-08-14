"""Ontology reasoner — traverses the RDF graph to expand queries.

This is the core of Pipeline 3. Given a user query, it:
1. Matches query terms to ontology concepts.
2. Traverses ontology relations (equivalence, hierarchy, domain properties).
3. Returns expanded terms and a detailed reasoning log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from rdflib import Graph, Namespace, RDFS, OWL, RDF

from src.config import ONTOLOGY_NAMESPACE, ONTOLOGY_FILE


MED = Namespace(ONTOLOGY_NAMESPACE)


@dataclass
class ReasoningTrace:
    """Captures the full reasoning path for explainability."""
    original_query: str
    matched_concepts: list[dict] = field(default_factory=list)
    expansions: list[dict] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)

    def get_all_terms(self) -> list[str]:
        """All expansion terms (labels) collected during reasoning."""
        return list(self.expanded_terms)

    def to_dict(self) -> dict:
        return {
            "original_query": self.original_query,
            "matched_concepts": self.matched_concepts,
            "expansions": self.expansions,
            "expanded_terms": self.expanded_terms,
        }

    def to_context_string(self) -> str:
        """Format reasoning trace as context string for the generator prompt."""
        lines = [f"Query: {self.original_query}"]
        for match in self.matched_concepts:
            lines.append(f"  Matched: '{match['term']}' → {match['concept_id']} ({match['label']})")
        for exp in self.expansions:
            lines.append(f"  Expansion ({exp['relation']}): {exp['source']} → {exp['target']} ({exp['target_label']})")
        return "\n".join(lines)


class OntologyReasoner:
    """Traverses the medical ontology to expand queries with related concepts."""

    def __init__(self, ontology_path: str | None = None):
        """Load the ontology graph.

        Args:
            ontology_path: Path to the .ttl ontology file. Defaults to config.
        """
        self.graph = Graph()
        path = ontology_path or str(ONTOLOGY_FILE)
        self.graph.parse(path, format="turtle")

        # Build label → concept URI lookup (case-insensitive)
        self._label_index: dict[str, list[tuple]] = {}
        for s, _, o in self.graph.triples((None, RDFS.label, None)):
            label_lower = str(o).lower()
            if label_lower not in self._label_index:
                self._label_index[label_lower] = []
            # Extract local name
            local_name = str(s).split("#")[-1] if "#" in str(s) else str(s).split("/")[-1]
            self._label_index[label_lower].append((s, local_name, str(o)))

    def match_concepts(self, query: str) -> list[dict]:
        """Find ontology concepts mentioned in the query.

        Uses a simple substring matching approach against concept labels.
        Returns matches sorted by label length (longest match first).
        """
        query_lower = query.lower()
        matches = []

        for label, concept_list in self._label_index.items():
            if label in query_lower:
                for uri, local_name, original_label in concept_list:
                    matches.append({
                        "uri": uri,
                        "concept_id": local_name,
                        "label": original_label,
                        "term": label,
                    })

        # Sort by label length descending (prefer longer, more specific matches)
        matches.sort(key=lambda x: len(x["term"]), reverse=True)

        # Deduplicate by concept_id
        seen = set()
        unique_matches = []
        for m in matches:
            if m["concept_id"] not in seen:
                seen.add(m["concept_id"])
                unique_matches.append(m)

        return unique_matches

    def expand_concept(
        self,
        concept_uri,
        enable_equivalence: bool = True,
        enable_hierarchy: bool = True,
        enable_properties: bool = True,
        max_depth: int = 2,
    ) -> list[dict]:
        """Expand a concept by traversing ontology relations.

        Args:
            concept_uri: The RDF URI of the concept to expand.
            enable_equivalence: Traverse owl:equivalentClass.
            enable_hierarchy: Traverse rdfs:subClassOf (up and down).
            enable_properties: Traverse domain properties (hasSymptom, treatedBy, etc.).
            max_depth: Maximum traversal depth for hierarchy.

        Returns:
            List of expansion dicts with relation, source, target, target_label.
        """
        expansions = []

        # 1. Equivalence expansions
        if enable_equivalence:
            # Forward: this concept equivalentClass other
            for _, _, equiv in self.graph.triples((concept_uri, OWL.equivalentClass, None)):
                label = self._get_label(equiv)
                expansions.append({
                    "relation": "equivalentClass",
                    "source": self._local_name(concept_uri),
                    "target": self._local_name(equiv),
                    "target_label": label,
                })

            # Reverse: other equivalentClass this concept
            for equiv, _, _ in self.graph.triples((None, OWL.equivalentClass, concept_uri)):
                label = self._get_label(equiv)
                expansions.append({
                    "relation": "equivalentClass",
                    "source": self._local_name(concept_uri),
                    "target": self._local_name(equiv),
                    "target_label": label,
                })

        # 2. Hierarchy expansions
        if enable_hierarchy:
            # Superclasses (go up)
            for _, _, parent in self.graph.triples((concept_uri, RDFS.subClassOf, None)):
                label = self._get_label(parent)
                if label:  # skip blank nodes / top-level OWL classes
                    expansions.append({
                        "relation": "subClassOf (parent)",
                        "source": self._local_name(concept_uri),
                        "target": self._local_name(parent),
                        "target_label": label,
                    })

            # Subclasses (go down, limited depth)
            self._collect_subclasses(concept_uri, expansions, depth=0, max_depth=max_depth)

        # 3. Domain property expansions
        if enable_properties:
            domain_props = [MED.hasSymptom, MED.treatedBy, MED.diagnosedBy, MED.relatedCondition]

            for prop in domain_props:
                # Forward: concept → related
                for _, _, target in self.graph.triples((concept_uri, prop, None)):
                    label = self._get_label(target)
                    expansions.append({
                        "relation": self._local_name(prop),
                        "source": self._local_name(concept_uri),
                        "target": self._local_name(target),
                        "target_label": label,
                    })

                # Reverse: related → concept (e.g., what diseases have this symptom?)
                for source, _, _ in self.graph.triples((None, prop, concept_uri)):
                    label = self._get_label(source)
                    expansions.append({
                        "relation": f"{self._local_name(prop)} (inverse)",
                        "source": self._local_name(concept_uri),
                        "target": self._local_name(source),
                        "target_label": label,
                    })

        return expansions

    def expand_query(
        self,
        query: str,
        use_equivalence: bool = True,
        use_hierarchy: bool = True,
        use_properties: bool = True,
    ) -> ReasoningTrace:
        """Alias for :meth:`reason` — matches the pipeline API.

        Expands a query by matching concepts and traversing ontology
        relations, returning a ReasoningTrace.
        """
        return self.reason(
            query,
            enable_equivalence=use_equivalence,
            enable_hierarchy=use_hierarchy,
            enable_properties=use_properties,
        )

    def reason(
        self,
        query: str,
        enable_equivalence: bool = True,
        enable_hierarchy: bool = True,
        enable_properties: bool = True,
    ) -> ReasoningTrace:
        """Full reasoning pipeline: match concepts → expand → collect terms.

        This is the main entry point for Pipeline 3.

        Args:
            query: The user's medical question.
            enable_equivalence: Whether to use owl:equivalentClass.
            enable_hierarchy: Whether to use rdfs:subClassOf.
            enable_properties: Whether to use domain properties.

        Returns:
            ReasoningTrace with matched concepts, expansions, and expanded terms.
        """
        trace = ReasoningTrace(original_query=query)

        # Step 1: Match query terms to ontology concepts
        matches = self.match_concepts(query)
        trace.matched_concepts = matches

        # Step 2: Expand each matched concept
        expanded_labels = set()
        for match in matches:
            expansions = self.expand_concept(
                match["uri"],
                enable_equivalence=enable_equivalence,
                enable_hierarchy=enable_hierarchy,
                enable_properties=enable_properties,
            )
            trace.expansions.extend(expansions)

            # Collect unique labels for query expansion
            for exp in expansions:
                if exp["target_label"]:
                    expanded_labels.add(exp["target_label"])

        trace.expanded_terms = sorted(expanded_labels)
        return trace

    def _collect_subclasses(self, uri, expansions: list, depth: int, max_depth: int):
        """Recursively collect subclasses up to max_depth."""
        if depth >= max_depth:
            return

        for child, _, _ in self.graph.triples((None, RDFS.subClassOf, uri)):
            label = self._get_label(child)
            if label:
                expansions.append({
                    "relation": f"subClassOf (child, depth={depth + 1})",
                    "source": self._local_name(uri),
                    "target": self._local_name(child),
                    "target_label": label,
                })
                self._collect_subclasses(child, expansions, depth + 1, max_depth)

    def _get_label(self, uri) -> str:
        """Get the rdfs:label for a URI, or empty string if none."""
        for _, _, label in self.graph.triples((uri, RDFS.label, None)):
            return str(label)
        return ""

    def _local_name(self, uri) -> str:
        """Extract the local name from a URI (part after # or last /)."""
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        return uri_str.split("/")[-1]
