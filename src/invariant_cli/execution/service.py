from pathlib import Path

from invariant_cli.capture.filesystem_probe import FileSystemProbe
from invariant_cli.capture.model import CaptureContext
from invariant_cli.capture.normalizer import (
    FileChangeNormalizer,
    ObservationNormalizerRegistry,
)
from invariant_cli.capture.service import CaptureService
from invariant_cli.execution.model import Execution
from invariant_cli.execution.runner import SubprocessExecutionRunner
from invariant_cli.observation.json_observer import JsonObserver
from invariant_cli.observation.model import Observation
from invariant_cli.observation.registry import ResourceDecoderRegistry
from invariant_cli.observation.sqlite_observer import SQLiteObserver

DEFAULT_DECODERS = ResourceDecoderRegistry([JsonObserver(), SQLiteObserver()])
DEFAULT_OBSERVERS = DEFAULT_DECODERS
DEFAULT_RUNNER = SubprocessExecutionRunner()


def capture_process(
    command: list[str],
    *,
    working_directory: Path,
) -> Execution:
    return DEFAULT_RUNNER.run(command, working_directory=working_directory)


def capture_execution(
    command: list[str],
    *,
    working_directory: Path,
    include_patterns: list[str] | None = None,
    observers: ResourceDecoderRegistry = DEFAULT_DECODERS,
) -> tuple[Execution, list[Observation]]:
    service = CaptureService(
        runner=DEFAULT_RUNNER,
        probes=[FileSystemProbe(capture_content=observers.accepts)],
        normalizers=ObservationNormalizerRegistry([FileChangeNormalizer(observers)]),
    )
    bundle = service.capture(
        command,
        context=CaptureContext(
            working_directory=working_directory,
            include_patterns=include_patterns,
        ),
    )
    return bundle.execution, bundle.observations
