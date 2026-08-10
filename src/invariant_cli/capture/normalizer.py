from collections.abc import Iterable
from typing import Protocol

from invariant_cli.capture.model import CaptureRecord, FileChangeRecord
from invariant_cli.observation.model import Observation
from invariant_cli.observation.registry import ResourceDecoderRegistry


class ObservationNormalizer(Protocol):
    def accepts(self, record: CaptureRecord) -> bool: ...

    def normalize(self, record: CaptureRecord) -> list[Observation]: ...


class FileChangeNormalizer:
    def __init__(self, decoders: ResourceDecoderRegistry) -> None:
        self._decoders = decoders

    def accepts(self, record: CaptureRecord) -> bool:
        return isinstance(record, FileChangeRecord) and self._decoders.accepts(record.path)

    def normalize(self, record: CaptureRecord) -> list[Observation]:
        if not isinstance(record, FileChangeRecord):
            return []
        return self._decoders.decode(
            record.path,
            record.before_content,
            record.after_content,
        )


class ObservationNormalizerRegistry:
    def __init__(self, normalizers: Iterable[ObservationNormalizer]) -> None:
        self._normalizers = tuple(normalizers)

    def normalize(self, records: Iterable[CaptureRecord]) -> list[Observation]:
        observations: list[Observation] = []

        for record in records:
            for normalizer in self._normalizers:
                if normalizer.accepts(record):
                    observations.extend(normalizer.normalize(record))

        return observations
