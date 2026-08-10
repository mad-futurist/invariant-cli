from pathlib import Path

from invariant_cli.observation.model import Observation, ValueChange
from invariant_cli.observation.observer import Observer
from invariant_cli.observation.registry import ObserverRegistry


class TextObserver(Observer):
    def accepts(self, path: Path) -> bool:
        return path.suffix == ".txt"

    def observe(
        self,
        path: Path,
        before_content: bytes | None,
        after_content: bytes | None,
    ) -> Observation | None:
        return Observation(
            source=str(path),
            kind="text",
            changes=[
                ValueChange(
                    path="$",
                    before=before_content,
                    after=after_content,
                )
            ],
        )


def test_registry_dispatches_to_accepting_observer() -> None:
    registry = ObserverRegistry([TextObserver()])

    assert registry.accepts(Path("note.txt"))
    assert not registry.accepts(Path("state.json"))

    observations = registry.observe(Path("note.txt"), b"before", b"after")

    assert len(observations) == 1
    assert observations[0].kind == "text"


def test_registry_returns_no_observations_for_unsupported_path() -> None:
    registry = ObserverRegistry([TextObserver()])

    assert registry.observe(Path("state.json"), b"before", b"after") == []
