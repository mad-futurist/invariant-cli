# Interprocedural program-context demo

This experiment analyzes Python source directories rather than single files. The source behavior
crosses from `service.pay` into `repository.persist_balance`; the positive target crosses from
`payment.process_payment` into `storage.AccountRepository.store`.

All variants preserve the same small-sample runtime relation:

`state.json#balance_cents * 0.01 = account.json#remaining_eur`

The Python adapter resolves explicit imported functions and simple module-level repository
instances exactly. Unknown external calls remain conservative:

- `target` supports the resolved repository behavior chain;
- `target_negative` contradicts the fully resolved source behavior chain;
- `target_unresolved` also reaches the unknown external call `logger.info`.

This experiment protects the safety rule: suffix-only call matching must never produce false
`SUPPORTS` or `CONTRADICTS`.

The full capture and inference workflows are tested by
`tests/experiments/test_interprocedural_demo.py`.
