"""End-to-end OntoGate-RAG pipelines and ablations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from evidence_gate.config import (
    ABSTAIN_LABEL,
    MAX_RERETRIEVAL_ROUNDS,
    RERETRIEVAL_TOP_K,
    TOP_K,
)
from evidence_gate.evidence_scorer import SufficiencyResult
from evidence_gate.gate_policy import GateDecision, GatePolicy
from evidence_gate.retriever import DenseRetriever, Passage


@dataclass
class RunResult:
    system: str
    pubid: str
    question: str
    gold: str
    answer: str
    decision: str
    sufficiency: float
    passages: list[dict] = field(default_factory=list)
    refinement: dict | None = None
    rounds: int = 0
    latency_s: float = 0.0
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "system": self.system,
            "pubid": self.pubid,
            "question": self.question,
            "gold": self.gold,
            "answer": self.answer,
            "decision": self.decision,
            "sufficiency": self.sufficiency,
            "passages": self.passages,
            "refinement": self.refinement,
            "rounds": self.rounds,
            "latency_s": self.latency_s,
            "trace": self.trace,
        }


def _passages_payload(passages: list[Passage]) -> list[dict]:
    return [
        {"id": p.id, "score": round(p.score, 4), "text": p.text} for p in passages
    ]


class OntoGatePipeline:
    def __init__(
        self,
        retriever: DenseRetriever,
        scorer,
        gate: GatePolicy,
        reasoner,
        generator,
        judge=None,
        top_k: int = TOP_K,
        max_rounds: int = MAX_RERETRIEVAL_ROUNDS,
        exclude_own: bool = True,
    ):
        self.retriever = retriever
        self.scorer = scorer
        self.gate = gate
        self.reasoner = reasoner
        self.generator = generator
        self.judge = judge
        self.top_k = top_k
        self.max_rounds = max_rounds
        self.exclude_own = exclude_own

    # ------------------------------------------------------------------
    def _retrieve(self, query: str, pubid: str, k: int | None = None) -> list[Passage]:
        exclude = {pubid} if self.exclude_own else set()
        return self.retriever.search(query, top_k=k or self.top_k, exclude_ids=exclude)

    def _score(self, question: str, passages: list[Passage]):
        if self.judge is not None:
            return self.judge.judge(question, [p.text for p in passages])
        return self.scorer.score(question, [p.text for p in passages])

    def _generate(self, question: str, passages: list[Passage]) -> dict:
        return self.generator.answer(question, [p.text for p in passages])

    def _answer_from_judgement(self, question: str, passages: list[Passage], judgement) -> str:
        answer = getattr(judgement, "answer", None)
        if answer in {"yes", "no", "maybe"}:
            return answer
        return self._generate(question, passages)["answer"]

    # ------------------------------------------------------------------
    def run_ontogate(self, pubid: str, question: str, gold: str) -> RunResult:
        started = time.perf_counter()
        passages = self._retrieve(question, pubid)
        ess1 = self._score(question, passages)
        gate1 = self.gate.decide(ess1.sufficiency_score, round_number=0, max_rounds=self.max_rounds)

        result = RunResult(
            system="ontogate",
            pubid=pubid,
            question=question,
            gold=gold,
            answer=ABSTAIN_LABEL,
            decision=gate1.decision.value,
            sufficiency=ess1.sufficiency_score,
            passages=_passages_payload(passages),
            rounds=0,
            trace={
                "ess_round0": ess1.to_dict(),
                "gate_round0": gate1.to_dict(),
            },
        )

        if gate1.decision is GateDecision.GENERATE:
            result.answer = self._answer_from_judgement(question, passages, ess1)
        elif gate1.decision is GateDecision.RE_RETRIEVE:
            refinement = self.reasoner.refine(
                question, [p.text for p in passages[:3]]
            )
            result.refinement = refinement.to_dict()
            if refinement.grounded:
                new_passages = self._retrieve(
                    refinement.query, pubid, k=RERETRIEVAL_TOP_K
                )
                merged = self._merge(passages, new_passages)
                ess2 = self._score(question, merged)
                gate2 = self.gate.decide(
                    ess2.sufficiency_score,
                    round_number=1,
                    max_rounds=self.max_rounds,
                )
                result.passages = _passages_payload(merged)
                result.sufficiency = ess2.sufficiency_score
                result.decision = (
                    "GENERATE"
                    if ess2.sufficiency_score >= self.gate.tau_high
                    else "ABSTAIN"
                )
                result.rounds = 1
                result.trace["ess_round1"] = ess2.to_dict()
                result.trace["gate_round1"] = gate2.to_dict()
                if ess2.sufficiency_score >= self.gate.tau_high:
                    result.answer = self._answer_from_judgement(question, merged, ess2)
            else:
                # Partially sufficient evidence but no ontology grounding:
                # abstain rather than answer from unsupported context.
                result.trace["refinement_skipped"] = "ungrounded"
                result.decision = "ABSTAIN"
        # ABSTAIN leaves the answer as "maybe" with no API call.

        result.latency_s = round(time.perf_counter() - started, 3)
        return result

    def run_gate_only(self, pubid: str, question: str, gold: str) -> RunResult:
        """Three-way gate, but the middle band generates without re-retrieval."""
        started = time.perf_counter()
        passages = self._retrieve(question, pubid)
        ess = self._score(question, passages)
        gate = self.gate.decide(ess.sufficiency_score, round_number=0, max_rounds=0)
        answer = ABSTAIN_LABEL
        if ess.sufficiency_score >= self.gate.tau_high:
            answer = self._answer_from_judgement(question, passages, ess)
        result = RunResult(
            system="gate_only",
            pubid=pubid,
            question=question,
            gold=gold,
            answer=answer,
            decision="GENERATE" if answer != ABSTAIN_LABEL else "ABSTAIN",
            sufficiency=ess.sufficiency_score,
            passages=_passages_payload(passages),
            latency_s=round(time.perf_counter() - started, 3),
            trace={"ess_round0": ess.to_dict(), "gate_round0": gate.to_dict()},
        )
        return result

    def run_ontogate_llm_refine(self, pubid: str, question: str, gold: str) -> RunResult:
        """Ablation: same gate, but missing evidence is sought with an LLM rewrite."""
        started = time.perf_counter()
        passages = self._retrieve(question, pubid)
        ess1 = self._score(question, passages)
        gate1 = self.gate.decide(
            ess1.sufficiency_score, round_number=0, max_rounds=self.max_rounds
        )
        result = RunResult(
            system="ontogate_llm_refine",
            pubid=pubid,
            question=question,
            gold=gold,
            answer=ABSTAIN_LABEL,
            decision=gate1.decision.value,
            sufficiency=ess1.sufficiency_score,
            passages=_passages_payload(passages),
            trace={"ess_round0": ess1.to_dict(), "gate_round0": gate1.to_dict()},
        )
        if gate1.decision is GateDecision.GENERATE:
            result.answer = self._answer_from_judgement(question, passages, ess1)
            result.latency_s = round(time.perf_counter() - started, 3)
            return result
        if gate1.decision is GateDecision.ABSTAIN:
            result.latency_s = round(time.perf_counter() - started, 3)
            return result

        refined_query = self.generator.refine(question, [p.text for p in passages])
        new_passages = self._retrieve(refined_query, pubid, k=RERETRIEVAL_TOP_K)
        merged = self._merge(passages, new_passages)
        ess2 = self._score(question, merged)
        gate2 = self.gate.decide(
            ess2.sufficiency_score, round_number=1, max_rounds=self.max_rounds
        )
        result.answer = ABSTAIN_LABEL
        if ess2.sufficiency_score >= self.gate.tau_high:
            result.answer = self._answer_from_judgement(question, merged, ess2)
        result.sufficiency = ess2.sufficiency_score
        result.decision = (
            "GENERATE" if ess2.sufficiency_score >= self.gate.tau_high else "ABSTAIN"
        )
        result.rounds = 1
        result.passages = _passages_payload(merged)
        result.trace["llm_refined_query"] = refined_query
        result.trace["ess_round1"] = ess2.to_dict()
        result.trace["gate_round1"] = gate2.to_dict()
        result.latency_s = round(time.perf_counter() - started, 3)
        return result

    def run_standard_rag(self, pubid: str, question: str, gold: str) -> RunResult:
        started = time.perf_counter()
        passages = self._retrieve(question, pubid)
        answer = self._generate(question, passages)["answer"]
        return RunResult(
            system="standard_rag",
            pubid=pubid,
            question=question,
            gold=gold,
            answer=answer,
            decision="GENERATE",
            sufficiency=float("nan"),
            passages=_passages_payload(passages),
            latency_s=round(time.perf_counter() - started, 3),
        )

    def run_score_only(self, pubid: str, question: str, gold: str) -> RunResult:
        """Log the ESS signal but always generate (no gating)."""
        started = time.perf_counter()
        passages = self._retrieve(question, pubid)
        ess = self._score(question, passages)
        answer = self._answer_from_judgement(question, passages, ess)
        return RunResult(
            system="score_only",
            pubid=pubid,
            question=question,
            gold=gold,
            answer=answer,
            decision="GENERATE",
            sufficiency=ess.sufficiency_score,
            passages=_passages_payload(passages),
            latency_s=round(time.perf_counter() - started, 3),
            trace={"ess_round0": ess.to_dict()},
        )

    def run_crag_style(self, pubid: str, question: str, gold: str) -> RunResult:
        """Binary relevance gate with a fixed threshold (CRAG-style, no web fallback)."""
        started = time.perf_counter()
        passages = self._retrieve(question, pubid)
        ess = self._score(question, passages)
        answer = ABSTAIN_LABEL
        decision = "ABSTAIN"
        if ess.sufficiency_score >= 0.50:
            answer = self._answer_from_judgement(question, passages, ess)
            decision = "GENERATE"
        return RunResult(
            system="crag",
            pubid=pubid,
            question=question,
            gold=gold,
            answer=answer,
            decision=decision,
            sufficiency=ess.sufficiency_score,
            passages=_passages_payload(passages),
            latency_s=round(time.perf_counter() - started, 3),
            trace={"ess_round0": ess.to_dict()},
        )

    def run_llm_only(self, pubid: str, question: str, gold: str) -> RunResult:
        started = time.perf_counter()
        answer = self.generator.answer(question, [])["answer"]
        return RunResult(
            system="llm_only",
            pubid=pubid,
            question=question,
            gold=gold,
            answer=answer,
            decision="GENERATE",
            sufficiency=float("nan"),
            latency_s=round(time.perf_counter() - started, 3),
        )

    @staticmethod
    def _merge(a: list[Passage], b: list[Passage]) -> list[Passage]:
        merged: list[Passage] = []
        seen: set[str] = set()
        for passage in [*a, *b]:
            if passage.id in seen:
                continue
            seen.add(passage.id)
            merged.append(passage)
        merged.sort(key=lambda p: p.score, reverse=True)
        return merged[: TOP_K]
