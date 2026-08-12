import sys

from calculation import compute
from repository import AccountRepository, account

repository = AccountRepository()


def process(value: float) -> None:
    current = account["remaining_eur"]
    updated = compute(current, value)
    repository.store(updated)


if __name__ == "__main__":
    process(float(sys.argv[1]))
