from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from invariant_cli.verification.model import (
    GateResult,
    GateVerdict,
    VerificationContext,
    VerificationObligation,
    VerificationReport,
)


class VerificationGate(Protocol):
    def supports(
        self,
        obligation: VerificationObligation,
        context: VerificationContext,
    ) -> bool: ...

    def evaluate(
        self,
        obligation: VerificationObligation,
        context: VerificationContext,
    ) -> GateResult: ...


class VerificationEngine:
    def __init__(self, gates: Sequence[VerificationGate]) -> None:
        self._gates = tuple(gates)

    def verify(self, context: VerificationContext) -> VerificationReport:
        results = tuple(
            self._evaluate_obligation(obligation, context)
            for obligation in context.plan.obligations
        )
        return VerificationReport(
            plan_id=context.plan.id,
            candidate=context.candidate,
            results=results,
            verdict=aggregate_verdict(results),
        )

    def _evaluate_obligation(
        self,
        obligation: VerificationObligation,
        context: VerificationContext,
    ) -> GateResult:
        gates = [gate for gate in self._gates if gate.supports(obligation, context)]
        if len(gates) != 1:
            return GateResult(
                gate_id="verification-engine",
                verdict=GateVerdict.INCONCLUSIVE,
                obligation_id=obligation.id,
                evidence=[{"supporting_gate_count": len(gates)}],
                message=(
                    "No gate supports this obligation."
                    if not gates
                    else "More than one gate supports this obligation."
                ),
                category="verification",
            )
        return gates[0].evaluate(obligation, context)


def aggregate_verdict(results: Sequence[GateResult]) -> GateVerdict:
    if any(result.verdict == GateVerdict.FAIL for result in results):
        return GateVerdict.FAIL
    if not results or any(result.verdict == GateVerdict.INCONCLUSIVE for result in results):
        return GateVerdict.INCONCLUSIVE
    return GateVerdict.PASS


__all__ = ["VerificationEngine", "VerificationGate", "aggregate_verdict"]
