import json
import sys
from pathlib import Path

STATE = Path(__file__).parent / "account.json"


def main() -> None:
    principal_payment = float(sys.argv[1])
    reserve_payment = float(sys.argv[2])
    account = json.loads(STATE.read_text(encoding="utf-8"))
    account["principal_eur"] -= principal_payment
    account["reserve_eur"] -= reserve_payment
    STATE.write_text(json.dumps(account, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
