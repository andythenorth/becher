"""Choose seeded tile compositions from fixed assemblies and compatible placements."""

from collections import Counter
from functools import lru_cache
from itertools import combinations
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
    result = []
    for source in part['shapes']:
        # Only coordinates and IDs change. Copy the shape and construct new
        # coordinate arrays below, rather than recursively copying immutable
        # material metadata and every old coordinate first.
        shape = source.copy()
        if 'crease_rings' in shape:
            shape['crease_rings'] = list(shape['crease_rings'])
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
        result.append(shape)
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
        rings = shape['rings']
        following = rings[1:]+rings[:1] if shape.get('closed') else rings[1:]
        for a,b in zip(rings,following):
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


def valid_addition(shapes, occupied, footprint_bounds, *, whole_tile=False):
    lower, upper = (0, 1) if whole_tile else (SITE_MIN, SITE_MAX)
    if (footprint_bounds[0] < lower-EPSILON or
        footprint_bounds[1] < lower-EPSILON or
        footprint_bounds[2] > upper+EPSILON or
        footprint_bounds[3] > upper+EPSILON):
        return False
    volumes = [box for shape in shapes for box in occupied_boxes(shape)]
    if any(box[0] < -EPSILON or box[1] < -EPSILON or
           box[3] > 1+EPSILON or box[4] > 1+EPSILON for box in volumes):
        return False
    if occupied:
        # A component's full enclosing box is a conservative collision test.
        # Most edge-packed parts have a gap, so avoid the costly primitive-
        # by-primitive comparisons unless the enclosing boxes overlap.
        left = min(box[0] for box in volumes)
        right = max(box[3] for box in volumes)
        front = min(box[1] for box in volumes)
        back = max(box[4] for box in volumes)
        if not (right <= min(box[0] for box in occupied) + EPSILON or
                max(box[3] for box in occupied) <= left + EPSILON or
                back <= min(box[1] for box in occupied) + EPSILON or
                max(box[4] for box in occupied) <= front + EPSILON):
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
        whole_tile = len(entries) == 1 and part.get('placement') == 'tile'
        if not valid_addition(piece, occupied, area, whole_tile=whole_tile):
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


def _edge_sites(parts, names, turns, axis):
    """Yield deterministic footprint-derived layouts, not a fixed site grid.

    Each new item touches one existing footprint across GAP, with its
    opposite-axis edges/centre/quarter-overlap aligned. This explores lateral,
    corner and staggered arrangements and uses the actual rotated extents.
    The complete assembly is translated into the tile after each placement;
    absolute component origins and names do not influence candidate sites.
    """
    if not 1 <= len(names) <= 3:
        raise ValueError('Place one, two or three components')
    boxes = [transformed_footprint(parts[n], (0, 0), t)
             for n, t in zip(names, turns)]
    extent = SITE_MAX - SITE_MIN
    if any(max(b[2]-b[0], b[3]-b[1]) > extent + EPSILON for b in boxes):
        return

    def translated(box, x, y):
        return (box[0]+x, box[1]+y, box[2]+x, box[3]+y)

    def layout(placed, positions):
        x0 = min(b[0] for b in placed)
        y0 = min(b[1] for b in placed)
        x1 = max(b[2] for b in placed)
        y1 = max(b[3] for b in placed)
        if x1-x0 > extent+EPSILON or y1-y0 > extent+EPSILON:
            return None
        dx, dy = .5-(x0+x1)/2, .5-(y0+y1)/2
        return tuple((round(x+dx, 8), round(y+dy, 8)) for x,y in positions)

    def attachments(box, reference):
        # Four faces, prioritising the requested original packing axis.
        sides = (('right', 'left', 'bottom', 'top') if axis == 0
                 else ('bottom', 'top', 'right', 'left'))
        for side in sides:
            if side in ('right', 'left'):
                x = (reference[2]+GAP-box[0] if side == 'right'
                     else reference[0]-GAP-box[2])
                # Align upper/lower edges, centre, and intermediate offsets.
                for fraction in (.5, 0., 1., .25, .75):
                    y = reference[1]+fraction*(reference[3]-reference[1]) - (
                        box[1]+fraction*(box[3]-box[1]))
                    yield x,y
            else:
                y = (reference[3]+GAP-box[1] if side == 'bottom'
                     else reference[1]-GAP-box[3])
                for fraction in (.5, 0., 1., .25, .75):
                    x = reference[0]+fraction*(reference[2]-reference[0]) - (
                        box[0]+fraction*(box[2]-box[0]))
                    yield x,y

    def explore(index, placed, positions):
        if index == len(boxes):
            sites = layout(placed, positions)
            if sites is not None:
                yield sites
            return
        seen = set()
        for reference in placed:
            for x,y in attachments(boxes[index], reference):
                key = (round(x,8),round(y,8))
                if key in seen:
                    continue
                seen.add(key)
                new = translated(boxes[index], x, y)
                candidate = placed + [new]
                if (max(b[2] for b in candidate)-min(b[0] for b in candidate) > extent+EPSILON
                    or max(b[3] for b in candidate)-min(b[1] for b in candidate) > extent+EPSILON):
                    continue
                # Different-level structures are ultimately checked in 3-D;
                # here the edge-attachment search intentionally avoids XY overlap.
                yield from explore(index+1, candidate, positions+[(x,y)])

    initial = boxes[0]
    if len(boxes) == 1:
        yield ((round(.5-(initial[0]+initial[2])/2,8),
                round(.5-(initial[1]+initial[3])/2,8)),)
    else:
        yield from explore(1,[initial],[(0.,0.)])


def packed_sites(parts, names, turns, axis):
    """Return the first footprint-derived placement (legacy public API)."""
    return next(_edge_sites(parts,names,turns,axis),None)


def packed_scene(parts, names, turns, axis):
    """Find a physically valid edge/corner/staggered placement."""
    for attempt, sites in enumerate(_edge_sites(parts,names,turns,axis)):
        if attempt >= (36 if len(names) == 3 else 12):
            break
        try:
            return arbitrary_scene(tuple((n,x,y,t) for n,(x,y),t in
                                         zip(names,sites,turns)),parts)
        except ValueError:
            continue
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
        if part.get('placement') == 'tile':
            if (max(map(top,part['shapes'])) >= HIGH_PROFILE) != (silhouette == 'high'):
                continue
            at = (.5,.5)
        else:
            at = (.5-(centre[0]+centre[2])/2,.5-(centre[1]+centre[3])/2)
        try:
            add(arbitrary_scene(((name,*at,0),),parts))
        except ValueError:
            pass

    # Every unordered component pair is attempted with both packing axes and
    # all four orientations of each component. No category restrictions.
    # Stop after the first valid placement *matching the requested silhouette*.
    def fits_packing_site(name):
        left,front,right,back = parts[name]['footprint']
        return max(right-left,back-front) <= SITE_MAX-SITE_MIN+EPSILON

    packable = [name for name in names
                if parts[name].get('placement') != 'tile' or fits_packing_site(name)]
    heights = {name: max(map(top,parts[name]['shapes'])) for name in packable}
    # Edge attachments never overlap in XY. Every successful pair must fit
    # its two shorter footprint dimensions side-by-side, plus clearance.
    # Quarter-turn rotations are already explored in the normal search.
    short_span = {
        name: min(parts[name]['footprint'][2] - parts[name]['footprint'][0],
                  parts[name]['footprint'][3] - parts[name]['footprint'][1])
        for name in packable
    }
    pair_limit = SITE_MAX - SITE_MIN - GAP + EPSILON

    def matches_profile(*names):
        height = max(heights[name] for name in names)
        return abs(height-HIGH_PROFILE) <= EPSILON or (height >= HIGH_PROFILE) == (silhouette == 'high')
    feasible_pairs = []
    for a,b in combinations(packable,2):
        # Preserve the current exclusion of different tank designs.
        if parts[a].get('role') == parts[b].get('role') == 'tank':
            continue
        if short_span[a] + short_span[b] > pair_limit:
            continue
        if not matches_profile(a,b):
            continue
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
    for name in packable:
        if not matches_profile(name) or 2 * short_span[name] > pair_limit:
            continue
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

    # Explore several differently sized partners for each component rather than
    # always taking its first feasible pair. This keeps triple discovery linear
    # in catalogue size while reaching compact/large mixed arrangements.
    if len(packable) > 2 and feasible_pairs:
        area = {
            name: (parts[name]['footprint'][2] - parts[name]['footprint'][0]) *
                  (parts[name]['footprint'][3] - parts[name]['footprint'][1])
            for name in packable
        }

        def samples(items, count):
            if len(items) <= count:
                return items
            return [items[i * (len(items) - 1) // (count - 1)]
                    for i in range(count)]

        for a in packable:
            partners = sorted({y if x == a else x for x, y in feasible_pairs
                               if a in (x, y)}, key=lambda name: (area[name], name))
            for b in (samples(partners, 3)[1:] if len(partners) >= 3
                      else partners):
                others = sorted((n for n in packable if n not in (a, b)),
                                key=lambda name: (area[name], name))
                for c in others[:1]:
                    if sum(parts[n].get('role') == 'tank' for n in (a, b, c)) > 1:
                        continue
                    if not matches_profile(a, b, c):
                        continue
                    # The footprint search never overlaps components in XY.
                    if area[a] + area[b] + area[c] > (SITE_MAX - SITE_MIN) ** 2:
                        continue
                    for axis in (0, 1):
                        scene = packed_scene(parts, (a, b, c), (0, 0, 0), axis)
                        if scene is not None and scene['catalogue']['silhouette'] == silhouette:
                            add(scene)
                            break
                    if scene is not None and scene['catalogue']['silhouette'] == silhouette:
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
