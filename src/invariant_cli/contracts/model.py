from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class ObservationSelector:
    resource: str
    path: str


@dataclass(frozen=True)
class DynamicEvidence:
    matched_pairs: int
    total_pairs: int
    distinct_transitions: int

    @property
    def score(self) -> float:
        if self.total_pairs == 0:
            return 0.0

        return self.matched_pairs / self.total_pairs


class RelationKind(StrEnum):
    EXACT = "exact"
    AFFINE = "affine"


@dataclass(frozen=True)
class Relation:
    kind: RelationKind
    # target = source * scale + offset
    scale: str = "1"
    offset: str = "0"


@dataclass(frozen=True)
class CorrespondenceCandidate:
    source: ObservationSelector
    target: ObservationSelector
    relation: Relation
    evidence: DynamicEvidence


@dataclass(frozen=True)
class ExecutionPairRef:
    source_execution: str
    target_execution: str


@dataclass(frozen=True)
class CandidateTranslationContract:
    version: int
    paired_executions: list[ExecutionPairRef]
    correspondences: list[CorrespondenceCandidate]
