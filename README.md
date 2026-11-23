# Becher

Becher builds indexed OpenTTD industrial sprites from authored components and procedural building geometry.

## Assembly batches

From the Becher checkout, use Python 3.10 or later with NumPy and Pillow installed.

```sh
python -m pip install -e .
python -m ui
```

Open http://127.0.0.1:8765/. Select one or more vocabularies, choose a silhouette and seed, and render 16 tiles at four angles each. See [the UI guide](ui/README.md) for previews, rerolls and exports.

## Tests

```sh
python -m pytest -q
```
