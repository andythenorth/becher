"""Immutable visible-surface data from the analytic ray-caster.

A g-buffer is the 1x visible projection, not a 3D modelling interchange format.
It records exactly what the ray-caster resolved, without generating new shapes.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import numpy as np

MATERIAL_IDS = {
    'metal': 1, 'roof': 2, 'concrete': 3,
    'frame': 4, 'glass': 5, 'chimney': 6, 'pipe': 7, 'tank_wall': 8
}

# Explicit 1x surface classes for downstream non-destructive treatments.
# These are *pixel-visible* classes, independent of the parent grammar tree.
SURFACE_ROLES = {
    'background': 0, 'wall': 1, 'roof_top': 2,
    'roof_fascia': 3, 'roof_underside': 4,
    'glazing': 5, 'detail': 6, 'foundation': 7,
    'sawtooth_sheet': 8,
}


@dataclass(frozen=True)
class VisibleSurfaces:
    material: np.ndarray
    normal: np.ndarray
    depth: np.ndarray
    primitive: np.ndarray
    reference_pixels: np.ndarray
    role: np.ndarray | None = None

    @classmethod
    def read(cls, source):
        with np.load(source, allow_pickle=False) as data:
            # Materialised copies make it safe to close the underlying ZIP.
            arrays = [np.array(data[k], copy=True) for k in
                      ('material', 'normal', 'depth', 'primitive', 'shaded')]
            role = np.array(data['role'], copy=True) if 'role' in data else None
        result = cls(*arrays, role=role)
        result.validate()
        return result

    def validate(self):
        expected = (128, 64)
        if self.material.shape != expected or self.primitive.shape != expected or self.reference_pixels.shape != expected:
            raise ValueError('All indexed buffers must be 128x64')
        if self.normal.shape != (*expected, 3) or self.depth.shape != expected:
            raise ValueError('Normals/depth dimensions are wrong')
        if not np.array_equal(self.material == 0, self.reference_pixels == 0):
            raise ValueError('Material mask differs from protected silhouette')
        visible = self.material > 0
        if self.role is not None:
            if self.role.shape != expected or self.role.dtype != np.uint8:
                raise ValueError('Surface role buffer must be 128x64 uint8')
            if not np.array_equal(self.role > 0, visible):
                raise ValueError('Surface role mask differs from silhouette')
        if not np.all(np.isfinite(self.normal[visible])):
            raise ValueError('Visible normals contain non-finite values')
        if not np.all(np.isfinite(self.depth[visible])):
            raise ValueError('Visible ray depth contains non-finite values')
        return True

    def digest(self):
        h = hashlib.sha256()
        for x in (self.material,self.normal,self.depth,self.primitive,self.reference_pixels):
            h.update(str(x.shape).encode())
            h.update(str(x.dtype).encode())
            h.update(x.tobytes())
        return h.hexdigest()

    @property
    def silhouette(self):
        return self.material > 0
