"""Three-way evidence gate.

    s >= tau_high            -> GENERATE
    tau_low <= s < tau_high  -> RE_RETRIEVE (once)
    s < tau_low              -> ABSTAIN (predict "maybe")
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from evidence_gate.config import TAU_HIGH, TAU_LOW


class GateDecision(str, Enum):
    GENERATE = "GENERATE"
    RE_RETRIEVE = "RE_RETRIEVE"
    ABSTAIN = "ABSTAIN"


@dataclass
class GateResult:
    decision: GateDecision
    sufficiency_score: float
    tau_high: float
    tau_low: float
    round_number: int = 0

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "sufficiency_score": self.sufficiency_score,
            "tau_high": self.tau_high,
            "tau_low": self.tau_low,
            "round_number": self.round_number,
        }


class GatePolicy:
    def __init__(self, tau_high: float = TAU_HIGH, tau_low: float = TAU_LOW):
        if not (0.0 <= tau_low <= tau_high <= 1.0):
            raise ValueError(
                f"Require 0 <= tau_low <= tau_high <= 1, got {tau_low}, {tau_high}"
            )
        self.tau_high = tau_high
        self.tau_low = tau_low

    def decide(
        self, score: float, round_number: int = 0, max_rounds: int = 1
    ) -> GateResult:
        if score >= self.tau_high or round_number >= max_rounds:
            decision = (
                GateDecision.GENERATE
                if score >= self.tau_low
                else GateDecision.ABSTAIN
            )
        elif score >= self.tau_low:
            decision = GateDecision.RE_RETRIEVE
        else:
            decision = GateDecision.ABSTAIN
        return GateResult(
            decision=decision,
            sufficiency_score=score,
            tau_high=self.tau_high,
            tau_low=self.tau_low,
            round_number=round_number,
        )
