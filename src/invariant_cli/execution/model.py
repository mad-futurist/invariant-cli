from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Execution:
    id: str
    command: list[str]
    working_directory: Path

    started_at: datetime
    finished_at: datetime
    duration_seconds: float

    exit_code: int
    stdout: str
    stderr: str
