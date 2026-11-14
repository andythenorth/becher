# Verification — v0.16.6 test hardening

Production implementation (`src/`, `data/`, `becher.py`) and frozen golden references (`tests/golden/`) are unchanged from v0.16.5.

- 160 collected pytest cases; **160 passed in one run (45.15 seconds)**.
- Golden validation now requires an exact candidate and rotation set, including duplicate rejection, before comparing any native indexed pixels, palette bytes, frozen meshes and scenes.
- 12 negative controls intentionally omit, duplicate or change rotations or invent candidates (three candidate modes). All are rejected by the golden inventory validator.
- Edge on/off integration checks exact four-rotation sets and matches records by angle, rather than truncating via `zip`.
- Seven selection tests each work on their own directory copied from immutable initial/refilled fixtures; no prior test mutation is required.
- Facade clearance requires at least one window on each nonblank-profile host. Bof facade tests require windows and doors to exist before checking their assignments.
- No new requirement was imposed for a separate `frame`-material door component because the current geometry need not contain one.
- The goldens are *regression* evidence against previously accepted factory rendering, not a general independent correctness proof.
- Individual reliability/utility review retained and updated in `TEST_SCORES.csv` / `TEST_SCORECARD.md`.
