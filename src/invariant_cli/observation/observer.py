from abc import ABC, abstractmethod
from pathlib import Path

from invariant_cli.observation.model import Observation


class ResourceDecoder(ABC):
    @abstractmethod
    def accepts(self, path: Path) -> bool: ...

    @abstractmethod
    def decode(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> Observation | None: ...

    def observe(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> Observation | None:
        """Compatibility wrapper for the pre-lifecycle observer API."""
        return self.decode(path, before_content, after_content)


class Observer(ResourceDecoder):
    """Deprecated adapter for third-party observers implementing ``observe``."""

    @abstractmethod
    def observe(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> Observation | None: ...

    def decode(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> Observation | None:
        return self.observe(path, before_content, after_content)
