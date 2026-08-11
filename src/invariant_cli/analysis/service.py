from pathlib import Path

from invariant_cli.analysis.analyzer import SemanticAnalyzer
from invariant_cli.analysis.model import ProgramSemanticModel
from invariant_cli.analysis.python.analyzer import PythonSemanticAnalyzer

DEFAULT_ANALYZER: SemanticAnalyzer = PythonSemanticAnalyzer()


def analyze_program(
    path: Path,
    *,
    analyzer: SemanticAnalyzer = DEFAULT_ANALYZER,
) -> ProgramSemanticModel:
    return analyzer.analyze(path)
