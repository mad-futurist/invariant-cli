from dataclasses import dataclass, field
from enum import StrEnum


class ObligationKind(StrEnum):
    FORBID_STATE_WRITE = "forbid_state_write"
    STATE_WRITE_OWNER = "state_write_owner"
    REQUIRE_DEPENDENCY = "require_dependency"


@dataclass(frozen=True)
class ComponentRef:
    id: str


@dataclass(frozen=True)
class Component:
    id: str
    modules: tuple[str, ...]


@dataclass(frozen=True)
class ArchitectureObligation:
    id: str
    kind: ObligationKind
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ArchitectureModel:
    version: int
    components: tuple[Component, ...]
    obligations: tuple[ArchitectureObligation, ...]
