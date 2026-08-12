from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath


class EntityKind(StrEnum):
    JSON_FIELD = "json_field"
    SQLITE_FIELD = "sqlite_field"
    FUNCTION = "function"


@dataclass(frozen=True, order=True)
class LogicalStateIdentity:
    owner: str
    path: str

    @property
    def locator(self) -> str:
        return f"{self.owner}.{self.path}"

    @classmethod
    def from_semantic_label(cls, label: str) -> "LogicalStateIdentity":
        owner, separator, path = label.partition(".")
        if not separator or not owner or not path:
            raise ValueError(f"State label must include logical owner and path: {label!r}.")
        return cls(owner=owner, path=path)


@dataclass(frozen=True)
class EntityRef:
    kind: EntityKind
    namespace: str
    identifier: str

    @property
    def locator(self) -> str:
        return f"{self.namespace}#{self.identifier}"

    @property
    def logical_state(self) -> LogicalStateIdentity:
        resource = PurePosixPath(self.namespace.replace("\\", "/")).name
        owner = resource.rsplit(".", 1)[0]
        return LogicalStateIdentity(owner=owner, path=self.identifier)


class EvidenceKind(StrEnum):
    DYNAMIC_TRANSITION = "dynamic_transition"
    STATIC_USAGE = "static_usage"
    STATIC_DATA_FLOW = "static_data_flow"
    CALL_CONTEXT = "call_context"
    SCHEMA = "schema"
    FUNCTION_BEHAVIOR = "function_behavior"


class EvidenceEffect(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class EvidenceFamily(StrEnum):
    RUNTIME = "runtime"
    OBSERVED_SCHEMA = "observed_schema"
    STATIC_PROGRAM = "static_program"
    DECLARED_SCHEMA = "declared_schema"


@dataclass(frozen=True)
class Evidence:
    kind: EvidenceKind
    producer: str
    family: EvidenceFamily
    attributes: dict[str, object] = field(default_factory=dict)
    effect: EvidenceEffect = EvidenceEffect.SUPPORTS
