from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EpistemicStatus(StrEnum):
    EXPLICIT = "explicit"
    DERIVED = "derived"
    OBSERVED = "observed"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class RequirementSource:
    adapter: str
    artifact: str
    heading: str
    mission: str
    work_package: str | None = None


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    sources: tuple[RequirementSource, ...]
    epistemic_status: EpistemicStatus = EpistemicStatus.EXPLICIT

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("A requirement ID cannot be empty.")
        if not self.text:
            raise ValueError(f"Requirement {self.id} has no text.")
        if not self.sources:
            raise ValueError(f"Requirement {self.id} has no provenance.")


@dataclass(frozen=True)
class Specification:
    id: str
    adapter: str
    mission: str
    work_package: str
    requirements: tuple[Requirement, ...]

    def __post_init__(self) -> None:
        requirement_ids = [requirement.id for requirement in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("Specification requirement IDs must be unique.")

    def requirement(self, requirement_id: str) -> Requirement:
        for requirement in self.requirements:
            if requirement.id == requirement_id:
                return requirement
        raise KeyError(requirement_id)


@dataclass(frozen=True)
class SpecificationObligation:
    """A structural binding; executable assertion semantics are added by later milestones."""

    id: str
    requirement_id: str
    scenario_id: str

    def __post_init__(self) -> None:
        if not self.id or not self.requirement_id or not self.scenario_id:
            raise ValueError("Specification obligation identifiers cannot be empty.")
