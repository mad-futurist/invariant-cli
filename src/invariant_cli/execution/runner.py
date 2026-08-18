import os
import subprocess
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from invariant_cli.execution.model import Execution
from invariant_cli.observation.filesystem import FileSystemDiff


class SubprocessExecutionRunner:
    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self._environment = dict(environment or {})

    def run(self, command: list[str], *, working_directory: Path) -> Execution:
        execution_id = str(uuid4())
        started_at = datetime.now(UTC)
        started_timer = time.perf_counter()

        completed = subprocess.run(
            command,
            cwd=working_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env={**os.environ, **self._environment} if self._environment else None,
        )

        return Execution(
            id=execution_id,
            command=command,
            working_directory=working_directory,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            duration_seconds=time.perf_counter() - started_timer,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            filesystem_diff=FileSystemDiff(created=[], deleted=[], modified=[]),
        )
