"""Choose seeded tile compositions from fixed assemblies and compatible placements."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random
import re
from tempfile import TemporaryDirectory

from .authored_scenes import render_geometry, render_scene_files

DIRECTORY = Path(__file__).resolve().parents[1] / 'data' / 'assemblies'
BATCH_SIZE = 16
TYPE_CAP = 12
HIGH_PROFILE = .42  # Height above the slab in tile units.
SLAB = .044

# Each storage plan gives the hall (X, Y, length) and a grid of vessel centres.
PLANS = {
    'end_single': ((.275, .28, .48), (.75,), (.70,)),
    'wall_pair': ((.5, .28, .81), (.37, .63), (.78,)),
    'wall_row': ((.5, .28, .81), (.23, .50, .77), (.78,)),
    'end_pair': ((.305, .28, .52), (.77,), (.59, .83)),
    'corner_square': ((.5, .25, .76), (.60, .85), (.55, .80)),
    'joined_pair': ((.5, .28, .81), (.50,), (.78,)),
}
VESSEL_PLANS = ('wall_pair', 'wall_row', 'end_pair', 'corner_square')


def vocabularies():
    return json.loads((DIRECTORY / 'vocabularies.json').read_text(encoding='utf-8'))


def component_catalogue():
    return {
        path.stem: path
        for path in sorted(DIRECTORY.glob('*.json'))
        if path.stem != 'vocabularies' and path.is_file()
        and re.fullmatch(r'[a-z0-9][a-z0-9_]*', path.stem)
    }


def list_components():
    return [{'id': key, 'label': key.replace('_', ' ')} for key in component_catalogue()]


def render_component(component, output):
    if component not in component_catalogue():
        raise ValueError(f'Unknown installed component: {component}')
    shapes = place(load_part(component), '', (.5, .5, 0))
    render_geometry({'shapes': shapes}, output)
    return {'id': component, 'sprites': 4}


def load_part(name):
    return json.loads((DIRECTORY / f'{name}.json').read_text(encoding='utf-8'))


def place(part, prefix, offset, xy_scale=(1, 1)):
    # Hall spans fit the authored placement plan; all component Z dimensions are fixed.
    def point(values):
        return [round(value * scale + base, 8)
                for value, scale, base in zip(values, (*xy_scale, 1), offset)]

    shapes = deepcopy(part['shapes'])
    for shape in shapes:
        shape['id'] = prefix + shape['id']
        if 'bounds' in shape:
            bounds = shape['bounds']
            shape['bounds'] = point(bounds[:3]) + point(bounds[3:])
        elif shape['type'] == 'rings':
            shape['rings'] = [[point(vertex) for vertex in ring] for ring in shape['rings']]
        elif shape['type'] == 'revolution' and xy_scale == (1, 1):
            shape['center'] = point(shape['center'])
            shape['profile'] = [[round(z + offset[2], 8), radius]
                                for z, radius in shape['profile']]
        elif shape['type'] == 'beam' and xy_scale == (1, 1):
            shape['start'] = point(shape['start'])
            shape['end'] = point(shape['end'])
        else:
            raise ValueError(f"Unsupported assembly placement for {shape['id']}")
    return shapes


def footprint(part, x, y, scale):
    a, b, c, d = part['footprint']
    sx, sy = scale
    return x + a*sx, y + b*sy, x + c*sx, y + d*sy


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def top(shape):
    if 'bounds' in shape:
        return shape['bounds'][5]
    if shape['type'] == 'rings':
        return max(point[2] for ring in shape['rings'] for point in ring)
    if shape['type'] == 'revolution':
        return max(z for z, _ in shape['profile'])
    return max(shape['start'][2], shape['end'][2]) + shape['thickness'] / 2


def compose(shed, plan, accessory, parts):
    hall = parts[shed]
    slab = dict(id='slab', type='box', material='concrete',
                bounds=[.035, .045, 0, .965, .955, SLAB])
    kind = 'none'
    placements = []
    if plan == 'equipment_tile':
        part = parts[accessory]
        kind = part['role'] + 's'
        hall_site = (.5, .5, (1, 1))
    elif plan in PLANS:
        (x, y, length), xs, ys = PLANS[plan]
        hall_site = (x, y, (length, .85))
        part = parts[accessory]
        kind = part['role'] + 's'
        placements = [(x, y) for y in ys for x in xs]
    else:
        hall_site = (.5 if plan == 'standalone' else .43, .5, (.90, 1.40))
        if plan == 'with_annex':
            part = parts[accessory]
            placements = [(.65, .812)]

    x, y, hall_scale = hall_site
    hall_bounds = footprint(hall, x, y, hall_scale)
    bounds = [hall_bounds]
    shapes = place(hall, 'hall_', (x, y, SLAB), hall_scale)
    for index, (x, y) in enumerate(placements):
        area = footprint(part, x, y, (1, 1))
        # An annex deliberately intersects its host wall. Storage needs a clear site.
        collision = any(overlaps(area, other) for other in bounds)
        if collision != (plan == 'with_annex'):
            raise ValueError(f'{shed}, {plan}, {accessory}: incompatible footprints')
        bounds.append(area)
        prefix = 'annex_' if plan == 'with_annex' else f'yard_{index}_'
        shapes.extend(place(part, prefix, (x, y, SLAB)))
    if any(not (0 <= a < c <= 1 and 0 <= b < d <= 1) for a, b, c, d in bounds):
        raise ValueError(f'{shed}, {plan}, {accessory}: assembly extends off the tile')

    if plan in PLANS and len(placements) > 1:
        reach = part['footprint'][2] - (.024 if kind == 'tanks' else .01)
        z = SLAB + part['port'][2]
        for row, y in enumerate(ys):
            for column, x in enumerate(xs):
                if column + 1 < len(xs):
                    shapes.append(dict(id=f'pipe_x_{row}_{column}', type='beam', material='pipe',
                                       start=[x + reach, y, z], end=[xs[column + 1] - reach, y, z],
                                       thickness=.023))
                if row + 1 < len(ys):
                    shapes.append(dict(id=f'pipe_y_{row}_{column}', type='beam', material='pipe',
                                       start=[x, y + reach, z], end=[x, ys[row + 1] - reach, z],
                                       thickness=.023))

    silhouette = 'high' if max(map(top, shapes)) - SLAB >= HIGH_PROFILE else 'low'
    label = shed.replace('_', ' ') if plan == 'equipment_tile' else ' · '.join(name.replace('_', ' ') for name in (shed, plan, accessory) if name)
    return {'shapes': [slab, *shapes], 'catalogue': {
        'composition': '_'.join(filter(None, (shed, plan, accessory))),
        'type': f'{plan}:{kind}',
        'layout': plan.replace('_', ' '),
        'ancillary': kind,
        'silhouette': silhouette,
        'label': label,
    }}


# General fixed-geometry composition.  No component geometry is generated or scaled.
# Components are translated and quarter-turned; primitive occupancy, not vocabulary
# roles, determines whether a combination is valid.
from functools import lru_cache
from itertools import combinations

SITE_MIN, SITE_MAX = .035, .965
# Ordered positions, ensuring adjacent and diagonal layouts are both considered.
SITES = ((.20,.20),(.80,.80),(.80,.20),(.20,.80),
         (.50,.20),(.80,.50),(.50,.80),(.20,.50))
EPSILON = 1e-6


def rotate_xy(x, y, turns):
    for _ in range(turns % 4):
        x, y = -y, x
    return x, y


def rigid_place(part, prefix, centre, turns=0):
    """Rigid transform of every supported authored primitive (never rescale)."""
    ox, oy = centre
    def pt(p):
        x, y = rotate_xy(p[0], p[1], turns)
        return [round(x + ox, 8), round(y + oy, 8), round(p[2] + SLAB, 8)]
    result = deepcopy(part['shapes'])
    for shape in result:
        shape['id'] = prefix + shape['id']
        if 'bounds' in shape:
            b = shape['bounds']
            xy = [rotate_xy(x,y,turns) for x in (b[0],b[3]) for y in (b[1],b[4])]
            shape['bounds'] = [round(min(x for x,y in xy)+ox,8),
                               round(min(y for x,y in xy)+oy,8),round(b[2]+SLAB,8),
                               round(max(x for x,y in xy)+ox,8),
                               round(max(y for x,y in xy)+oy,8),round(b[5]+SLAB,8)]
        elif shape['type'] == 'rings':
            shape['rings'] = [[pt(vertex) for vertex in ring] for ring in shape['rings']]
        elif shape['type'] == 'revolution':
            shape['center'] = pt([*shape['center'], 0])[:2]
            shape['profile'] = [[round(z+SLAB,8), radius] for z,radius in shape['profile']]
        elif shape['type'] == 'beam':
            shape['start'] = pt(shape['start'])
            shape['end'] = pt(shape['end'])
        else:
            raise ValueError(f"Unsupported rigid placement for {shape['id']}")
    return result


def occupied_boxes(shape):
    """Primitive-level conservative volumes. Segment beams are subdivided to
    avoid treating a long diagonal beam as one filled rectangular prism."""
    typ = shape['type']
    if 'bounds' in shape:
        return [tuple(shape['bounds'])]
    if typ == 'revolution':
        x,y = shape['center']
        r = max(radius for z,radius in shape['profile'])
        return [(x-r,y-r,min(z for z,radius in shape['profile']),
                 x+r,y+r,max(z for z,radius in shape['profile']))]
    if typ == 'rings':
        # Each swept interval gets its own volume, not the entire swept path.
        result = []
        for a,b in zip(shape['rings'],shape['rings'][1:]):
            vs = a+b
            result.append(tuple(min(p[k] for p in vs) for k in range(3))+
                          tuple(max(p[k] for p in vs) for k in range(3)))
        return result or [tuple(min(p[k] for ring in shape['rings'] for p in ring) for k in range(3))+
                          tuple(max(p[k] for ring in shape['rings'] for p in ring) for k in range(3))]
    if typ == 'beam':
        a,b = shape['start'],shape['end']
        radius = shape['thickness']/2
        length = max(abs(a[k]-b[k]) for k in range(3))
        n = max(1, int(length/.04)+1)
        boxes = []
        for i in range(n):
            p = [a[k]+(b[k]-a[k])*i/n for k in range(3)]
            q = [a[k]+(b[k]-a[k])*(i+1)/n for k in range(3)]
            boxes.append(tuple(min(p[k],q[k])-radius for k in range(3))+
                         tuple(max(p[k],q[k])+radius for k in range(3)))
        return boxes
    raise ValueError(f'Unsupported collision primitive: {typ}')


def volumes_overlap(a,b):
    return all(a[k] < b[k+3]-EPSILON and b[k] < a[k+3]-EPSILON for k in range(3))


def transformed_footprint(part, centre, turns):
    a,b,c,d = part['footprint']
    xy = [rotate_xy(x,y,turns) for x in (a,c) for y in (b,d)]
    return (min(x for x,y in xy)+centre[0],min(y for x,y in xy)+centre[1],
            max(x for x,y in xy)+centre[0],max(y for x,y in xy)+centre[1])


def valid_addition(shapes, occupied, footprint_bounds):
    if (footprint_bounds[0] < SITE_MIN-EPSILON or
        footprint_bounds[1] < SITE_MIN-EPSILON or
        footprint_bounds[2] > SITE_MAX+EPSILON or
        footprint_bounds[3] > SITE_MAX+EPSILON):
        return False
    volumes = [box for shape in shapes for box in occupied_boxes(shape)]
    if any(box[0] < -EPSILON or box[1] < -EPSILON or
           box[3] > 1+EPSILON or box[4] > 1+EPSILON for box in volumes):
        return False
    if any(volumes_overlap(box, old) for box in volumes for old in occupied):
        return False
    return True


def arbitrary_scene(entries, parts):
    """entries: (component ID, x, y, quarter-turns) tuples."""
    slab = dict(id='slab',type='box',material='concrete',
                bounds=[.035,.045,0,.965,.955,SLAB])
    shapes, occupied = [], []
    for index,(name,x,y,turns) in enumerate(entries):
        part = parts[name]
        piece = rigid_place(part, f'part_{index}_', (x,y), turns)
        area = transformed_footprint(part,(x,y),turns)
        if not valid_addition(piece, occupied, area):
            raise ValueError(f'Incompatible geometry for {name} at {(x,y,turns)}')
        shapes.extend(piece)
        occupied.extend(box for shape in piece for box in occupied_boxes(shape))
    high = max(map(top,shapes))-SLAB >= HIGH_PROFILE
    identifier = '__'.join(f'{name}_{round(x*100):02d}_{round(y*100):02d}_r{turns}'
                           for name,x,y,turns in entries)
    return {'shapes':[slab,*shapes], 'catalogue':{
        'composition':identifier,
        'type':f'{len(entries)}-component',
        'layout':f'{len(entries)} independent components',
        'ancillary':'mixed' if len(entries)>1 else 'none',
        'silhouette':'high' if high else 'low',
        'label':' + '.join(name.replace('_',' ') for name,*_ in entries),
        'components':[name for name,*_ in entries],
    }}


def all_names(tags):
    groups = vocabularies()
    if not tags or set(tags)-groups.keys():
        raise ValueError('Select a supported assembly vocabulary')
    return sorted({name for tag in tags for role,items in groups[tag].items()
                   for name in items})


@lru_cache(maxsize=16)
def _general_candidates(names, silhouette):
    if silhouette not in ('low','high'):
        raise ValueError('Select a low or high silhouette')
    parts = {name:load_part(name) for name in names}
    pool = {}
    def add(entries):
        try:
            scene=arbitrary_scene(entries,parts)
        except ValueError:
            return False
        if scene['catalogue']['silhouette'] == silhouette:
            pool[scene['catalogue']['composition']]=scene
        return True

    # Every component is eligible alone, irrespective of original role.
    for name in names:
        add(((name,.5,.5,0),))

    # Exhaustive unordered component pairs. For each pair select the first
    # feasible site from each of two contrasting placement orders. No role
    # restrictions, and the same names work across vocabulary boundaries.
    for a,b in combinations(names,2):
        for first,second in ((a,b),(b,a)):
            base=(first,.5,.5,0)
            for x,y in SITES:
                turns = 0 if x==y else 1
                entries=(base,(second,x,y,turns))
                if add(entries):
                    break

    # Repeated instances of the same component, where their geometry fits.
    for name in names:
        base=(name,.28,.5,0)
        for x,y in ((.72,.5),(.5,.75),(.75,.75)):
            if add((base,(name,x,y,0))):
                break

    # Three-component arrangements formed from any compatible pair and a
    # third independently selected component, without role compatibility.
    # Bounded to keep the candidate catalogue reasonably fast to enumerate.
    if len(names)>2:
        for i,a in enumerate(names):
            b=names[(i+1)%len(names)]
            c=names[(i+2)%len(names)]
            for x,y in SITES:
                first=((a,.36,.36,0),(b,x,y,0))
                try:
                    arbitrary_scene(first,parts)
                except ValueError:
                    continue
                for xx,yy in reversed(SITES):
                    if add((*first,(c,xx,yy,0))):
                        break
                break
    if not pool:
        raise ValueError('No compositions match this silhouette and vocabulary')
    return pool


def candidates(tags,silhouette):
    return _general_candidates(tuple(all_names(tags)),silhouette)


def draw(pool, current, rng, exclude=None):
    counts = Counter(current)
    by_type = {}
    for key, scene in pool.items():
        by_type.setdefault(scene['catalogue']['type'], []).append(key)
    type_counts = {kind: sum(counts[key] for key in keys) for kind, keys in by_type.items()}
    cap = TYPE_CAP if len(by_type) > 1 else BATCH_SIZE
    allowed = [
        [key for key in keys if key != exclude]
        for kind, keys in by_type.items() if type_counts[kind] < cap
    ]
    allowed = [keys for keys in allowed if keys]
    if not allowed:
        raise ValueError('No different composition is available under the type cap')
    keys = rng.choice(allowed)
    # Keep repeats within a type useful by trying its lesser-used designs first.
    fewest = min(counts[key] for key in keys)
    return rng.choice([key for key in keys if counts[key] == fewest])


def draft(tags, seed, silhouette):
    pool = candidates(tags, silhouette)
    rng = random.Random(seed)
    current = []
    for _ in range(BATCH_SIZE):
        current.append(draw(pool, current, rng))
    return {f'{row:02d}': pool[key] for row, key in enumerate(current, start=1)}


def redraft(tags, seed, silhouette, current, row, revision):
    pool = candidates(tags, silhouette)
    if len(current) != BATCH_SIZE or set(current) - pool.keys():
        raise ValueError(f'Provide the {BATCH_SIZE} current composition IDs in row order')
    if not 1 <= row <= BATCH_SIZE or revision < 1:
        raise ValueError('Provide a valid row and positive revision')
    index = row - 1
    rng = random.Random(f'{seed}:{row}:{revision}')
    key = draw(pool, current[:index] + current[index+1:], rng, exclude=current[index])
    return {f'{row:02d}': pool[key]}


def render_draft(scenes, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f'Use a fresh output directory: {output}')
    with TemporaryDirectory(dir=output.parent) as work:
        sources = {}
        for row, scene in scenes.items():
            path = Path(work) / f'{row}.json'
            path.write_text(json.dumps(scene, indent=2) + '\n', encoding='utf-8')
            sources[row] = path
        rendered = Path(work) / 'rendered'
        render_scene_files(sources, rendered)
        for row, path in sources.items():
            (rendered / row / 'scene.json').write_bytes(path.read_bytes())
        rendered.rename(output)
    return {'entries': [{'id': row, **scene['catalogue']} for row, scene in scenes.items()]}
