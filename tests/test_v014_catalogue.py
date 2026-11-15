"""v0.14 active catalogue contract, distinct from archived renderer regression."""
from pathlib import Path
from src.architectures import generate, library
from src.architectural_validation import validate
from src.feature_passes import build_features, validate_features
from src.mesh.render import cast
from src.geometry import VisibleSurfaces

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (
    'broad_high_roof_hall', 'low_production_shed',
    'flat_roof_factory_block', 'multi_slope_industrial_hall',
    'broad_brick_roof_hall', 'low_masonry_works',
)

def test_six_approved_default_families():
    assert tuple(f['id'] for f in library()) == EXPECTED

def test_approved_family_mass_properties_and_validity():
    for i in range(120):
        b=generate(1267,i)
        assert b.family==EXPECTED[i%6]
        assert validate(b)['passes'], (i,validate(b))
        main=next(c for c in b.components if c.id=='main')
        x0,y0,z0,x1,y1,z1=main.bounds
        assert z1-z0 < max(x1-x0,y1-y0)
        assert (x1-x0)>.55 or (y1-y0)>.65
        if i%6 in (0,3,4):
            assert (x0,x1)==(0,1)
        if i%6==1:
            assert (y0,y1)==(0,1)
        full=build_features(b)
        assert validate_features(full)['passes'], (i,validate_features(full))

def test_four_view_native_sprites_all_families():
    for i in range(6):
        model=build_features(generate(1267,i))
        for r in (0,90,180,270):
            surface,_=cast(model,r,facade_mode='decals')
            assert surface.validate()
            assert surface.reference_pixels.shape==(128,64)
