# Independent test review: remediation and negative controls

| Finding | Change | Adversarial verification |
|---|---|---|
| Golden falsely passed with missing 270° | Exact (candidate, rotation) set checked before file comparisons; rejects cardinality mismatch | 12 parameterised negative controls (missing, duplicate, unexpected angle, unexpected candidate × 3 modes) |
| Selection tests depend on prior methods | Initial and post-refill fixtures built once, copied per test; export dirs separate | Test 04 passes alone; full 160-case run passes |
| Edge on/off comparisons silently truncated via `zip` | Validate four exact rotation IDs and compare keyed dictionaries | Static review of assertion; deliberate omission now fails before image loop (not dynamically mutation-tested) |
| Conditional feature assertions can be vacuous | Bof windows and doors required; every nonblank window profile host produces windows | Current targeted tests pass; broader removal mutation not yet performed |
| Golden correctness vs consistency conflated | Explicit distinction in verification and scorecard; baseline not automatically updated | Existing frozen images, scenes, mesh hashes unchanged |
| Self-derived integrity/determinism oracles | No misleading upgrade to their rating; further byte-level independence is future work | Not fully remediated |

## Scope and limits

This release changes tests and documentation only. It intentionally does not expand the golden corpus, reapprove its artwork, or alter the renderer or geometry. New coverage controls are tested against deliberately damaged *metadata*; no claim of comprehensive mutation coverage is made.
