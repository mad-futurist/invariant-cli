from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ComparisonVerdict(StrEnum):
    MATCH = "MATCH"
    DIFF = "DIFF"
    # No comparable observations on either side.
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class ObservationDifference:
    source: str
    path: str
    expected: Any
    actual: Any


@dataclass(frozen=True)
class ComparisonResult:
    verdict: ComparisonVerdict
    differences: list[ObservationDifference]

    @property
    def matches(self) -> bool:
        return self.verdict == ComparisonVerdict.MATCH
