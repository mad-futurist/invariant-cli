import json
import sys
from pathlib import Path

STATE_PATH = Path(__file__).parent / "account.json"


def main() -> None:
    payment = int(sys.argv[1])

    account = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    account["remaining"] -= payment

    if account["remaining"] == 0:
        account["state"] = "paid"

    STATE_PATH.write_text(
        json.dumps(account, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
