# GroundGuard v0.1.0 Production Update

Validated update for the contradiction/evidence evaluation layer.

## Changed

- `groundguard/domain/proposition_comparison.py` — preserves strict subject/predicate comparison and treats individual `operates_in` values as conflicting when directly compared.
- `groundguard/domain/propositions.py` — normalizes launch-date extraction to the expected `year` attribute and canonicalizes largest-claim categories such as `ocean` / `ocean basin`.
- `groundguard/domain/contradiction.py` — adds question-aware contradiction handling, entity-alias alignment, set-aware operating-location comparison, and conservative additive-fact handling.
- `groundguard/application/evaluator.py` — passes the question into contradiction evaluation.
- contradiction benchmark tests — pass the benchmark question into the evaluator.
- `README.md` — updated current contradiction benchmark result.

## Validation

Full suite: **226 passed**

Contradiction benchmark: **248/250 correct (99.20%)**

Contradiction error rate: **0.80%**

Regression suite remains green.

## Remaining benchmark errors

- `synthetic_040`: product-list contradiction not inferred because the answer and evidence share an additive product.
- `synthetic_047`: temporal/location contradiction where the same entity appears with different years across countries.

These are benchmark-specific false negatives and were deliberately not addressed with broad heuristics that could increase false positives.
