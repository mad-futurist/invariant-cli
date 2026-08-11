import json
import sys
from pathlib import Path

ACCOUNT_PATH = Path(__file__).parent / "account.json"


def store(value: float) -> None:
    account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    account["remaining_eur"] = value
    ACCOUNT_PATH.write_text(json.dumps(account, indent=2), encoding="utf-8")


def process_payment(value: float) -> None:
    account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    current = account["remaining_eur"]
    updated = current - value
    store(updated)


if __name__ == "__main__":
    process_payment(float(sys.argv[1]))
