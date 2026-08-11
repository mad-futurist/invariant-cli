import json
import sys
from pathlib import Path

STATE_PATH = Path(__file__).parent / "state.json"


def persist_balance(value: int) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state["balance_cents"] = value
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def pay(amount: int) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    balance = state["balance_cents"]
    remaining = balance - amount
    persist_balance(remaining)


if __name__ == "__main__":
    pay(int(sys.argv[1]))
