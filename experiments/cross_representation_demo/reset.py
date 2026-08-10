import json
import sqlite3
import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).parent
SOURCE_DATABASE = DEMO_ROOT / "source" / "legacy.db"
TARGET_STATE = DEMO_ROOT / "target" / "account.json"


def main() -> None:
    balance_cents = int(sys.argv[1])
    SOURCE_DATABASE.unlink(missing_ok=True)

    connection = sqlite3.connect(SOURCE_DATABASE)
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

    TARGET_STATE.write_text(
        json.dumps({"remaining_eur": balance_cents / 100}, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
