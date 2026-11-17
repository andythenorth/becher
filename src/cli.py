"""Supported Becher CLI: a single generation path and independent artist passes.

Historical generators and experimental texture-browser commands are not part of
this interface. Grammar generation itself remains accessible through the model API.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image

from .geometry import VisibleSurfaces
from .palette import load_palette, open_indexed, save_indexed
from .lighting import shade


def main(argv=None):
    parser=argparse.ArgumentParser(prog='becher')
    sub=parser.add_subparsers(dest='cmd',required=True)

    family_list=sub.add_parser('families',help='list the available candidate families as JSON')
    family_list.add_argument('--grammars')

    sub.add_parser('scenes',help='list installed geometry scenes from data/scenes')
    authored=sub.add_parser('render-scene',help='render an installed geometry scene at four rotations')
    authored.add_argument('--scene',required=True,help='scene ID from the scenes command')
    authored.add_argument('--out',required=True)

    authored_batch=sub.add_parser('render-scenes',help='render a batch of installed geometry scenes')
    authored_batch.add_argument('--scene',action='append',required=True,help='repeat for each scene ID')
    authored_batch.add_argument('--out',required=True)
    authored_batch.add_argument('--workers',type=int)

    sub.add_parser('components', help='list live assembly components')
    component = sub.add_parser('render-component', help='render an assembly component at four rotations')
    component.add_argument('--component', required=True, help='component ID from the components command')
    component.add_argument('--out', required=True)

    sheets = sub.add_parser('component-sheets', help='render labelled component sheets by vocabulary')
    sheets.add_argument('--out', required=True, help='output directory for PNG sheets')

    sub.add_parser('vocabularies',help='list installed assembly vocabularies')
    compose = sub.add_parser('compose', help='assemble and render 16 seeded tiles')
    reroll_tile = sub.add_parser('reroll-tile', help='replace one row of a composition batch')
    for command in (compose, reroll_tile):
        command.add_argument('--vocabulary', action='append', required=True)
        command.add_argument('--seed', type=int, default=1267)
        command.add_argument('--silhouette', choices=('low', 'high'), default='low')
        command.add_argument('--out', required=True)
    reroll_tile.add_argument('--row', type=int, required=True)
    reroll_tile.add_argument('--revision', type=int, required=True)
    reroll_tile.add_argument('--current', action='append', required=True,
                             help='current composition ID, repeated for each row in order')

    bake=sub.add_parser('bake-scene',help='compile a renderer-independent geometry JSON scene to frozen mesh')
    bake.add_argument('--input',required=True)
    bake.add_argument('--out',required=True)

    render_mesh=sub.add_parser('render-mesh',help='raycast frozen mesh at four rotations')
    render_mesh.add_argument('--mesh',required=True)
    render_mesh.add_argument('--out',required=True,help='output directory')

    rer=sub.add_parser('reroll',help='reroll one feature pass of a saved candidate')
    rer.add_argument('--run',default='output/pipeline')
    rer.add_argument('--candidate',required=True)
    rer.add_argument('--stage',required=True,choices=('windows','doors','equipment','greeble'))
    rer.add_argument('--counter',type=int)

    ev=sub.add_parser('evaluate',help='deterministic validity and visual-diversity report')
    ev.add_argument('--run',default='output/pipeline')
    ev.add_argument('--similarity',type=float,default=.94)
    ev.add_argument('--min-pixels',type=int,default=250)

    vt=sub.add_parser('vote',help='accept/reject candidates without browser UI')
    vt.add_argument('--run',default='output/pipeline')
    vt.add_argument('--accept',action='append',default=[])
    vt.add_argument('--reject',action='append',default=[])
    vt.add_argument('--undecided',action='append',default=[])

    refill=sub.add_parser('refill',help='replace rejected candidates, preserve history')
    refill.add_argument('--run',default='output/pipeline')
    refill.add_argument('--workers',type=int,default=4)
    refill.add_argument('--grammars')
    refill.add_argument('--no-buffers',action='store_true')
    refill.add_argument('--dry-run',action='store_true')

    sel=sub.add_parser('selection',help='export approved or active indexed sprites')
    sel.add_argument('--run',default='output/pipeline')
    sel.add_argument('--out',default='output/selected')
    sel.add_argument('--mode',choices=('approved','active'),default='approved')
    sel.add_argument('--no-buffers',action='store_true')

    handoff=sub.add_parser('handoff',help='export candidate geometry and paint-over data')
    handoff.add_argument('--run',default='output/pipeline')
    handoff.add_argument('--candidate',action='append')
    handoff.add_argument('--approved-only',action='store_true')
    handoff.add_argument('--out',default='output/handoff')
    handoff.add_argument('--presets')
    handoff.add_argument('--profile',action='append')
    handoff.add_argument('--sun',nargs=3,type=float,metavar=('X','Y','Z'))

    grade=sub.add_parser('grade',help='branch lighting/material treatment from saved geometry')
    grade.add_argument('--handoff',default='output/handoff')
    grade.add_argument('--candidate')
    grade.add_argument('--name',default='variant')
    grade.add_argument('--presets')
    grade.add_argument('--profile',action='append')
    grade.add_argument('--sun',nargs=3,type=float,metavar=('X','Y','Z'))

    edges=sub.add_parser('edges',help='edge contrast on saved geometry without overwriting source')
    edges.add_argument('--geometry',required=True)
    edges.add_argument('--out',required=True)
    edges.add_argument('--mode',choices=('on','off'),default='on')
    edges.add_argument('--mask')

    relight=sub.add_parser('relight',help='rerender lighting from saved geometry')
    relight.add_argument('--geometry',required=True)
    relight.add_argument('--out',required=True)
    relight.add_argument('--light',nargs=3,type=float,default=(.94,.64,.23))

    rgba=sub.add_parser('import-paint',help='quantise Photoshop RGBA paint to indexed sprite')
    rgba.add_argument('--geometry',required=True)
    rgba.add_argument('--source',required=True)
    rgba.add_argument('--art',required=True)
    rgba.add_argument('--out',required=True)
    rgba.add_argument('--exact',action='store_true')

    pnt=sub.add_parser('paint',help='composite a saved indexed paint layer')
    pnt.add_argument('--geometry',required=True)
    pnt.add_argument('--source',required=True)
    pnt.add_argument('--layer',required=True)
    pnt.add_argument('--out',required=True)

    args=parser.parse_args(argv)
    if args.cmd=='families':
        from .sampling import catalogue
        primary, ancillary = catalogue(args.grammars)
        value = {
            category: [{'id': item['id'], 'label': item.get('label', item['id'])} for item in group]
            for category, group in (('primary', primary), ('ancillary', ancillary))
        }
    elif args.cmd=='scenes':
        from .authored_scenes import list_scenes
        value=list_scenes()
    elif args.cmd=='render-scene':
        from .authored_scenes import render_scene
        try:
            value=render_scene(args.scene,args.out)
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.error(str(error))
    elif args.cmd=='render-scenes':
        from .authored_scenes import render_scenes
        try:
            value=render_scenes(args.scene,args.out,args.workers)
        except (ValueError, OSError) as error:
            parser.error(str(error))
    elif args.cmd == 'components':
        from .composition import list_components
        value = list_components()
    elif args.cmd == 'render-component':
        from .composition import render_component
        try:
            value = render_component(args.component, args.out)
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.error(str(error))
    elif args.cmd == 'component-sheets':
        from .component_sheets import render_sheets
        try:
            value = render_sheets(args.out)
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.error(str(error))
    elif args.cmd=='vocabularies':
        from .composition import vocabularies
        value=sorted(vocabularies())
    elif args.cmd in ('compose', 'reroll-tile'):
        from .composition import draft, redraft, render_draft
        try:
            brief = (args.vocabulary, args.seed, args.silhouette)
            if args.cmd == 'compose':
                scenes = draft(*brief)
            else:
                scenes = redraft(*brief, args.current, args.row, args.revision)
            value = render_draft(scenes, args.out)
        except (ValueError, OSError) as error:
            parser.error(str(error))
    elif args.cmd=='bake-scene':
        from .mesh.compile import compile_scene, save_mesh
        path=Path(args.out)
        if path.exists():parser.error('Output already exists; refusing to overwrite mesh')
        path.parent.mkdir(parents=True,exist_ok=True)
        mesh=compile_scene(json.loads(Path(args.input).read_text()))
        save_mesh(mesh,path)
        value={'mesh':str(path),'triangles':len(mesh.vertices)}
    elif args.cmd=='render-mesh':
        from .mesh.compile import load_mesh
        from .mesh.render import cast_mesh
        from .mesh.io import save
        mesh=load_mesh(args.mesh)
        path=Path(args.out)
        if path.exists():parser.error('Output directory already exists')
        path.mkdir(parents=True)
        sprites=[]
        for angle in (0,90,180,270):
            surface,metrics=cast_mesh(mesh,angle)
            target=path/f'r{angle:03d}.png'
            save(surface,target,buffers=True)
            sprites.append({'rotation':angle,'file':target.name,'occupied_pixels':metrics['occupied_pixels']})
        value={'sprites':sprites,'triangles':len(mesh.vertices)}
    elif args.cmd=='reroll':
        from .pipeline import branch
        value=branch(args.run,args.candidate,args.stage,counter=args.counter)
    elif args.cmd=='evaluate':
        from .selection import evaluate
        value=evaluate(args.run,near_duplicate_iou=args.similarity,min_pixels=args.min_pixels)['summary']
    elif args.cmd=='vote':
        from .selection import vote
        value=vote(args.run,accept=args.accept,reject=args.reject,undecided=args.undecided)
    elif args.cmd=='refill':
        from .selection import refill
        value=refill(args.run,workers=args.workers,grammar_file=args.grammars,
                     buffers=not args.no_buffers,dry_run=args.dry_run)
    elif args.cmd=='selection':
        from .selection import export_selection
        value=export_selection(args.run,args.out,mode=args.mode,buffers=not args.no_buffers)
    elif args.cmd=='handoff':
        from .handoff import prepare, DEFAULT_PROFILES
        from .lighting import SUN_FIVE
        candidates=args.candidate
        if args.approved_only:
            if candidates:
                parser.error('--approved-only cannot be combined with --candidate')
            from .pipeline import read_feedback,_load_manifest
            manifest=_load_manifest(args.run)
            feedback=read_feedback(args.run)['candidates']
            candidates=[key for key,info in sorted(manifest['candidates'].items())
                        if info.get('active',True) and feedback.get(key,{}).get('vote')=='yes']
            if not candidates:
                parser.error('No active approved candidates')
        value=prepare(args.run,args.out,candidates,preset_path=args.presets,
                      profile_names=args.profile or DEFAULT_PROFILES,light=args.sun or SUN_FIVE)
    elif args.cmd=='grade':
        from .handoff import grade,DEFAULT_PROFILES
        from .lighting import SUN_FIVE
        value=grade(args.handoff,candidate=args.candidate,
                    profile_names=args.profile or DEFAULT_PROFILES,light=args.sun or SUN_FIVE,
                    preset_path=args.presets,name=args.name)
    elif args.cmd=='edges':
        from .edge_contrast import apply
        src=Path(args.geometry).resolve();out=Path(args.out).resolve()
        if out.exists() or out==src:
            parser.error('--out must be a new destination')
        mask_path=Path(args.mask).resolve() if args.mask else None
        if mask_path is not None and (mask_path.exists() or mask_path in (src,out)):
            parser.error('--mask must be a new destination')
        surf=VisibleSurfaces.read(src)
        pixels,mask=apply(surf,load_palette(),enabled=args.mode=='on')
        save_indexed(out,pixels,load_palette())
        if mask_path:
            mask_path.parent.mkdir(parents=True,exist_ok=True)
            Image.fromarray(mask,mode='L').save(mask_path)
        value={'output':str(out),'changed_pixels':int(np.count_nonzero(mask))}
    elif args.cmd=='relight':
        surf=VisibleSurfaces.read(args.geometry)
        save_indexed(args.out,shade(surf,load_palette(),args.light),load_palette())
        value={'output':args.out}
    elif args.cmd=='import-paint':
        from .paint import apply_rgba
        palette=load_palette()
        surf=VisibleSurfaces.read(args.geometry)
        source=Path(args.source).resolve();art=Path(args.art).resolve();out=Path(args.out).resolve()
        if out in (source,art):
            raise ValueError('Cannot overwrite source or artist artwork')
        pixels=apply_rgba(surf,open_indexed(source,palette),art,palette,exact=args.exact)
        if out.exists():
            if not np.array_equal(open_indexed(out,palette),pixels):
                raise ValueError('Existing destination differs')
        else:
            save_indexed(out,pixels,palette)
        value={'output':str(out)}
    elif args.cmd=='paint':
        from .paint import apply
        pal=load_palette();surf=VisibleSurfaces.read(args.geometry)
        pixels=apply(surf,open_indexed(args.source,pal),args.layer,pal)
        save_indexed(args.out,pixels,pal)
        value={'output':args.out}
    print(json.dumps(value,indent=2))


if __name__=='__main__':
    main()
