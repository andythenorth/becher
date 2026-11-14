# Task 2: role-independent fixed-component composition (refactored)

The browser batch composer selects authored components from the union of chosen
vocabularies. Every unordered component pair is eligible, regardless of role.
Pair placement uses the components' rotated authored footprints, tests both
packing axes, and tries all four quarter turns for each component. Components
are moved but never rescaled or procedurally deformed. Candidate search stops
when a valid *silhouette-matching* placement is found. A pair may be absent if
it cannot fit the tile without conservative occupied-volume intersections.

The composer also considers singletons, repeated components, and a bounded,
linear-sized set of triples. **Triple enumeration is not exhaustive.** The
sampling stage retains deterministic seeds and the 16-row repetition cap.

The shared ground tile slab is generated exactly once by `arbitrary_scene` and
is not part of collision testing. Authored local footings, plinths and bases
are left untouched and ARE included in occupied-volume collision checks.
Primitive envelopes are conservative approximations, not exact triangle-mesh
intersections; valid tight clearances may still be rejected.

Retired: `compose`, `PLANS`, `VESSEL_PLANS`, scaling `place`, `footprint`,
`overlaps`, and their obsolete layout regression test. The old procedural
building generator is a *different* pipeline and is not removed here.
