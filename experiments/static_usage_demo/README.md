# Static usage demo

This experiment represents the same balance in two different programs:

- `source/wallet.json#available_cents` stores an integer number of cents;
- `target/account.json#spendable_eur` stores the corresponding number of euros.

The applications also update the fields with different Python syntax:

```python
wallet["available_cents"] -= payment_cents
account["spendable_eur"] = account["spendable_eur"] - payment_eur
```

Invariant should infer the dynamic relation `target = source * 0.01` and attach matching static operations: `read`, `subtract`, and `write`.

Reset both states to a cents balance with:

```bash
python experiments/static_usage_demo/reset.py 10000
```

The complete capture, inference, and held-out validation workflow is exercised by `tests/experiments/test_static_usage_demo.py`.
