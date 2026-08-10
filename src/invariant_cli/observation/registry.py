from collections.abc import Iterable
from pathlib import Path

from invariant_cli.observation.model import Observation
from invariant_cli.observation.observer import ResourceDecoder


class ResourceDecoderRegistry:
    def __init__(self, decoders: Iterable[ResourceDecoder]) -> None:
        self._decoders = tuple(decoders)

    def accepts(self, path: Path) -> bool:
        return any(decoder.accepts(path) for decoder in self._decoders)

    def decode(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> list[Observation]:
        observations: list[Observation] = []

        for decoder in self._decoders:
            if not decoder.accepts(path):
                continue

            observation = decoder.decode(path, before_content, after_content)
            if observation is not None:
                observations.append(observation)

        return observations

    def observe(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> list[Observation]:
        """Compatibility wrapper for callers using the old registry name."""
        return self.decode(path, before_content, after_content)


ObserverRegistry = ResourceDecoderRegistry
