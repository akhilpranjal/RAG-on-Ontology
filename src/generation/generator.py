"""Gemini-based answer generator with shared prompt template.

All three pipelines use the same generator; only the context
provided differs (Pipeline 3 appends ontology reasoning context).
"""

from __future__ import annotations

from google import genai
from google.genai import types

from src.config import GOOGLE_API_KEY, GENERATOR_MODEL, GENERATOR_TEMPERATURE


def _get_client() -> genai.Client:
    return genai.Client(api_key=GOOGLE_API_KEY)


# ──────────────────────────────────────────────
# Prompt Templates
# ──────────────────────────────────────────────

BASE_SYSTEM_PROMPT = """You are a medical question-answering assistant. Your role is to provide accurate, evidence-based answers using ONLY the provided context documents. If the context does not contain sufficient information to answer the question, say so clearly.

Guidelines:
- Base your answer strictly on the provided context.
- Be concise but thorough.
- Use medical terminology appropriately, explaining lay terms when relevant.
- If the context is insufficient, state: "The provided context does not contain enough information to fully answer this question."
"""

BASE_USER_PROMPT = """Context Documents:
{context}

Question: {question}

Provide a comprehensive, evidence-based answer using only the context above."""

ONTOLOGY_ENHANCED_USER_PROMPT = """Context Documents:
{context}

Ontology Reasoning Context:
{ontology_context}

Question: {question}

Provide a comprehensive, evidence-based answer using the context documents above. The ontology reasoning context shows related medical concepts that were used to improve document retrieval."""


def generate_answer(
    question: str,
    context_chunks: list[str],
    ontology_context: str | None = None,
) -> str:
    """Generate an answer using Gemini given a question and retrieved context.

    Args:
        question: The user's medical question.
        context_chunks: List of retrieved document chunk texts.
        ontology_context: Optional ontology reasoning trace (Pipeline 3 only).

    Returns:
        Generated answer string.
    """
    client = _get_client()

    # Format context
    context = "\n\n---\n\n".join(
        f"[Document {i + 1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )

    if ontology_context:
        user_prompt = ONTOLOGY_ENHANCED_USER_PROMPT.format(
            context=context,
            ontology_context=ontology_context,
            question=question,
        )
    else:
        user_prompt = BASE_USER_PROMPT.format(
            context=context,
            question=question,
        )

    response = client.models.generate_content(
        model=GENERATOR_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=BASE_SYSTEM_PROMPT,
            temperature=GENERATOR_TEMPERATURE,
        ),
    )

    return response.text

