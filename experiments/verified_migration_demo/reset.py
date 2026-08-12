import json
import sys
from pathlib import Path

root = Path(__file__).parent
balance_cents = int(sys.argv[1])
(root / "source" / "state.json").write_text(
    json.dumps({"balance_cents": balance_cents}), encoding="utf-8"
)
(root / "target" / "account.json").write_text(
    json.dumps({"remaining_eur": balance_cents / 100}), encoding="utf-8"
)
