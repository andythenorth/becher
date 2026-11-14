"""Flush wall-surface windows and doors, evaluated at ray-hit world coordinates.

Only supported facade panels are replaced. Equipment, greeble, lintels for
non-facade systems, roof glazing and all other raycast solids are unchanged.
The decal has no thickness and inherits the winning wall hit's depth/normal.
"""
import numpy as np
from .geometry import MATERIAL_IDS, SURFACE_ROLES


def is_panel(component):
    return component.role in ('windows', 'doors') and (
        component.material == 'glass' or
        (component.role == 'doors' and component.id.rsplit('/', 1)[-1] == 'lintel')
    )


def apply(ctx, material, roles, component_by_pid, building):
    """Mutate category/primitive buffers of visible fabric hits only.

    ctx rays are already inverse-rotated into the model's original XY frame.
    We never paint screen-space polygons or modify wall depth/normals.
    """
    panels = [c for c in building.components if is_panel(c)]
    if not panels:
        return 0
    hosts = {c.id: c for c in building.components if c.role == 'fabric'}
    # Save the actual ray hit point. The ray kernel already owns a t-best buffer;
    # this postprocess does not require keeping a separate hit buffer.
    finite = np.isfinite(ctx['tbest'])
    times = np.where(finite, ctx['tbest'], 0)
    hit = ctx['origin'] + times[..., None] * ctx['ray']
    px, py, pz = (hit[..., k] for k in range(3))
    nx, ny, nz = (ctx['normal'][..., k] for k in range(3))
    fabric_pids = {cid: int(pid) for pid, cid in component_by_pid.items() if cid in hosts}
    next_id = max((int(k) for k in component_by_pid), default=0) + 1
    count = 0
    # The currently visible host wall must be the same assembly as the panel.
    # This preserves all geometry-based occlusion by attached volumes and fixtures.
    for panel in panels:
        host = hosts.get(panel.parent)
        host_pid = fabric_pids.get(panel.parent)
        if host is None or host_pid is None:
            continue
        x0, y0, z0, x1, y1, z1 = host.bounds
        a, b, low, c, d, high = panel.bounds
        name = panel.id
        if '/front/' in name or (panel.role == 'doors' and abs(b-y0) < .045):
            side = 'front'
        elif '/back/' in name or (panel.role == 'doors' and abs(d-y1) < .045):
            side = 'back'
        elif '/left/' in name or (panel.role == 'doors' and abs(a-x0) < .045):
            side = 'left'
        elif '/right/' in name or (panel.role == 'doors' and abs(c-x1) < .045):
            side = 'right'
        else:
            continue
        wall = (ctx['prim'] == host_pid) & (material == MATERIAL_IDS['metal'])
        if side == 'front':
            area = (np.abs(py-y0) < 1e-4) & (ny < -.9) & (px >= a) & (px <= c)
        elif side == 'back':
            area = (np.abs(py-y1) < 1e-4) & (ny > .9) & (px >= a) & (px <= c)
        elif side == 'left':
            area = (np.abs(px-x0) < 1e-4) & (nx < -.9) & (py >= b) & (py <= d)
        else:
            area = (np.abs(px-x1) < 1e-4) & (nx > .9) & (py >= b) & (py <= d)
        selected = wall & area & (pz >= low) & (pz <= high)
        if not np.any(selected):
            continue
        material[selected] = MATERIAL_IDS['glass']
        roles[selected] = SURFACE_ROLES['glazing']
        ctx['prim'][selected] = next_id
        component_by_pid[next_id] = panel.id
        next_id += 1
        # A door has a flush, wall-local surround. It is a material boundary,
        # not another 3-D box: the hit point, normal and depth stay unchanged.
        # Reserve a proportionally thicker surround for process/loading doors.
        if panel.role == 'doors':
            u = px if side in ('front','back') else py
            left,right = (a,c) if side in ('front','back') else (b,d)
            profile = name.split('/')[-3] if len(name.split('/')) >= 3 else ''
            rim = (.017 if profile == 'personnel' else .026)
            top_rim = .022 if profile == 'personnel' else .034
            surround = selected & ((u < left+rim) | (u > right-rim) |
                                   (pz > high-top_rim))
            if np.any(surround):
                material[surround] = MATERIAL_IDS['frame']
                roles[surround] = SURFACE_ROLES['detail']
                ctx['prim'][surround] = next_id
                component_by_pid[next_id] = panel.id+':frame'
                next_id += 1
        count += int(np.count_nonzero(selected))
    return count
