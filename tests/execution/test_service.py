import sys
from pathlib import Path

from invariant_cli.execution.service import capture_process


def test_capture_process(tmp_path: Path) -> None:
    execution = capture_process(
        [
            sys.executable,
            "-c",
            "print('hello invariant')",
        ],
        working_directory=tmp_path,
    )

    assert execution.exit_code == 0
    assert execution.stdout.strip() == "hello invariant"
    assert execution.stderr == ""
    assert execution.duration_seconds >= 0
