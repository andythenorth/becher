# Working on Becher

Read `purpose.md` first, then `ARCHITECTURE.md` and the current `README.md`. These are the only authoritative project guides.

- Protect the working 0.16.2 visual/geometry baseline; do not alter rendering or grammar semantics during maintenance.
- Code is directly under `src/`; authored inputs under `data/`; test-only old grammars under `tests/fixtures/`.
- Do not revive legacy analytic raycasting or turn the mesh renderer into a collection of object-specific exceptions.
- Prefer ordinary geometry algorithms, one implementation path and minimal dependencies.
- Run focused tests and fixed-seed four-view render comparisons for relevant changes. Distinguish visual judgement from numerical tests.
- `related` pipeline mode requires `--industry` with an existing primary grammar ID. There is no main CLI `--vocabulary` option.
- Do not claim an experimental mine or farm grammar is integrated unless verified against current source.
- Keep documentation current; do not recreate per-release changelog collections or historical README variants.
