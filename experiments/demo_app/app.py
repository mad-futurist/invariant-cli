import json
import sys
from pathlib import Path


def calculate_total(price: float, quantity: int) -> float:
    return price * quantity


if __name__ == "__main__":
    price = float(sys.argv[1])
    quantity = int(sys.argv[2])

    total = calculate_total(price, quantity)

    state_path = Path(__file__).with_name("state.json")
    previous_state: dict[str, object] = {}
    if state_path.exists():
        previous_state = json.loads(state_path.read_text(encoding="utf-8"))

    state = {
        "price": price,
        "quantity": quantity,
        "total": total,
        "runs": int(previous_state.get("runs", 0)) + 1,
    }
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    print(f"price={price}")
    print(f"quantity={quantity}")
    print(f"total={total}")
