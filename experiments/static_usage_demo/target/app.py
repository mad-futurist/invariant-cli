import json
import sys
from pathlib import Path

ACCOUNT_PATH = Path(__file__).parent / "account.json"


def main() -> None:
    payment_eur = float(sys.argv[1])
    account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))

    account["spendable_eur"] = account["spendable_eur"] - payment_eur

    ACCOUNT_PATH.write_text(
        json.dumps(account, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
