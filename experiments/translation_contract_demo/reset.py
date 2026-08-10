import json
import sys
from pathlib import Path

_DEMO = Path(__file__).parent

SOURCE_PATH = _DEMO / "source" / "state.json"
TARGET_PATH = _DEMO / "target" / "account.json"


def main() -> None:
    balance = int(sys.argv[1])

    source = {
        "balance": balance,
        "status": "open",
    }

    target = {
        "remaining": balance,
        "state": "open",
    }

    SOURCE_PATH.write_text(
        json.dumps(source, indent=2),
        encoding="utf-8",
    )

    TARGET_PATH.write_text(
        json.dumps(target, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
