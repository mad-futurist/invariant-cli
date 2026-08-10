import sqlite3
from pathlib import Path

from invariant_cli.observation.sqlite_observer import SQLiteObserver


def _database(path: Path, balance: int) -> bytes:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, balance INTEGER)")
        connection.execute("INSERT INTO accounts (id, balance) VALUES (1, ?)", (balance,))
        connection.commit()
    finally:
        connection.close()
    return path.read_bytes()


def test_sqlite_observer_accepts_database_extensions() -> None:
    observer = SQLiteObserver()

    assert observer.accepts(Path("state.db"))
    assert observer.accepts(Path("state.sqlite"))
    assert observer.accepts(Path("state.sqlite3"))
    assert not observer.accepts(Path("state.json"))


def test_sqlite_observer_reports_cell_change(tmp_path: Path) -> None:
    before = _database(tmp_path / "before.db", 100)
    after = _database(tmp_path / "after.db", 70)

    observation = SQLiteObserver().observe(Path("state.db"), before, after)

    assert observation is not None
    assert observation.kind == "sqlite"

    changes = {change.path: change for change in observation.changes}
    balance = changes["accounts[id=1].balance"]
    assert balance.before == 100
    assert balance.after == 70
