# Working on Becher

Read `purpose.md` for project intent and `ARCHITECTURE.md` for architectural context. Consult `README.md` for current usage. Verify implementation details against the source and tests.

- Prefer straightforward, general-purpose solutions over special cases, parallel implementations or new dependencies.
- Preserve established behaviour unless the task explicitly calls for changing it.
- For rendering or geometry changes, use deterministic tests and inspect all four sprite rotations where relevant. Numerical tests do not establish visual quality.
- Treat existing architecture as a deliberate starting point, not an immutable constraint. Explain substantial departures.
- Verify claims about features and supported grammars against the current implementation.
- Keep documentation consistent with the code. Avoid accumulating obsolete documentation or temporary investigation files.

When instructions, documentation and implementation disagree, investigate rather than silently choosing one.
