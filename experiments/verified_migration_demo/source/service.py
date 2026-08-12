import sys

from calculation import calculate
from repository import persist_balance, state


def pay(amount: int) -> None:
    current = state["balance_cents"]
    updated = calculate(current, amount)
    persist_balance(updated)


if __name__ == "__main__":
    pay(int(sys.argv[1]))
