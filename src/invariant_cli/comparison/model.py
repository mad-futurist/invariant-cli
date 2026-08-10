from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ObservationDifference:
    source: str
    path: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class ComparisonResult:
    matches: bool
    differences: list[ObservationDifference]
