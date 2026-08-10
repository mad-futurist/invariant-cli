from pathlib import Path

from invariant_cli.observation.json_observer import JsonObserver
from invariant_cli.observation.model import ABSENT


def test_json_observer_accepts_json() -> None:
    observer = JsonObserver()

    assert observer.accepts(Path("state.json"))
    assert not observer.accepts(Path("state.txt"))


def test_json_observer_distinguishes_null_from_absent() -> None:
    observer = JsonObserver()

    observation = observer.observe(
        Path("state.json"),
        None,
        '{"value": null}',
    )

    assert observation is not None
    assert len(observation.changes) == 1

    change = observation.changes[0]

    assert change.path == "value"
    assert change.before is ABSENT
    assert change.after is None
