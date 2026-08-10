from dataclasses import dataclass
from typing import Any


class _AbsentType:
    """Sentinel: key did not exist in the JSON object (distinct from JSON null)."""

    _instance: "_AbsentType | None" = None

    def __new__(cls) -> "_AbsentType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "ABSENT"


ABSENT = _AbsentType()

# Sentinel used in JSON storage to round-trip ABSENT through disk.
_ABSENT_JSON_MARKER = {"__invariant__": "absent"}


def serialize_value(value: Any) -> Any:
    if isinstance(value, _AbsentType):
        return _ABSENT_JSON_MARKER
    return value


def deserialize_value(value: Any) -> Any:
    if value == _ABSENT_JSON_MARKER:
        return ABSENT
    return value


@dataclass(frozen=True)
class ValueChange:
    path: str
    before: Any
    after: Any


@dataclass(frozen=True)
class Observation:
    source: str
    kind: str
    changes: list[ValueChange]
