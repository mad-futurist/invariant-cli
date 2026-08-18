from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from invariant_cli.verification.model import (
    AllOfAssertion,
    AssertionKind,
    EntityAssertion,
    EvidenceFact,
    ExecutableAssertion,
    ExitCodeAssertion,
    ExitCodeOperator,
    GateResult,
    GateVerdict,
    SetAssertion,
    StateUnchangedAssertion,
    VerificationContext,
    VerificationObligation,
    VerificationSourceKind,
)


@dataclass(frozen=True)
class _AssertionResult:
    verdict: GateVerdict
    evidence: list[dict[str, object]]
    message: str


@dataclass(frozen=True)
class SpecificationGate:
    id: str = "specification"

    def supports(
        self,
        obligation: VerificationObligation,
        context: VerificationContext,
    ) -> bool:
        source = next(
            (source for source in context.plan.sources if source.id == obligation.source_id),
            None,
        )
        return source is not None and source.kind == VerificationSourceKind.SPECIFICATION

    def evaluate(
        self,
        obligation: VerificationObligation,
        context: VerificationContext,
    ) -> GateResult:
        result = _evaluate_assertion(obligation.assertion, context)
        return GateResult(
            gate_id=self.id,
            verdict=result.verdict,
            obligation_id=obligation.id,
            evidence=result.evidence,
            message=result.message,
            category="specification",
        )


def _evaluate_assertion(
    assertion: ExecutableAssertion,
    context: VerificationContext,
) -> _AssertionResult:
    if isinstance(assertion, ExitCodeAssertion):
        return _exit_code(assertion, context)
    if isinstance(assertion, SetAssertion):
        return _set_relation(assertion, context)
    if isinstance(assertion, StateUnchangedAssertion):
        return _state_unchanged(assertion, context)
    if isinstance(assertion, EntityAssertion):
        return _entity(assertion, context)
    return _all_of(assertion, context)


def _exit_code(assertion: ExitCodeAssertion, context: VerificationContext) -> _AssertionResult:
    fact = context.fact(assertion.actual_fact)
    if fact is None or not isinstance(fact.value, int) or isinstance(fact.value, bool):
        return _missing_or_invalid(assertion.id, assertion.actual_fact, fact, "integer")
    matches = fact.value == assertion.expected
    if assertion.operator == ExitCodeOperator.NOT_EQUAL:
        matches = not matches
    return _comparison_result(
        assertion.id,
        matches,
        {
            "kind": assertion.kind.value,
            "operator": assertion.operator.value,
            "expected": assertion.expected,
            "observed": fact.value,
            "producer": fact.producer,
        },
    )


def _set_relation(assertion: SetAssertion, context: VerificationContext) -> _AssertionResult:
    expected_fact = context.fact(assertion.expected_fact)
    observed_fact = context.fact(assertion.observed_fact)
    invalid = _require_string_tuple(assertion.id, assertion.expected_fact, expected_fact)
    if invalid is not None:
        return invalid
    invalid = _require_string_tuple(assertion.id, assertion.observed_fact, observed_fact)
    if invalid is not None:
        return invalid
    assert expected_fact is not None and observed_fact is not None
    expected_value = cast(tuple[str, ...], expected_fact.value)
    observed_value = cast(tuple[str, ...], observed_fact.value)
    expected = set(expected_value)
    observed = set(observed_value)
    matches = expected == observed
    if assertion.kind == AssertionKind.SET_CONTAINS:
        matches = expected <= observed
    return _comparison_result(
        assertion.id,
        matches,
        {
            "kind": assertion.kind.value,
            "expected": sorted(expected),
            "observed": sorted(observed),
            "missing": sorted(expected - observed),
            "unexpected": sorted(observed - expected),
            "producers": [expected_fact.producer, observed_fact.producer],
        },
    )


def _state_unchanged(
    assertion: StateUnchangedAssertion,
    context: VerificationContext,
) -> _AssertionResult:
    before = context.fact(assertion.before_fact)
    after = context.fact(assertion.after_fact)
    if before is None:
        return _missing_or_invalid(assertion.id, assertion.before_fact, None, "fact")
    if after is None:
        return _missing_or_invalid(assertion.id, assertion.after_fact, None, "fact")
    return _comparison_result(
        assertion.id,
        before.value == after.value,
        {
            "kind": assertion.kind.value,
            "before": before.value,
            "after": after.value,
            "producers": [before.producer, after.producer],
        },
    )


def _entity(assertion: EntityAssertion, context: VerificationContext) -> _AssertionResult:
    collection = context.fact(assertion.collection_fact)
    invalid = _require_string_tuple(assertion.id, assertion.collection_fact, collection)
    if invalid is not None:
        return invalid
    assert collection is not None
    collection_value = cast(tuple[str, ...], collection.value)
    exists = assertion.entity in collection_value
    matches = exists == assertion.should_exist
    return _comparison_result(
        assertion.id,
        matches,
        {
            "kind": assertion.kind.value,
            "entity": assertion.entity,
            "collection": list(collection_value),
            "producer": collection.producer,
        },
    )


def _all_of(assertion: AllOfAssertion, context: VerificationContext) -> _AssertionResult:
    children = [_evaluate_assertion(child, context) for child in assertion.assertions]
    verdict = GateVerdict.PASS
    if any(child.verdict == GateVerdict.FAIL for child in children):
        verdict = GateVerdict.FAIL
    elif any(child.verdict == GateVerdict.INCONCLUSIVE for child in children):
        verdict = GateVerdict.INCONCLUSIVE
    return _AssertionResult(
        verdict=verdict,
        evidence=[
            {
                "kind": assertion.kind.value,
                "assertion_id": assertion.id,
                "children": [
                    {
                        "verdict": child.verdict.value,
                        "message": child.message,
                        "evidence": child.evidence,
                    }
                    for child in children
                ],
            }
        ],
        message=f"Assertion {assertion.id}: {verdict.value}.",
    )


def _require_string_tuple(
    assertion_id: str,
    fact_id: str,
    fact: EvidenceFact | None,
) -> _AssertionResult | None:
    if (
        fact is None
        or not isinstance(fact.value, tuple)
        or not all(isinstance(item, str) for item in fact.value)
    ):
        return _missing_or_invalid(assertion_id, fact_id, fact, "tuple of strings")
    return None


def _missing_or_invalid(
    assertion_id: str,
    fact_id: str,
    fact: EvidenceFact | None,
    expected_type: str,
) -> _AssertionResult:
    reason = "missing" if fact is None else "invalid_type"
    return _AssertionResult(
        verdict=GateVerdict.INCONCLUSIVE,
        evidence=[
            {
                "assertion_id": assertion_id,
                "fact": fact_id,
                "reason": reason,
                "expected_type": expected_type,
            }
        ],
        message=f"Required fact {fact_id} is {reason.replace('_', ' ')}.",
    )


def _comparison_result(
    assertion_id: str,
    matches: bool,
    evidence: dict[str, object],
) -> _AssertionResult:
    verdict = GateVerdict.PASS if matches else GateVerdict.FAIL
    evidence["assertion_id"] = assertion_id
    return _AssertionResult(
        verdict=verdict,
        evidence=[evidence],
        message=f"Assertion {assertion_id}: {verdict.value}.",
    )


__all__ = ["SpecificationGate"]
