from dataclasses import dataclass

from invariant_cli.contracts.function_inference import infer_function_correspondences
from invariant_cli.contracts.model import (
    FunctionCorrespondenceCandidate,
    FunctionCorrespondenceStatus,
)
from invariant_cli.contracts.validation import ContractValidationResult, ValidationVerdict
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
            context.contract.candidate_sets,
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
        runtime_verdict = _mapped_validation_verdict(context.validation, candidate)
        if runtime_verdict == ValidationVerdict.FAIL:
            return self._result(GateVerdict.FAIL, "Held-out state relation failed.", candidate)
        if runtime_verdict == ValidationVerdict.INCONCLUSIVE:
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


def _mapped_validation_verdict(
    validation: ContractValidationResult,
    candidate: FunctionCorrespondenceCandidate,
) -> ValidationVerdict:
    relevant = set(candidate.mapped_state_reads) | set(candidate.mapped_state_writes)
    if not relevant or not validation.pairs:
        return ValidationVerdict.INCONCLUSIVE

    verdicts: list[ValidationVerdict] = []
    for pair in validation.pairs:
        by_mapping = {(item.source, item.target): item.verdict for item in pair.correspondences}
        for mapping in relevant:
            verdicts.append(by_mapping.get(mapping, ValidationVerdict.INCONCLUSIVE))
    if any(verdict == ValidationVerdict.FAIL for verdict in verdicts):
        return ValidationVerdict.FAIL
    if not verdicts or any(verdict == ValidationVerdict.INCONCLUSIVE for verdict in verdicts):
        return ValidationVerdict.INCONCLUSIVE
    return ValidationVerdict.PASS


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
