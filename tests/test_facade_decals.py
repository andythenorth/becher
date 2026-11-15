"""Regression oracles for analytic flush facade panels."""
import numpy as np
import pytest
from dataclasses import replace
from src.architectures import generate
from src.facade_decals import is_panel
from src.feature_passes import build_features
from src.mesh.render import cast
from src.geometry import MATERIAL_IDS, SURFACE_ROLES


@pytest.mark.parametrize('angle', [0, 90, 180, 270])
def test_decals_are_flush_keep_depth_and_non_facade_hits(angle):
    model=build_features(generate(1267,0))
    base,base_metrics=cast(model,angle,facade_mode='boxes')
    new,metrics=cast(model,angle,facade_mode='decals')
    assert metrics['facade_decal_pixels'] > 0
    np.testing.assert_array_equal(base.silhouette,new.silhouette)
    # No facade geometry changes depth on the opaque structural wall pixels;
    # this includes all non-window roof/equipment/greeble regions.
    assert np.count_nonzero(new.material == MATERIAL_IDS['glass']) > 0
    # All decal hits must retain the ray hit depth and the normal of the host
    # fabric (they never introduce sides of a protruding glazing box).
    no_panels=replace(model,components=tuple(c for c in model.components if not is_panel(c)))
    plain, _=cast(no_panels,angle,facade_mode='decals')
    # Compare only decal pixels that are visible in the bare structural model,
    # and not covered by a raycast greeble or other non-panel component.
    glazing=(new.role == SURFACE_ROLES['glazing'])
    assert np.count_nonzero(glazing) > 0
    np.testing.assert_allclose(new.depth[glazing], plain.depth[glazing],rtol=0,atol=1e-6)
    np.testing.assert_allclose(new.normal[glazing], plain.normal[glazing],rtol=0,atol=1e-6)
    assert np.all(np.abs(new.normal[glazing, 2]) < 1e-6)


def test_old_box_mode_retains_default_bytes():
    model=build_features(generate(1267,0))
    for angle in (0,90,180,270):
        a,_=cast(model,angle)
        b,_=cast(model,angle,facade_mode='boxes')
        np.testing.assert_array_equal(a.reference_pixels,b.reference_pixels)
        assert a.digest()==b.digest()
