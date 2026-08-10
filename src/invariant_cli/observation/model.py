from dataclasses import dataclass
from typing import Any


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
