import json
import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).parent
SOURCE_STATE = DEMO_ROOT / "source" / "wallet.json"
TARGET_STATE = DEMO_ROOT / "target" / "account.json"


def main() -> None:
    balance_cents = int(sys.argv[1])

    SOURCE_STATE.write_text(
        json.dumps({"available_cents": balance_cents}, indent=2),
        encoding="utf-8",
    )
    TARGET_STATE.write_text(
        json.dumps({"spendable_eur": balance_cents / 100}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
