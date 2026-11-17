"""Labelled PNG overviews of installed assembly components."""

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import json

from PIL import Image, ImageDraw, ImageFont

from .composition import component_catalogue, vocabularies, load_part, rigid_place
from .mesh.compile import compile_scene
from .mesh.io import save
from .mesh.render import cast_mesh

SPRITE = (64, 128)
CELL_W, CELL_H, GAP, COLUMNS = 206, 178, 10, 4
BLUE = (0, 0, 255)
INK = (24, 24, 24)


def _slug(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def _font(size=12):
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/Library/Fonts/Arial.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _render_thumbnail(job):
    source, target = job
    scene = json.loads(source.read_text(encoding='utf-8'))
    mesh = compile_scene(scene)
    surfaces, _ = cast_mesh(mesh, 0)
    save(surfaces, target, buffers=False)


def _sheet(path, title, entries, memberships=None):
    """entries are (component ID, one sprite path, optional subgroup label) tuples."""
    cols = COLUMNS
    rows = (len(entries) + cols - 1) // cols
    header = 42
    image = Image.new('RGB', (cols * CELL_W + (cols + 1) * GAP,
                             header + rows * (CELL_H + GAP) + GAP), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((GAP, 10), title, fill=INK, font=_font(18))
    for index, (component, sprite_paths, subgroup) in enumerate(entries):
        x = GAP + (index % cols) * (CELL_W + GAP)
        y = header + (index // cols) * (CELL_H + GAP)
        draw.text((x, y), component.replace('_', ' '), fill=INK, font=_font(12))
        label = subgroup or (', '.join(memberships.get(component, ())) if memberships else '')
        if label:
            draw.text((x, y + 15), label[:30], fill=(80, 80, 80), font=_font(9))
        sprite = Image.open(sprite_paths).convert('RGB')
        sprite.thumbnail(SPRITE, Image.Resampling.NEAREST)
        sx = x + (CELL_W - sprite.width) // 2
        sy = y + 34
        image.paste(sprite, (sx, sy))
    image.save(path, format='PNG', optimize=True)


def render_sheets(output, workers=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    components = component_catalogue()
    groups = vocabularies()
    membership = defaultdict(list)
    vocab_entries = {}
    for vocabulary, subgroups in groups.items():
        entries = []
        for subgroup, ids in subgroups.items():
            for component in ids:
                if component in components:
                    entries.append((component, subgroup))
                    membership[component].append(f'{vocabulary} / {subgroup}')
        vocab_entries[vocabulary] = entries

    # Render one representative orientation per installed file in parallel.
    # Vocabulary sheets reuse these sprites; individual preview still renders all four.
    with TemporaryDirectory(prefix='becher-component-sprites-') as temp:
        root = Path(temp)
        scene_root = root / 'scenes'
        scene_root.mkdir()
        jobs = []
        paths = {}
        for component in components:
            scene = {'shapes': rigid_place(load_part(component), '', (.5, .5), 0)}
            scene_path = scene_root / f'{component}.json'
            scene_path.write_text(json.dumps(scene), encoding='utf-8')
            sprite_path = root / f'{component}.png'
            paths[component] = sprite_path
            jobs.append((scene_path, sprite_path))
        if workers is None:
            workers = min(4, os.cpu_count() or 1)
        if workers < 1:
            raise ValueError('Workers must be positive')
        if workers == 1 or len(jobs) == 1:
            for job in jobs:
                _render_thumbnail(job)
        else:
            with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
                list(pool.map(_render_thumbnail, jobs))

        all_entries = [(component, paths[component], None) for component in components]
        files = [{'name': 'all-components.png', 'label': 'All components'}]
        _sheet(output / files[0]['name'], 'All installed components', all_entries,
               {k: v for k, v in membership.items()})

        for vocabulary, entries in vocab_entries.items():
            filename = f'{_slug(vocabulary)}.png'
            files.append({'name': filename, 'label': vocabulary})
            _sheet(output / filename, vocabulary,
                   [(component, paths[component], subgroup)
                    for component, subgroup in entries])

        unassigned = [component for component in components if component not in membership]
        if unassigned:
            files.append({'name': 'unassigned.png', 'label': 'Unassigned'})
            _sheet(output / 'unassigned.png', 'Unassigned components',
                   [(component, paths[component], None) for component in unassigned])
    return {'components': len(components), 'sheets': files}
