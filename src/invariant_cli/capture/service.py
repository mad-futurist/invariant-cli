from dataclasses import replace
from pathlib import Path
from typing import Protocol

from invariant_cli.capture.model import CaptureBundle, CaptureContext, CaptureRecord
from invariant_cli.capture.normalizer import ObservationNormalizerRegistry
from invariant_cli.capture.probe import CaptureProbe
from invariant_cli.execution.model import Execution
from invariant_cli.observation.filesystem import FileSystemDiff


class ExecutionRunner(Protocol):
    def run(self, command: list[str], *, working_directory: Path) -> Execution: ...


class CaptureService:
    def __init__(
        self,
        *,
        runner: ExecutionRunner,
        probes: list[CaptureProbe],
        normalizers: ObservationNormalizerRegistry,
    ) -> None:
        self._runner = runner
        self._probes = probes
        self._normalizers = normalizers

    def capture(self, command: list[str], *, context: CaptureContext) -> CaptureBundle:
        sessions = [probe.start(context) for probe in self._probes]
        execution = self._runner.run(command, working_directory=context.working_directory)
        probe_results = [session.stop(execution) for session in sessions]

        records: list[CaptureRecord] = [
            record for result in probe_results for record in result.records
        ]
        filesystem_diff = _merge_filesystem_diffs(
            [
                result.filesystem_diff
                for result in probe_results
                if result.filesystem_diff is not None
            ]
        )
        execution = replace(execution, filesystem_diff=filesystem_diff)

        return CaptureBundle(
            execution=execution,
            records=records,
            observations=self._normalizers.normalize(records),
        )


def _merge_filesystem_diffs(diffs: list[FileSystemDiff]) -> FileSystemDiff:
    return FileSystemDiff(
        created=sorted({path for diff in diffs for path in diff.created}),
        deleted=sorted({path for diff in diffs for path in diff.deleted}),
        modified=sorted({path for diff in diffs for path in diff.modified}),
    )
