# Task 2: General fixed-component tile composition

The browser's `compose` and `reroll` operations now use a role-independent
candidate catalogue. Every distinct component named by any selected vocabulary
is eligible for solo placement and for pairwise combination with every other
selected component, including across vocabularies. Repeated instances and
bounded three-part layouts are also attempted. There is no requirement for a
shed or a primary role.

- **Geometry is fixed:** only rigid translation and rotations by 90 degrees.
  Neither mesh deformation, swept-path variation nor scaling occurs at runtime.
- **Validity:** candidate components must fit the tile. Primitive-level 3D
  collision volumes are tested between components. This is *conservative*,
  not exact triangle-mesh intersection: curved surfaces use envelopes, beam
  sweeps use small segments and ring sweeps use per-interval envelopes.
  Therefore some physically feasible tight arrangements may be excluded.
- **Placement search:** pairs try a bounded series of positions and a quarter
  turn. "Everything combines with everything" means all component pairings
  are eligible, **not** that every pair is guaranteed a feasible placement.
- **Sampling:** deterministic, seeded 16-row draws retain the existing type
  cap, four orientations, UI, row rerolls and scene export.
- **Legacy:** `compose()` and `PLANS` remain for compatibility with historical
  tests, but are no longer used to enumerate candidates in the active UI.

Examples of tests: mine headframe + chimney from two different vocabularies,
repeated tanks, three-component compositions, 3D collision checks, rigid
rotation, rendering, row rerolls and exported-scene reproducibility.
