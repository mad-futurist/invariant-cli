# Ambiguity ranking demo

This experiment intentionally gives one source field two indistinguishable target fields:

- `source/state.json#balance`;
- `target/account.json#remaining`;
- `target/account.json#total`.

All three fields undergo the same varied transitions and expose the same observed schema. Invariant
must preserve both direct hypotheses, give them the same deterministic rank, and mark the source
candidate set as `ambiguous`. The derived `remaining + total` expression also remains as a lower-ranked
alternative. Held-out validation may pass for every hypothesis, but it must not silently turn the tie
into an arbitrary choice.
