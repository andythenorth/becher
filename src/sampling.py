"""Candidate selection policy, independent of geometry and raycasting.

The six approved halls are PRIMARY grammars. Ancillaries are standalone
single-tile buildings and equipment yards; they do not have to tile-seam.
Diverse uses a deterministic structural farthest-first choice; related uses
half variations of an industry hall and half support buildings.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .architectures import generate, library
from .architectural_validation import validate

ANCILLARY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'grammars' / 'ancillary_v1.json'


def catalogue(primary=None):
    primary = library(primary)
    ancillary = library(ANCILLARY_PATH)
    names = [f['id'] for f in primary + ancillary]
    if len(names) != len(set(names)):
        raise ValueError('Primary and ancillary grammar IDs must be unique')
    return primary, ancillary


def category(family):
    return family.get('category', 'primary')


def industry_choices(primary):
    return [f['id'] for f in primary]


def _hash_int(seed, index, tag):
    return int.from_bytes(hashlib.sha256(f'{seed}|{index}|{tag}'.encode()).digest()[:8], 'big')


def variation(seed, index, *, mode):
    """Coarse architectural changes, not pixel-noise or arbitrary texture."""
    if mode == 'classic':
        return None
    r = _hash_int(seed, index, 'structural-v1')
    arrangements = ('baseline', 'broad_annex', 'short_annex', 'offset_annex')
    # Distinct seeded bands with structural relationships still validated.
    return dict(
        arrangement=arrangements[r % 4],
        aspect=('broad', 'square', 'long')[(r // 4) % 3],
        height=('low', 'medium', 'raised')[(r // 12) % 3],
        roof_variant=(r // 36) % 4,
        annex_mode=('normal', 'include', 'omit_optional')[(r // 144) % 3],
    )


def planned_family(index, seed, primary, ancillary, mode, industry=None):
    if mode == 'classic':
        return primary[index % len(primary)]
    if mode == 'related':
        if not industry:
            raise ValueError('related mode requires --industry from primary grammar IDs')
        main = next((f for f in primary if f['id'] == industry), None)
        if main is None:
            raise ValueError(f'Unknown primary industry: {industry!r}')
        # Even/odd positions interleave theme buildings and support structures.
        if index % 2 == 0:
            return main
        return ancillary[(index // 2 + _hash_int(seed, 0, 'ancillary-offset')) % len(ancillary)]
    if mode == 'diverse':
        all_families = primary + ancillary
        return all_families[index % len(all_families)]
    raise ValueError(f'Unsupported candidate mode: {mode}')


def _signature(model):
    """Structural descriptor uses 3D components, not palette or decorations."""
    bodies = [c for c in model.components if c.role == 'fabric']
    main = next(c for c in bodies if c.parent is None)
    x0, y0, z0, x1, y1, z1 = main.bounds
    roofs = tuple(sorted(c.roof for c in model.components if c.role == 'roof'))
    equipment = sum(c.role in ('vessel', 'equipment') for c in model.components)
    return dict(family=model.family, category=model.parameters.get('grammar_category', 'primary'),
                bodies=len(bodies), roofs=roofs, width=x1-x0, depth=y1-y0,
                height=z1-z0, ratio=(x1-x0)/max(0.01, y1-y0),
                equipment=equipment,
                arrangement=model.parameters.get('variation', {}).get('arrangement', 'baseline'))


def structural_distance(a, b):
    a = _signature(a); b = _signature(b)
    score = 0.0
    score += 5.0 if a['family'] != b['family'] else 0.0
    score += 1.5 if a['category'] != b['category'] else 0.0
    score += min(1.8, abs(a['bodies']-b['bodies']) * .9)
    score += min(2.0, len(set(a['roofs']) ^ set(b['roofs'])) * .85)
    score += min(1.0, abs(a['equipment']-b['equipment']) * .35)
    score += min(1.5, abs(a['width']-b['width']) * 3)
    score += min(1.5, abs(a['depth']-b['depth']) * 3)
    score += min(1.0, abs(a['height']-b['height']) * 2)
    score += .7 if a['arrangement'] != b['arrangement'] else 0.0
    return score


def create(seed, index, *, primary, ancillary, mode='classic', industry=None):
    family = planned_family(index, seed, primary, ancillary, mode, industry)
    return generate(seed, index, families=[family], variation=variation(seed, index, mode=mode))


def candidates(seed, designs, start, primary, ancillary, mode, industry, max_attempts):
    if mode not in ('classic', 'diverse', 'related'):
        raise ValueError('candidate mode must be classic, diverse or related')
    if industry is not None and (mode != 'related' or industry not in industry_choices(primary)):
        raise ValueError('--industry requires related mode and a valid primary family ID')
    if mode == 'related' and industry is None:
        raise ValueError('related mode requires --industry')
    if mode == 'classic':
        ancillary = []
    pool = []
    rejected = []
    cursor = start
    # Generate a bounded oversized pool for diverse selection. Related and
    # classic preserve production order, supporting predictable 50/50 batches.
    wanted = min(max_attempts, max(designs * (5 if mode == 'diverse' else 1), designs))
    while cursor < start + max_attempts and len(pool) < wanted:
        model = create(seed, cursor, primary=primary, ancillary=ancillary, mode=mode, industry=industry)
        verdict = validate(model)
        if verdict['passes']:
            pool.append(model)
        else:
            rejected.append(dict(index=cursor, issues=verdict['issues']))
        cursor += 1
    if len(pool) < designs:
        raise RuntimeError(f'Only {len(pool)} valid buildings generated')
    if mode == 'diverse':
        # First selection is deterministic and favours the primary set; later
        # selections maximise minimum structural distance to the selected set.
        chosen = [pool.pop(0)]
        while len(chosen) < designs:
            selected = max(pool, key=lambda m: (
                min(structural_distance(m, s) for s in chosen),
                -m.index))
            chosen.append(selected)
            pool.remove(selected)
        selected = chosen
    else:
        selected = pool[:designs]
    return selected, rejected, cursor
