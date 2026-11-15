"""Deterministic candidate checks, feedback-only refill, and indexed selection export.

These are *pipeline management* operations, not artistic-quality judgments.
Geometry, accepted sprites and artist layers are not modified by evaluation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from .architectures import generate, library
from .architectural_validation import validate
from .palette import load_palette
from . import pipeline

ROTATIONS = (0, 90, 180, 270)


def _image_record(path: Path, expected: dict, palette: bytes):
    issues = []
    if not path.is_file():
        return None, ['missing_sprite']
    try:
        with Image.open(path) as im:
            if im.mode != 'P' or im.size != (64, 128):
                return None, ['not_native_indexed_sprite']
            if bytes(im.getpalette() or []) != bytes(palette):
                issues.append('palette_mismatch')
            pixels = np.asarray(im, dtype=np.uint8).copy()
    except (OSError, ValueError) as exc:
        return None, [f'bad_sprite:{type(exc).__name__}']
    digest = hashlib.sha256(pixels.tobytes()).hexdigest()
    if digest != expected.get('sha256'):
        issues.append('sprite_hash_mismatch')
    return pixels != 0, issues


def evaluate(run, *, near_duplicate_iou=.94, min_pixels=250, save=True):
    """Check geometry and four indexed PNGs, flag suspicious silhouettes.

    Similarity and small silhouettes are *advisory* only: they never hard-reject
    a candidate. The 4-rotation masks use exact, native-scale pixel occupancy.
    This deterministic report is isolated from the geometry/rendering stages.
    """
    if not 0 <= near_duplicate_iou <= 1:
        raise ValueError('near_duplicate_iou must be 0..1')
    out = Path(run)
    manifest = pipeline._load_manifest(out)
    votes = pipeline.read_feedback(out)['candidates']
    pal = bytes(load_palette())
    result = {}
    silhouettes = {}
    for key, info in sorted(manifest['candidates'].items()):
        node = manifest['nodes'][info['current']]
        try:
            model = pipeline.load_scene(out, info['current'])
            verdict = pipeline._accept(model)
            hard = [] if verdict['passes'] else ['invalid_scene']
        except (KeyError, OSError, ValueError) as exc:
            hard = [f'invalid_scene:{type(exc).__name__}']
        masks = []
        occupied = []
        records = {int(r['rotation']): r for r in node.get('sprites', [])}
        for rotation in ROTATIONS:
            if rotation not in records:
                hard.append(f'missing_rotation:{rotation}')
                continue
            rec = records[rotation]
            mask, issues = _image_record(out / rec['file'], rec, pal)
            hard += [f'r{rotation}:{issue}' for issue in issues]
            if mask is not None:
                occupied.append(int(np.count_nonzero(mask)))
                masks.append(mask)
        if len(masks) == 4:
            silhouettes[key] = np.stack(masks)
        warnings = []
        if occupied and min(occupied) < min_pixels:
            warnings.append('small_projected_footprint')
        if not info.get('active', True):
            warnings.append('archived_candidate')
        result[key] = {
            'family': info['family'],
            'status': 'active' if info.get('active', True) else 'archived',
            'vote': votes.get(key, {}).get('vote', 'undecided'),
            'geometry_valid': not any(issue.startswith('invalid_scene') for issue in hard),
            'hard_failures': hard,
            'warnings': warnings,
            'pixels_by_rotation': occupied,
            'max_silhouette_iou': 0.0,
            'most_similar': None,
        }
    # Deliberately compare only active candidates, and compare matching angles.
    keys = [key for key in sorted(silhouettes) if result[key]['status'] == 'active']
    for i, first in enumerate(keys):
        a = silhouettes[first]
        for second in keys[i+1:]:
            b = silhouettes[second]
            intersect = np.count_nonzero(a & b, axis=(1, 2))
            union = np.count_nonzero(a | b, axis=(1, 2))
            iou = round(float(np.mean(np.divide(intersect, union, out=np.zeros(4), where=union>0))), 6)
            for key, other in ((first, second), (second, first)):
                if iou > result[key]['max_silhouette_iou']:
                    result[key]['max_silhouette_iou'] = iou
                    result[key]['most_similar'] = other
    for key in keys:
        if result[key]['max_silhouette_iou'] >= near_duplicate_iou:
            result[key]['warnings'].append('near_duplicate_silhouette')
    report = {
        'schema_version': 1,
        'source_seed': manifest['seed'],
        'source_manifest_sha256': hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest(),
        'thresholds': {'near_duplicate_iou': near_duplicate_iou, 'min_pixels': min_pixels},
        'summary': {
            'active': sum(x['status']=='active' for x in result.values()),
            'archived': sum(x['status']=='archived' for x in result.values()),
            'hard_failures': sum(bool(x['hard_failures']) for x in result.values()),
            'advisory_warnings': sum(bool(x['warnings']) for x in result.values()),
        },
        'candidates': result,
        'note': 'Silhouette similarity is advisory. No aesthetic or architectural superiority is inferred.',
    }
    if save:
        pipeline._write_json(out/'evaluation.json', report)
    return report


def vote(run, *, accept=(), reject=(), undecided=()):
    """CLI-friendly review feedback; never changes a scene or raster."""
    sets = [set(accept), set(reject), set(undecided)]
    if sum(map(len,sets)) != len(set().union(*sets)):
        raise ValueError('A candidate cannot receive multiple votes in one command')
    manifest = pipeline._load_manifest(run)
    unknown = set().union(*sets) - set(manifest['candidates'])
    if unknown:
        raise ValueError(f'Unknown candidates: {sorted(unknown)}')
    changes = {}
    for names, value in ((accept,'yes'), (reject,'no'), (undecided,'undecided')):
        for key in sorted(names):
            changes[key] = pipeline.feedback_action(run,key,'vote',value=value)
    return {'updated': sorted(changes), 'votes': {key:item['vote'] for key,item in changes.items()}}


def refill(run, *, workers=4, buffers=True, grammar_file=None, dry_run=False,
           max_attempts=512):
    """Replace explicitly rejected, active candidates without deleting ancestors.

    Family-aware indexing maintains the existing family mix. Every candidate
    gets a new immutable structural scene and four fresh independent feature
    stages. A replacement is never *claimed* to be better artistically.
    """
    out = Path(run)
    manifest = pipeline._load_manifest(out)
    feedback = pipeline.read_feedback(out)['candidates']
    rejected = [key for key,info in sorted(manifest['candidates'].items())
                if info.get('active',True) and feedback.get(key,{}).get('vote')=='no']
    if dry_run or not rejected:
        return {'rejected_active': rejected, 'replaced': {}, 'dry_run': bool(dry_run)}
    if not 1 <= workers <= 64: raise ValueError('workers must be 1..64')
    if max_attempts < 1: raise ValueError('max_attempts must be >= 1')
    if manifest.get('pipeline_revision') != pipeline.PIPELINE_REVISION:
        raise ValueError('Refill requires a run generated with the current family selection policy')
    from .sampling import catalogue, create, select_families
    primary, ancillary = catalogue(grammar_file)
    families = select_families(primary, ancillary, manifest['grammar_families'])
    grammar_sha=hashlib.sha256(json.dumps(families,sort_keys=True).encode()).hexdigest()
    if grammar_sha != manifest['grammar_sha256']:
        raise ValueError('Grammar library differs from saved run: use the original grammar pack')
    # Build everything before changing any manifest entry; interrupted work can
    # leave harmless immutable orphan nodes but never half-updated candidates.
    cursor = max(manifest.get('next_design_index',manifest['start']+manifest['attempted']),
                 max(x['index'] for x in manifest['candidates'].values())+1)
    used = {key for key in manifest['candidates']}
    built = []
    for old_key in rejected:
        original=manifest['candidates'][old_key]
        wanted_family=original['family']
        found=None
        for _ in range(max_attempts):
            index=cursor
            cursor+=1
            if families[index % len(families)]['id'] != wanted_family:
                continue
            model=create(manifest['seed'],index,families)
            if not validate(model)['passes'] or f'{index:04d}' in used:
                continue
            found=model
            break
        if found is None:
            raise RuntimeError(f'No valid replacement for {old_key} after {max_attempts} indices')
        key=f'{found.index:04d}'
        used.add(key)
        new_nodes,leaf=pipeline._assemble_candidate(out,found)
        history=[node['id'] for node in new_nodes]
        built.append((old_key,key,found,new_nodes,history,leaf))
    leaves=[(nodes[-1],leaf) for _,_,model,nodes,_,leaf in built]
    pipeline._render_nodes(leaves,out,workers,buffers,
        manifest.get('edge_contrast','off'),manifest.get('semantic_colour','on'),
        manifest.get('semantic_hues',3),manifest.get('roof_colours','off'),manifest.get('facade_mode','boxes'),manifest.get('renderer','analytic'))
    for old_key,key,model,nodes,history,leaf in built:
        for node in nodes:
            if node['id'] in manifest['nodes']:
                raise RuntimeError('Unexpected duplicate node during refill')
            manifest['nodes'][node['id']]=node
        manifest['candidates'][old_key]['active']=False
        manifest['candidates'][old_key]['replaced_by']=key
        manifest['candidates'][key]={
            'index':model.index,'family':model.family,'label':model.label,
            'root':nodes[0]['id'],'current':nodes[-1]['id'],
            'history':history,'active':True,'replacement_for':old_key,
        }
    manifest['next_design_index']=cursor
    manifest['refill_count']=manifest.get('refill_count',0)+1
    pipeline._write_json(out/'manifest.json',manifest)
    # Keep original feedback entries, including the decision that caused refill.
    pipeline._write_contact_sheet(out,manifest)
    return {'rejected_active':rejected,
            'replaced':{old:new for old,new,*_ in built},
            'active_count':sum(x.get('active',True) for x in manifest['candidates'].values()),
            'archived_count':sum(not x.get('active',True) for x in manifest['candidates'].values()),
            'next_design_index':cursor}


def export_selection(run, out, *, mode='approved', buffers=True):
    """Copy selected 4-view 8bpp sprites; original scene/renders untouched."""
    if mode not in ('approved','active'):
        raise ValueError('mode must be approved or active')
    run=Path(run);out=Path(out)
    manifest=pipeline._load_manifest(run)
    votes=pipeline.read_feedback(run)['candidates']
    selected={key:info for key,info in sorted(manifest['candidates'].items())
              if info.get('active',True) and (mode=='active' or votes.get(key,{}).get('vote')=='yes')}
    if not selected:raise ValueError(f'No {mode} candidates')
    if out.resolve() == run.resolve() or run.resolve() in out.resolve().parents:
        # A subdirectory of run can be safe, but creates accidental recursion
        # when users archive the entire run later. Require a sibling export.
        raise ValueError('Export directory must be separate from source run')
    expected_export={'schema_version':1,'source_seed':manifest['seed'],'selection':mode,
        'candidates':{},'note':'Copies preserve native 8bpp sprite pixels and source provenance.'}
    if (out/'manifest.json').exists():
        prior=json.loads((out/'manifest.json').read_text())
        if prior['selection']!=mode or prior['source_seed']!=manifest['seed']:
            raise FileExistsError('Export manifest differs; choose a new output directory')
    target=out/'sprites'
    target.mkdir(parents=True, exist_ok=True)
    results={}
    for key,info in selected.items():
        src_node=manifest['nodes'][info['current']]
        rotation_files=[]
        for record in src_node['sprites']:
            rotation=int(record['rotation'])
            src=run/record['file']
            dest=target/f'{key}_r{rotation:03d}.png'
            with Image.open(src) as im:
                if im.mode!='P' or im.size!=(64,128):
                    raise ValueError(f'Invalid source indexed sprite {src}')
                if bytes(im.getpalette() or [])!=bytes(load_palette()):
                    raise ValueError(f'Invalid source DOS palette {src}')
                if hashlib.sha256(im.tobytes()).hexdigest()!=record['sha256']:
                    raise ValueError(f'Sprite checksum mismatch {src}')
            if dest.exists():
                if dest.read_bytes()!=src.read_bytes():
                    raise FileExistsError(f'Export conflicts with existing file: {dest}')
            else: shutil.copy2(src,dest)
            if buffers:
                buf=src.with_suffix('.npz')
                if buf.exists():
                    target_buf=dest.with_suffix('.npz')
                    if target_buf.exists() and target_buf.read_bytes()!=buf.read_bytes():
                        raise FileExistsError(f'Geometry buffer conflict: {target_buf}')
                    if not target_buf.exists():shutil.copy2(buf,target_buf)
            rotation_files.append({'rotation':rotation,'path':f'sprites/{dest.name}',
                                   'sha256':record['sha256']})
        results[key]={'family':info['family'],'node':info['current'], 'rotations':rotation_files}
    export_manifest={'schema_version':1,'source_seed':manifest['seed'],'selection':mode,
                     'candidates':results,'note':'Copies preserve native 8bpp sprite pixels and source provenance.'}
    if (out/'manifest.json').exists() and json.loads((out/'manifest.json').read_text())!=export_manifest:
        raise FileExistsError('Export manifest differs; choose a new output directory')
    pipeline._write_json(out/'manifest.json',export_manifest)
    return {'selected_designs':len(selected),'sprites':len(selected)*4,'output':str(out)}
