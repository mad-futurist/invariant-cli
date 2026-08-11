from dataclasses import dataclass, field
from enum import StrEnum


class EntityKind(StrEnum):
    JSON_FIELD = "json_field"
    SQLITE_FIELD = "sqlite_field"


@dataclass(frozen=True)
class EntityRef:
    kind: EntityKind
    namespace: str
    identifier: str

    @property
    def locator(self) -> str:
        return f"{self.namespace}#{self.identifier}"


class EvidenceKind(StrEnum):
    DYNAMIC_TRANSITION = "dynamic_transition"
    STATIC_USAGE = "static_usage"
    STATIC_DATA_FLOW = "static_data_flow"
    CALL_CONTEXT = "call_context"
    SCHEMA = "schema"


class EvidenceEffect(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class Evidence:
    kind: EvidenceKind
    producer: str
    attributes: dict[str, object] = field(default_factory=dict)
    effect: EvidenceEffect = EvidenceEffect.SUPPORTS
