import json
import sys
from pathlib import Path

DEMO_ROOT = Path(__file__).parent


def main() -> None:
    balance_cents = int(sys.argv[1])
    balance_eur = balance_cents / 100
    (DEMO_ROOT / "source" / "state.json").write_text(
        json.dumps({"balance_cents": balance_cents}, indent=2),
        encoding="utf-8",
    )
    for target in ("target", "target_negative", "target_unresolved"):
        (DEMO_ROOT / target / "account.json").write_text(
            json.dumps(
                {
                    "remaining_eur": balance_eur,
                    "unrelated_total": balance_eur,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
