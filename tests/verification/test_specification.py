from __future__ import annotations

import pytest

from invariant_cli.verification import (
    AllOfAssertion,
    EvidenceFact,
    ExitCodeAssertion,
    ExitCodeOperator,
    GateVerdict,
    SetAssertion,
    SpecificationGate,
    StateUnchangedAssertion,
    VerificationCandidate,
    VerificationContext,
    VerificationEngine,
    VerificationObligation,
    VerificationPlan,
    VerificationScenario,
    VerificationSource,
    VerificationSourceKind,
    VerificationSubject,
)
from invariant_cli.verification.model import AssertionKind


def test_set_coverage_produces_minimal_counterexample() -> None:
    context = _context(
        EvidenceFact("scenario.dirty", ("WP01", "WP03"), "scenario-v1"),
        EvidenceFact("execution.reported", ("WP01",), "pilot-output-v1"),
    )

    report = VerificationEngine([SpecificationGate()]).verify(context)

    assert report.verdict == GateVerdict.FAIL
    assert report.results[0].evidence == [
        {
            "kind": "set_contains",
            "expected": ["WP01", "WP03"],
            "observed": ["WP01"],
            "missing": ["WP03"],
            "unexpected": [],
            "producers": ["scenario-v1", "pilot-output-v1"],
            "assertion_id": "A-FR003-coverage",
        }
    ]


def test_set_coverage_passes_when_every_blocker_is_reported() -> None:
    context = _context(
        EvidenceFact("scenario.dirty", ("WP01", "WP03"), "scenario-v1"),
        EvidenceFact("execution.reported", ("WP03", "WP01"), "pilot-output-v1"),
    )

    report = VerificationEngine([SpecificationGate()]).verify(context)

    assert report.verdict == GateVerdict.PASS


def test_missing_fact_is_inconclusive() -> None:
    report = VerificationEngine([SpecificationGate()]).verify(
        _context(EvidenceFact("scenario.dirty", ("WP01", "WP03"), "scenario-v1"))
    )

    assert report.verdict == GateVerdict.INCONCLUSIVE
    assert report.results[0].evidence[0]["reason"] == "missing"


def test_all_of_assertion_aggregates_exit_and_state_without_eval() -> None:
    assertion = AllOfAssertion(
        id="A-FR004",
        assertions=(
            ExitCodeAssertion(
                id="A-FR004-exit",
                actual_fact="execution.exit_code",
                expected=0,
                operator=ExitCodeOperator.NOT_EQUAL,
            ),
            StateUnchangedAssertion(
                id="A-FR004-refs",
                before_fact="git.before.refs",
                after_fact="git.after.refs",
            ),
        ),
    )
    context = _context(
        EvidenceFact("execution.exit_code", 1, "execution-v1"),
        EvidenceFact("git.before.refs", "abc", "git-state-v1"),
        EvidenceFact("git.after.refs", "abc", "git-state-v1"),
        assertion=assertion,
    )

    report = VerificationEngine([SpecificationGate()]).verify(context)

    assert report.verdict == GateVerdict.PASS


def test_plan_rejects_dangling_requirement_source() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        _plan(source_id="FR-999")


def _context(
    *facts: EvidenceFact,
    assertion: SetAssertion | AllOfAssertion | None = None,
) -> VerificationContext:
    return VerificationContext(
        plan=_plan(assertion=assertion),
        candidate=VerificationCandidate(label="candidate", ref="abc123"),
        facts=facts,
    )


def _plan(
    *,
    assertion: SetAssertion | AllOfAssertion | None = None,
    source_id: str = "FR-003",
) -> VerificationPlan:
    return VerificationPlan(
        id="pilot:multiple-dirty",
        subject=VerificationSubject(repository="spec-kitty", candidate_ref="abc123"),
        sources=(
            VerificationSource(
                id="FR-003",
                kind=VerificationSourceKind.SPECIFICATION,
                artifact="kitty-specs/017-preflight/spec.md",
            ),
        ),
        obligations=(
            VerificationObligation(
                id="O-FR003-aggregate-blockers",
                source_id=source_id,
                scenario_id="multiple_dirty",
                assertion=assertion
                or SetAssertion(
                    id="A-FR003-coverage",
                    expected_fact="scenario.dirty",
                    observed_fact="execution.reported",
                    kind=AssertionKind.SET_CONTAINS,
                ),
            ),
        ),
        scenarios=(VerificationScenario(id="multiple_dirty"),),
        evidence_requirements=("scenario.dirty", "execution.reported"),
    )
