import json
import sys
from pathlib import Path

from storage import AccountRepository

ACCOUNT_PATH = Path(__file__).parent / "account.json"
repository = AccountRepository()


def process_payment(value: float) -> None:
    account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    remaining = account["remaining_eur"]
    _ = remaining
    result = account["unrelated_total"] - value
    repository.store(result)


if __name__ == "__main__":
    process_payment(float(sys.argv[1]))
