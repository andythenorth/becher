"""Immutable scene compiler: authored components -> material-tagged triangle soup.

No camera, shading or raycaster imports. All coordinates remain in world space.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .solids import box, cylinder, roof
from .author import scene_faces, beam_between
from ..geometry import MATERIAL_IDS

@dataclass(frozen=True)
class Mesh:
    vertices: np.ndarray    # (n,3,3), world coordinates
    normals: np.ndarray     # (n,3,3), world coordinates
    materials: np.ndarray   # (n,)
    component_ids: np.ndarray  # (n,) 1-based IDs
    component_names: tuple[str,...]

    def __post_init__(self):
        if self.vertices.shape != self.normals.shape or self.vertices.ndim != 3 or self.vertices.shape[1:]!=(3,3):
            raise ValueError('Expected triangle and normal arrays (n,3,3)')
        n = len(self.vertices)
        if self.materials.shape != (n,) or self.component_ids.shape != (n,):
            raise ValueError('Material and component buffers must match triangles')
        if not np.all(np.isfinite(self.vertices)) or not np.all(np.isfinite(self.normals)):
            raise ValueError('Non-finite mesh coordinates/normals')
        for array in (self.vertices,self.normals,self.materials,self.component_ids):
            array.setflags(write=False)


def compile_building(building, *, facade_mode="boxes"):
    parts=[]
    parent_material={c.id:c.material for c in building.components if c.role in ('fabric','monitor')}
    if facade_mode not in ('boxes', 'decals'):
        raise ValueError('facade_mode must be boxes or decals')
    if facade_mode == 'decals':
        from ..facade_decals import is_panel
    for component in building.components:
        if facade_mode == 'decals' and is_panel(component):
            continue
        if component.role=='roof':
            parts.extend(roof(component,parent_material.get(component.parent,'metal')))
        elif component.shape=='box':
            parts.extend(box(component.bounds,component.material,component.id))
        elif component.shape=='beam':
            spec=building.parameters.get('beam_segments',{}).get(component.id)
            if spec is None:
                raise ValueError(f'Missing beam geometry: {component.id}')
            parts.extend(beam_between(spec['start'],spec['end'],spec['thickness'],material=component.material,part=component.id))
        elif component.shape=='cylinder':
            parts.extend(cylinder(component.bounds,component.material,component.id))
            if component.role=='stack':
                x0,y0,z0,x1,y1,z1=component.bounds
                rx=(x1-x0)*.5;ry=(y1-y0)*.5
                cx=(x0+x1)*.5;cy=(y0+y1)*.5
                parts.extend(cylinder((cx-rx*1.2,cy-ry*1.2,z1-.018,
                                       cx+rx*1.2,cy+ry*1.2,z1+.017),
                                      'chimney',component.id+':cap'))
        else:
            raise ValueError(f'Unsupported render geometry {component.id}: {component.shape}')
    return compile_faces(parts)


def compile_faces(parts):
    """One frozen mesh contract for buildings, arbitrary sweeps and imported triangles."""
    if not parts:
        raise ValueError('Geometry has no triangles')
    names=tuple(dict.fromkeys(f.part for f in parts))
    ids={name:i+1 for i,name in enumerate(names)}
    return Mesh(np.stack([f.xyz for f in parts]),
                np.stack([f.normals for f in parts]),
                np.array([MATERIAL_IDS[f.material] for f in parts],np.uint8),
                np.array([ids[f.part] for f in parts],np.uint16),names)


def compile_scene(scene):
    """JSON scene → frozen Mesh; independent of Becher grammar and the renderer."""
    return compile_faces(scene_faces(scene))


def save_mesh(mesh,path):
    """Frozen uncompressed arrays: no geometry import required for reading."""
    np.savez_compressed(path, vertices=mesh.vertices, normals=mesh.normals,
                        materials=mesh.materials, component_ids=mesh.component_ids,
                        component_names=np.array(mesh.component_names,dtype='U128'))


def load_mesh(path):
    with np.load(path,allow_pickle=False) as data:
        return Mesh(*(np.array(data[key],copy=True) for key in
                      ('vertices','normals','materials','component_ids')),
                    tuple(data['component_names'].tolist()))
