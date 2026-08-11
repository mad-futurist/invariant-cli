import json
import logging
import sys
from pathlib import Path

from storage import AccountRepository

ACCOUNT_PATH = Path(__file__).parent / "account.json"
logger = logging.getLogger(__name__)
repository = AccountRepository()


def process_payment(value: float) -> None:
    account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    remaining = account["remaining_eur"]
    logger.info(remaining)
    result = account["unrelated_total"] - value
    repository.store(result)


if __name__ == "__main__":
    process_payment(float(sys.argv[1]))
