# Horizontal tank + building placement improvement (v5 overlay)

Install **after v4** from the Becher project root:

```sh
unzip -o becher_horizontal_tank_combinations_v5.zip -d .
python -m pytest -q tests/test_composition.py tests/test_liquid_vocabularies.py tests/test_placement_coverage.py
```

Changes only `src/composition.py` and adds `tests/test_placement_coverage.py`.
There are no geometry or vocabulary modifications. It does not change `draw()`:
seeded sampling, type balancing, and existing repetition behaviour are intact.

## Generic placement improvements

- Three-component candidate construction samples several feasible partners over
  the footprint-area spectrum instead of taking the first alphabetical match.
- Compact third components are tried in multiple orders, axes, and quarter-turns.
- A new L-shaped footprint packing option uses the same primitive collision,
  tile-boundary and high/low checks as existing straight packing.
- Existing restriction on combining different tank designs remains unchanged.
- Search stays bounded; it does not enumerate every triple.

## 100-seed comparison (16-tile batches)

Average tiles containing **both a horizontal tank and a building** from the
specified vocabulary, comparing v4 to this patch:

| Additional vocabulary | Profile | v4 | v5 |
| --- | --- | ---: | ---: |
| General industrial | low | 0.41 | 0.90 |
| General industrial | high | 0.77 | 1.63 |
| Compact process buildings | low | 0.43 | 0.98 |
| Compact process buildings | high | 0.57 | 1.06 |
| Large process buildings | low | 0.07 | 0.12 |
| Large process buildings | high | 0.00 | 0.00 |

Large process buildings were not a performance target. No sampling preferences
or weights were introduced. These are deterministic seed-sample results, not
per-batch guarantees.
