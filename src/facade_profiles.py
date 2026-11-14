"""Industrial facade profiles expressed as wall-local rectangles.

Only windows and doors use flush analytic decals; service fittings and other
3-D details stay with the existing feature stages. Profiles are assigned by
fabric function in the grammar rather than chosen per visible wall pixel.
"""
from __future__ import annotations

WINDOW_PROFILES = frozenset(('blank', 'clerestory', 'tall_factory', 'sparse_utility', 'office'))
DOOR_PROFILES = frozenset(('none', 'loading', 'personnel', 'process'))


def _surface_band(edge, sign):
    # At an intentional tile seam the facade metadata must stay within
    # world bounds. Decals still resolve against the exact wall hit.
    if edge < .012 and sign < 0:
        sign = 1
    elif edge > .988 and sign > 0:
        sign = -1
    return tuple(sorted((edge+sign*.002,edge+sign*.012)))


def _wall_rect(host, side, bounds):
    """Wall-local rectangle (u0, u1, z0, z1), independent of decal thickness."""
    a,b,low,c,d,high = bounds
    return (a,c,low,high) if side in ('front','back') else (b,d,low,high)


def _overlaps(first, second, clearance):
    a,b,z0,z1=first
    c,d,q0,q1=second
    return (a < d+clearance and b > c-clearance and
            z0 < q1+clearance and z1 > q0-clearance)


def panels(host, stage, profile, counter=0, *, reserved=()):
    """Return (side, name, box, material) records for the feature pass.

    The boxes specify surface rectangles in wall-local coordinates; the decal
    renderer never casts them as solids. Bounds retain compatibility with the
    existing building-component and feature-pass representations.
    """
    x0,y0,z0,x1,y1,z1 = host.bounds
    w,d,h=x1-x0,y1-y0,z1-z0
    out=[]
    if stage == 'windows':
        if profile not in WINDOW_PROFILES:
            raise ValueError(f'Unknown window facade profile: {profile}')
        if profile == 'blank':
            return out
        # Fractional positions deliberately respect the native 1x footprint.
        if profile == 'clerestory':
            spans=((.14,.30),(.37,.53),(.60,.76),(.83,.94))
            vertical=(.77,.89)
        elif profile == 'tall_factory':
            spans=((.16,.30),(.43,.57),(.70,.84))
            vertical=(.28,.78)
        elif profile == 'sparse_utility':
            spans=((.20,.34),(.70,.82))
            vertical=(.51,.66)
        else:  # explicitly reserved for administration/service buildings
            spans=((.17,.30),(.43,.56),(.69,.82))
            vertical=(.37,.57)
        for side in ('front','back','left','right'):
            for n,(start,end) in enumerate(spans):
                # Side walls may be very narrow: avoid nearly subpixel slivers.
                length=w if side in ('front','back') else d
                if length*(end-start) < .028:
                    continue
                zl=z0+h*vertical[0]
                zh=min(z0+h*vertical[1], z1-.045)
                if zh-zl < .035:
                    continue
                if side in ('front','back'):
                    edge=y0 if side=='front' else y1
                    sign=-1 if side=='front' else 1
                    a,b=_surface_band(edge,sign)
                    bounds=(x0+w*start,a,zl,x0+w*end,b,zh)
                else:
                    edge=x0 if side=='left' else x1
                    sign=-1 if side=='left' else 1
                    a,b=_surface_band(edge,sign)
                    bounds=(a,y0+d*start,zl,b,y0+d*end,zh)
                rect=_wall_rect(host,side,bounds)
                # Reserve opening and surround clearance before issuing windows.
                # All comparisons use model-space coordinates, not screen pixels.
                clearance=max(.018, h*.035)
                if any(side==door_side and _overlaps(rect, door_rect, clearance)
                       for door_side,door_rect in reserved):
                    continue
                out.append((side, f'{profile}/{side}/{n}', bounds, 'glass'))
    elif stage == 'doors':
        if profile not in DOOR_PROFILES:
            raise ValueError(f'Unknown door facade profile: {profile}')
        if profile == 'none':
            return out
        # Deliberate role-based difference: large near-floor process opening
        # versus small personnel entrance; no protruding lintels or jambs.
        if profile == 'loading':
            side='right'; centre=.55; width=.38; height=.72
        elif profile == 'process':
            side='front'; centre=.48; width=.56; height=.84
        else:
            side='right'; centre=.72; width=.19; height=.48
        if side in ('front','back'):
            edge=y0 if side=='front' else y1
            sign=-1 if side=='front' else 1
            a,b=_surface_band(edge,sign)
            bounds=(x0+w*(centre-width/2),a,z0+.004,
                    x0+w*(centre+width/2),b,z0+h*height)
        else:
            edge=x0 if side=='left' else x1
            sign=-1 if side=='left' else 1
            a,b=_surface_band(edge,sign)
            bounds=(a,y0+d*(centre-width/2),z0+.004,
                    b,y0+d*(centre+width/2),z0+h*height)
        out.append((side,f'{profile}/{side}/door',bounds,'glass'))
    else:
        raise ValueError(f'Unsupported facade stage: {stage}')
    return out


def door_reservations(host, profile, counter=0):
    """Calculate door clearance independently of feature-pass order."""
    return tuple((side, _wall_rect(host,side,bounds))
                 for side, _name, bounds, _material in
                 panels(host,'doors',profile,counter))
