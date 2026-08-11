import json
from pathlib import Path

ACCOUNT_PATH = Path(__file__).parent / "account.json"


class AccountRepository:
    def store(self, amount: float) -> None:
        account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
        account["remaining_eur"] = amount
        ACCOUNT_PATH.write_text(json.dumps(account, indent=2), encoding="utf-8")
