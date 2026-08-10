from collections.abc import Iterable
from pathlib import Path

from invariant_cli.observation.model import Observation
from invariant_cli.observation.observer import Observer


class ObserverRegistry:
    def __init__(self, observers: Iterable[Observer]) -> None:
        self._observers = tuple(observers)

    def accepts(self, path: Path) -> bool:
        return any(observer.accepts(path) for observer in self._observers)

    def observe(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> list[Observation]:
        observations: list[Observation] = []

        for observer in self._observers:
            if not observer.accepts(path):
                continue

            observation = observer.observe(path, before_content, after_content)
            if observation is not None:
                observations.append(observation)

        return observations
