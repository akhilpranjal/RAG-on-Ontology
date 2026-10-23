"""Answer-quality evaluation metrics.

Complements the retrieval metrics with answer-level measures:

1. Concept-Coverage F1 — objective: which expected medical concepts appear
   in the generated answer? Precision / Recall / F1 over ontology concepts.
2. LLM-as-judge correctness — holistic binary grading by a *different*
   Gemini variant than the generator (cross-model, avoids self-judging).
"""

from __future__ import annotations

import json
import re

from google import genai
from google.genai import types

from src.config import GOOGLE_API_KEY, LLM_JUDGE_MODEL
from src.ontology.reasoner import OntologyReasoner
from src.rate_limiter import acquire_generation


class ConceptResolver:
    """Maps ontology concept local names to their labels for answer scanning.

    Consistent with the reasoner's substring-matching approach: a concept is
    present in a text if any of its labels appears verbatim (case-insensitive).
    """

    def __init__(self):
        self.reasoner = OntologyReasoner()
        self._concept_labels: dict[str, list[str]] = {}
        for label_lower, concepts in self.reasoner._label_index.items():
            for _, local_name, original_label in concepts:
                self._concept_labels.setdefault(local_name, [])
                if original_label not in self._concept_labels[local_name]:
                    self._concept_labels[local_name].append(original_label)

    def extract_concepts(self, text: str) -> list[str]:
        """Return ontology concept local names mentioned in `text`."""
        text_lower = (text or "").lower()
        found = []
        for local_name, labels in self._concept_labels.items():
            if any(label.lower() in text_lower for label in labels):
                found.append(local_name)
        return sorted(set(found))


def concept_coverage_f1(
    answer: str,
    expected_concepts: list[str],
    resolver: ConceptResolver | None = None,
) -> dict:
    """Compute concept-coverage Precision / Recall / F1 for an answer.

    Args:
        answer: The generated answer text.
        expected_concepts: Ground-truth concept local names for the query
            (from queries.json 'target_concepts').
        resolver: ConceptResolver instance (reused for efficiency).

    Returns:
        Dict with precision, recall, f1, and the predicted concept set.
    """
    if resolver is None:
        resolver = ConceptResolver()

    predicted = set(resolver.extract_concepts(answer))
    expected = set(expected_concepts)

    if not expected:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "predicted_concepts": sorted(predicted),
            "expected_concepts": [],
        }

    true_positives = len(predicted & expected)
    precision = true_positives / len(predicted) if predicted else 0.0
    recall = true_positives / len(expected)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "predicted_concepts": sorted(predicted),
        "expected_concepts": sorted(expected),
    }


# ──────────────────────────────────────────────
# LLM-as-judge (cross-model)
# ──────────────────────────────────────────────

JUDGE_SYSTEM_PROMPT = """You are a strict medical answer grader. Given a medical question, the set of expected medical concepts, and a model's answer, judge whether the answer is CORRECT.

An answer is CORRECT if it directly addresses the question AND covers the expected concepts without major factual errors or unsupported claims.

Respond with ONLY a JSON object in this exact shape:
{"correct": true or false, "score": integer 0-10, "reason": "one short sentence"}"""


def _parse_judge_response(text: str) -> dict:
    """Extract structured fields from a judge response (JSON or loose text)."""
    text = (text or "").strip()
    # Try strict JSON first.
    try:
        data = json.loads(text)
        return {
            "correct": bool(data.get("correct", False)),
            "score": int(data.get("score", 0)),
            "reason": str(data.get("reason", "")),
        }
    except (json.JSONDecodeError, ValueError):
        pass

    # Loose parsing fallback.
    correct = "true" in text.lower()
    score_match = re.search(r"score[\"':\s]*(\d{1,2})", text, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else (10 if correct else 0)
    reason_match = re.search(r"reason[\"':\s]*([^\"]+)", text, re.IGNORECASE)
    reason = reason_match.group(1).strip() if reason_match else ""

    return {"correct": correct, "score": score, "reason": reason}


def judge_answer(
    question: str,
    expected_concepts: list[str],
    answer: str,
    judge_model: str = LLM_JUDGE_MODEL,
) -> dict:
    """Grade an answer with a separate Gemini model (cross-model judge).

    Args:
        question: The medical question.
        expected_concepts: Ground-truth concept local names.
        answer: The generated answer to grade.
        judge_model: Judge model id — must differ from the generator model.

    Returns:
        Dict with correct (bool), score (0-10), and reason.
    """
    client = genai.Client(api_key=GOOGLE_API_KEY)

    user_prompt = (
        f"Question: {question}\n\n"
        f"Expected concepts: {', '.join(expected_concepts)}\n\n"
        f"Answer: {answer}\n"
    )

    acquire_generation(judge_model)
    response = client.models.generate_content(
        model=judge_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_SYSTEM_PROMPT,
            temperature=0.0,
        ),
    )

    return _parse_judge_response(response.text)