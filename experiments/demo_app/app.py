import sys


def calculate_total(price: float, quantity: int) -> float:
    return price * quantity


if __name__ == "__main__":
    price = float(sys.argv[1])
    quantity = int(sys.argv[2])

    total = calculate_total(price, quantity)

    print(f"price={price}")
    print(f"quantity={quantity}")
    print(f"total={total}")
