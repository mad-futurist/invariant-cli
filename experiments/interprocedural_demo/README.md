# Interprocedural program-context demo

This experiment analyzes Python source directories rather than single files. The source behavior
crosses from `service.pay` into `repository.persist_balance`; the positive target crosses from
`payment.process_payment` into `storage.AccountRepository.store`.

All variants preserve the same small-sample runtime relation:

`state.json#balance_cents * 0.01 = account.json#remaining_eur`

The program evidence distinguishes them:

- `target`: the candidate field reaches `subtract -> local method -> field write`, so call context
  supports the candidate;
- `target_negative`: the candidate field reaches a proven dead end while `unrelated_total` reaches
  the repository, so call context contradicts the candidate;
- `target_unresolved`: the candidate field reaches the unknown external call `logger.info`, so call
  context is neutral rather than contradictory.

The full capture and inference workflows are tested by
`tests/experiments/test_interprocedural_demo.py`.
