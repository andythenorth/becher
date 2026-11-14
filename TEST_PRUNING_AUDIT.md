# Adversarial test-pruning audit — v0.16.5

## Deletion standard

Remove a test only if its assertion is logically vacuous, it enforces source layout rather than executable behaviour, or its sole purpose is backward compatibility with retired data/behaviour. Preserve or strengthen meaningful neighbouring assertions. Production code is not modified.

## Deletions challenged

| Deleted test or clause | Why it was retired | Adversarial counterargument / surviving protection |
|---|---|---|
| `test_isolation_no_import_dependency` | Tests forbidden *strings* in Python imports and requires an examples directory; does not establish a useful runtime contract. | Real import failures are exercised by the entire suite and CLI tests. Golden outputs and mesh tests guard actual behaviour. Deliberately importing dead code *without using it* is not a render failure, so retaining this source-policing check was not justified. |
| `test_production_imports_do_not_execute_archived_experiments` | Checks that loaded modules aren't under a now-deleted `archive/` directory. | A dependency on deleted modules fails import/run tests. This negative is guaranteed by absence of archive and says nothing about geometry or imagery. |
| `test_no_active_analytic_kernel_or_archived_imports` | Asserts filenames are absent and checks import AST against historical names. | The active pipeline rejects analytic renderer selection; current integration/golden tests require the mesh renderer. A source file's name is not a behavioural guarantee. |
| `test_no_profiles_means_no_schema_change_for_existing_grammars` | Validates the retired v0.13 grammar compatibility contract. | Current facade profiles remain covered by current fixtures, door clearance, decoration and golden rendering. If backward compatibility were later made a requirement, this must be reintroduced intentionally. |
| `test_standalone_cast_has_no_generated_ribs` | Asserts an obsolete `wall_details=full` parameter is ignored. | Current generators are still challenged for forbidden wall artifacts, with rerolls and rendered scenes. An ignored retired flag need not be supported. |
| `test_saved_surface_roles_and_legacy_without_roles` **legacy clause only** | Simulates a role-less historical NPZ buffer, a retired compatibility path. | Same test still checks native role buffer serialization and output equivalence for current formats. We have not removed backward-compatible production code, only its implied requirement. |
| Archive assertions in `test_v014_catalogue` | Requires twelve retired v0.13 families to remain in fixtures. | Active six-family contract and validity checks remain. The removed fixture's presence was not a current product requirement. |
| Historical grammar fixture used by `test_architectural_generation`, `test_step3_pipeline`, sawtooth, wall tests | Test-only dependency accidentally allowed an obsolete catalogue to govern development. | Rebound substantive geometry checks to the six current approved families; updated seeds where necessary; reran tests. Sawtooth's actual exposed clerestory is asserted for a current reference model. |
| `>= 0` glazing/decal checks in two facade test files | Mathematically tautological for pixel counts; could never detect disappearance. | Replaced with `> 0` and tested against current example renders across four rotations. Surrounding depth/normal constraints remain. |
| Building ID changes on stage reroll | Contradicted current model semantics; IDs identify building, not stage counter. | Replaced with explicit deterministic counter increment and unchanged repeatability checks. |

## Deliberate adversarial checks

1. Before editing the tests, freeze actual v0.16.4 program output as **20 native indexed PNGs, five frozen mesh records, and five scene hashes**. Test targets: classic, diverse and related; four rotations each.
2. **Mutate lighting** by reversing the sun's vertical component. The golden test rejects the altered output; 707 pixels differ in the first sprite.
3. **Mutate geometry** by moving one triangle vertex by 0.002 world units. The golden test rejects the frozen mesh vertex hash before rendering comparison.
4. Run the substantive tests retargeted from the historical grammar on current approved families. Address test assumptions that were wrong for the active model instead of changing production behaviour.
5. Confirm no tests or source imports still reference the deleted v0.13 fixture or unused oracle files.

## Caveats

- Golden images are reference outputs, not a substitute for a human judging new designs. **Do not auto-refresh** them when production output changes. Human approval is needed to update or replace accepted image fixtures.
- A checksum rejects changes but does not explain whether a change is an improvement. Pixel-difference masks are emitted on image mismatches.
- The test-scoring rubric is qualitative; only the golden tests received explicit deliberate-mutation challenges in this review.
- Seven selection tests remain shared-state/order-dependent; these have low reliability scores and merit a separate isolation refactor.
- Full pytest collection has 148 cases. The entire suite timed out in one invocation; two independently run batches passed 86 and 62 cases respectively.
