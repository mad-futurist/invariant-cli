import json
import sys
from pathlib import Path

WALLET_PATH = Path(__file__).parent / "wallet.json"


def main() -> None:
    payment_cents = int(sys.argv[1])
    wallet = json.loads(WALLET_PATH.read_text(encoding="utf-8"))

    wallet["available_cents"] -= payment_cents

    WALLET_PATH.write_text(
        json.dumps(wallet, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
