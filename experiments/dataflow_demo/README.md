# Static data-flow demo

This vertical slice keeps the runtime relation identical in both target programs:

`state.json#balance_cents * 0.01 = account.json#remaining_eur`

The source and positive target also share a behavioral shape despite different names:

`field read -> subtract -> persistence call`

The second target deliberately reads `remaining_eur` only for logging. Its persisted value is
computed from `unrelated_total`, which happens to contain the same values in the small training
set. Because `logger.info` is external and unresolved, static program evidence is neutral rather
than contradictory: unknown is not treated as false.

The end-to-end positive and negative workflows are exercised by
`tests/experiments/test_dataflow_demo.py`.
