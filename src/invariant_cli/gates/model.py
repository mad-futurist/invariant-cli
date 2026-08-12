from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from invariant_cli.analysis.model import ProgramSemanticModel
from invariant_cli.architecture.model import ArchitectureModel
from invariant_cli.contracts.model import CandidateTranslationContract
from invariant_cli.contracts.validation import ContractValidationResult


class GateVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    verdict: GateVerdict
    obligation_id: str
    evidence: list[dict[str, object]] = field(default_factory=list)
    message: str = ""
    category: str = "behavior"


@dataclass(frozen=True)
class VerificationContext:
    contract: CandidateTranslationContract
    source_program: ProgramSemanticModel
    target_program: ProgramSemanticModel
    architecture: ArchitectureModel | None = None
    validation: ContractValidationResult | None = None


class Gate(Protocol):
    @property
    def id(self) -> str: ...

    def evaluate(self, context: VerificationContext) -> GateResult: ...
