import subprocess
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from invariant_cli.execution.model import Execution
from invariant_cli.observation import observe_json
from invariant_cli.observation.filesystem import FileSystemDiff, diff_snapshots, snapshot_directory
from invariant_cli.observation.model import Observation


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


def capture_execution(
    command: list[str],
    *,
    working_directory: Path,
) -> tuple[Execution, list[Observation]]:
    before_snapshot = snapshot_directory(working_directory)
    before_contents = {
        path: (working_directory / path).read_text(encoding="utf-8")
        for path in before_snapshot
        if (working_directory / path).is_file()
    }

    execution = capture_process(
        command,
        working_directory=working_directory,
    )

    after_snapshot = snapshot_directory(working_directory)
    filesystem_diff = diff_snapshots(before_snapshot, after_snapshot)

    changed_paths = sorted(
        set(filesystem_diff.created) | set(filesystem_diff.deleted) | set(filesystem_diff.modified)
    )
    observations: list[Observation] = []

    for changed_path in changed_paths:
        if changed_path.suffix.lower() != ".json":
            continue

        absolute_path = working_directory / changed_path

        before_content = before_contents.get(changed_path, "{}")
        if absolute_path.exists():
            after_content = absolute_path.read_text(encoding="utf-8")
        else:
            after_content = "{}"

        if before_content != after_content:
            observations.append(
                observe_json(
                    str(changed_path),
                    before_content,
                    after_content,
                )
            )

    return replace(execution, filesystem_diff=filesystem_diff), observations
