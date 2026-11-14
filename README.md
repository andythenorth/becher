# Becher

Procedural OpenTTD industrial sprites. Becher generates batches from selected building families using the mesh renderer and high-five-o’clock lighting.

## Run

Requires Python 3.10+, NumPy and Pillow. From the repository root:

```bash
python -m pip install -e .
python -m becher pipeline --seed 1267 --designs 12 \
  --workers 4 --facade-mode decals --edge-contrast on --roof-colours on \
  --out output/pipeline
```

`python becher.py ...` also works without installation when dependencies are available. Rendered sprites are indexed 64 × 128 PNGs with four rotations; `output/pipeline/review.png` provides a contact sheet.

For all commands and options: `python -m becher --help` and `python -m becher pipeline --help`.

To generate from specific families, list their IDs with `python -m becher families`
and pass one `--family` per selected family:

```bash
python -m becher pipeline --family broad_high_roof_hall --family tank_yard \
  --seed 1267 --designs 12 --out output/selected-families
```

The batch cycles through the eligible families in catalogue order, skips
invalid designs, and applies seeded structural variation. The design count
is the total for the batch. With no `--family` flags, all primary factory
families are eligible.

Run `python -m ui` from the checkout and open <http://127.0.0.1:8765/> to
choose families and review sprites in the browser.

Use a new output directory for generation with this policy. Older runs
can still be reviewed, rerolled and exported. Refill requires a new-policy run.

## Tests

```bash
python -m pytest -q tests/test_golden_outputs.py
python -m pytest -q
```

Five frozen building scenes exercise mesh compilation and rendering against
the original mesh references and 20 indexed sprites. Sampling tests cover
family selection, determinism and refill separately.

## Layout

- `purpose.md` — why Becher exists and what matters.
- `ARCHITECTURE.md` — actual source structure and editing seams.
- `AGENTS.md` — short guidance for agent-assisted work.
- `src/` — application implementation, including `src/mesh/`.
- `data/` — active authored grammar, materials and palette inputs.
- `tests/` — behavioural, geometry and lighting regression tests.
- `examples/` — small declarative geometry scenes and facade fixtures used by tests.

Run outputs belong in `output/` (ignored locally); do not commit generated previews as source.
