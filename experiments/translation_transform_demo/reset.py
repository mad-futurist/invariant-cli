import json
import sys
from pathlib import Path

_DEMO = Path(__file__).parent

SOURCE_PATH = _DEMO / "source" / "state.json"
TARGET_PATH = _DEMO / "target" / "account.json"


def main() -> None:
    balance_cents = int(sys.argv[1])

    SOURCE_PATH.write_text(
        json.dumps({"balance_cents": balance_cents}, indent=2),
        encoding="utf-8",
    )

    TARGET_PATH.write_text(
        json.dumps({"remaining": balance_cents / 100}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
