import sqlite3
import sys
from pathlib import Path

DATABASE = Path(__file__).parent / "modern.db"


def main() -> None:
    payment_eur = float(sys.argv[1])

    connection = sqlite3.connect(DATABASE)
    try:
        connection.execute(
            "UPDATE accounts SET available_eur = available_eur - ? WHERE id = 1",
            (payment_eur,),
        )
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
