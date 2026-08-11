from pathlib import Path
from typing import Protocol

from invariant_cli.analysis.model import ProgramSemanticModel


class SemanticAnalyzer(Protocol):
    name: str

    def analyze(self, path: Path) -> ProgramSemanticModel: ...
