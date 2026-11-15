# Liquid tanks v4

This overlay replaces the overlarge generated tank selection with a curated
catalogue of **24** active tank assemblies in Liquid storage, including four
original designs and a small range of distinct sizes and arrangements. Liquid
processing shares 13 tank designs plus its original tall process tank.

Changes:
- Drop most redundant generated tank variants, reducing tank-only results.
- Exclude combinations of two different tank designs in the compositor;
  combinations with non-tank equipment remain unrestricted.
- Rework horizontal tanks as broad-bodied, capped cylinders with a pair of
  hoops and simple support saddles; some high-profile variants have one service
  riser. Both silhouettes remain represented.
- Only a narrow mixed-tank exclusion is added to the compositor. No other
  placement, collision, renderer, lighting, UI or silhouette-code changes.

## Install

From the Becher project root:

```bash
unzip -o becher_liquid_tanks_patch_v4.zip -d .
python remove_superseded_liquid_tanks.py
```

The cleanup script removes only previously generated tank files matching
known filenames and not referenced by any current vocabulary. It does not
remove hand-authored tanks or components in use by another vocabulary.

## Sampled results (40 seeds, 16 tiles each)

Tank-plus-non-tank compositions in Liquid storage:
- Low profile: 55.9%
- High profile: 60.8%

Tests: `PYTHONPATH=. python -m pytest -q tests/test_liquid_vocabularies.py tests/test_composition.py`.
