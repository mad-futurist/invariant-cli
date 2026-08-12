import json
from pathlib import Path

STATE_FILE = Path(__file__).parents[1] / "target" / "account.json"
account = json.loads(STATE_FILE.read_text(encoding="utf-8"))


class AccountRepository:
    def store(self, value: float) -> None:
        account["remaining_eur"] = value
        STATE_FILE.write_text(json.dumps(account), encoding="utf-8")
