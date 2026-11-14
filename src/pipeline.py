"""Step 3: deterministic candidate DAG, selective rerolls, and reviewed 4-view sprites.

Only the current leaf is selected; parent scenes and raster outputs are immutable.
The feedback file is intentionally separate from the deterministic build manifest.
"""
from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from time import perf_counter
import hashlib
import json
import multiprocessing as mp
import os
import tempfile

from .architectures import Building, Component, generate, library
from .architectural_validation import validate
from .mesh.render import cast_mesh
from .mesh.compile import compile_building, save_mesh
from .mesh.io import save
from .edge_contrast import apply as apply_edges
from .semantic_colour import apply as apply_semantic
from .roof_colour import apply as apply_roof_colour
from .feature_passes import STAGES, build_features, reroll as reroll_features, validate_features
from .palette import load_palette

# Change when scene construction or raster output semantics change.
PIPELINE_REVISION = "v0.16.1-mesh-only"


def _write_json(path, data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+'\n'
    # Atomic output protects manifests and review history from interrupted writes.
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=p.parent,delete=False) as fh:
        fh.write(payload);tmp=Path(fh.name)
    os.replace(tmp,p)


def scene_from_dict(data):
    return Building(data['id'],data['family'],data['label'],int(data['seed']),
                    int(data['index']),tuple(Component(**{**c,'bounds':tuple(c['bounds'])})
                                        for c in data['components']),data['parameters'])


def _scene_path(out,node_id):
    return Path(out)/'nodes'/node_id/'scene.json'


def _node_id(parent,stage,model):
    return hashlib.sha256(f'{parent}|{stage}|{model.id}'.encode()).hexdigest()[:20]


def _record_node(out, parent, stage, model, validation):
    id_=_node_id(parent,stage,model)
    file=_scene_path(out,id_)
    # Immutable content-addressed scene. Existing data must be identical.
    expected=model.to_dict()
    if file.exists():
        if json.loads(file.read_text())!=json.loads(json.dumps(expected,sort_keys=True)):
            raise RuntimeError(f'Node ID collision: {id_}')
    else:_write_json(file,expected)
    rec={'id':id_,'parent':parent,'stage':stage,'scene':f'nodes/{id_}/scene.json',
         'building_id':model.id,'validation':validation,
         'feature_counters':model.parameters.get('feature_counters',{}),
         'sprites':[]}
    return rec


def _assemble_candidate(out, root):
    """Single canonical fabric -> feature-stage DAG assembly for build/refill.

    Node IDs and stage ordering deliberately match v0.11 exactly.
    """
    nodes=[]
    parent=None
    model=root
    for stage in ('fabric', *STAGES):
        if stage != 'fabric':
            model=build_features(root, through=stage)
        verdict=_accept(model)
        if not verdict['passes']:
            raise RuntimeError(f'Feature stage {stage} invalid for {root.index:04d}: {verdict}')
        node=_record_node(out,parent,stage,model,verdict)
        nodes.append(node)
        parent=node['id']
    return nodes,model


def _assert_cached_sprites(out, manifest):
    """Fail closed on missing/corrupt active sprites instead of false cache hits."""
    from PIL import Image
    import numpy as np
    palette=load_palette()
    for key,info in manifest['candidates'].items():
        if not info.get('active',True):
            continue
        node=manifest['nodes'][info['current']]
        records=node.get('sprites',[])
        if len(records)!=4 or {int(r['rotation']) for r in records}!={0,90,180,270}:
            raise RuntimeError(f'Cached run {key} has incomplete sprite records; use a new --out directory')
        for record in records:
            path=Path(out)/record['file']
            if not path.is_file():
                raise RuntimeError(f'Cached sprite missing: {path}; use a new --out directory')
            try:
                with Image.open(path) as im:
                    if im.mode!='P' or im.size!=(64,128) or list(im.getpalette()[:768])!=palette:
                        raise ValueError('invalid indexed sprite or palette')
                    pixels=np.asarray(im, dtype=np.uint8)
                    digest=hashlib.sha256(pixels.tobytes()).hexdigest()
            except (OSError, ValueError) as exc:
                raise RuntimeError(f'Cached sprite invalid: {path}') from exc
            if digest!=record['sha256']:
                raise RuntimeError(f'Cached sprite checksum mismatch: {path}; use a new --out directory')


def _render_task(item):
    model,angle,out,buf,edge_contrast,semantic_colour,semantic_hues,roof_colours,facade_mode,renderer,frozen_mesh=item
    if renderer != 'mesh':
        raise ValueError("v0.16.1 supports only the mesh renderer")
    surfaces,metrics=cast_mesh(frozen_mesh,angle,building=model,facade_mode=facade_mode)
    fn=f'nodes/{out[0]}/r{angle:03d}.png'
    path=Path(out[1])/fn
    palette=load_palette()
    if edge_contrast=='on':
        edged,edge_mask=apply_edges(surfaces,palette)
    else:
        edged,edge_mask=surfaces.reference_pixels,None
    display,colour_assignments=apply_semantic(
        surfaces,metrics['primitive_components'],model,palette,
        enabled=semantic_colour=='on',max_hues=semantic_hues,
        base_pixels=edged,contrast_mask=edge_mask)
    display,roof_assignments=apply_roof_colour(
        surfaces,metrics['primitive_components'],model,palette,
        enabled=roof_colours=='on',base_pixels=display,contrast_mask=edge_mask)
    # The NPZ always retains the unmodified shaded base. The PNG may show an
    # optional post-process; both outputs share the same depth/ID/normal data.
    save(surfaces,path,buffers=buf,display_pixels=display)
    return {'rotation':angle,'file':fn,'sha256':hashlib.sha256(
                display.tobytes()).hexdigest(),
            'occupied_pixels':metrics['occupied_pixels'],
            'visible_primitive_ids':metrics['visible_primitive_ids'],
            'render_ms':metrics['render_ms'], 'semantic_assignments':colour_assignments, 'roof_assignments':roof_assignments}


def _render_nodes(items, out, workers=4, buffers=True, edge_contrast="off", semantic_colour="on", semantic_hues=3, roof_colours="off", facade_mode="boxes", renderer="mesh"):
    """Render four rotations of each leaf in a stable order."""
    meshes={}
    if renderer != 'mesh':
        raise ValueError('v0.16.1 supports only renderer=mesh')
    for node,model in items:
        frozen=compile_building(model,facade_mode=facade_mode)
        filename=Path(out)/'nodes'/node['id']/'mesh.npz'
        filename.parent.mkdir(parents=True,exist_ok=True)
        save_mesh(frozen,filename)
        meshes[node['id']]=frozen
        node['mesh']=f'nodes/{node["id"]}/mesh.npz'
    jobs=[(model,angle,(node['id'],str(out)),buffers,edge_contrast,
           semantic_colour,semantic_hues,roof_colours,facade_mode,renderer,meshes.get(node['id']))
          for node,model in items for angle in (0,90,180,270)]
    if workers==1:results=[_render_task(j) for j in jobs]
    else:
        method='fork' if 'fork' in mp.get_all_start_methods() else 'spawn'
        with ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context(method)) as pool:
            results=list(pool.map(_render_task,jobs,chunksize=2))
    for i,(node,_) in enumerate(items):
        node['sprites']=[{k:v for k,v in r.items() if k!='render_ms'}
                         for r in results[4*i:4*i+4]]
    return results


def _accept(model):
    structural=validate(model)
    features=validate_features(model)
    return {'passes':structural['passes'] and features['passes'],
            'structural':structural,'features':features}


def _load_manifest(out):
    return json.loads((Path(out)/'manifest.json').read_text())


def load_scene(out,node_id):
    return scene_from_dict(json.loads(_scene_path(out,node_id).read_text()))


def read_feedback(out):
    path=Path(out)/'feedback.json'
    if not path.exists():return {'schema_version':1,'candidates':{}}
    return json.loads(path.read_text())


def feedback_action(out,candidate,action,value=None,notes=None):
    manifest=_load_manifest(out)
    if candidate not in manifest['candidates']:raise ValueError(f'Unknown candidate {candidate}')
    review=read_feedback(out)
    entry=review['candidates'].setdefault(candidate,{'vote':'undecided','locks':[],'notes':''})
    if action=='vote':
        if value not in ('yes','no','undecided'):raise ValueError('Invalid vote')
        entry['vote']=value
    elif action=='lock':
        if value not in STAGES:raise ValueError('Unknown feature pass')
        lock=set(entry['locks']);lock.add(value);entry['locks']=sorted(lock)
    elif action=='unlock':
        if value not in STAGES:raise ValueError('Unknown feature pass')
        lock=set(entry['locks']);lock.discard(value);entry['locks']=sorted(lock)
    elif action=='notes':entry['notes']=str(notes or '')[:2000]
    else:raise ValueError('Invalid feedback action')
    _write_json(Path(out)/'feedback.json',review)
    return entry


def build(out, *, seed=1267, designs=12, start=0, workers=4, grammar_file=None,
          buffers=True, max_attempts=None, edge_contrast="off",
          semantic_colour="on", semantic_hues=3, roof_colours="off", facade_mode="boxes",
          candidate_mode="classic", industry=None, renderer="mesh"):
    if renderer != 'mesh': raise ValueError('v0.16.1 supports only renderer=mesh')
    if edge_contrast not in ('off','on'):raise ValueError('invalid edge contrast mode')
    if semantic_colour not in ('off','on'):raise ValueError('invalid semantic colour mode')
    if roof_colours not in ('off','on'):raise ValueError('invalid roof colour mode')
    if facade_mode not in ('boxes','decals'):raise ValueError('invalid facade mode')
    if semantic_hues not in (3,4):raise ValueError('semantic hues must be 3 or 4')
    if candidate_mode not in ('classic','diverse','related'):raise ValueError('invalid candidate mode')
    if not 1<=designs<=256:raise ValueError('designs must be 1..256')
    if not 1<=workers<=64:raise ValueError('workers must be 1..64')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    t0=perf_counter()
    from .sampling import catalogue, candidates as sample_candidates
    primary, ancillary=catalogue(grammar_file)
    families=primary + (ancillary if candidate_mode != 'classic' else [])
    grammar_sha=hashlib.sha256(json.dumps(families,sort_keys=True).encode()).hexdigest()
    if candidate_mode=='related' and industry not in {f['id'] for f in primary}:
        raise ValueError('related mode requires a valid --industry primary grammar ID')
    if candidate_mode!='related' and industry is not None:
        raise ValueError('--industry applies only to related mode')
    existing=out/'manifest.json'
    if existing.exists():
        old=_load_manifest(out)
        if old.get('pipeline_revision') != PIPELINE_REVISION:
            raise ValueError('Existing output was compiled by a different Becher revision; use a new --out directory (old PNGs are preserved)')
        if (old.get('seed'),old.get('start'),old.get('designs'),old.get('grammar_sha256'),old.get('edge_contrast','off'),old.get('semantic_colour','on'),old.get('semantic_hues',3),old.get('roof_colours','off'),old.get('facade_mode','boxes'),old.get('candidate_mode','classic'),old.get('industry'),old.get('renderer','analytic')) != (seed,start,designs,grammar_sha,edge_contrast,semantic_colour,semantic_hues,roof_colours,facade_mode,candidate_mode,industry,renderer):
            raise ValueError('Output already contains a different run; select a new --out path')
        _assert_cached_sprites(out,old)
        if not (out/'index.html').exists():
            from .pipeline_review import write_review
            write_review(out)
        return {**json.loads((out/'timing.json').read_text()),'cached':True}

    accepted,rejected,attempt=sample_candidates(
        seed,designs,start,primary,ancillary,candidate_mode,industry,
        max_attempts or designs*12)
    nodes={};candidates={};leaves=[]
    for root in accepted:
        candidate_key=f'{root.index:04d}'
        chain,model=_assemble_candidate(out,root)
        for node in chain:
            nodes[node['id']]=node
        candidates[candidate_key]={'index':root.index,'family':root.family,
            'label':root.label,'root':chain[0]['id'],'current':chain[-1]['id'],
            'history':[node['id'] for node in chain]}
        leaves.append((chain[-1],model))
    timings=_render_nodes(leaves,out,workers,buffers,edge_contrast,semantic_colour,semantic_hues,roof_colours,facade_mode,renderer)
    # histories: remove potential duplicates and sort chronologically root -> leaf
    for candidate in candidates.values():
        candidate['history']=list(reversed(_ancestry_ids(nodes,candidate['current'])))
    manifest={'schema_version':1,'compiler':'becher-step3','pipeline_revision':PIPELINE_REVISION,
              'edge_contrast':edge_contrast, 'semantic_colour':semantic_colour,
              'semantic_hues':semantic_hues, 'roof_colours':roof_colours, 'facade_mode':facade_mode,
              'candidate_mode':candidate_mode,'industry':industry,'renderer':renderer,
              'grammar_families':[f['id'] for f in families],
              'seed':seed,'start':start,'designs':len(accepted),
              'rotations_per_design':4,
              'grammar_sha256':grammar_sha,
              'attempted':attempt-start,'rejected':rejected,
              'stages':list(STAGES),'nodes':nodes,'candidates':candidates}
    _write_json(out/'manifest.json',manifest)
    _write_json(out/'feedback.json',{'schema_version':1,'candidates':{}})
    from .pipeline_review import write_review
    write_review(out)
    _write_contact_sheet(out, manifest)
    render_ms=round((perf_counter()-t0)*1000,2)
    metrics={'designs':len(accepted),'sprites':4*len(accepted),'workers':workers,
             'total_ms':render_ms,'slowest_render_ms':max(x['render_ms'] for x in timings)}
    _write_json(out/'timing.json',metrics)
    return metrics


def _write_contact_sheet(out, manifest, limit=12):
    """Reference contact sheet only; never used to create sprite geometry."""
    from PIL import Image, ImageDraw
    out=Path(out)
    items=[(key, info) for key, info in manifest['candidates'].items()
           if info.get('active', True)][:limit]
    width=4*122
    height=max(1,len(items))*151
    img=Image.new('RGB',(width,height),(25,33,43))
    draw=ImageDraw.Draw(img)
    for row,(key,info) in enumerate(items):
        sprites=manifest['nodes'][info['current']]['sprites']
        for col,r in enumerate(sprites):
            with Image.open(out/r['file']) as sprite:
                alpha=Image.fromarray((__import__('numpy').asarray(sprite)!=0).astype('uint8')*255,mode='L')
                tile=Image.new('RGB',(64,128),(0,0,255))
                tile.paste(sprite.convert('RGB'),(0,0),alpha)
            img.paste(tile,(col*122+29,row*151))
            draw.text((col*122+4,row*151+130),f'{key} {r["rotation"]:03d}',fill=(218,225,231))
    img.save(out/'review.png')


def _ancestry_ids(nodes,node_id):
    result=[]
    while node_id is not None:
        result.append(node_id)
        node_id=nodes[node_id]['parent']
    return result


def _ancestry(nodes,node_id):
    return [nodes[i] for i in _ancestry_ids(nodes,node_id)[:-1]]


def branch(out, candidate, stage, *, counter=None, workers=1, buffers=True, parent=None):
    out=Path(out)
    manifest=_load_manifest(out)
    if candidate not in manifest['candidates']:raise ValueError('Unknown candidate')
    info=manifest['candidates'][candidate]
    parent=parent or info['current']
    if parent not in info['history']:raise ValueError('Parent is not in this candidate lineage')
    review=read_feedback(out)['candidates'].get(candidate,{})
    locks=review.get('locks',[])
    model=load_scene(out,parent)
    if not model.parameters.get('feature_pipeline'):
        raise ValueError('Cannot reroll feature from a fabric-only node')
    new=reroll_features(model,stage,counter,locked=locks)
    verdict=_accept(new)
    if not verdict['passes']:raise ValueError('Rerolled feature rejected: '+str(verdict))
    node=_record_node(out,parent,stage,new,verdict)
    if node['id'] not in manifest['nodes']:
        _render_nodes([(node,new)],out,workers,buffers,manifest.get('edge_contrast','off'),
                      manifest.get('semantic_colour','on'),manifest.get('semantic_hues',3),manifest.get('roof_colours','off'),manifest.get('facade_mode','boxes'),manifest.get('renderer','analytic'))
        manifest['nodes'][node['id']]=node
    info['current']=node['id']
    if node['id'] not in info['history']:info['history'].append(node['id'])
    _write_json(out/'manifest.json',manifest)
    return node


def select(out,candidate,node_id):
    manifest=_load_manifest(out)
    if candidate not in manifest['candidates']:raise ValueError('Unknown candidate')
    info=manifest['candidates'][candidate]
    if node_id not in info['history']:raise ValueError('Node not in candidate history')
    if not manifest['nodes'][node_id]['sprites']:
        raise ValueError('Node has no rendered sprites; select a rendered leaf')
    info['current']=node_id
    _write_json(Path(out)/'manifest.json',manifest)
    return manifest['nodes'][node_id]
