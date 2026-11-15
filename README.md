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
python -m becher compose --vocabulary 'Wrapped process buildings' \
  --silhouette low --seed 1267 --out output/process
```

## Other CLI workflows

```sh
python -m becher pipeline --seed 1267 --designs 12 --workers 4 \
  --facade-mode decals --out output/pipeline
python -m becher --help
```

The procedural pipeline writes its contact sheet to `review.png` in the output directory. Use `evaluate`, `vote`, `refill`, `selection` and `handoff` for saved procedural runs. Use `scenes` and `render-scene` for installed, standalone geometry.

Assembly components and their vocabulary index live in `data/assemblies/`. Saved scenes live in `data/scenes/`. See [Architecture](ARCHITECTURE.md) for the rendering and data boundaries.

## Tests

```sh
python -m pytest -q
```
