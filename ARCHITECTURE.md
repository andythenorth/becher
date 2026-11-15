# Architecture

## Procedural saved runs and regression fixtures

`data/grammars/industrial_v1.json` and `data/grammars/ancillary_v1.json` → `src/architectures.py` / `src/sampling.py` / `src/feature_passes.py` → immutable building model → `src/mesh/compile.py` → frozen triangle mesh → `src/mesh/intersect.py` and `src/mesh/render.py` → indexed PNG, optional surface buffers and review output. `src/pipeline.py` implements saved-run operations and can build procedural regression fixtures from Python. New batches in the UI use assembly composition.

## Assembly composition

`data/assemblies/` and the placement plans in `src/composition.py` produce
a pool of eligible tile scenes for the selected vocabulary and silhouette.
The seeded sampler draws 16 rows. Each scene goes through the existing mesh
compiler and renderer via `src/authored_scenes.py`. The local web UI calls the
`compose` and `reroll-tile` CLI commands. A reroll renders one replacement
scene and reuses the other rows' exported files.

## Editing seams

- **Content:** `data/` holds current family definitions, parameter ranges, DOS palette, material lighting ramps and handoff profiles. Change design choices here where the existing schema permits.
- **Geometry algorithms:** `src/architectures.py`, `src/geometry.py` and `src/mesh/author.py`, `src/mesh/solids.py`, `src/mesh/compile.py`. Add reusable construction rules here, not through renderer conditionals.
- **Rendering:** `src/mesh/camera.py`, `src/mesh/intersect.py`, `src/mesh/render.py` and `src/lighting.py`. Generic nearest-hit triangle raycasting; four camera rotations; screen-relative high-elevation light.
- **Appearance and production:** `src/palette.py`, `src/semantic_colour.py`, `src/roof_colour.py`, `src/edge_contrast.py`, `src/facade_decals.py`, `src/paint.py`, and `src/handoff.py`. Surface-buffer editing and artistic passes do not redefine the scene geometry.
- **CLI:** `becher.py` is a one-line application entry point; `src/cli.py` defines the commands. `python -m becher` and `python becher.py` invoke the same implementation.

## Preserved boundaries

One authoritative mesh compiler and one active generic raycaster. Geometry is built separately from render projection and material shading. Screen-space appearance must not be corrected by geometry-specific raycaster branches. Standardise scenes and verify the four views before extending building grammar families.

## Data and tests

The current six-family industrial grammar lives in `data/grammars/industrial_v1.json`. The ancillary catalogue has separate data. Retired experimental mine conversion tools and historical references are not distributed. Adding mine vocabulary requires new, reviewed geometry work.

For repository consolidation, the criterion is pixel-equivalent deterministic output from the preserved rendering path; feature work may intentionally change output but should introduce its own comparison.
