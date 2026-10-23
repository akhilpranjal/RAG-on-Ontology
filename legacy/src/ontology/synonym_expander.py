"""Simple synonym/dictionary expander for Pipeline 2.

Loads a flat JSON synonym dictionary and expands query terms.
This serves as a baseline to prove whether a full ontology is
better than a simple lookup table.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import SYNONYM_DICT_FILE


class SynonymExpander:
    """Dictionary-based synonym expansion for Pipeline 2."""

    def __init__(self, dict_path: str | None = None):
        """Load the synonym dictionary.

        Args:
            dict_path: Path to the synonym JSON file. Defaults to config.
        """
        path = Path(dict_path) if dict_path else SYNONYM_DICT_FILE

        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self._synonyms: dict[str, list[str]] = json.load(f)
        else:
            self._synonyms = {}

        # Build reverse mapping too (clinical → lay)
        self._reverse: dict[str, list[str]] = {}
        for lay_term, clinical_terms in self._synonyms.items():
            for clinical in clinical_terms:
                if clinical.lower() not in self._reverse:
                    self._reverse[clinical.lower()] = []
                self._reverse[clinical.lower()].append(lay_term)

    def expand(self, query: str) -> list[str]:
        """Expand a query by looking up synonym matches.

        Performs case-insensitive substring matching against the dictionary.

        Args:
            query: The user's original query.

        Returns:
            List of expanded synonym terms.
        """
        query_lower = query.lower()
        expanded = []

        # Check lay → clinical
        for lay_term, clinical_terms in self._synonyms.items():
            if lay_term.lower() in query_lower:
                expanded.extend(clinical_terms)

        # Check clinical → lay
        for clinical_term, lay_terms in self._reverse.items():
            if clinical_term in query_lower:
                expanded.extend(lay_terms)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for term in expanded:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique.append(term)

        return unique
