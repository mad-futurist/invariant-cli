from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    invariant_dir: Path
    config: Path
    cases: Path
    executions: Path
    observations: Path
    contracts: Path
    gates: Path
    results: Path
