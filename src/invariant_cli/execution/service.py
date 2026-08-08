import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from invariant_cli.execution.model import Execution
from invariant_cli.observation.filesystem import FileSystemDiff


def capture_process(
    command: list[str],
    *,
    working_directory: Path,
) -> Execution:
    execution_id = str(uuid4())

    started_at = datetime.now(UTC)
    started_timer = time.perf_counter()

    completed = subprocess.run(
        command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    duration_seconds = time.perf_counter() - started_timer
    finished_at = datetime.now(UTC)

    return Execution(
        id=execution_id,
        command=command,
        working_directory=working_directory,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        filesystem_diff=FileSystemDiff(
            created=[],
            deleted=[],
            modified=[],
        ),
    )
