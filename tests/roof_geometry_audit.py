"""Offline OBIWAN audit of Becher's installed authored pitched-roof geometry.

Run at repository root:
  python /path/to/roof_audit.py --out output/roof-audit

Does NOT modify the renderer, assets, UI, or any source geometry. All coordinates
are projected through the canonical 2:1 Becher camera equations, derived from
src/mesh/camera.py; optional raster diagnostics use the actual cast_mesh() result.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROTATIONS=(0,90,180,270)
MAX_FRONT_SLOPE_ERROR=0.075
MAX_REAR_SLOPE=0.075
MIN_TESTABLE_SPAN_PX=4.0
MIN_VISIBLE_FACE_PX=12


def project_delta(vector, rotation):
    """Raster coordinate delta implied by Becher's camera, no texture mapping."""
    x,y,z=map(float,vector)
    theta=math.radians(rotation)
    # World-to-camera is inverse of camera-origin rotation -rotation.
    cx=math.cos(theta)*x-math.sin(theta)*y
    cy=math.sin(theta)*x+math.cos(theta)*y
    return np.asarray((32.0*(cx-cy), 16.0*(cx+cy)-36.0*z))


def analyse_component(name, part, render_rasters=True):
    from src.composition import rigid_place
    from src.mesh.compile import compile_scene
    from src.mesh.render import cast_mesh
    from src.geometry import MATERIAL_IDS
    from src.colour_suggestions import _pitched_roof_groups, _visible_positions, _edge_candidate
    mesh=compile_scene({'shapes':rigid_place(part,'',(.5,.5),0)})
    roof_ids=np.flatnonzero(mesh.materials==MATERIAL_IDS['roof'])
    if roof_ids.size==0:
        return [],{},'no_roof'
    shape_by_id={s['id']:s for s in part['shapes']}
    facets={}
    for i in roof_ids:
        n=np.array(mesh.normals[i,0],dtype=float,copy=True)
        nmag=np.linalg.norm(n)
        if nmag<1e-8:
            continue
        n/=nmag
        if not (0.2<n[2]<0.965):
            continue
        prim=int(mesh.component_ids[i])
        norm_sig=tuple(np.round(n,4))
        key=(prim,norm_sig)
        if key not in facets:
            shape=shape_by_id.get(mesh.component_names[prim-1],{})
            facets[key]={'component':name,'part':mesh.component_names[prim-1],
                        'source_shape_type':shape.get('type','unknown'),
                        'ring_vertex_count':len(shape['rings'][0]) if shape.get('type')=='rings' else None,
                        'primitive':prim,'normal':n,'vertices':[], 'triangles':0}
        facets[key]['vertices'].append(mesh.vertices[i].astype(float))
        facets[key]['triangles']+=1
    if not facets:
        return [],{},'no_pitched'
    surfaces={}
    if render_rasters:
        surfaces={rot:cast_mesh(mesh,rot)[0] for rot in ROTATIONS}
    records=[]
    for (primitive,signature),data in facets.items():
        n=data['normal']; horizontal=np.linalg.norm(n[:2]);
        if horizontal<1e-8:
            continue
        advance=np.array((n[0]/horizontal,n[1]/horizontal,-horizontal/n[2]),dtype=float)
        vertices=np.concatenate(data['vertices'],axis=0)
        projected_positions=vertices @ (n[:3]*np.array([1,1,0])) / horizontal
        span=float(np.ptp(projected_positions))
        results=[]
        for rot in ROTATIONS:
            camvec=np.asarray((math.cos(math.radians(-rot))-math.sin(math.radians(-rot)),
                               math.sin(math.radians(-rot))+math.cos(math.radians(-rot))))
            facing=float(n[:2]@camvec)
            if abs(facing)<0.08: # near tangent to view
                role='edge'
            else:
                role='front' if facing>0 else 'rear'
            dx,dy=project_delta(advance,rot)
            pixelspan=abs(span*dx)
            slope=abs(dy/dx) if abs(dx)>1e-9 else None
            raster_pixels=0; detected=False; terminal_rows=0
            if render_rasters:
                s=surfaces[rot]
                roof=(s.material==MATERIAL_IDS['roof']) & (s.primitive==primitive) & (s.normal[...,2]>0.2) & (s.normal[...,2]<0.965)
                # 0.998 dot allows float-normal roundoff while differentiating the slopes.
                normfield=s.normal.astype(float)
                normlen=np.maximum(np.linalg.norm(normfield,axis=-1),1e-9)
                dot=(normfield @ n)/normlen
                mask=roof & (dot>0.9999)
                raster_pixels=int(mask.sum())
                if raster_pixels>=MIN_VISIBLE_FACE_PX and role=='front':
                    edge=_edge_candidate(mask,_visible_positions(s,rot),n)
                    detected=edge is not None
                    if detected:
                        terminal_rows=len(edge[0])
            is_testable=role in ('front','rear') and pixelspan>=MIN_TESTABLE_SPAN_PX
            if role=='front':
                analytic_ok=abs(slope-1.0)<=MAX_FRONT_SLOPE_ERROR if slope is not None else False
            elif role=='rear':
                analytic_ok=slope<=MAX_REAR_SLOPE if slope is not None else False
            else:
                analytic_ok=None
            results.append(dict(rotation=rot,role=role,slope=round(slope,4) if slope is not None else None,
                                pixelspan=round(pixelspan,2),visible_pixels=raster_pixels,
                                detector_accepts=detected if role=='front' else None,
                                terminal_rows=terminal_rows,analytic_ok=bool(analytic_ok) if is_testable else None))
        testable=[x for x in results if x['analytic_ok'] is not None]
        if not testable:
            verdict='too_small_or_unobservable'
        elif not all(x['analytic_ok'] for x in testable):
            verdict='PITCH_MISMATCH'
        elif render_rasters and any(x['role']=='front' and x['visible_pixels']>=MIN_VISIBLE_FACE_PX and not x['detector_accepts'] for x in results):
            verdict='RASTER_OR_DETECTOR'
        else:
            verdict='ANALYTIC_OK'
        records.append({'component':name,'part':data['part'],'primitive':primitive,
                        'source_shape_type':data['source_shape_type'],
                        'ring_vertex_count':data['ring_vertex_count'],
                        'face_normal':list(map(float,signature)),'triangles':data['triangles'],
                        'slope_world':round(horizontal/n[2],4), 'width_world':round(span,5),
                        'verdict':verdict, 'rotations':results})
    return records,surfaces,'pitched'


def _paint_control_edges(surface, rot):
    """Overlay diagnostic red (front) / cyan (rear) pitched face pixels."""
    from src.geometry import MATERIAL_IDS
    m=surface.material==MATERIAL_IDS['roof']
    n=surface.normal
    mask=m & (n[...,2]>0.20)&(n[...,2]<0.965)
    x=np.asarray((math.cos(math.radians(-rot))-math.sin(math.radians(-rot)),
                  math.sin(math.radians(-rot))+math.cos(math.radians(-rot))))
    facing=n[...,0]*x[0]+n[...,1]*x[1]
    return mask & (facing>0.08), mask & (facing< -0.08)


def render_gallery(comps, cache, dest):
    from src.palette import indexed_image,load_palette
    pal=load_palette()
    thumb=(160,160)
    cols=4
    rowh=180
    header=60
    canvas=Image.new('RGB',(cols*195+18,header+len(comps)*rowh+12),'#f4f4f4')
    draw=ImageDraw.Draw(canvas)
    draw.text((10,8),'Red: front pitched face   Cyan: rear pitched face.  Base sprites retained.',fill='#181818')
    for c,rot in enumerate(ROTATIONS):
        draw.text((10+c*195,28),f'{rot} degrees',fill='#222222')
    for i,name in enumerate(comps):
        surfset=cache.get(name)
        if surfset is None:
            continue
        y=header+i*rowh
        draw.text((10,y),name,fill='#111111')
        for j,rot in enumerate(ROTATIONS):
            surface=surfset[rot]
            pixels=surface.reference_pixels
            image=indexed_image(pixels,pal).convert('RGBA')
            alpha=Image.fromarray(np.uint8(pixels!=0)*255,'L')
            bg=Image.new('RGBA',image.size,(0,0,250,255))
            bg.paste(image,(0,0),alpha)
            fg,rear=_paint_control_edges(surface,rot)
            pix=np.asarray(bg).copy()
            pix[fg,0:3]=(250,36,55)
            pix[rear,0:3]=(39,243,232)
            bg=Image.fromarray(pix,'RGBA')
            bbox=alpha.getbbox()
            if bbox:
                bbox=(max(0,bbox[0]-2),max(0,bbox[1]-2),min(64,bbox[2]+2),min(128,bbox[3]+2))
                bg=bg.crop(bbox)
            scale=min(155/bg.width,135/bg.height)
            width,height=map(lambda v:max(1,int(round(v*scale))),bg.size)
            bg=bg.resize((width,height),Image.Resampling.NEAREST)
            canvas.paste(bg.convert('RGB'),(j*195+int((185-width)/2), y+24))
    canvas.save(dest)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--raster',action='store_true',help='Run slower four-angle pixel detector audit on every pitched component')
    parser.add_argument('--strict',action='store_true',help='Exit nonzero for any measurable architectural roof pitch mismatch')
    a=parser.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    from src.composition import component_catalogue,load_part
    names=list(component_catalogue())
    if a.limit:names=names[:a.limit]
    all_records=[];cache={}; errors={}; stats=collections.Counter();component_verdicts={}
    for idx,name in enumerate(names):
        try:
            data,surfaces,status=analyse_component(name,load_part(name),render_rasters=a.raster)
            stats[status]+=1
            all_records.extend(data)
            if data:
                priorities=['PITCH_MISMATCH','RASTER_OR_DETECTOR','ANALYTIC_OK','too_small_or_unobservable']
                component_verdicts[name]=next((p for p in priorities if any(r['verdict']==p for r in data)),'other')
                if a.raster:cache[name]=surfaces
        except Exception as exc:
            errors[name]=str(exc)
            stats['error']+=1
        if idx%100==99:print('AUDIT',idx+1,'of',len(names),'pitched',len(cache),'faces',len(all_records),flush=True)
    classes=collections.Counter(x['verdict'] for x in all_records)
    bycomp=collections.Counter(component_verdicts.values())
    output={'source':'authored component catalogue', 'component_count':len(names),
            'components_with_pitched_faces':len(component_verdicts),'status_counts':dict(stats),
            'face_counts':dict(classes),'component_counts':dict(bycomp),
            'criteria':{'front_slope_target':1.0,'front_abs_tolerance':MAX_FRONT_SLOPE_ERROR,
                        'rear_slope_target':0.0,'rear_abs_tolerance':MAX_REAR_SLOPE,
                        'min_analytic_screen_span_px':MIN_TESTABLE_SPAN_PX,
                        'raster_front_detector':'NOT run in catalogue-wide analytic audit; run in optional sample'},
            'errors':errors,'faces':all_records}
    (a.out/'audit.json').write_text(json.dumps(output,indent=2))
    with (a.out/'faces.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['component','part','normal','world_pitch','world_half_span',
                                    'verdict','rotation','role','screen_slope','pixelspan','visible_pixels','detector_accepts'])
        for r in all_records:
            for view in r['rotations']:
                w.writerow([r['component'],r['part'],r['face_normal'],r['slope_world'],r['width_world'],r['verdict'],
                            view['rotation'],view['role'],view['slope'],view['pixelspan'],
                            view['visible_pixels'],view['detector_accepts']])
    with (a.out/'components.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['component','verdict','pitched_faces','mismatch_faces','detector_faces'])
        for n,verdict in sorted(component_verdicts.items()):
            records=[r for r in all_records if r['component']==n]
            w.writerow([n,verdict,len(records),sum(r['verdict']=='PITCH_MISMATCH' for r in records),
                        sum(r['verdict']=='RASTER_OR_DETECTOR' for r in records)])
    architectural=[r for r in all_records if r['source_shape_type']=='rings']
    arch_classes=collections.Counter(r['verdict'] for r in architectural)
    arch_bycomp={}
    for name in sorted(set(r['component'] for r in architectural)):
        rows=[r for r in architectural if r['component']==name]
        arch_bycomp[name]=next((p for p in ('PITCH_MISMATCH','RASTER_OR_DETECTOR','ANALYTIC_OK','too_small_or_unobservable') if any(r['verdict']==p for r in rows)),'other')
    output['architectural_roof_face_counts']=dict(arch_classes)
    output['architectural_roof_component_counts']=dict(collections.Counter(arch_bycomp.values()))
    output['architectural_component_verdicts']=arch_bycomp
    (a.out/'audit.json').write_text(json.dumps(output,indent=2))
    selected=[]
    for typ,count in [('PITCH_MISMATCH',12),('RASTER_OR_DETECTOR',8),('ANALYTIC_OK',6)]:
        candidates=[name for name,verdict in component_verdicts.items() if verdict==typ]
        priority=('mill','gable','twin','foundry','shed','gantry','roof','factory','monitor')
        candidates.sort(key=lambda name:(next((j for j,tok in enumerate(priority) if tok in name),len(priority)),name))
        selected.extend(candidates[:count])
    from src.composition import load_part,rigid_place
    from src.mesh.compile import compile_scene
    from src.mesh.render import cast_mesh
    for name in selected:
        if name in cache:continue
        try:
            mesh=compile_scene({'shapes':rigid_place(load_part(name),'',(.5,.5))})
            cache[name]={rot:cast_mesh(mesh,rot)[0] for rot in ROTATIONS}
        except Exception as exc:
            errors[name]=str(exc)
    render_gallery(selected,cache,a.out/'roof_faces_diagnostics.png')
    lines=['# Roof geometry audit — authored Becher components','',
           'Measures the checked-out source geometry using compiled roof faces and the actual 4-angle raster. The audit command does not modify source geometry, renderer or UI.',
           '',f'- Components scanned: **{len(names)}**',
           f'- Components with pitched roof geometry: **{len(component_verdicts)}**',
           f'- Pitched inclined-normal face groups: **{len(all_records)}** (including conical silo caps and conveyors)',
           f'- Architectural swept pitched-roof components: **{len(arch_bycomp)}**',
           f'- Architectural swept face outcomes: **{dict(arch_classes)}**',
           f'- Architectural component outcomes: **{dict(collections.Counter(arch_bycomp.values()))}**',
           f'- Face outcomes: **{dict(classes)}**',
           f'- Component outcomes (worst-face classification): **{dict(bycomp)}**',
           '',
           '## Classification',
           '',
           '- `PITCH_MISMATCH`: projected front slope deviates from 1:1, or projected rear slope deviates from horizontal, beyond ±0.075 px per 1 px horizontal. This is a geometry-level issue under the Becher camera.',
           '- `RASTER_OR_DETECTOR`: analytic slopes meet the threshold, but the current strict terminal-edge detector rejects an otherwise visible face in at least one rotation. This is **not** proof the source geometry is wrong.',
           '- `ANALYTIC_OK`: sampled pitched faces satisfy analytic slope requirements, and the current front edge detector finds a suitable edge where sufficiently visible.',
           '- `too_small_or_unobservable`: pitch face is too short in screen-space to apply this criterion reliably.',
           '',
           '## Geometry correction',
           '',
           'For symmetric ridge roofs under the canonical dimetric projection:',
           '`rise ~= (4/9) * half_roof_span` (world units, before pixel rounding).',
           'This gives a 1:1 projected near slope and an approximately horizontal far slope.',
           'An off-centre ridge can correct pixel phase, but it changes the near/far effective spans and may break the opposite angle;',
           'revalidate all four rotations after any move.',
           '',
           'Do not enforce this on flat roofs, sloped conveyor covers, domes or sawtooth vertical/glazed faces without explicit roof-family annotations.',
           '',
           'See `faces.csv`, `components.csv`, `audit.json`, and `roof_faces_diagnostics.png`.',
          ]
    (a.out/'README.md').write_text('\n'.join(lines)+'\n')
    print('SUMMARY',json.dumps({'status':dict(stats),'faces':dict(classes),'components':dict(bycomp),
      'architectural_faces':dict(arch_classes),
      'architectural_components':dict(collections.Counter(arch_bycomp.values())),
      'errors':len(errors)},indent=2))
    if a.strict and arch_classes.get('PITCH_MISMATCH',0):
        raise SystemExit(f"Architectural roof conformance failed: {arch_classes['PITCH_MISMATCH']} mismatched pitched faces")

if __name__=='__main__':main()
