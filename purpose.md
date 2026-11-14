# Purpose: Becher

## Intent

Becher produces convincing, varied, deterministic OpenTTD industrial sprites from procedural geometry. The primary output is artwork: the machinery matters insofar as it helps us author, vary, inspect and improve that artwork efficiently.

## Outcomes that matter

- Native 64 × 128 pixel, indexed TTD DOS-palette PNGs, with four isometric views per design.
- Recognisable industrial architecture with credible proportions, silhouettes, details and readable pixel-scale lighting.
- Repeatable, seed-controlled generation so visual changes can be assessed rather than guessed.
- Geometry and design data should be editable independently of the renderer wherever useful.
- Generated results are reviewed visually; passing tests alone does not establish artistic quality.

## Scope

Generate building geometry from grammar/catalogue content; compile geometry to ordinary triangle meshes; render four views with a general-purpose mesh raycaster; support appearance passes, deterministic variation and review/export workflows.

## Principles and constraints

- Preserve a reliable renderer and baseline geometry when extending the system.
- Prefer simple, well-understood geometry and rasterisation algorithms to special-case visual fixes.
- Author what a building is separately from how a triangle is intersected and shaded.
- Use declarative content for dimensions, material choices and variation ranges when that creates a better editing seam. Keep genuine construction algorithms in Python.
- Use the smallest implementation that solves the actual artistic or technical problem; do not accumulate dormant alternatives or parallel engines.
- A stylistically effective pixel-art result takes precedence over physically exact illumination.

## Non-goals

Photorealism, physically accurate engineering, a general-purpose 3D engine, reusable Python-library APIs, elaborate UI infrastructure and backwards compatibility with abandoned experimental implementations are not priorities.

This document describes intent, not implementation detail. For current commands use `README.md`; for code boundaries use `ARCHITECTURE.md`.
