import json
import sys
from pathlib import Path

STATE = Path(__file__).parent / "account.json"


def main() -> None:
    payment_eur = float(sys.argv[1])
    account = json.loads(STATE.read_text(encoding="utf-8"))
    account["remaining_eur"] -= payment_eur
    STATE.write_text(json.dumps(account, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
