# Becher: agent workflow for structural geometry

**Status:** Authoring procedure, not an executable graph schema.  
**Scope:** Create, challenge, render and hand off novel industrial structures without changing Becher's established geometry compiler or renderer.  
**Read first:** `purpose.md`, `ARCHITECTURE.md`, and the actual source interfaces identified below. If any instruction here disagrees with current source, stop and report the discrepancy rather than inventing an API.

**Fundamental boundary:** An *agent-authored structural graph* is a design representation. The current Becher application (v0.16.6) does **not** expose a general graph parser or constraint solver. Its executable interchange format is a JSON scene with a `shapes` array, compiled by `src/mesh/compile.py:compile_scene` through `src/mesh/author.py:scene_faces`. Do not present a conceptual graph as executable Becher input.

## 0. Inspect the actual capabilities (mandatory)

Before designing anything:

1. Read `src/mesh/author.py` (`scene_faces`, `beam_between`, `sweep_rings`, `revolution`), `src/mesh/compile.py`, `src/geometry.py` (`MATERIAL_IDS`), and `examples/geometry_scene.json`.
2. Check `python -m becher --help` and the `bake-scene` / `render-mesh` commands. Do not assume that a current factory grammar accepts arbitrary graph definitions.
3. Locate the current tests, especially mesh geometry, camera/light, and golden tests. **Do not modify or regenerate their baselines** as part of authoring a new design.
4. Record any unsupported operation as a limitation, not as a reason to alter the renderer. If an essential feature is impossible with the current compiler, stop that feature and propose a small, general-purpose geometry extension separately.

**Gate:** List the primitives, materials, units/conventions, and invocation methods confirmed by the checked-out code. Never rely solely on this document for version-specific API details.

## 1. State the visual brief

Write a compact design brief before constructing geometry:

- **Identity:** e.g. gantry crane, cement silo cluster, mine headframe; intended industrial function.
- **Recognisable features:** choose two or three silhouette-defining features visible at native resolution.
- **Spatial envelope:** approximate overall footprint, height, ground clearance and relative proportions.
- **View constraints:** design must read at all four 90° rotations, not only one flattering angle.
- **Style:** native **64 × 128** pixel OpenTTD-style indexed output; low-detail, legible, deliberate silhouette rather than physical realism.
- **Reference status:** distinguish observed design facts, your own artistic decisions and hypotheses. Do not assert structural or visual fidelity without inspection.

**Gate:** Could a viewer identify the structure from its massing at 100%? If not, simplify or revise the brief before adding details.

## 2. Author a structural graph as a *design specification*

Express the design explicitly as a small graph. This is for planning and review; it is not a Becher JSON schema.

**Node record** (one per meaningful structural component):

- Stable ID and semantic role (`support`, `vessel`, `crossbeam`, `brace`, `deck`, `hopper`, etc.).
- Approximate size and placement / reference axes.
- Intended primitive or profile family (`box`, `beam`, `cylinder`, `revolution`, `rings`/sweep, or custom triangles only if necessary).
- Material from the **actual** `MATERIAL_IDS` mapping.
- Attachment points and any adjustable dimensions.

**Edge record** (one per relationship):

- Endpoints (node IDs and, where needed, named attachment points).
- Relationship: `supports`, `connects`, `suspends`, `aligns`, `passes_through`, `rests_on`, etc.
- Geometric condition to verify, e.g. coincident attachments, equal elevations, nonzero clearance, shared alignment.

Use explicit XYZ coordinates and one consistent world-axis convention. Avoid anonymous placements and unrecorded offsets. Note which links are functional relationships versus visually decorative touches.

**Gate:** Every component has a purpose; every claimed support or connection has a named, checkable relationship. The graph is intelligible without looking at Python code.

## 3. Check the graph before compilation

Challenge the design specification *without rendering*:

1. **Connectivity:** Does every supposed load-bearing chain actually connect? Are isolated nodes intentional?
2. **Support:** Are vessels, platforms and overhead members visibly supported? Are beams anchored where claimed?
3. **Dimensions:** Positive thickness, nondegenerate members, coherent relative scale, plausible access and clearances.
4. **Intersections:** Identify intended unions, tolerated overlaps, and unintended penetrations. Do not demand strict nonintersection where overlapping solids are deliberately used.
5. **Visibility:** Is the identifying structure likely to survive projection, occlusion and 64 × 128 pixel quantisation in *all* views?
6. **Complexity:** Remove decorative nodes whose projected contribution is negligible or noisy.

**Gate:** Record any exceptions and why they are acceptable. Do not quietly convert broken relationships into arbitrary geometry.

## 4. Lower the graph into the executable scene format

Translate graph nodes and edges into **only the primitives the checked-out compiler supports**. The current known `scene_faces` cases are:

| Scene `type` | Required geometry fields | Notes |
|---|---|---|
| `box` | `bounds` (6 numbers) | Min/max XYZ bounds |
| `cylinder` | `bounds` (6 numbers) | Axis and shape per implementation |
| `beam` | `start`, `end` (XYZ), `thickness` | Square cross-section; suitable for structural edges |
| `revolution` | `profile` as `(z, radius)` pairs | Optional `center` (XY), `segments` |
| `rings` | `rings` (matched 3D contour arrays) | Sweep through sections; simple planar caps |
| `triangles` | `vertices` (triangles) | Optional `normals`; avoid unless the other primitives cannot express it |

Each shape can include a stable `id` and supported `material` string. Current material identifiers are `metal`, `roof`, `concrete`, `frame`, `glass`, `chimney`, `pipe`; **verify in source** before use.

Minimal *executable* example showing a graph relationship lowered to two shapes:

```json
{
  "shapes": [
    {"id": "support_a", "type": "box", "bounds": [0.2, 0.3, 0.05, 0.3, 0.4, 0.5], "material": "concrete"},
    {"id": "cross_member", "type": "beam", "start": [0.25, 0.35, 0.5], "end": [0.75, 0.35, 0.5], "thickness": 0.05, "material": "frame"}
  ]
}
```

This scene **does not encode** the `supports` relation or enforce attachment constraints; those remain in the design specification and checks. Don't imply the compiler validates semantic edges. Prefer declarative scene content over adding code for each new design. Do not modify `src/mesh/intersect.py`, rendering, lighting, palette or existing factory grammars to accommodate a scene.

**Gate:** Save a well-formed scene JSON; every shape must map to a supported primitive and every component ID must be meaningful.

## 5. Compile and inspect (all four rotations)

From the repository root, using fresh, nonexisting output paths:

```bash
python -m becher bake-scene --input work/design_01.json --out work/design_01.npz
python -m becher render-mesh --mesh work/design_01.npz --out work/design_01_views
```

Inspect `r000.png`, `r090.png`, `r180.png`, `r270.png` and the frozen mesh. For each rotation, view at:

- **100%:** actual 64 × 128 display pixels: recognisability, proportions, feature legibility.
- **400% nearest-neighbour:** occlusion, seams, holes, raster artefacts, excessive pixel noise.
- **Contact sheet:** compare relative silhouette and apparent material/lighting consistency across views.

A successful compile is **not** evidence of good geometry. Check that the named graph connections are visible, that no important members vanish, that negative spaces stay open, and that no back-facing surfaces become inexplicable bright bands.

**Gate:** Record a short outcome for **each** rotation. If an essential feature fails at native scale, revise the graph and scene, not the renderer.

## 6. Adversarial review (mandatory, separate pass)

Adopt the stance: **the design is wrong until the evidence addresses concrete failure modes**. If possible, assign this stage to a second agent given the brief, graph, scene and *all four* rendered views; otherwise perform it as an explicit second pass, without reusing the author's justifications as proof.

Attack the following claims:

1. **Identity challenge:** Would the silhouette still read as the specified machine/building if labels were hidden? What could it be mistaken for?
2. **Topology challenge:** Delete or move one claimed structural connection mentally or in a diagnostic copy; is it visibly required? Are supported components actually supported?
3. **View challenge:** Identify the worst of the four rotations; inspect hidden faces, false intersections and projection overlaps.
4. **Scale challenge:** Which features are under 1–2 output pixels, or too thin to persist? Which features dominate disproportionately?
5. **Shape challenge:** Look for holes accidentally filled by sweep caps; inverted or inconsistent normals; implausible cylindrical profiles; missing negative space.
6. **Renderer-boundary challenge:** Have any proposed fixes added shape-specific shading, visibility, camera or ray-intersection exceptions? Reject those as geometry authoring workarounds.
7. **Oracle challenge:** Do validation numbers merely show compilation/nonempty output? What visual claim remains unsupported by tests?
8. **Complexity challenge:** Can a node, edge, profile station or special-case parameter be removed without harming the 100% render?

For each material objection, report **evidence** (component ID, rotation, screenshot or measured geometry), **severity** (blocker/major/minor), and a **geometry-level remedy**. Do not assert a defect without distinguishing observation from speculation.

**Gate:** No unresolved blockers. Major issues either fixed and rerendered or explicitly reported as limitations. Do not silently bless a scene because all automated tests pass.

## 7. Verify determinism and guard against misleading tests

- Recompile the same unchanged JSON twice; check identical topology/material/component inventory and rendered output. Compare array contents numerically where floating-point portability is relevant; do not treat cross-platform raw `float64` hashes as a correctness oracle.
- Confirm output inventory is **exactly** rotations `0, 90, 180, 270`: no missing, duplicate or unexpected records.
- Check component/triangle counts and finite vertices/normals; assert positive feature witnesses **before** property checks, where those features are required.
- If asserting geometry against a reference, compare floats with a stated tolerance and discrete IDs exactly. Keep indexed pixels/palettes exact when the current environment permits; report platform-specific deviations rather than automatically refreshing reference images.
- Challenge one important test with a deliberate bad input (e.g. missing support, degenerate beam, inverted/invalid sweep, absent rotation) and verify it fails for the **intended reason**. Use a disposable copy of input/output; do not alter production sources or approved golden fixtures.
- Run relevant existing tests, but understand that the factory golden suite primarily safeguards the **established factory baseline**, not a new graph design's artistic quality.

**Gate:** Produce both positive evidence and at least one meaningful negative-control result. Never regenerate approved goldens as an automatic response to failures.

## 8. Deliver and hand off

Deliver a small, inspectable package:

1. `brief.md`: identity, design rationale and intended recognisable features.
2. `graph.md` or `graph.json`: **design-specification** nodes and relationships, clearly labelled *not an executable Becher graph API*.
3. `scene.json`: actual Becher-compatible compiled input.
4. Four native indexed PNGs (plus optional contact sheet), and optionally the `.npz` intermediate mesh.
5. `review.md`: each rotation reviewed at 100% and 400%, adversarial issues and their disposition, tests/negative control, and known limitations.
6. Reproduction commands and fixed inputs/seeds (when any stochastic authoring step was involved).

Use one design per output directory. Preserve the original brief and source scene; do not mix generated outputs with current application source or modify approved grammar families. **No claim of visual acceptance without human review.**

## Stop conditions

Stop and report rather than improvise if: the required geometry is unsupported; scene parsing would need an invented schema; constraints are not representable; structural validity cannot be checked; the output fails to compile; or the requested change would require modifying the renderer or jeopardising the approved factory baseline. Offer the smallest isolated geometry-side extension as a separate proposal.
