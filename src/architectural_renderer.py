"""Compatibility import path for pre-0.16 clients.

No analytic scene construction or raycasting survives in the active package.
Use becher.mesh.compile and becher.mesh.render for new code.
"""
from .mesh.render import cast
from .mesh.io import save

__all__ = ('cast', 'save')
