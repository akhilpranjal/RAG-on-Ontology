"""NLI-based Evidence Sufficiency Scorer (ESS).

Relevance and sufficiency are different signals. A passage can be topically
relevant (high embedding similarity) yet contain no claim that supports or
contradicts the question. The ESS measures inferential support instead:

    e_i = max(P(entail | p_i, h), P(contradict | p_i, h))
    s   = mean of the top-m e_i

Both entailment and contradiction are decision-relevant; ``neutral`` is the
insufficiency signal.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from evidence_gate.config import NLI_BATCH_SIZE, NLI_MODEL, TOP_M, configure_cpu

logger = logging.getLogger(__name__)

# Function words and generic clinical vocabulary. These tokens are ignored
# when checking whether a passage is topically about the question.
CONTENT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "between",
    "by", "can", "could", "did", "do", "does", "during", "for", "from", "had",
    "has", "have", "how", "if", "in", "into", "is", "it", "its", "may",
    "might", "more", "most", "no", "not", "of", "on", "or", "our", "should",
    "than", "that", "the", "their", "them", "these", "they", "this", "those",
    "to", "was", "we", "were", "what", "when", "which", "who", "why", "will",
    "with", "would", "after", "before", "also", "any", "all", "both", "each",
    "other", "some", "such", "use", "used", "using", "associated", "association",
    "effect", "effects", "effective", "efficacy", "outcome", "outcomes",
    "patient", "patients", "study", "studies", "trial", "trials", "group",
    "groups", "risk", "risks", "role", "roles", "level", "levels", "result",
    "results", "increase", "increases", "increased", "decrease", "decreases",
    "decreased", "reduce", "reduces", "reduced", "improve", "improves",
    "improved", "higher", "lower", "compared", "comparison", "difference",
    "differences", "significant", "significantly", "versus", "vs", "among",
    "there", "however", "therefore", "conclusion", "conclusions", "background",
    "objective", "objectives", "methods", "method", "aim", "aims", "purpose",
    "status", "time", "times", "year", "years", "age", "ages", "female",
    "male", "women", "woman", "men", "man", "children", "child", "adult",
    "adults", "human", "humans", "clinical", "clinically", "treatment",
    "treatments", "treated", "treat", "therapy", "therapies", "therapeutic",
    "disease", "diseases", "disorder", "disorders", "condition", "conditions",
    "symptom", "symptoms", "diagnosis", "diagnoses", "diagnostic", "care",
    "health", "medical", "medicine",
}


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def content_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {
        _stem(word)
        for word in words
        if len(word) >= 3 and word not in CONTENT_STOPWORDS
    }



@dataclass
class SufficiencyResult:
    query: str
    hypothesis: str
    sufficiency_score: float
    per_passage_scores: list[float] = field(default_factory=list)
    per_passage_probs: list[dict[str, float]] = field(default_factory=list)
    per_passage_overlap: list[float] = field(default_factory=list)
    top_m_indices: list[int] = field(default_factory=list)
    nli_answer: str = "maybe"

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "hypothesis": self.hypothesis,
            "sufficiency_score": self.sufficiency_score,
            "per_passage_scores": self.per_passage_scores,
            "per_passage_probs": self.per_passage_probs,
            "per_passage_overlap": self.per_passage_overlap,
            "top_m_indices": self.top_m_indices,
            "nli_answer": self.nli_answer,
        }


class EvidenceSufficiencyScorer:
    def __init__(self, model_name: str = NLI_MODEL, device: str | None = None):
        configure_cpu()
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        logger.info("Loading NLI model %s on %s", model_name, device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(device).eval()
        self._detect_labels()

    def _detect_labels(self) -> None:
        id2label = getattr(self.model.config, "id2label", {}) or {}
        self.entail_idx, self.neutral_idx, self.contradict_idx = 0, 1, 2
        for idx, label in id2label.items():
            name = str(label).lower()
            if "entail" in name:
                self.entail_idx = int(idx)
            elif "neutral" in name:
                self.neutral_idx = int(idx)
            elif "contra" in name:
                self.contradict_idx = int(idx)
        logger.info(
            "NLI label order: entail=%d neutral=%d contradict=%d",
            self.entail_idx,
            self.neutral_idx,
            self.contradict_idx,
        )

    @staticmethod
    def query_to_hypothesis(query: str) -> str:
        """Turn a yes/no research question into a declarative hypothesis."""
        q = query.strip()
        if q.endswith("?"):
            q = q[:-1].strip()

        match = re.match(r"^(does|do|did)\s+(.+)", q, re.IGNORECASE)
        if match:
            rest = match.group(2)
            return rest[0].upper() + rest[1:] + "."

        match = re.match(r"^(is|are|was|were)\s+(.+)", q, re.IGNORECASE)
        if match:
            verb, rest = match.group(1).lower(), match.group(2)
            return f"{rest[0].upper()}{rest[1:]} {verb}."

        match = re.match(
            r"^(can|could|should|would|will|may|might)\s+(.+)", q, re.IGNORECASE
        )
        if match:
            modal, rest = match.group(1).lower(), match.group(2)
            return f"{rest[0].upper()}{rest[1:]} {modal}."

        match = re.match(r"^(has|have|had)\s+(.+)", q, re.IGNORECASE)
        if match:
            verb, rest = match.group(1).lower(), match.group(2)
            return f"{rest[0].upper()}{rest[1:]} {verb}."

        return q[0].upper() + q[1:] + "." if q else q

    @torch.no_grad()
    def _predict(self, premises: list[str], hypothesis: str) -> np.ndarray:
        output: list[np.ndarray] = []
        for start in range(0, len(premises), NLI_BATCH_SIZE):
            batch = premises[start : start + NLI_BATCH_SIZE]
            inputs = self.tokenizer(
                batch,
                [hypothesis] * len(batch),
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(self.device)
            logits = self.model(**inputs).logits
            output.append(torch.softmax(logits, dim=-1).cpu().numpy())
        return np.vstack(output)

    def score(
        self,
        query: str,
        passages: list[str],
        top_m: int = TOP_M,
        min_overlap: float = 0.20,
    ) -> SufficiencyResult:
        if not passages:
            return SufficiencyResult(query=query, hypothesis="", sufficiency_score=0.0)

        hypothesis = self.query_to_hypothesis(query)
        probs = self._predict(passages, hypothesis)
        query_tokens = content_tokens(query)

        per_scores: list[float] = []
        per_probs: list[dict[str, float]] = []
        overlaps: list[float] = []
        for row, passage in zip(probs, passages):
            entail = float(row[self.entail_idx])
            neutral = float(row[self.neutral_idx])
            contradict = float(row[self.contradict_idx])
            passage_tokens = content_tokens(passage)
            overlap = (
                len(query_tokens & passage_tokens) / len(query_tokens)
                if query_tokens
                else 0.0
            )
            overlaps.append(overlap)
            # An unrelated passage can be confidently classified as a
            # contradiction. Require lexical topic overlap before treating
            # an NLI decision as evidence about this question.
            strength = max(entail, contradict) if overlap >= min_overlap else 0.0
            per_scores.append(strength)
            per_probs.append(
                {
                    "entail": entail,
                    "neutral": neutral,
                    "contradict": contradict,
                    "overlap": overlap,
                }
            )

        order = sorted(range(len(per_scores)), key=lambda i: per_scores[i], reverse=True)
        top_idx = order[: min(top_m, len(order))]
        sufficiency = float(np.mean([per_scores[i] for i in top_idx]))

        # Cheap NLI-only answer used for threshold calibration (no LLM calls).
        entail_sum = sum(per_probs[i]["entail"] for i in top_idx)
        contra_sum = sum(per_probs[i]["contradict"] for i in top_idx)
        if sufficiency == 0.0:
            nli_answer = "maybe"
        elif entail_sum >= contra_sum + 0.15:
            nli_answer = "yes"
        elif contra_sum >= entail_sum + 0.15:
            nli_answer = "no"
        else:
            nli_answer = "maybe"

        return SufficiencyResult(
            query=query,
            hypothesis=hypothesis,
            sufficiency_score=sufficiency,
            per_passage_scores=per_scores,
            per_passage_probs=per_probs,
            per_passage_overlap=overlaps,
            top_m_indices=top_idx,
            nli_answer=nli_answer,
        )
