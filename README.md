# Becher

Becher builds indexed OpenTTD industrial sprites from authored components and procedural building geometry.

## Assembly batches

From the Becher checkout, use Python 3.10 or later with NumPy and Pillow installed.

```sh
python -m pip install -e .
python -m ui
```

Open http://127.0.0.1:8765/. Select one or more vocabularies, choose a silhouette and seed, and render 16 tiles at four angles each. See [the UI guide](ui/README.md) for previews, rerolls and exports.

```sh
python -m becher compose --vocabulary 'Compact process buildings' \
  --silhouette low --seed 1267 --out output/process
```

## Other CLI workflows

Use `scenes` and `render-scene` for installed standalone geometry. Existing
procedural runs can still be opened with `evaluate`, `vote`, `refill`,
`selection` and `handoff`. The grammar files supply the family catalogue used
by `families` and saved-run refill.

Assembly components and their vocabulary index live in `data/assemblies/`. Saved scenes live in `data/scenes/`. See [Architecture](ARCHITECTURE.md) for the rendering and data boundaries.

## Tests

```sh
python -m pytest -q
```
