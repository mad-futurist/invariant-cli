import sqlite3
import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).parent
SOURCE_DATABASE = DEMO_ROOT / "source" / "legacy.db"
TARGET_DATABASE = DEMO_ROOT / "target" / "modern.db"


def main() -> None:
    balance_cents = int(sys.argv[1])
    _reset_source(balance_cents)
    _reset_target(balance_cents / 100)


def _reset_source(balance_cents: int) -> None:
    connection = _fresh_database(SOURCE_DATABASE)
    try:
        connection.execute(
            "CREATE TABLE wallets (id INTEGER PRIMARY KEY, balance_cents INTEGER NOT NULL)"
        )
        connection.execute(
            "INSERT INTO wallets (id, balance_cents) VALUES (1, ?)",
            (balance_cents,),
        )
        connection.commit()
    finally:
        connection.close()


def _reset_target(balance_eur: float) -> None:
    connection = _fresh_database(TARGET_DATABASE)
    try:
        connection.execute(
            "CREATE TABLE accounts (id INTEGER PRIMARY KEY, available_eur REAL NOT NULL)"
        )
        connection.execute(
            "INSERT INTO accounts (id, available_eur) VALUES (1, ?)",
            (balance_eur,),
        )
        connection.commit()
    finally:
        connection.close()


def _fresh_database(path: Path) -> sqlite3.Connection:
    path.unlink(missing_ok=True)
    return sqlite3.connect(path)


if __name__ == "__main__":
    main()
