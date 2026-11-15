"""Standalone FIRS-inspired industry preview sheets.

Run: python -m src.industry_previews --seed 1267 --count 4 --out output/industry-previews

This module owns its catalogue, recipes, selection, tile planning, sprite assembly,
CLI and export. It imports only the public-ish existing composition and rendering
functions; it never mutates Becher's catalogue, CLI, renderer or geometry.

FIRS industry names: https://www.grf.farm/firs/5.2.0/html/industries.html
The recipes are deliberately approximations, not claims of exact FIRS tile artwork.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import random
import re
import shutil
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

from . import composition
from .authored_scenes import render_geometry

# The complete list is deliberately not treated as eligible. These are the
# industries whose principal above-ground structures the installed Becher
# vocabularies can reasonably suggest. Each tuple is (vocabulary, weight).
# One module means catalogue edits do not propagate into unrelated code.
RECIPES = {
    'Appliance Factory': (('General industrial', 8), ('Large process buildings', 3), ('Compact process buildings', 1)),
    'Assembly Plant': (('General industrial', 8), ('Large process buildings', 4), ('Compact process buildings', 1)),
    'Body Plant': (('General industrial', 8), ('Large process buildings', 3)),
    'Carbon Black Plant': (('Liquid processing', 6), ('Liquid storage', 3), ('Chimneys', 1), ('General industrial', 2)),
    'Chemical Plant': (('Liquid processing', 7), ('Liquid storage', 4), ('Compact process buildings', 3), ('Chimneys', 1)),
    'Chlor-alkali Plant': (('Liquid processing', 7), ('Liquid storage', 4), ('Compact process buildings', 2)),
    'Coal Mine': (('Mining and aggregates', 9), ('Dry material handling', 4), ('General industrial', 1)),
    'Concrete Plant': (('Dry material handling', 7), ('General industrial', 4), ('Mining and aggregates', 2)),
    'Copper Mine': (('Mining and aggregates', 9), ('Dry material handling', 4), ('General industrial', 1)),
    'Cryo Plant': (('Liquid processing', 6), ('Liquid storage', 4), ('Compact process buildings', 2)),
    'Dairy': (('General industrial', 6), ('Liquid storage', 2), ('Compact process buildings', 2)),
    'Elastomer Products Plant': (('General industrial', 6), ('Liquid processing', 3), ('Compact process buildings', 2)),
    'Engine Plant': (('General industrial', 8), ('Large process buildings', 3)),
    'Flour Mill': (('Dry material handling', 9), ('General industrial', 3), ('Chimneys', 1)),
    'Food Processing Plant': (('General industrial', 7), ('Dry material handling', 3), ('Liquid storage', 1)),
    'Iron Ore Mine': (('Mining and aggregates', 9), ('Dry material handling', 4)),
    'Limestone Mine': (('Mining and aggregates', 9), ('Dry material handling', 4)),
    'Liquids Terminal': (('Liquid storage', 9), ('Liquid processing', 3), ('General industrial', 1)),
    'Metal Works': (('General industrial', 6), ('Large process buildings', 4), ('Chimneys', 1)),
    'Paper Mill': (('Large process buildings', 6), ('General industrial', 5), ('Dry material handling', 2), ('Chimneys', 1)),
    'Pipe Shop': (('General industrial', 8), ('Large process buildings', 3)),
    'Potash Mine': (('Mining and aggregates', 9), ('Dry material handling', 4)),
    'Power Systems Factory': (('General industrial', 8), ('Large process buildings', 3)),
    'Precision Parts Plant': (('General industrial', 8), ('Compact process buildings', 3)),
    'Quarry': (('Mining and aggregates', 9), ('Dry material handling', 4)),
    'Slag Grinding Plant': (('Dry material handling', 8), ('Mining and aggregates', 3), ('General industrial', 2)),
    'Tracked Vehicle Factory': (('General industrial', 8), ('Large process buildings', 3)),
    'Tyre Plant': (('General industrial', 7), ('Liquid processing', 2), ('Compact process buildings', 2)),
}

FOOTPRINTS = ((6, 3), (5, 4), (3, 6))
# Local module-owned rules for less appropriate tiles. Distinctive multi-tank
# assemblies are intentionally allowed, but their size classes are not mixed
# within the same tile by this module (we draw only existing validated scenes).
EXCLUDED_COMPONENTS = frozenset({'aggregate_bays'})  # open ground aggregate yards need terrain

# Preview-only grouping. These are deliberately ordinary installed Becher parts,
# not new multi-tile geometry. Matching neighbouring facades and roof pitches
# make credible long halls at contact-sheet scale even when seams remain visible.
HALL_INDUSTRIES = frozenset({
    'Appliance Factory', 'Assembly Plant', 'Body Plant', 'Engine Plant',
    'Metal Works', 'Paper Mill', 'Pipe Shop', 'Power Systems Factory',
    'Precision Parts Plant', 'Tracked Vehicle Factory', 'Tyre Plant',
    'Elastomer Products Plant', 'Food Processing Plant', 'Dairy',
})
HALL_COMPONENTS = (
    'gable_shed', 'monitor_shed', 'sawtooth_hall',
    'twin_bay_shed', 'dispatch_shed',
)



@dataclass(frozen=True)
class Tile:
    col: int
    row: int
    vocabulary: str
    components: tuple[str, ...]
    composition_id: str


def _available():
    """Read installed vocabulary membership; fail closed on absent vocabularies."""
    groups = composition.vocabularies()
    installed = composition.component_catalogue()
    result = {}
    for name, roles in groups.items():
        # Deduplicate IDs shared across roles; preserve sorted stable iteration.
        names = sorted({item for items in roles.values() for item in items
                        if item in installed and item not in EXCLUDED_COMPONENTS})
        if names:
            result[name] = names
    return result


def eligible():
    available = _available()
    # Require the dominant vocabulary. A missing supporting vocabulary simply
    # disappears, never silently substitutes geometries from another industry.
    return {industry: tuple((v, w) for v, w in recipe if v in available)
            for industry, recipe in RECIPES.items() if recipe[0][0] in available}


def _single(name, part):
    """Use existing collision/footprint rules. Never invent a placement."""
    footprint = composition.transformed_footprint(part, (0, 0), 0)
    centre = (.5 - (footprint[0] + footprint[2]) / 2,
              .5 - (footprint[1] + footprint[3]) / 2)
    if part.get('placement') == 'tile':
        centre = (.5, .5)
    return composition.arbitrary_scene(((name, *centre, 0),), {name: part})


def _scene_pool(names, rng, cache):
    """Bounded, validated local pool; does NOT call composition.draft()."""
    pool = []
    # A sparse representative subset avoids building the huge all-pairs pool.
    sample = names[:]
    rng.shuffle(sample)
    for name in sample[:min(22, len(sample))]:
        if name not in cache:
            try:
                cache[name] = _single(name, composition.load_part(name))
            except (ValueError, KeyError):
                cache[name] = None
        if cache[name] is not None:
            pool.append(cache[name])
    # Add plausible prevalidated co-tile pairs. Never alter a part's shape and
    # never bypass the compositor's existing footprint/collision checks.
    short = sample[:min(9, len(sample))]
    for i, a in enumerate(short):
        for b in short[i + 1:i + 4]:
            if a == b:
                continue
            try:
                pa, pb = composition.load_part(a), composition.load_part(b)
                for axis in (0, 1):
                    scene = composition.packed_scene({a: pa, b: pb}, (a, b), (0, 0), axis)
                    if scene is not None:
                        pool.append(scene)
                        break
            except (ValueError, KeyError):
                pass
    return pool


def _hall_scene(name, turns, cache):
    """Validate a particular pre-existing hall orientation using Becher rules."""
    key = (name, turns)
    if key not in cache:
        part = composition.load_part(name)
        footprint = composition.transformed_footprint(part, (0, 0), turns)
        centre = (.5 - (footprint[0] + footprint[2]) / 2,
                  .5 - (footprint[1] + footprint[3]) / 2)
        try:
            cache[key] = composition.arbitrary_scene(
                ((name, *centre, turns),), {name: part})
        except (KeyError, ValueError):
            cache[key] = None
    return cache[key]


def _place_hall_runs(industry, width, height, rng, available, scenes):
    """Reserve adjacent runs before placing the remaining industry machinery.

    No geometry is changed. A run is repeated validated single-tile halls,
    aligned along each hall's long axis. Neighbouring runs may use a second
    compatible hall design, but each individual run uses exactly one design.
    """
    if industry not in HALL_INDUSTRIES or 'General industrial' not in available:
        return {}
    families = [name for name in HALL_COMPONENTS if name in available['General industrial']]
    if not families:
        return {}
    selected = {}
    # Most factory layouts should contain at least one recognisable elongated
    # building; a second parallel run appears when the footprint permits it.
    target = 1 + (rng.random() < .55 and min(width, height) >= 3)
    scene_cache = {}
    last_axis = None
    for number in range(int(target)):
        options = []
        for axis in (0, 1):
            limit = width if axis == 0 else height
            for length in range(min(5, limit), 1, -1):
                for y in range(height - (length if axis == 1 else 1) + 1):
                    for x in range(width - (length if axis == 0 else 1) + 1):
                        cells = [(x + i * (axis == 0), y + i * (axis == 1))
                                 for i in range(length)]
                        if all(cell not in selected for cell in cells):
                            # Favour longer runs, a common direction, and a
                            # modest perimeter margin for ancillary buildings.
                            score = length * 5 + (axis == last_axis) * 3
                            score -= abs(x + (length / 2 if axis == 0 else .5) - width / 2)
                            score -= abs(y + (length / 2 if axis == 1 else .5) - height / 2)
                            options.append((score + rng.random() * 3, axis, cells))
        if not options:
            break
        options.sort(key=lambda candidate: candidate[0], reverse=True)
        # Draw from the highest-scoring arrangements for variation across seeds.
        _, axis, cells = rng.choice(options[:min(9, len(options))])
        family = rng.choice(families)
        # A hall's local X axis is the long axis in the installed geometry.
        scene = _hall_scene(family, axis, scene_cache)
        if scene is None:
            continue
        identifier = scene['catalogue']['composition']
        scenes[identifier] = scene
        run_id = f'hall-{number + 1}'
        for index, cell in enumerate(cells):
            selected[cell] = ('General industrial', scene, {
                'id': run_id, 'family': family, 'axis': 'x' if axis == 0 else 'y',
                'index': index, 'length': len(cells),
            })
        last_axis = axis
    return selected


def _choose_layout(industry, width, height, seed, available, scene_cache, scenes):
    rng = random.Random(f'{seed}:{industry}:{width}x{height}')
    recipes = eligible()[industry]
    vocab_names = [v for v, _ in recipes]
    weights = [w for _, w in recipes]
    dominant = vocab_names[0]
    pools = {v: _scene_pool(available[v], rng, scene_cache) for v in vocab_names}
    if not pools[dominant]:
        raise ValueError(f'{industry}: dominant vocabulary has no valid tile scene')
    selected = _place_hall_runs(industry, width, height, rng, available, scenes)
    positions = [(x, y) for y in range(height) for x in range(width)
                 if (x, y) not in selected]
    rng.shuffle(positions)
    usage = Counter()
    for idx, (x, y) in enumerate(positions):
        # Preserve the dominant recipe even where most of the layout is halls.
        if idx and rng.random() < .10:
            continue
        v = dominant if idx == 0 else rng.choices(vocab_names, weights=weights, k=1)[0]
        if not pools[v]:
            v = dominant
        min_count = min(usage[(v, s['catalogue']['composition'])] for s in pools[v])
        options = [s for s in pools[v] if usage[(v, s['catalogue']['composition'])] == min_count]
        scene = rng.choice(options)
        label = scene['catalogue']['composition']
        scenes[label] = scene
        usage[(v, label)] += 1
        selected[(x, y)] = (v, scene, None)
    return selected


def plan(seed=1267, count=4, industry=None, footprint=None):
    """Return JSON-compatible deterministic plan and associated transient scenes."""
    if count < 1:
        raise ValueError('--count must be positive')
    if footprint is not None and footprint not in FOOTPRINTS:
        raise ValueError('Footprint must be one of 6x3, 5x4, 3x6')
    recipes = eligible()
    if industry is not None and industry not in recipes:
        raise ValueError(f'Unsupported industry: {industry!r}; use --list')
    available = _available()
    rng = random.Random(seed)
    industries = [industry] if industry else rng.sample(sorted(recipes), k=min(count, len(recipes)))
    layouts = []
    scene_cache = {}
    scenes = {}
    for index, name in enumerate(industries):
        w, h = footprint or FOOTPRINTS[index % len(FOOTPRINTS)]
        tiles = _choose_layout(name, w, h, seed + index, available, scene_cache, scenes)
        layouts.append({'industry': name, 'width': w, 'height': h, 'seed': seed + index,
                        'tiles': [{'x': x, 'y': y, 'vocabulary': v,
                                   'components': scene['catalogue']['components'],
                                   'composition': scene['catalogue']['composition'],
                                   **({'building_run': run} if run else {})}
                                  for (x, y), (v, scene, run) in sorted(tiles.items(), key=lambda p: (p[0][1], p[0][0]))]})
    return {'catalogue': 'FIRS 5.2', 'seed': seed, 'layouts': layouts}, scenes


def _tile_sheet(layout, images, rotation=0):
    """Dimetric native-sprite montage, with rotation-consistent tile centres.

    Project a translated world tile by 32 px on X-Y and 16 px on X+Y.
    Rotate tile positions in the same camera convention as the renderer.
    Alpha compositing preserves the renderer's unmodified sprite pixels.
    """
    w, h = layout['width'], layout['height']
    def project(x, y):
        if rotation == 90:
            x, y = y, -x
        elif rotation == 180:
            x, y = -x, -y
        elif rotation == 270:
            x, y = -y, x
        return 32 * (x - y), 16 * (x + y)
    positions = {(x, y): project(x, y) for y in range(h) for x in range(w)}
    min_x = min(p[0] for p in positions.values())
    max_x = max(p[0] for p in positions.values())
    min_y = min(p[1] for p in positions.values())
    max_y = max(p[1] for p in positions.values())
    out = Image.new('RGBA', (64 + max_x - min_x, 128 + max_y - min_y), (0, 0, 0, 0))
    # Back-to-front painter order for occlusion across tile edges.
    for tile in sorted(layout['tiles'], key=lambda t: (positions[t['x'], t['y']][1],
                                                      positions[t['x'], t['y']][0])):
        px, py = positions[tile['x'], tile['y']]
        out.alpha_composite(images[tile['composition']], (px - min_x, py - min_y))
    return out



def _contact_sheet(rendered):
    font = ImageFont.load_default()
    pad, heading, gutter = 14, 25, 16
    max_w = max(image.width for _, image in rendered)
    card_w = max_w + pad * 2
    card_h = max(image.height for _, image in rendered) + pad * 2 + heading
    cols = min(3, len(rendered))
    rows = (len(rendered) + cols - 1) // cols
    result = Image.new('RGBA', (cols * (card_w + gutter) + gutter,
                                rows * (card_h + gutter) + gutter), '#e7e9e6')
    draw = ImageDraw.Draw(result)
    for n, (layout, image) in enumerate(rendered):
        x = gutter + (n % cols) * (card_w + gutter)
        y = gutter + (n // cols) * (card_h + gutter)
        draw.rectangle((x, y, x + card_w - 1, y + card_h - 1), fill='#ffffff', outline='#b5babb')
        draw.text((x + pad, y + 9), f"{layout['industry']}  ({layout['width']}x{layout['height']})", font=font, fill='#222222')
        result.alpha_composite(image, (x + (card_w - image.width)//2, y + heading + pad))
    return result.convert('RGB')


def export(out, manifest, scene_cache, *, rotation=0):
    """Atomic directory export. No writes until all sprites were rendered."""
    if rotation not in (0, 90, 180, 270):
        raise ValueError('Rotation must be 0, 90, 180 or 270')
    out = Path(out)
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite existing output: {out}')
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='industry-previews-', dir=out.parent) as tmp:
        root = Path(tmp)
        # Cache unique scene sprites by composition ID across all industries.
        scene_by_id = {}
        for layout in manifest['layouts']:
            for tile in layout['tiles']:
                scene_by_id[tile['composition']] = scene_cache[tile['composition']]
        images = {}
        for i, (key, scene) in enumerate(sorted(scene_by_id.items())):
            path = root / 'sprites' / f'{i:04d}'
            render_geometry(scene, path)
            with Image.open(path / f'r{rotation:03d}.png') as img:
                images[key] = img.convert('RGBA')
        rendered = []
        (root / 'layouts').mkdir()
        for i, layout in enumerate(manifest['layouts'], 1):
            img = _tile_sheet(layout, images, rotation)
            slug = re.sub(r'[^a-z0-9]+', '-', layout['industry'].lower()).strip('-')
            img.save(root / 'layouts' / f'{i:02d}-{slug}.png')
            rendered.append((layout, img))
        _contact_sheet(rendered).save(root / 'sheet.png')
        (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        shutil.rmtree(root / 'sprites')
        # Copy after success; output path appears only when everything is valid.
        shutil.copytree(root, out)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description='Standalone FIRS-inspired Becher industry preview sheets')
    parser.add_argument('--seed', type=int, default=1267)
    parser.add_argument('--count', type=int, default=4)
    parser.add_argument('--industry', help='Exact FIRS industry name; overrides --count')
    parser.add_argument('--footprint', choices=('6x3', '5x4', '3x6'))
    parser.add_argument('--rotation', type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument('--out', default='output/industry-previews')
    parser.add_argument('--list', action='store_true', help='List achievable industries and exit')
    parser.add_argument('--plan-only', action='store_true', help='Print JSON plan without rendering')
    args = parser.parse_args(argv)
    if args.list:
        print(json.dumps(sorted(eligible()), indent=2))
        return
    footprint = tuple(map(int, args.footprint.split('x'))) if args.footprint else None
    manifest, scenes = plan(args.seed, args.count, args.industry, footprint)
    if args.plan_only:
        print(json.dumps(manifest, indent=2))
    else:
        path = export(args.out, manifest, scenes, rotation=args.rotation)
        print(f'Wrote {path / "sheet.png"} and {path / "manifest.json"}')


if __name__ == '__main__':
    main()
