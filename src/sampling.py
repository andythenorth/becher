"""Family selection and deterministic structural variation."""
from __future__ import annotations
import hashlib
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


def select_families(primary, ancillary, family_ids):
    if family_ids is None:
        return primary
    families = primary + ancillary
    requested = set(family_ids)
    unknown = requested - {family['id'] for family in families}
    if unknown:
        raise ValueError(f"Unknown family IDs: {', '.join(sorted(unknown))}")
    if not requested:
        raise ValueError('Select at least one family')
    return [family for family in families if family['id'] in requested]


def _hash_int(seed, index):
    return int.from_bytes(hashlib.sha256(f'{seed}|{index}|structural-v1'.encode()).digest()[:8], 'big')


def variation(seed, index):
    """Coarse architectural changes within a family's grammar."""
    r = _hash_int(seed, index)
    arrangements = ('baseline', 'broad_annex', 'short_annex', 'offset_annex')
    # Distinct seeded bands with structural relationships still validated.
    return dict(
        arrangement=arrangements[r % 4],
        aspect=('broad', 'square', 'long')[(r // 4) % 3],
        height=('low', 'medium', 'raised')[(r // 12) % 3],
        roof_variant=(r // 36) % 4,
        annex_mode=('normal', 'include', 'omit_optional')[(r // 144) % 3],
    )


def create(seed, index, families):
    return generate(seed, index, families=families, variation=variation(seed, index))


def candidates(seed, designs, start, families, max_attempts):
    accepted = []
    rejected = []
    cursor = start
    while cursor < start + max_attempts and len(accepted) < designs:
        model = create(seed, cursor, families)
        verdict = validate(model)
        if verdict['passes']:
            accepted.append(model)
        else:
            rejected.append(dict(index=cursor, issues=verdict['issues']))
        cursor += 1
    if len(accepted) < designs:
        raise RuntimeError(f'Only {len(accepted)} valid buildings generated')
    return accepted, rejected, cursor
