# Becher assembly batches

Run from the checkout root in the Becher Python environment.

```sh
python -m ui
```

Open <http://127.0.0.1:8765/>. Select one or more installed vocabularies,
choose **Low** or **High**, and enter a seed. Every batch has 16 rows with
four angles per row.

Click a sprite to see 100%, 200%, 400% and 800% side by side. Left and Right
move between sprites, and Escape returns to the contact sheet. **Reroll row**
replaces all four angles of one row using the original batch settings.

Copy a sprite or contact sheet as an image. Save individual indexed PNGs,
scene geometry JSON, a contact sheet, or a batch ZIP with 64 sprites and 16
scene files. Contact sheets use the selected preview background.

**Preview components** still renders one current file from `data/assemblies/`
at four angles, centred at its authored size without a seed or added slab.
The low-priority **Build labelled component sheets** action renders one PNG
with every installed component and one PNG per vocabulary, plus an unassigned
sheet when needed. Each entry shows one representative 0° view; use the
individual component preview for all four rotations. Choose a sheet to view,
copy or save it. The CLI equivalent is
`python -m becher component-sheets --out output/component-sheets`.

The individual CLI commands are `python -m becher components` and
`python -m becher render-component --component tank --out output/tank`.

## Composition

The selected vocabularies determine the eligible components. Becher packs
compatible footprints together and also offers standalone tiles. The highest
point above the shared slab determines the silhouette. A height of at least
0.42 tile units is high.

The seed picks eligible compositions. Up to 12 rows can share a component
count when more than one count is available. Within each count, the sampler
favours less-used compositions.

## CLI

```sh
python -m becher compose --vocabulary 'Dry material handling' --seed 1267 --silhouette low --out output/dry_material
```

Use a fresh output directory. Each numbered row contains a `scene.json`
and four native PNGs. The command prints JSON with the rows and their
composition IDs. `python -m becher reroll-tile --help` describes the
single-row operation used by the UI. Pass the same brief, current composition
IDs in row order, and the row's next revision, starting at 1.
