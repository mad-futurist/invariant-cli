# One-to-many semantic mapping experiment

The legacy application stores one SQLite value, `balance_cents`. The target application splits the
same balance between two JSON fields, `principal_eur` and `reserve_eur`. Their proportions vary
between runs, so neither target field can be matched to the source independently.

The expected expression correspondence is:

```text
principal_eur + reserve_eur = balance_cents * 0.01
```

The automated experiment captures three varied training pairs, verifies that pairwise inference
finds nothing, infers the sum expression, inspects the expression/component Evidence Graph, and
validates the relation on a held-out split.

```bash
uv run pytest tests/experiments/test_one_to_many_demo.py -q
```
