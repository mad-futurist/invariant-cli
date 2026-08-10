import sys
from pathlib import Path

from invariant_cli.capture.filesystem_probe import FileSystemProbe
from invariant_cli.capture.model import CaptureContext, FileChangeRecord
from invariant_cli.capture.normalizer import (
    FileChangeNormalizer,
    ObservationNormalizerRegistry,
)
from invariant_cli.capture.service import CaptureService
from invariant_cli.execution.runner import SubprocessExecutionRunner
from invariant_cli.observation.json_observer import JsonObserver
from invariant_cli.observation.registry import ResourceDecoderRegistry


def test_capture_lifecycle_preserves_raw_record_and_normalized_observation(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state.json"
    state.write_text('{"value": 1}', encoding="utf-8")
    decoders = ResourceDecoderRegistry([JsonObserver()])
    service = CaptureService(
        runner=SubprocessExecutionRunner(),
        probes=[FileSystemProbe(capture_content=decoders.accepts)],
        normalizers=ObservationNormalizerRegistry([FileChangeNormalizer(decoders)]),
    )

    bundle = service.capture(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('state.json').write_text('{\"value\": 2}')",
        ],
        context=CaptureContext(working_directory=tmp_path, include_patterns=["*.json"]),
    )

    assert bundle.execution.exit_code == 0
    assert bundle.execution.filesystem_diff.modified == [Path("state.json")]
    assert bundle.records == [
        FileChangeRecord(
            path=Path("state.json"),
            before_content=b'{"value": 1}',
            after_content=b'{"value": 2}',
        )
    ]
    assert bundle.observations[0].source == "state.json"
    assert bundle.observations[0].changes[0].path == "value"
    assert bundle.observations[0].changes[0].before == 1
    assert bundle.observations[0].changes[0].after == 2
