# SQLite observer demo

This experiment runs the translation-contract pipeline against relational state instead of JSON files.

The source application stores a wallet balance in cents:

```text
source/legacy.db -> wallets[id=1].balance_cents
```

The target application stores the corresponding balance in euros under a different schema:

```text
target/modern.db -> accounts[id=1].available_eur
```

Reset both databases:

```bash
python experiments/sqlite_observer_demo/reset.py 10000
```

Capture only the database used by a command:

```bash
invariant capture --observe "source/*.db" -- python source/app.py 3000
invariant capture --observe "target/*.db" -- python target/app.py 30
```

Across several execution pairs, Invariant should infer `target = source * 0.01`. The end-to-end workflow, including held-out validation, is covered by `tests/experiments/test_sqlite_observer_demo.py`.
