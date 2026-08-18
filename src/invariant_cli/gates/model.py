from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from invariant_cli.analysis.model import ProgramSemanticModel
from invariant_cli.architecture.model import ArchitectureModel
from invariant_cli.contracts.model import CandidateTranslationContract
from invariant_cli.contracts.validation import ContractValidationResult
from invariant_cli.verification.model import GateResult, GateVerdict


@dataclass(frozen=True)
class TranslationVerificationContext:
    contract: CandidateTranslationContract
    source_program: ProgramSemanticModel
    target_program: ProgramSemanticModel
    architecture: ArchitectureModel | None = None
    validation: ContractValidationResult | None = None


class Gate(Protocol):
    @property
    def id(self) -> str: ...

    def evaluate(self, context: TranslationVerificationContext) -> GateResult: ...


# Compatibility alias for the existing translation CLI and integrations. New verification
# pathways should import VerificationContext from invariant_cli.verification.
VerificationContext = TranslationVerificationContext


__all__ = [
    "Gate",
    "GateResult",
    "GateVerdict",
    "TranslationVerificationContext",
    "VerificationContext",
]
