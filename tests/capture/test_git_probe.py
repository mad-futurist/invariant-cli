from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from invariant_cli.capture.git_probe import GitStateProbe
from invariant_cli.capture.model import CaptureContext, GitStateRecord
from invariant_cli.capture.normalizer import ObservationNormalizerRegistry
from invariant_cli.capture.service import CaptureService
from invariant_cli.execution.runner import SubprocessExecutionRunner


def test_git_state_probe_captures_repository_state_around_execution(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    _run(["git", "init", "-b", "main"], repository)
    _run(["git", "config", "user.email", "probe@example.invalid"], repository)
    _run(["git", "config", "user.name", "Git Probe"], repository)
    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _run(["git", "add", "tracked.txt"], repository)
    _run(["git", "commit", "-m", "fixture"], repository)
    _run(["git", "branch", "pilot-WP01"], repository)
    wp01 = tmp_path / "wp01"
    _run(["git", "worktree", "add", str(wp01), "pilot-WP01"], repository)
    (wp01 / "before.txt").write_text("before\n", encoding="utf-8")
    missing = tmp_path / "wp02"
    service = CaptureService(
        runner=SubprocessExecutionRunner(),
        probes=[
            GitStateProbe(
                repository_root=repository,
                expected_worktrees={"WP01": wp01, "WP02": missing},
            )
        ],
        normalizers=ObservationNormalizerRegistry([]),
    )

    bundle = service.capture(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('after.txt').write_text('after\\n')",
        ],
        context=CaptureContext(working_directory=wp01),
    )

    assert bundle.execution.exit_code == 0
    assert bundle.observations == []
    assert len(bundle.records) == 1
    record = bundle.records[0]
    assert isinstance(record, GitStateRecord)
    assert record.before.current_branch == "pilot-WP01"
    assert record.before.local_branches == record.after.local_branches
    assert record.before.expected_worktree_status == {
        "WP01": ("?? before.txt",),
        "WP02": None,
    }
    assert record.after.expected_worktree_status == {
        "WP01": ("?? after.txt", "?? before.txt"),
        "WP02": None,
    }
    assert record.before.merge_in_progress is False
    assert record.after.merge_in_progress is False
    assert {worktree.branch for worktree in record.before.worktrees} == {
        "main",
        "pilot-WP01",
    }


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
