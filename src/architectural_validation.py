"""Fast deterministic semantic/structural checks before invoking the raycaster."""
from collections import Counter
import math


def _area_touch(a,b,eps=.012):
    x0,y0,z0,x1,y1,z1=a
    u0,v0,w0,u1,v1,w1=b
    xoverlap=min(x1,u1)-max(x0,u0)
    yoverlap=min(y1,v1)-max(y0,v0)
    # True contact may be a shared wall or intersecting plan, but not a
    # diagonal corner or a building linked only by the foundation slab.
    return ((xoverlap>eps and yoverlap >=-eps) or
            (yoverlap>eps and xoverlap >=-eps)) and min(z1,w1)-max(z0,w0)>eps


def validate(model):
    issues=[]
    components=model.components
    names=[c.id for c in components]
    if len(names)!=len(set(names)):issues.append('duplicate_component_ids')
    byid={c.id:c for c in components}
    bodies=[c for c in components if c.role=='fabric']
    roots=[c for c in bodies if c.parent is None]
    if len(roots)!=1:issues.append('must_have_exactly_one_primary_hall')
    if not 1<=len(bodies)<=7:issues.append('unsupported_room_count')
    for c in components:
        b=c.bounds
        if any(not math.isfinite(v) for v in b):issues.append(f'{c.id}:nonfinite');continue
        x0,y0,z0,x1,y1,z1=b
        if x0>=x1 or y0>=y1 or z0>z1 or (z0==z1 and c.role!='roof'):
            issues.append(f'{c.id}:degenerate')
        if x0<0 or y0<0 or x1>1 or y1>1 or z0<0 or z1>1.9:
            issues.append(f'{c.id}:out_of_bounds')
        if c.parent and c.parent not in byid:issues.append(f'{c.id}:orphan')
        if c.role=='roof':
            host=byid.get(c.parent)
            if host is None or host.role not in ('fabric','monitor'):
                issues.append(f'{c.id}:roof_without_host')
            elif any(abs(u-v)>1e-5 for u,v in zip((x0,y0,x1,y1),
                  (host.bounds[0],host.bounds[1],host.bounds[3],host.bounds[4]))):
                issues.append(f'{c.id}:roof_footprint_mismatch')
            if c.roof not in ('gable_x','gable_y','shed','flat','sawtooth','monitor'):
                issues.append(f'{c.id}:unknown_roof')
            if c.roof=='sawtooth' and c.count not in (2,3,4,5):
                issues.append(f'{c.id}:invalid_sawtooth_count')
        if c.role in ('stack','tank'):
            host=byid.get(c.parent)
            if host is None or not (host.bounds[0]-.01<=x0 and
                    x1<=host.bounds[3]+.01 and host.bounds[1]-.01<=y0 and
                    y1<=host.bounds[4]+.01):
                issues.append(f'{c.id}:fixture_outside_parent')
    # Attachment semantics are stricter than merely touching some room.
    # A furnace cooling bay, for example, must be connected to its furnace,
    # not accidentally joined through an unrelated distant outbuilding.
    for c in bodies:
        if c.parent:
            parent=byid.get(c.parent)
            if parent is None or parent.role!='fabric' or not _area_touch(c.bounds,parent.bounds):
                issues.append(f'{c.id}:invalid_parent_attachment')
    # Ensure every architectural room belongs to a single connected mass.
    if bodies:
        reached={bodies[0].id}
        changed=True
        while changed:
            old=len(reached)
            for a in bodies:
                if a.id in reached:continue
                if any(_area_touch(a.bounds,b.bounds) for b in bodies if b.id in reached):
                    reached.add(a.id)
            changed=len(reached)>old
        for c in bodies:
            if c.id not in reached:issues.append(f'{c.id}:detached_room')
    if not any(c.role=='roof' for c in components):issues.append('no_roof')
    return {'passes':not issues,'issues':issues,'body_count':len(bodies),
            'component_count':len(components),'roles':dict(Counter(c.role for c in components))}
