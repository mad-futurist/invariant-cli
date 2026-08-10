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
        b'{"value": null}',
    )

    assert observation is not None
    assert len(observation.changes) == 1

    change = observation.changes[0]

    assert change.path == "$"
    assert change.before is ABSENT
    assert change.after == {"value": None}


def test_json_observer_records_empty_document_creation() -> None:
    observation = JsonObserver().observe(Path("state.json"), None, b"{}")

    assert observation is not None
    assert len(observation.changes) == 1
    assert observation.changes[0].path == "$"
    assert observation.changes[0].before is ABSENT
    assert observation.changes[0].after == {}


def test_json_observer_reports_field_changes_in_existing_document() -> None:
    observation = JsonObserver().observe(
        Path("state.json"),
        b'{"balance": 100}',
        b'{"balance": 70}',
    )

    assert observation is not None
    assert observation.changes[0].path == "balance"
    assert observation.changes[0].before == 100
    assert observation.changes[0].after == 70
