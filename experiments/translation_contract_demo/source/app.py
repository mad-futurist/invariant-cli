import json
import sys
from pathlib import Path

STATE_PATH = Path(__file__).parent / "state.json"


def main() -> None:
    payment = int(sys.argv[1])

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    state["balance"] -= payment

    if state["balance"] == 0:
        state["status"] = "paid"

    STATE_PATH.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
