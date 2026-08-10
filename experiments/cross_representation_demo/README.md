# Cross-representation experiment

This experiment checks the first generic capture lifecycle and Evidence Graph on two
implementations that store the same concept in different technologies:

- the source keeps `wallets[id=1].balance_cents` in SQLite;
- the target keeps `remaining_eur` in JSON;
- the expected relation is `target = source * 0.01`.

The automated test captures three varied training pairs, infers the affine relation, inspects
the Evidence Graph stored with the candidate contract, and validates it on a held-out pair. It
then checks that the validation graph links the PASS result back to the inferred correspondence.

Run it with:

```bash
uv run pytest tests/experiments/test_cross_representation_demo.py -q
```
