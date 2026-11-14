"""Declarative industry typologies and seeded, attached structural components.

Data is independent of rendering; all coordinate values are authorable in JSON.
Individual streams are identified by semantic paths so rerolling a roof does not
perturb room dimensions, and each architectural model is rotation-invariant.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import random

GRAMMAR_PATH = Path(__file__).resolve().parents[1] / 'data' / 'grammars' / 'industrial_v1.json'


from .facade_profiles import WINDOW_PROFILES, DOOR_PROFILES

ALLOWED_ROOFS = {'gable_x','gable_y','shed','flat','sawtooth','monitor'}
ALLOWED_FIXTURES = {'double_stack','tower_stack','roof_vent','ridge_monitor',
                    'tank_pair','pipe_bank','loading_canopy'}


def library(path=None):
    path = Path(path) if path is not None else GRAMMAR_PATH
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError(f'{path}: expected grammar schema_version 1')
    families = data.get('families', [])
    if not families or len({f.get('id') for f in families}) != len(families):
        raise ValueError(f'{path}: need unique family ids')
    for fam in families:
        room_names={'main'}
        for annex in fam.get('annexes',[]):
            if annex['id'] in room_names:raise ValueError('Duplicate room name')
            room_names.add(annex['id'])
        specs=[{'id':'main','rect':fam['main'],'roofs':fam['main_roofs'],
                **{key:fam[key] for key in ('windows','doors','edge_span_axis') if key in fam}}]+fam.get('annexes',[])
        for spec in specs:
            rect=spec['rect']
            if (len(rect)!=5 or not (0<=rect[0]<rect[2]<=1 and 0<=rect[1]<rect[3]<=1)
                    or not (.18 < rect[4] < 1.25)):
                raise ValueError(f'{fam["id"]} {spec["id"]}: invalid room dimensions')
            if spec.get('edge_span_axis') not in (None, 'x', 'y'):
                raise ValueError(f'{fam["id"]} {spec["id"]}: invalid edge span axis')
            if spec.get('windows', 'office') not in WINDOW_PROFILES:
                raise ValueError(f'{fam["id"]} {spec["id"]}: unknown window profile')
            if spec.get('doors', 'loading') not in DOOR_PROFILES:
                raise ValueError(f'{fam["id"]} {spec["id"]}: unknown door profile')
            if not spec['roofs'] or not set(spec['roofs']) <= ALLOWED_ROOFS:
                raise ValueError(f'{fam["id"]} {spec["id"]}: unknown roof family')
            parent=spec.get('attach_to','main')
            if spec['id']!='main' and parent not in room_names:
                raise ValueError(f'{fam["id"]} {spec["id"]}: missing attachment {parent}')
        if not set(fam.get('fixtures',[]))<=ALLOWED_FIXTURES:
            raise ValueError(f'{fam["id"]}: unknown industrial fixture')
        if fam.get('category', 'primary') not in ('primary', 'ancillary'):
            raise ValueError(f'{fam["id"]}: unknown grammar category')
        for item in fam.get('free_structures', []):
            if item.get('shape') not in ('box', 'cylinder') or item.get('material') not in ('metal','roof','concrete','frame','glass','chimney','pipe'):
                raise ValueError(f'{fam["id"]}: unsupported standalone equipment')
            b=item.get('bounds', [])
            if len(b)!=6 or not (0<=b[0]<b[3]<=1 and 0<=b[1]<b[4]<=1 and .0<=b[2]<b[5]<=1.9):
                raise ValueError(f'{fam["id"]}: equipment outside tile')
    return families


def stream(seed: int, design_index: int, path: str, rerolls=None):
    rerolls = rerolls or {}
    payload = f'{seed}|{design_index}|{path}|{rerolls.get(path, 0)}'.encode()
    return random.Random(int.from_bytes(hashlib.sha256(payload).digest()[:16], 'little'))


@dataclass(frozen=True)
class Component:
    id: str
    role: str
    shape: str
    bounds: tuple[float, float, float, float, float, float]
    parent: str | None = None
    roof: str | None = None
    rise: float = 0.0
    count: int = 0
    material: str = 'metal'

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Building:
    id: str
    family: str
    label: str
    seed: int
    index: int
    components: tuple[Component, ...]
    parameters: dict

    def to_dict(self):
        return {'id': self.id, 'family': self.family, 'label': self.label,
                'seed': self.seed, 'index': self.index,
                'components': [x.to_dict() for x in self.components],
                'parameters': self.parameters}


def _map_coord(v, horizontal_scale, mid=.5):
    return mid + (v-mid)*horizontal_scale


def generate(seed: int, index: int, *, families=None, rerolls=None, variation=None):
    """Generate a structural model; rotations are deliberately not sampled here."""
    families = families or library()
    # Spread a batch over all families before repeating any one family.
    family = families[index % len(families)]
    family_id = family['id']
    rng = stream(seed,index,'fabric',rerolls)
    sx,sy = rng.uniform(.95,1.04), rng.uniform(.94,1.05)
    scale_z = rng.uniform(.91,1.09)
    if variation:
        # Architectural bands remain within one tile. Preserve the exact
        # axis-spanning dimension by pinning after all affine transforms.
        bands = {'broad': (1.08, .89), 'square': (1.0, 1.0),
                 'long': (.88, 1.09)}
        vx, vy = bands[variation['aspect']]
        sx *= vx
        sy *= vy
        scale_z *= {'low': .76, 'medium': .88, 'raised': 1.0}[variation['height']]
    layout = stream(seed,index,'layout',rerolls).choice(('normal','mirror_x','mirror_y'))
    base=.050
    components=[]
    rooms=[]
    roof_params={}
    omissions=[]
    facade_profiles={}

    # The same ground-plane transform is applied to all attached rooms; shared
    # interfaces remain shared after proportion mutations.
    def transformed(rect, edge_span_axis=None, *, annex=False):
        x0,y0,x1,y1,h = rect
        if variation and annex:
            mode=variation['arrangement']
            if mode in ('broad_annex', 'short_annex'):
                amount=1.14 if mode=='broad_annex' else .82
                cx,cy=(x0+x1)/2,(y0+y1)/2
                x0,x1=cx-(x1-x0)*amount/2,cx+(x1-x0)*amount/2
                y0,y1=cy-(y1-y0)*amount/2,cy+(y1-y0)*amount/2
            elif mode=='offset_annex':
                # Mild coherent offset; overlap with the main hall is still
                # checked by structural validation.
                x0,x1=x0+.035,x1+.035
        xa,xb=_map_coord(x0,sx),_map_coord(x1,sx)
        ya,yb=_map_coord(y0,sy),_map_coord(y1,sy)
        if layout=='mirror_x':xa,xb=1-xb,1-xa
        elif layout=='mirror_y':ya,yb=1-yb,1-ya
        xa,xb=max(0.0, xa),min(1.0, xb)
        ya,yb=max(0.0, ya),min(1.0, yb)
        # Explicit modular edge spans are pinned after scaling and mirroring.
        # Other dimensions retain normal seeded variation.
        if edge_span_axis=='x': xa,xb=0.0,1.0
        elif edge_span_axis=='y': ya,yb=0.0,1.0
        return (round(xa,6),round(ya,6),round(xb,6),round(yb,6),
                round(h*scale_z,6))

    specs=[{'id':'main','rect':family['main'],'roofs':family['main_roofs'],
            **{key:family[key] for key in ('windows','doors','edge_span_axis') if key in family}}]+family.get('annexes',[])
    for spec in specs:
        name=spec['id']; choose=stream(seed,index,f'assembly:{name}',rerolls)
        if spec.get('optional'):
            if variation and variation['annex_mode']=='omit_optional':
                omissions.append(name);continue
            if not variation or variation['annex_mode']=='normal':
                if choose.random()<.30:
                    omissions.append(name);continue
        x0,y0,x1,y1,h=transformed(spec['rect'],spec.get('edge_span_axis'),annex=name!='main')
        # Heights mutate locally. Joints remain valid because heights rise from
        # the same foundation plane; contact is checked independently.
        height=h*choose.uniform(.95,1.07)
        ztop=round(base+height,6)
        if name=='main': parent=None
        else:parent=spec.get('attach_to','main')
        body=Component(name,'fabric','box',(x0,y0,base,x1,y1,ztop),parent)
        components.append(body)
        rooms.append(body)
        if 'windows' in spec or 'doors' in spec:
            facade_profiles[name]={'windows':spec.get('windows','blank'),
                                   'doors':spec.get('doors','none')}
        roof_rng=stream(seed,index,f'roof:{name}',rerolls)
        roof=roof_rng.choice(spec['roofs'])
        if variation and len(spec['roofs'])>1:
            roof=spec['roofs'][(variation['roof_variant'] + (0 if name=='main' else 1)) % len(spec['roofs'])]
        rise=round(roof_rng.uniform(.105,.235)*min(1.0,(y1-y0)/.65),6)
        if roof in ('flat',):rise=.025
        if roof=='sawtooth':
            # At native 1x, a pitch steeper than the ~32-degree viewing
            # elevation hides nearly every roof sheet from the opposite
            # pair of rotations. Constrain per-bay pitch to 0.42 (23 deg),
            # retaining meaningful clerestories in all four views.
            count=roof_rng.randint(2,4)
            bay_depth=(y1-y0)/count
            rise=round(min(roof_rng.uniform(.11,.17), bay_depth*.42),6)
        else:
            count=1
        if roof=='monitor':rise=round(roof_rng.uniform(.09,.14),6)
        # Native-scale correction for the loading warehouse's shallow main gable.
        # The camera projects world Z at 36 pixels/unit: 1/36 raises the ridge
        # by one actual output pixel, not one antialiased/zoomed preview pixel.
        # This is a single 3-D geometry adjustment shared by all rotations;
        # other building families, annexes, and roof systems are untouched.
        if (family_id == 'loading_warehouse' and name == 'main'
                and roof in ('gable_x', 'gable_y') and rise < .16):
            rise = round(rise + 1.0/36.0, 6)
        components.append(Component(f'{name}:roof','roof','roof',body.bounds,
                                    name,roof=roof,rise=rise,count=count,material='roof'))
        roof_params[name]={'roof':roof,'rise':rise,'bays':count}
        if roof=='monitor':
            # A raised longitudinal cap and actual secondary volume, not merely
            # a coloured roof polygon.
            mx0=x0+(x1-x0)*.20;mx1=x1-(x1-x0)*.20
            my0=y0+(y1-y0)*.36;my1=y1-(y1-y0)*.36
            components.append(Component(f'{name}:monitor','monitor','box',
                                        (mx0,my0,ztop+.065,mx1,my1,ztop+.24),name))
            components.append(Component(f'{name}:monitor_roof','roof','roof',
                                        (mx0,my0,ztop+.24,mx1,my1,ztop+.24),
                                        f'{name}:monitor',roof='gable_x',rise=.063,material='roof'))
    # A single supporting slab grounds every assembly; it must not be used as
    # a shortcut for structural connectivity tests.
    components.insert(0,Component('base','foundation','box',(.043,.065,0,.957,.935,base),material='concrete'))

    # Structural fixtures are stable attached subassemblies. Fine surface
    # greeble remains outside Step 2 and belongs to a later pass.
    fixture_rng=stream(seed,index,'fixtures',rerolls)
    fixtures=[]
    fixture_types=family.get('fixtures',[])
    for kind in fixture_types:
        if kind=='double_stack':
            for number,rx in enumerate((.30,.66)):
                host=rooms[0] if number==0 else rooms[min(len(rooms)-1,1)]
                x0,y0,z0,x1,y1,zt=host.bounds
                cx=x0+(x1-x0)*rx;cy=y0+(y1-y0)*.28
                h=fixture_rng.uniform(.43,.68)
                components.append(Component(f'stack:{number}','stack','cylinder',
                                            (cx-.036,cy-.036,zt-.01,cx+.036,cy+.036,zt+h),host.id,
                                            material='chimney'))
                fixtures.append(f'stack:{number}')
        elif kind=='tower_stack':
            host=next((r for r in rooms if 'tower' in r.id or 'transformer' in r.id), rooms[0])
            x0,y0,z0,x1,y1,zt=host.bounds
            cx=(x0+x1)/2;cy=(y0+y1)/2
            components.append(Component('tower_stack','stack','cylinder',
                                        (cx-.05,cy-.05,zt-.01,cx+.05,cy+.05,zt+.55),host.id,
                                        material='chimney'))
            fixtures.append('tower_stack')
        elif kind=='roof_vent':
            host=rooms[0];x0,y0,z0,x1,y1,z=host.bounds
            cx=x0+(x1-x0)*.30;cy=(y0+y1)/2
            components.append(Component('ridge_vent','vent','box',
                                        (cx-.04,cy-.04,z+.04,cx+.04,cy+.04,z+.21),host.id))
            fixtures.append('ridge_vent')
        elif kind=='ridge_monitor':
            host=rooms[0];x0,y0,z0,x1,y1,z=host.bounds
            components.append(Component('ridge_monitor','vent','box',
                                        (x0+.2*(x1-x0),y0+.35*(y1-y0),z+.07,
                                         x1-.2*(x1-x0),y1-.35*(y1-y0),z+.21),host.id))
            fixtures.append('ridge_monitor')
        elif kind=='tank_pair':
            host=rooms[-1];x0,y0,z0,x1,y1,z=host.bounds
            for j,u in enumerate((.30,.70)):
                cx=x0+(x1-x0)*u;cy=y0+(y1-y0)*.32;r=min(.055,(x1-x0)*.14)
                components.append(Component(f'tank:{j}','tank','cylinder',
                                            (cx-r,cy-r,z-.03,cx+r,cy+r,z+.19),host.id,
                                            material='pipe'))
                fixtures.append(f'tank:{j}')
        elif kind=='pipe_bank':
            host=rooms[-1];x0,y0,z0,x1,y1,z=host.bounds
            for j in range(3):
                cy=y0+(y1-y0)*(.36+j*.14)
                components.append(Component(f'pipe:{j}','pipe','box',
                                            (x0-.025,cy,z*.55,x1-.02,cy+.014,z*.55+.025),host.id,
                                            material='pipe'))
                fixtures.append(f'pipe:{j}')
        elif kind=='loading_canopy':
            host=rooms[-1];x0,y0,z0,x1,y1,z=host.bounds
            components.append(Component('canopy','canopy','box',
                                        (x1-.02,y0+.14*(y1-y0),base+min(.42,(z-base)*.58),
                                         min(.97,x1+.095),y1-.14*(y1-y0),base+min(.44,(z-base)*.61)),
                                        host.id,material='roof'))
            fixtures.append('canopy')

    # Freestanding ancillary machinery uses existing raycast boxes/cylinders.
    # It is not a facade texture or a new rendering primitive.
    for item in family.get('free_structures', []):
        a,b,z,c,d,top=item['bounds']
        # Small deterministic group-scale changes preserve the equipment yard.
        if variation:
            centre_x, centre_y=(a+c)*.5,(b+d)*.5
            factor={'broad':1.04,'square':1.0,'long':.96}[variation['aspect']]
            a,c=centre_x-(c-a)*factor/2,centre_x+(c-a)*factor/2
            b,d=centre_y-(d-b)*factor/2,centre_y+(d-b)*factor/2
        components.append(Component('standalone:'+item['id'],'vessel','cylinder' if item['shape']=='cylinder' else 'box',
                        tuple(round(v,6) for v in (a,b,z,c,d,top)),None,material=item['material']))
    param={'layout':layout,'global_scale':[round(sx,4),round(sy,4),round(scale_z,4)],
           'omitted_optional':omissions,'roof_config':roof_params,'fixtures':fixtures,
           'rerolls':dict(rerolls or {}),'schema_version':1}
    if variation or 'category' in family:
        param['grammar_category']=family.get('category','primary')
    if variation:
        param['variation']=dict(variation)
    if facade_profiles:
        param['facade_profiles']=facade_profiles
    fingerprint={'seed':seed,'index':index,'family':family_id,
                 'components':[c.to_dict() for c in components]}
    if variation:
        fingerprint['variation']=variation
    digest=hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()[:16]
    return Building(digest,family_id,family['label'],seed,index,tuple(components),param)
