from abc import ABC, abstractmethod
from pathlib import Path

from invariant_cli.observation.model import Observation


class Observer(ABC):
    @abstractmethod
    def accepts(self, path: Path) -> bool: ...

    @abstractmethod
    def observe(
        self,
        path: Path,
        before_content: str | None,
        after_content: str | None,
    ) -> Observation | None: ...
