from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum


class GateVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    verdict: GateVerdict
    obligation_id: str
    evidence: list[dict[str, object]] = field(default_factory=list)
    message: str = ""
    category: str = "behavior"


class AssertionKind(StrEnum):
    EXIT_CODE = "exit_code"
    SET_EQUAL = "set_equal"
    SET_CONTAINS = "set_contains"
    STATE_UNCHANGED = "state_unchanged"
    ENTITY_EXISTS = "entity_exists"
    ENTITY_ABSENT = "entity_absent"
    ALL_OF = "all_of"


class ExitCodeOperator(StrEnum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"


@dataclass(frozen=True)
class ExitCodeAssertion:
    id: str
    actual_fact: str
    expected: int
    operator: ExitCodeOperator = ExitCodeOperator.EQUAL
    kind: AssertionKind = field(init=False, default=AssertionKind.EXIT_CODE)


@dataclass(frozen=True)
class SetAssertion:
    id: str
    expected_fact: str
    observed_fact: str
    kind: AssertionKind = AssertionKind.SET_EQUAL

    def __post_init__(self) -> None:
        if self.kind not in {AssertionKind.SET_EQUAL, AssertionKind.SET_CONTAINS}:
            raise ValueError(f"Unsupported set assertion kind: {self.kind}")


@dataclass(frozen=True)
class StateUnchangedAssertion:
    id: str
    before_fact: str
    after_fact: str
    kind: AssertionKind = field(init=False, default=AssertionKind.STATE_UNCHANGED)


@dataclass(frozen=True)
class EntityAssertion:
    id: str
    entity: str
    collection_fact: str
    should_exist: bool = True

    @property
    def kind(self) -> AssertionKind:
        return AssertionKind.ENTITY_EXISTS if self.should_exist else AssertionKind.ENTITY_ABSENT


@dataclass(frozen=True)
class AllOfAssertion:
    id: str
    assertions: tuple[ExecutableAssertion, ...]
    kind: AssertionKind = field(init=False, default=AssertionKind.ALL_OF)

    def __post_init__(self) -> None:
        if not self.assertions:
            raise ValueError("An all-of assertion requires at least one child assertion.")


type ExecutableAssertion = (
    ExitCodeAssertion | SetAssertion | StateUnchangedAssertion | EntityAssertion | AllOfAssertion
)


class VerificationSourceKind(StrEnum):
    SPECIFICATION = "specification"
    ARCHITECTURE = "architecture"
    EXISTING_BEHAVIOR = "existing_behavior"
    TEST = "test"


@dataclass(frozen=True)
class VerificationSubject:
    repository: str
    candidate_ref: str
    change_ref: str | None = None


@dataclass(frozen=True)
class VerificationCandidate:
    label: str
    ref: str


@dataclass(frozen=True)
class VerificationSource:
    id: str
    kind: VerificationSourceKind
    artifact: str


@dataclass(frozen=True)
class VerificationScenario:
    id: str
    description: str = ""


@dataclass(frozen=True)
class VerificationObligation:
    id: str
    source_id: str
    scenario_id: str
    assertion: ExecutableAssertion


@dataclass(frozen=True)
class VerificationPlan:
    id: str
    subject: VerificationSubject
    sources: tuple[VerificationSource, ...]
    obligations: tuple[VerificationObligation, ...]
    scenarios: tuple[VerificationScenario, ...]
    evidence_requirements: tuple[str, ...] = ()
    assumptions: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_unique("source", (source.id for source in self.sources))
        _require_unique("obligation", (item.id for item in self.obligations))
        _require_unique("scenario", (scenario.id for scenario in self.scenarios))
        source_ids = {source.id for source in self.sources}
        scenario_ids = {scenario.id for scenario in self.scenarios}
        for obligation in self.obligations:
            if obligation.source_id not in source_ids:
                raise ValueError(
                    f"Obligation {obligation.id} references unknown source {obligation.source_id}."
                )
            if obligation.scenario_id not in scenario_ids:
                raise ValueError(
                    f"Obligation {obligation.id} references unknown scenario "
                    f"{obligation.scenario_id}."
                )


type FactValue = None | bool | int | float | str | tuple[FactValue, ...] | dict[str, FactValue]


@dataclass(frozen=True)
class EvidenceFact:
    id: str
    value: FactValue
    producer: str


@dataclass(frozen=True)
class VerificationContext:
    plan: VerificationPlan
    candidate: VerificationCandidate
    facts: tuple[EvidenceFact, ...]

    def __post_init__(self) -> None:
        _require_unique("fact", (fact.id for fact in self.facts))
        if self.candidate.ref != self.plan.subject.candidate_ref:
            raise ValueError(
                "Verification candidate does not match the candidate ref bound to the plan."
            )

    def fact(self, fact_id: str) -> EvidenceFact | None:
        return next((fact for fact in self.facts if fact.id == fact_id), None)


@dataclass(frozen=True)
class VerificationReport:
    plan_id: str
    candidate: VerificationCandidate
    results: tuple[GateResult, ...]
    verdict: GateVerdict


def _require_unique(kind: str, identifiers: Iterable[str]) -> None:
    values = list(identifiers)
    if len(values) != len(set(values)):
        raise ValueError(f"Verification {kind} IDs must be unique.")
