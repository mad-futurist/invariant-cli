import json
import sys
from pathlib import Path

PATH = Path(__file__).parent / "account.json"


def main() -> None:
    payment_eur = float(sys.argv[1])

    account = json.loads(PATH.read_text(encoding="utf-8"))

    account["remaining"] -= payment_eur

    PATH.write_text(
        json.dumps(account, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
