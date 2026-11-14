"""Deterministic, independently rerollable 3-D feature passes.

A feature pass adds real raycastable solids to a frozen structural Building.
No textures or 2-D projected polygon painting occurs in these passes.
"""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json

from .architectures import Building, Component, stream

STAGES = ('windows', 'doors', 'equipment', 'greeble')
PREFIX = 'feat/'


def is_feature(c: Component, stage: str | None = None) -> bool:
    return c.id.startswith(PREFIX if stage is None else f'{PREFIX}{stage}/')


def fabric_only(model: Building) -> Building:
    return replace(model, id=model.parameters.get('base_building_id',model.id),
                   components=tuple(c for c in model.components if not is_feature(c)),
                   parameters={k:v for k,v in model.parameters.items()
                               if k not in ('feature_pipeline','feature_counters','feature_schema')})


def _component(stage, host, name, bounds, material='metal'):
    return Component(f'{PREFIX}{stage}/{host.id}/{name}', stage, 'box',
                     tuple(round(float(v), 6) for v in bounds), host.id, material=material)


def stage_components(base: Building, stage: str, counter: int = 0) -> tuple[Component, ...]:
    """Create a stage deterministically without touching other stages or seed streams."""
    if stage not in STAGES:
        raise ValueError(f'Unknown feature stage {stage!r}')
    hosts = [c for c in base.components if c.role == 'fabric']
    out=[]
    for host in hosts:
        x0,y0,z0,x1,y1,z1=host.bounds
        w,d,h=x1-x0,y1-y0,z1-z0
        rng=stream(base.seed,base.index,f'features:{stage}:{host.id}',
                   {f'features:{stage}:{host.id}':int(counter)})
        def add(name,bounds,material='frame'):
            out.append(_component(stage,host,name,bounds,material))
        facade_spec=base.parameters.get('facade_profiles',{}).get(host.id)
        if facade_spec is not None and stage in ('windows','doors'):
            from .facade_profiles import panels, door_reservations
            reserved=(door_reservations(host,facade_spec['doors'],
                        int(base.parameters.get('feature_counters',{}).get('doors',0)))
                      if stage=='windows' else ())
            for side,name,bounds,material in panels(
                    host,stage,facade_spec[stage],counter,reserved=reserved):
                add(name,bounds,material)
            continue
        if stage=='windows':
            # Windows are exterior solid glazing panels; their attachment is
            # geometrically meaningful and interior walls are self-occluded.
            columns=max(2,min(7,round(w / (.115 if counter==0 else rng.uniform(.095,.16)))))
            end_columns=max(2,min(5,round(d / (.16 if counter==0 else rng.uniform(.12,.20)))))
            rows=(2 if h>.83 else 1) if counter==0 else (2 if h>.75 and rng.random()<.80 else 1)
            for side in ('front','back','left','right'):
                count=columns if side in ('front','back') else end_columns
                for row in range(rows):
                    zl=z0+h*((.29+row*.35) if counter==0 else (.29+row*.34))
                    zh=min(z1-.07,zl+min(.105,h*.16))
                    if zh-zl<.034:continue
                    for i in range(count):
                        u=(i+.5)/count
                        # Reserve a door-sized envelope on the right gable.
                        if side=='right' and row==0 and .36<u<.74 and counter>0:continue
                        if counter>0 and rng.random()<.06:continue
                        if side in ('front','back'):
                            centre=x0+w*u; width=min(.047,w/count*.49)
                            yf=y0 if side=='front' else y1
                            sign=-1 if side=='front' else 1
                            a,b=sorted((yf+sign*.002,yf+sign*.016))
                            add(f'{side}/{row}/{i}',(centre-width/2,a,zl,centre+width/2,b,zh),'glass')
                            # Avoid detached 1x pale sill pixels. Windows
                            # remain as actual, depth-tested glazing panels.
                        else:
                            centre=y0+d*u; width=min(.048,d/count*.48)
                            xf=x0 if side=='left' else x1
                            sign=-1 if side=='left' else 1
                            a,b=sorted((xf+sign*.002,xf+sign*.016))
                            add(f'{side}/{row}/{i}',(a,centre-width/2,zl,b,centre+width/2,zh),'glass')
        elif stage=='doors':
            # Primary loading door on right wall. Optional annex side entrance.
            if host.id!='main' and rng.random()<.30:continue
            side='right' if host.id=='main' else rng.choice(('front','back'))
            top=min(z1-.08,z0+h*(.65 if counter==0 else rng.uniform(.54,.69)))
            if side=='right':
                width=min(.15,d*.35) if counter==0 else min(.148,d*.31);centre=y0+d*(.59 if counter==0 else rng.uniform(.48,.68))
                add('door',(x1+.003,centre-width/2,z0+.004,x1+.019,centre+width/2,top),'glass')
                # Do not emit slender full-height door jambs. At 1x these
                # project as isolated vertical stripes rather than legible trim.
                add('lintel',(x1+.019,centre-width/2-.012,top+.014,x1+.028,centre+width/2+.012,top+.029))
            else:
                width=min(.13,w*.33);centre=x0+w*.52
                fy=y0 if side=='front' else y1;sign=-1 if side=='front' else 1
                a,b=sorted((fy+sign*.003,fy+sign*.019))
                add('door',(centre-width/2,a,z0+.004,centre+width/2,b,top),'glass')
                a,b=sorted((fy+sign*.019,fy+sign*.028))
                add('lintel',(centre-width/2-.01,a,top+.012,centre+width/2+.01,b,top+.03))
        elif stage=='equipment':
            if host.id!='main' and rng.random()<.65:continue
            # These roof service boxes sit above the highest roof profile.
            roof=next((c for c in base.components if c.id==host.id+':roof'),None)
            rise=roof.rise if roof else .10
            n=rng.choice((1,1,2))
            for i in range(n):
                cx=x0+w*(.32+.33*i);cy=y0+d*rng.uniform(.35,.58)
                # Place vent foot on the *actual* analytic roof plane.
                kind=roof.roof if roof else 'flat'
                if kind in ('gable_x','monitor'):
                    roof_z=z1+rise*(1-abs(2*(cy-y0)/d-1))
                elif kind=='gable_y':
                    roof_z=z1+rise*(1-abs(2*(cx-x0)/w-1))
                elif kind=='shed':
                    roof_z=z1+rise*(1-(cy-y0)/d)
                elif kind=='sawtooth':
                    n=max(1,roof.count)
                    cell=((cy-y0)/d*n)%1
                    roof_z=z1+rise*(1-cell)
                else:roof_z=z1+.027
                bottom=roof_z-.018
                sz=rng.uniform(.06,.115)
                add(f'roof_vent/{i}',(cx-.021,cy-.020,bottom,cx+.021,cy+.020,bottom+sz),'metal')
        elif stage=='greeble':
            # Low-density true 3-D service plates, deliberately deferred to
            # this final structural pass; pixel texture is not generated here.
            for side in ('front','back'):
                yf=y0 if side=='front' else y1;sgn=-1 if side=='front' else 1
                # A modular seam has no outward-facing space for solid plates.
                if (yf < .03 and sgn < 0) or (yf > .97 and sgn > 0):
                    continue
                a,b=sorted((yf+sgn*.018,yf+sgn*.029))
                for i in range(rng.randint(1,3)):
                    cx=x0+w*rng.uniform(.16,.85)
                    z=z0+h*rng.uniform(.08,.19)
                    add(f'{side}/plate/{i}',(cx-.015,a,z,cx+.015,b,z+.019),'concrete')
    return tuple(out)


def _with_id(base, components, counters):
    params=dict(base.parameters)
    params.update(feature_pipeline=True,feature_schema=1,base_building_id=base.id,
                  feature_counters={s:int(counters.get(s,0)) for s in STAGES})
    digest=hashlib.sha256(json.dumps({'base':base.id,
        'components':[c.to_dict() for c in components]},sort_keys=True).encode()).hexdigest()[:16]
    return replace(base,id=digest,components=tuple(components),parameters=params)


def build_features(base: Building, counters=None, through=None):
    """Build up to a named pass; base geometry always remains unchanged."""
    base=fabric_only(base)
    counters=dict(counters or {})
    selected=STAGES if through is None else STAGES[:STAGES.index(through)+1]
    parts=list(base.components)
    for stage in selected:
        parts.extend(stage_components(base,stage,counters.get(stage,0)))
    return _with_id(base,parts,counters)


def reroll(model: Building, stage: str, counter=None, locked=()):
    """Replace only one feature pass in an immutable previously compiled scene."""
    if stage not in STAGES:raise ValueError(f'Unknown feature pass: {stage}')
    if stage in locked:raise ValueError(f'Pass is locked: {stage}')
    old=dict(model.parameters.get('feature_counters',{}))
    new=int(old.get(stage,0))+1 if counter is None else int(counter)
    if new<0:raise ValueError('Reroll counter must be nonnegative')
    old[stage]=new
    base=fabric_only(model)
    new_features=stage_components(base,stage,new)
    # Preserve every other pass exactly; no cascade of unintended mutations.
    parts=[c for c in model.components if not is_feature(c,stage)]
    parts.extend(new_features)
    geometry=[c for c in parts if not is_feature(c)]
    ordered=geometry+[c for s in STAGES for c in parts if is_feature(c,s)]
    return _with_id(base,ordered,old)


def validate_features(model: Building):
    """Validate each generated feature's wall/roof association and containment."""
    issues=[]
    by_id={c.id:c for c in model.components}
    for c in model.components:
        if not is_feature(c):continue
        if c.parent not in by_id or by_id[c.parent].role!='fabric':
            issues.append(f'{c.id}:missing_fabric_host');continue
        host=by_id[c.parent];x0,y0,z0,x1,y1,z1=host.bounds
        a,b,z,cx,dy,top=c.bounds
        if top<=z or cx<=a or dy<=b:issues.append(f'{c.id}:nonpositive_feature')
        if a<x0-.06 or cx>x1+.06 or b<y0-.06 or dy>y1+.06:
            issues.append(f'{c.id}:outside_host_footprint')
        stage=c.id.split('/')[1]
        if stage in ('windows','doors','greeble'):
            if z<z0-.001 or top>z1+.065:
                issues.append(f'{c.id}:outside_wall_height')
        if stage=='equipment' and z<z1-.020:
            issues.append(f'{c.id}:equipment_below_roof')
        if stage in ('windows','doors','greeble'):
            # Surface solids must actually touch a wall, not float inside a hall.
            touches=(abs(a-x0)<.042 or abs(cx-x1)<.042 or
                     abs(b-y0)<.042 or abs(dy-y1)<.042)
            if not touches:issues.append(f'{c.id}:not_on_external_wall')
    return {'passes':not issues,'issues':issues,
            'feature_counts':{stage:sum(is_feature(c,stage) for c in model.components)
                              for stage in STAGES}}
