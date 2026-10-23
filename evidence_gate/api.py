"""Gemini generation with on-disk caching, retry, and rate limiting."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path

from evidence_gate.config import (
    CACHE_DIR,
    GENERATION_PER_MINUTE,
    GENERATOR_MODEL,
    GENERATOR_TEMPERATURE,
    GOOGLE_API_KEY,
    MAX_GENERATION_RETRIES,
)

logger = logging.getLogger(__name__)

ANSWER_SYSTEM_PROMPT = """You answer biomedical research questions using only the
provided evidence passages. The answer must be exactly one of: yes, no, maybe.

- Answer "yes" when the evidence clearly supports the affirmative.
- Answer "no" when the evidence clearly supports the negative.
- Answer "maybe" when the evidence is insufficient, mixed, or ambiguous.

Output only one word: yes, no, or maybe."""

REFINE_SYSTEM_PROMPT = """You are a biomedical literature search assistant.
Given a question and partially relevant passages, write one focused follow-up
search query that targets the missing evidence. Output only the query (under
30 words)."""


def _parse_answer(text: str) -> str:
    match = re.search(r"\b(yes|no|maybe)\b", text.strip().lower())
    return match.group(1) if match else "maybe"


class GenerationClient:
    """Thin wrapper around the Gemini API with a persistent response cache."""

    def __init__(
        self,
        model: str = GENERATOR_MODEL,
        temperature: float = GENERATOR_TEMPERATURE,
        cache_path: Path | str = CACHE_DIR / "generation_cache.json",
    ):
        self.model = model
        self.temperature = temperature
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict] = {}
        if self.cache_path.exists():
            try:
                self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Ignoring corrupt generation cache.")
        self._client = None
        self._min_interval = 60.0 / max(GENERATION_PER_MINUTE, 1)
        self._last_call = 0.0
        self.n_api_calls = 0

    def _get_client(self):
        if self._client is None:
            if not GOOGLE_API_KEY:
                raise RuntimeError(
                    "GOOGLE_API_KEY is not set. Add it to .env or use a cached run."
                )
            from google import genai

            self._client = genai.Client(api_key=GOOGLE_API_KEY)
        return self._client

    def _key(self, system: str, user: str) -> str:
        raw = f"{self.model}|{self.temperature}|{system}|{user}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _call(self, system: str, user: str, max_output_tokens: int = 8) -> str:
        from google.genai import types

        client = self._get_client()
        # Disable hidden reasoning tokens so the tiny answer/JSON budgets are not
        # consumed by thinking. Models that reject the field are retried once
        # without it (see the except block).
        thinking_disabled = True
        for attempt in range(MAX_GENERATION_RETRIES):
            extra = (
                {"thinking_config": types.ThinkingConfig(thinking_budget=0)}
                if thinking_disabled
                else {}
            )
            wait = self._min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=self.temperature,
                        max_output_tokens=max_output_tokens,
                        **extra,
                    ),
                )
                self.n_api_calls += 1
                return (response.text or "").strip()
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if thinking_disabled and (
                    "thinking" in message.lower() or "INVALID_ARGUMENT" in message
                ):
                    thinking_disabled = False
                    continue
                exhausted = "RESOURCE_EXHAUSTED" in message or "429" in message
                # Free-tier daily quota exhaustion does not recover within a
                # retry loop; fail fast so the resumable runner can stop
                # cleanly instead of burning minutes per question.
                if exhausted and attempt >= 1:
                    raise
                if attempt == MAX_GENERATION_RETRIES - 1:
                    raise
                match = re.search(r"retry in ([0-9.]+)s", message, re.IGNORECASE)
                delay = float(match.group(1)) if match else 5.0 * (attempt + 1)
                delay = min(delay + 1.0, 30.0)
                logger.warning("Generation failed (%s); retrying in %.1fs", message[:120], delay)
                time.sleep(delay)
        raise RuntimeError("unreachable")

    def _cached_call(self, system: str, user: str, max_output_tokens: int = 8) -> str:
        key = self._key(system, user)
        if key in self._cache:
            return self._cache[key]["text"]
        text = self._call(system, user, max_output_tokens=max_output_tokens)
        self._cache[key] = {"model": self.model, "text": text}
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._cache), encoding="utf-8")
        tmp.replace(self.cache_path)
        return text

    def answer(self, question: str, passages: list[str], max_chars: int = 1400) -> dict:
        context = "\n\n---\n\n".join(
            f"[Passage {i + 1}]\n{p[:max_chars]}" for i, p in enumerate(passages)
        )
        user = (
            f"Evidence passages:\n{context}\n\n"
            f"Research question: {question}\n\n"
            "Based on the evidence above, is the answer yes, no, or maybe?"
        )
        raw = self._cached_call(ANSWER_SYSTEM_PROMPT, user)
        return {"answer": _parse_answer(raw), "raw": raw}

    def refine(self, question: str, passages: list[str]) -> str:
        context = "\n\n".join(f"[Passage {i + 1}]\n{p[:400]}" for i, p in enumerate(passages[:3]))
        user = (
            f"Original question: {question}\n\n"
            f"Partially relevant passages:\n{context}\n\n"
            "What specific search query would find the missing evidence?"
        )
        return self._cached_call(REFINE_SYSTEM_PROMPT, user, max_output_tokens=64).strip()
