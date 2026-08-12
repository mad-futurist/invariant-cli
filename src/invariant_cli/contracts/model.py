from dataclasses import dataclass, field
from enum import StrEnum

from invariant_cli.matching.model import EntityRef, Evidence


class RelationKind(StrEnum):
    EXACT = "exact"
    AFFINE = "affine"


class ExpressionKind(StrEnum):
    IDENTITY = "identity"
    SUM = "sum"


class CandidateShape(StrEnum):
    FIELD = "field"
    EXPRESSION = "expression"


class CandidateSetStatus(StrEnum):
    WELL_SUPPORTED_CANDIDATE = "well_supported_candidate"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    REJECTED = "rejected"


class FunctionCorrespondenceStatus(StrEnum):
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class VerificationObligationKind(StrEnum):
    BEHAVIOR_PRESERVATION = "behavior_preservation"
    ARCHITECTURE = "architecture"


@dataclass(frozen=True)
class Relation:
    kind: RelationKind
    # target = source * scale + offset
    scale: str = "1"
    offset: str = "0"


@dataclass(frozen=True)
class CorrespondenceCandidate:
    source: EntityRef
    target: EntityRef
    relation: Relation
    evidence: list[Evidence]


@dataclass(frozen=True)
class EntityExpression:
    kind: ExpressionKind
    components: tuple[EntityRef, ...]

    def __post_init__(self) -> None:
        if not self.components:
            raise ValueError("An entity expression requires at least one component.")
        if self.kind == ExpressionKind.IDENTITY and len(self.components) != 1:
            raise ValueError("An identity expression requires exactly one component.")
        if self.kind == ExpressionKind.SUM and len(self.components) < 2:
            raise ValueError("A sum expression requires at least two components.")
        if len(set(self.components)) != len(self.components):
            raise ValueError("Expression components must be distinct.")


@dataclass(frozen=True)
class ExpressionCorrespondenceCandidate:
    source: EntityExpression
    target: EntityExpression
    relation: Relation
    evidence: list[Evidence]


CandidateHypothesis = CorrespondenceCandidate | ExpressionCorrespondenceCandidate


@dataclass(frozen=True)
class RankedCandidate:
    shape: CandidateShape
    rank: int
    score: int
    factors: dict[str, int]
    candidate: CandidateHypothesis


@dataclass(frozen=True)
class CandidateSet:
    source: EntityRef
    status: CandidateSetStatus
    candidates: list[RankedCandidate] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionPairRef:
    source_execution: str
    target_execution: str


@dataclass(frozen=True)
class FunctionCorrespondenceCandidate:
    source: EntityRef
    target: EntityRef
    evidence: list[Evidence]
    mapped_state_reads: tuple[tuple[EntityRef, EntityRef], ...] = ()
    mapped_state_writes: tuple[tuple[EntityRef, EntityRef], ...] = ()
    status: FunctionCorrespondenceStatus = FunctionCorrespondenceStatus.CANDIDATE


@dataclass(frozen=True)
class VerificationObligation:
    id: str
    kind: VerificationObligationKind
    source: EntityRef | None = None
    target: EntityRef | None = None
    rule: str | None = None


@dataclass(frozen=True)
class CandidateTranslationContract:
    version: int
    paired_executions: list[ExecutionPairRef]
    correspondences: list[CorrespondenceCandidate]
    expression_correspondences: list[ExpressionCorrespondenceCandidate] = field(
        default_factory=list
    )
    candidate_sets: list[CandidateSet] = field(default_factory=list)
    function_correspondences: list[FunctionCorrespondenceCandidate] = field(default_factory=list)
    obligations: list[VerificationObligation] = field(default_factory=list)
