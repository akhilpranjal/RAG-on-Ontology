"""LLM-based evidence sufficiency verification.

The NLI scorer is cheap but its contradiction head fires on merely unrelated
passages, so it cannot separate "related but uninformative" from "sufficient".
A single structured LLM call is a more reliable verifier and also returns the
answer, so the gate does not need a second generation call.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from evidence_gate.api import GenerationClient

JUDGE_SYSTEM_PROMPT = """You are a careful biomedical evidence assessor. You receive a research
question and retrieved evidence passages. Decide whether the passages contain
enough information to answer the question with a clear yes or no. Then answer.

Return strict JSON only:
{"sufficient": "yes" | "partial" | "no", "answer": "yes" | "no" | "maybe"}

- sufficient=yes: the passages directly address the question and support a clear answer.
- sufficient=partial: the passages are related but do not settle the question.
- sufficient=no: the passages are off-topic or irrelevant.
- answer=maybe only when the evidence is genuinely ambiguous or conflicting."""

SUFFICIENCY_SCORES = {"yes": 1.0, "partial": 0.5, "no": 0.0}


@dataclass
class JudgeResult:
    sufficiency_score: float
    sufficient: str
    answer: str
    raw: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def nli_answer(self) -> str:
        return self.answer

    def to_dict(self) -> dict:
        return {
            "sufficiency_score": self.sufficiency_score,
            "sufficient": self.sufficient,
            "answer": self.answer,
            "raw": self.raw,
            **self.metadata,
        }


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = re.sub(r"^json", "", text, flags=re.IGNORECASE).strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            payload = json.loads(match.group(0))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
    return {}


class LLMEvidenceJudge:
    """One structured call: sufficiency label + answer, with disk caching."""

    def __init__(self, generator: GenerationClient, max_chars: int = 1200):
        self.generator = generator
        self.max_chars = max_chars

    def judge(self, question: str, passages: list[str]) -> JudgeResult:
        if not passages:
            return JudgeResult(0.0, "no", "maybe", metadata={"reason": "no_passages"})
        context = "\n\n---\n\n".join(
            f"[Passage {i + 1}]\n{p[: self.max_chars]}"
            for i, p in enumerate(passages)
        )
        user = (
            f"Research question: {question}\n\n"
            f"Evidence passages:\n{context}\n\n"
            "Return the JSON object."
        )
        raw = self.generator._cached_call(
            JUDGE_SYSTEM_PROMPT, user, max_output_tokens=80
        )
        payload = _parse_json(raw)
        sufficient = str(payload.get("sufficient", "no")).strip().lower()
        if sufficient not in SUFFICIENCY_SCORES:
            sufficient = "no"
        answer = str(payload.get("answer", "maybe")).strip().lower()
        if answer not in {"yes", "no", "maybe"}:
            answer = "maybe"
        return JudgeResult(
            sufficiency_score=SUFFICIENCY_SCORES[sufficient],
            sufficient=sufficient,
            answer=answer,
            raw=raw,
        )
