from collections.abc import Callable
from pathlib import Path

from invariant_cli.capture.model import CaptureContext, FileChangeRecord, ProbeResult
from invariant_cli.capture.probe import ProbeSession
from invariant_cli.execution.model import Execution
from invariant_cli.observation.filesystem import FileState, diff_snapshots, snapshot_directory


class FileSystemProbe:
    def __init__(self, *, capture_content: Callable[[Path], bool]) -> None:
        self._capture_content = capture_content

    def start(self, context: CaptureContext) -> ProbeSession:
        before_snapshot = snapshot_directory(
            context.working_directory,
            include_patterns=context.include_patterns,
        )
        before_contents = {
            path: (context.working_directory / path).read_bytes()
            for path in before_snapshot
            if self._capture_content(path)
        }

        return _FileSystemProbeSession(
            context=context,
            capture_content=self._capture_content,
            before_snapshot=before_snapshot,
            before_contents=before_contents,
        )


class _FileSystemProbeSession:
    def __init__(
        self,
        *,
        context: CaptureContext,
        capture_content: Callable[[Path], bool],
        before_snapshot: dict[Path, FileState],
        before_contents: dict[Path, bytes],
    ) -> None:
        self._context = context
        self._capture_content = capture_content
        self._before_snapshot = before_snapshot
        self._before_contents = before_contents

    def stop(self, execution: Execution) -> ProbeResult:
        del execution

        after_snapshot = snapshot_directory(
            self._context.working_directory,
            include_patterns=self._context.include_patterns,
        )
        filesystem_diff = diff_snapshots(self._before_snapshot, after_snapshot)
        changed_paths = sorted(
            set(filesystem_diff.created)
            | set(filesystem_diff.deleted)
            | set(filesystem_diff.modified)
        )

        records: list[FileChangeRecord] = []
        for path in changed_paths:
            if not self._capture_content(path):
                continue

            absolute_path = self._context.working_directory / path
            records.append(
                FileChangeRecord(
                    path=path,
                    before_content=self._before_contents.get(path),
                    after_content=absolute_path.read_bytes() if absolute_path.exists() else None,
                )
            )

        return ProbeResult(
            records=records,
            filesystem_diff=filesystem_diff,
        )
