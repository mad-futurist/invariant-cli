import json
import sys
from pathlib import Path

from calculation import compute

STATE_FILE = Path(__file__).parents[1] / "target" / "account.json"
account = json.loads(STATE_FILE.read_text(encoding="utf-8"))


def process(value: float) -> None:
    current = account["remaining_eur"]
    updated = compute(current, value)
    account["remaining_eur"] = updated
    STATE_FILE.write_text(json.dumps(account), encoding="utf-8")


if __name__ == "__main__":
    process(float(sys.argv[1]))
