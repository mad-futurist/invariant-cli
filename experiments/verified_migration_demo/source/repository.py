import json
from pathlib import Path

STATE_FILE = Path(__file__).parents[1] / "source" / "state.json"
state = json.loads(STATE_FILE.read_text(encoding="utf-8"))


def persist_balance(value: int) -> None:
    state["balance_cents"] = value
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
