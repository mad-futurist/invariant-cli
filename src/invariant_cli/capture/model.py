from dataclasses import dataclass
from pathlib import Path

from invariant_cli.execution.model import Execution
from invariant_cli.observation.filesystem import FileSystemDiff
from invariant_cli.observation.model import Observation


@dataclass(frozen=True)
class CaptureContext:
    working_directory: Path
    include_patterns: list[str] | None = None


@dataclass(frozen=True)
class FileChangeRecord:
    path: Path
    before_content: bytes | None
    after_content: bytes | None


CaptureRecord = FileChangeRecord


@dataclass(frozen=True)
class ProbeResult:
    records: list[CaptureRecord]
    filesystem_diff: FileSystemDiff | None = None


@dataclass(frozen=True)
class CaptureBundle:
    execution: Execution
    records: list[CaptureRecord]
    observations: list[Observation]
