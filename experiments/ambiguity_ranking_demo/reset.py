import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def main() -> None:
    balance = int(sys.argv[1])
    (ROOT / "source" / "state.json").write_text(
        json.dumps({"balance": balance}, indent=2),
        encoding="utf-8",
    )
    (ROOT / "target" / "account.json").write_text(
        json.dumps({"remaining": balance, "total": balance}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
