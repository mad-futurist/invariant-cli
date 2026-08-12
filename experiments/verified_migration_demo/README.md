# Verified migration demo

This experiment separates behavioral preservation from target architecture compliance.

- `target/`: subtraction through `AccountRepository` — both gate groups pass.
- `target_bad_arch/`: correct subtraction with a direct state write — behavior passes and
  architecture fails.
- `target_bad_behavior/`: repository boundary with addition — architecture passes and behavior
  fails.

The architecture artifact declares only deterministic v1 rules: forbidden direct writes, state
ownership, and a required component dependency. The automated acceptance test proves all three
independent outcomes.

```text
invariant gate run CONTRACT --source-code source --target-code target \
  --architecture invariant.arch.yaml --validation VALIDATION.json
```
