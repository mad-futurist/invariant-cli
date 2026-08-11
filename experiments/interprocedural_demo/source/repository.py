import json
from pathlib import Path

STATE_PATH = Path(__file__).parent / "state.json"


def persist_balance(value: int) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state["balance_cents"] = value
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
