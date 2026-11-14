# Becher

Procedural OpenTTD industrial sprites. **Current application: v0.16.6.** The working baseline is the v0.16.2 mesh renderer and high-five-o’clock lighting, unchanged by the repository consolidation.

## Run

Requires Python 3.10+, NumPy and Pillow. From the repository root:

```bash
python -m pip install -e .
python -m becher pipeline --candidate-mode diverse --seed 1267 --designs 12 \
  --workers 4 --facade-mode decals --edge-contrast on --roof-colours on \
  --out output/diverse
```

`python becher.py ...` also works without installation when dependencies are available. Rendered sprites are indexed 64 × 128 PNGs with four rotations; `output/diverse/review.png` provides a contact sheet.

For a related set, provide a primary family ID:

```bash
python -m becher pipeline --candidate-mode related \
  --industry multi_slope_industrial_hall --seed 5027 --designs 16 \
  --workers 4 --facade-mode decals --edge-contrast on --roof-colours on \
  --out output/related
```

For all commands and options: `python -m becher --help` and `python -m becher pipeline --help`.

## Tests

```bash
python -m pytest -q tests/test_golden_outputs.py
python -m pytest -q
```

The golden test suite compares 20 frozen native sprites, the underlying compiled mesh buffers, and generated scenes for three representative pipeline configurations. **Never regenerate approved reference images automatically.** Tests use a captured v0.16.4 baseline: deliberate image changes require review.

`TEST_SCORECARD.md` and `TEST_SCORES.csv` score every surviving test. `TEST_PRUNING_AUDIT.md` records removed assertions and deliberate mutation tests. Some full-suite workflow tests are comparatively slow and seven selection tests depend on shared state.

## Layout

- `purpose.md` — why Becher exists and what matters.
- `ARCHITECTURE.md` — actual source structure and editing seams.
- `AGENTS.md` — short guidance for agent-assisted work.
- `src/` — application implementation, including `src/mesh/`.
- `data/` — active authored grammar, materials and palette inputs.
- `tests/` — behavioural, geometry and lighting regression tests.
- `examples/` — small declarative geometry scenes and facade fixtures used by tests.

Run outputs belong in `output/` (ignored locally); do not commit generated previews as source.
