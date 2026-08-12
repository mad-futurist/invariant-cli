from dataclasses import dataclass

from invariant_cli.contracts.function_inference import infer_function_correspondences
from invariant_cli.contracts.model import FunctionCorrespondenceStatus
from invariant_cli.contracts.validation import ValidationVerdict
from invariant_cli.gates.model import GateResult, GateVerdict, VerificationContext
from invariant_cli.matching.model import EvidenceEffect


@dataclass(frozen=True)
class BehaviorPreservationGate:
    obligation_id: str
    source_locator: str
    target_locator: str
    id: str = "behavior-preservation"

    def evaluate(self, context: VerificationContext) -> GateResult:
        current_candidates = infer_function_correspondences(
            context.source_program,
            context.target_program,
            context.contract.correspondences,
        )
        candidate = next(
            (
                item
                for item in current_candidates
                if item.source.locator == self.source_locator
                and item.target.locator == self.target_locator
            ),
            None,
        )
        if candidate is None:
            return self._result(GateVerdict.INCONCLUSIVE, "Function correspondence is missing.")

        effects = {item.effect for item in candidate.evidence}
        if (
            candidate.status == FunctionCorrespondenceStatus.REJECTED
            or EvidenceEffect.CONTRADICTS in effects
        ):
            return self._result(
                GateVerdict.FAIL,
                "Resolved function behavior is incompatible.",
                candidate,
            )
        if (
            candidate.status == FunctionCorrespondenceStatus.INCONCLUSIVE
            or EvidenceEffect.NEUTRAL in effects
        ):
            return self._result(
                GateVerdict.INCONCLUSIVE,
                "Function behavior could not be fully resolved.",
                candidate,
            )
        if context.validation is None:
            return self._result(
                GateVerdict.INCONCLUSIVE,
                "Held-out state validation was not supplied.",
                candidate,
            )
        if context.validation.verdict == ValidationVerdict.FAIL:
            return self._result(GateVerdict.FAIL, "Held-out state relation failed.", candidate)
        if context.validation.verdict == ValidationVerdict.INCONCLUSIVE:
            return self._result(
                GateVerdict.INCONCLUSIVE,
                "Held-out state relation is inconclusive.",
                candidate,
            )
        return self._result(
            GateVerdict.PASS,
            "Mapped reads, writes, operations, effects, and held-out state relation agree.",
            candidate,
        )

    def _result(
        self,
        verdict: GateVerdict,
        message: str,
        candidate: object | None = None,
    ) -> GateResult:
        evidence: list[dict[str, object]] = []
        if candidate is not None:
            evidence.append({"source": self.source_locator, "target": self.target_locator})
        return GateResult(
            gate_id=self.id,
            verdict=verdict,
            obligation_id=self.obligation_id,
            evidence=evidence,
            message=message,
            category="behavior",
        )


@dataclass(frozen=True)
class StateCorrespondenceGate:
    id: str = "state-correspondence"

    def evaluate(self, context: VerificationContext) -> GateResult:
        if context.validation is None:
            verdict = GateVerdict.INCONCLUSIVE
            message = "Held-out validation was not supplied."
        else:
            verdict = GateVerdict(context.validation.verdict.value)
            message = f"Held-out state validation: {context.validation.verdict.value}."
        return GateResult(
            gate_id=self.id,
            verdict=verdict,
            obligation_id="state-correspondence",
            message=message,
            category="state",
        )
