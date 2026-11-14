"""Choose seeded tile compositions from fixed assemblies and compatible placements."""

from collections import Counter
from functools import lru_cache
from itertools import combinations
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

EPSILON = 1e-6
SITE_MIN, SITE_MAX = .035, .965
GAP = .018  # Clearance between the occupied footprints of packed components.


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
    shapes = rigid_place(load_part(component), '', (.5, .5), 0)
    render_geometry({'shapes': shapes}, output)
    return {'id': component, 'sprites': 4}


def load_part(name):
    return json.loads((DIRECTORY / f'{name}.json').read_text(encoding='utf-8'))


def top(shape):
    if 'bounds' in shape:
        return shape['bounds'][5]
    if shape['type'] == 'rings':
        return max(point[2] for ring in shape['rings'] for point in ring)
    if shape['type'] == 'revolution':
        return max(z for z, _ in shape['profile'])
    return max(shape['start'][2], shape['end'][2]) + shape['thickness'] / 2


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


def packed_sites(parts, names, turns, axis):
    """Pack intact component footprints, centred in the tile.

    The component origin is irrelevant. The returned positions are derived
    solely from the rotated authored footprints; no role or magic site list.
    """
    bounds = [transformed_footprint(parts[n], (0, 0), t)
              for n, t in zip(names, turns)]
    widths = [b[2]-b[0] for b in bounds]
    heights = [b[3]-b[1] for b in bounds]
    if axis == 0:
        if sum(widths)+GAP*(len(names)-1) > SITE_MAX-SITE_MIN+EPSILON or max(heights)>SITE_MAX-SITE_MIN+EPSILON:
            return None
        cursor = .5 - (sum(widths)+GAP*(len(names)-1))/2
        sites=[]
        for b,w in zip(bounds,widths):
            sites.append((round(cursor-b[0],8), round(.5-(b[1]+b[3])/2,8)))
            cursor += w+GAP
        return sites
    if sum(heights)+GAP*(len(names)-1) > SITE_MAX-SITE_MIN+EPSILON or max(widths)>SITE_MAX-SITE_MIN+EPSILON:
        return None
    cursor = .5 - (sum(heights)+GAP*(len(names)-1))/2
    sites=[]
    for b,h in zip(bounds,heights):
        sites.append((round(.5-(b[0]+b[2])/2,8), round(cursor-b[1],8)))
        cursor += h+GAP
    return sites


def packed_scene(parts, names, turns, axis):
    sites = packed_sites(parts, names, turns, axis)
    if sites is None:
        return None
    try:
        return arbitrary_scene(tuple((n,x,y,t) for n,(x,y),t in zip(names,sites,turns)),parts)
    except ValueError:
        return None


@lru_cache(maxsize=16)
def _general_candidates(names, silhouette):
    if silhouette not in ('low','high'):
        raise ValueError('Select a low or high silhouette')
    parts = {name:load_part(name) for name in names}
    pool = {}

    def add(scene):
        if scene is not None and scene['catalogue']['silhouette'] == silhouette:
            pool[scene['catalogue']['composition']] = scene

    # Standalone parts are a fallback, rather than the dominant batch output.
    for name in names:
        part = parts[name]
        centre = transformed_footprint(part,(0,0),0)
        at = (.5-(centre[0]+centre[2])/2,.5-(centre[1]+centre[3])/2)
        try:
            add(arbitrary_scene(((name,*at,0),),parts))
        except ValueError:
            pass

    # Every unordered component pair is attempted with both packing axes and
    # all four orientations of each component. No category restrictions.
    # Stop after the first valid placement *matching the requested silhouette*.
    feasible_pairs = []
    for a,b in combinations(names,2):
        selected = None
        for axis in (0,1):
            for ta in range(4):
                for tb in range(4):
                    scene = packed_scene(parts,(a,b),(ta,tb),axis)
                    if scene is not None and scene['catalogue']['silhouette'] == silhouette:
                        selected = scene
                        break
                if selected is not None:
                    break
            if selected is not None:
                break
        if selected is not None:
            add(selected)
            feasible_pairs.append((a,b))

    # Repeat identical parts where a second copy fits; no special casing.
    for name in names:
        for axis in (0,1):
            found = False
            for t in range(4):
                scene=packed_scene(parts,(name,name),(0,t),axis)
                if scene is not None and scene['catalogue']['silhouette'] == silhouette:
                    add(scene)
                    found=True
                    break
            if found:
                break

    # Triple diversity is bounded linearly with catalogue size, rather than
    # attempting a cubic number of tuples. All pairings remain eligible above.
    if len(names)>2 and feasible_pairs:
        for i,a in enumerate(names):
            partners = next(((x,y) for x,y in feasible_pairs if a in (x,y)), None)
            if partners is None:
                continue
            b = partners[1] if partners[0] == a else partners[0]
            others = [n for n in names if n not in (a,b)]
            if not others:
                continue
            c = others[i % len(others)]
            for axis in (0,1):
                scene=packed_scene(parts,(a,b,c),(0,0,0),axis)
                if scene is not None and scene['catalogue']['silhouette'] == silhouette:
                    add(scene)
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
