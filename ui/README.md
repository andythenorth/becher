# Becher assembly batches

Run from the checkout root in the Becher Python environment.

```sh
python -m ui
```

Open <http://127.0.0.1:8765/>. Choose **Grain handling**, **Liquid storage**,
or both. Pick a **Low** or **High** tile silhouette, then set the seed and
render the batch. Every batch has 16 rows with four angles per row.

Click a sprite to inspect it. Use **1** and **4** or the zoom buttons to
switch between 100% and 400%. Left and Right move between sprites, and Escape
returns to the selected sprite in the contact sheet. **Reroll row** replaces
all four angles using the batch's original settings. Each contact-sheet row
also has a reroll button.

Copy a sprite or contact sheet as an image. Save individual indexed PNGs,
geometry JSON, a contact sheet, or a batch ZIP with all 64 sprites and 16
scene files. The contact sheet uses the selected preview background.

**Preview a component** renders a single current file from `data/assemblies/`
at four rotations. It places the component at the centre of the tile at its
authored size, without a seed, a layout plan or an added slab. Editing the
assembly changes its next preview. The CLI equivalents are
`python -m becher components` and
`python -m becher render-component --component tank --out output/tank`.

## Assembly inputs

`data/assemblies/` holds the local geometry, footprints, roles and storage
connection elevations. Tall shed and short silo variants are stored alongside
the original designs. Composition uses fixed plan dimensions for hall spans.
The highest point above the slab determines the tile profile. At or above
0.42 tile units is high.

The seed chooses a layout and storage type, then an eligible assembly
combination within that type. A type can appear up to 12 times unless it
is the sole eligible type. The sampler favours less-used combinations
within the chosen type. Small catalogues can still produce repeated rows.

The procedural factory generator is available via `python -m becher pipeline`.

## CLI

```sh
python -m becher compose --vocabulary 'Grain handling' --seed 1267 --silhouette low --out output/grain
```

Use a fresh output directory. Each numbered row contains a `scene.json`
and four native PNGs. The command prints JSON with the rows and their
composition IDs. `python -m becher reroll-tile --help` describes the
single-row operation used by the UI. Pass the same brief, current composition
IDs in row order, and the row's next revision, starting at 1.
