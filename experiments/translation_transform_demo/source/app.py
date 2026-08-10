import json
import sys
from pathlib import Path

PATH = Path(__file__).parent / "state.json"


def main() -> None:
    payment_cents = int(sys.argv[1])

    state = json.loads(PATH.read_text(encoding="utf-8"))

    state["balance_cents"] -= payment_cents

    PATH.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
