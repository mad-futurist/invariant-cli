from dataclasses import dataclass


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


@dataclass(frozen=True)
class CorrespondenceCandidate:
    source: ObservationSelector
    target: ObservationSelector
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
