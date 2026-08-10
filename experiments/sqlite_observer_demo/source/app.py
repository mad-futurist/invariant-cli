import sqlite3
import sys
from pathlib import Path

DATABASE = Path(__file__).parent / "legacy.db"


def main() -> None:
    payment_cents = int(sys.argv[1])

    connection = sqlite3.connect(DATABASE)
    try:
        connection.execute(
            "UPDATE wallets SET balance_cents = balance_cents - ? WHERE id = 1",
            (payment_cents,),
        )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
