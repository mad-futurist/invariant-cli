import json
import sys
from pathlib import Path

from repository import persist_balance

STATE_PATH = Path(__file__).parent / "state.json"


def pay(amount: int) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    current = state["balance_cents"]
    updated = current - amount
    persist_balance(updated)


if __name__ == "__main__":
    pay(int(sys.argv[1]))
