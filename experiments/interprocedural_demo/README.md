# Interprocedural program-context demo

This experiment analyzes Python source directories rather than single files. The source behavior
crosses from `service.pay` into `repository.persist_balance`; the positive target crosses from
`payment.process_payment` into `storage.AccountRepository.store`.

All variants preserve the same small-sample runtime relation:

`state.json#balance_cents * 0.01 = account.json#remaining_eur`

The Python adapter can see all three possible callees, but it cannot yet prove imported-function or
receiver-type identity. The unique suffix matches are therefore recorded as `heuristic`, and all
three variants conservatively produce neutral call-context evidence:

- `target` would be compatible if the receiver were resolved, but heuristic resolution cannot
  support it;
- `target_negative` would be incompatible if the imported source call were resolved, but an
  unresolved source path cannot prove contradiction;
- `target_unresolved` also reaches the unknown external call `logger.info`.

This experiment protects the safety rule: suffix-only call matching must never produce false
`SUPPORTS` or `CONTRADICTS`.

The full capture and inference workflows are tested by
`tests/experiments/test_interprocedural_demo.py`.
