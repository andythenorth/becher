"""Optional material references cannot mutate Becher's original render path."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image
import pytest

from src.colour_suggestions import (
    STYLES, ROTATIONS, recolour, render,
    FLAT_ROOF_BASE, FLAT_ROOF_DARK, FLAT_ROOF_LIGHT,
    PITCHED_ROOF_MAX_Z,
)
from src.geometry import MATERIAL_IDS
from src.mesh.compile import compile_scene
from src.mesh.render import cast_mesh
from src.palette import load_palette, ramp
from src.lighting import RAMPS, SUN_FIVE, shade
from src.mesh.camera import rotate_xy
from src.composition import load_part, rigid_place


def sample_scene():
    return {"shapes": [
        {"id": "foundation", "type": "box", "material": "concrete",
         "bounds": [.05, .05, 0, .95, .95, .04]},
        {"id": "building_walls", "type": "box", "material": "wall",
         "bounds": [.2, .2, .04, .8, .7, .38]},
        {"id": "building_roof", "type": "box", "material": "roof",
         "bounds": [.17, .17, .37, .83, .73, .43]},
        {"id": "building_window", "type": "box", "material": "glass",
         "bounds": [.3, .185, .17, .5, .205, .27]},
        {"id": "tower", "type": "cylinder", "material": "tank_wall",
         "bounds": [.82, .74, .04, .92, .84, .34]},
    ]}


def test_colour_guides_preserve_silhouette_and_all_other_materials():
    mesh = compile_scene(sample_scene())
    surface, _ = cast_mesh(mesh, 90)
    original = surface.reference_pixels.copy()
    walls = surface.material == MATERIAL_IDS['wall']
    roofs = surface.material == MATERIAL_IDS['roof']
    flat_top = (roofs & (surface.role == 2) &
                (surface.normal[..., 2] >= PITCHED_ROOF_MAX_Z))
    flat_primitives = np.unique(surface.primitive[flat_top])
    flat_fascia = (roofs & (surface.role == 3) &
                   (np.abs(surface.normal[..., 2]) <= 0.08) &
                   np.isin(surface.primitive, flat_primitives))
    other_roofs = roofs & ~flat_top & ~flat_fascia
    vessels = surface.material == MATERIAL_IDS['tank_wall']
    unchanged = ~(walls | roofs | vessels)
    assert walls.any() and roofs.any() and (surface.material == MATERIAL_IDS['glass']).any()
    for style, config in STYLES.items():
        output = recolour(surface, 90, style)
        assert output.dtype == np.uint8
        assert np.array_equal(output == 0, original == 0)
        assert np.array_equal(output[unchanged], original[unchanged])
        assert set(np.unique(output[walls])) <= set(config['wall'])
        assert set(np.unique(output[other_roofs])) <= set(config['roof'])
        assert set(np.unique(output[flat_top])) <= {
            FLAT_ROOF_DARK, FLAT_ROOF_BASE, FLAT_ROOF_LIGHT}
        assert np.all(output[flat_fascia] == FLAT_ROOF_BASE)
        assert set(np.unique(output[vessels])) <= set(config['tank_wall'])
    assert np.array_equal(surface.reference_pixels, original)
    with pytest.raises(ValueError, match='Unknown colour suggestion'):
        recolour(surface, 90, 'unknown')



def test_all_colour_ramps_are_increasing_in_brightness():
    """No shading ramp may cross into another DOS palette colour family."""
    palette = np.asarray(load_palette(), dtype=np.float64).reshape(256, 3)
    luma = palette @ np.array([0.2126, 0.7152, 0.0722])
    for style, spec in STYLES.items():
        for material in ('wall', 'roof', 'tank_wall', 'pipe'):
            indices = spec[material]
            assert np.all(np.diff(luma[list(indices)]) > 0), (style, material, indices)


def test_four_rotations_all_styles_native_indexed_pngs():
    with TemporaryDirectory() as scratch:
        root = Path(scratch)
        source = root / 'scene.json'
        source.write_text(json.dumps(sample_scene()), encoding='utf-8')
        target = root / 'suggestions'
        result = render(source, target)
        assert len(result['styles']) == 5
        assert result['palette'] == 'data/ttd-dos.act'
        assert len(list(target.glob('*/r*.png'))) == len(STYLES) * len(ROTATIONS)
        palette = load_palette()
        mesh = compile_scene(sample_scene())
        for angle in ROTATIONS:
            baseline, _ = cast_mesh(mesh, angle)
            for style in STYLES:
                path = target / style / f'r{angle:03d}.png'
                with Image.open(path) as image:
                    assert image.mode == 'P'
                    assert image.size == (64, 128)
                    assert image.getpalette()[:768] == palette
                    assert image.info.get('transparency', 0) == 0
                    assert np.array_equal(np.asarray(image) == 0, baseline.reference_pixels == 0)
        assert json.loads((target / 'suggestions.json').read_text()) == result
        assert json.loads(source.read_text()) == sample_scene()
        with pytest.raises(FileExistsError):
            render(source, target)


def test_source_assemblies_directly_encode_building_versus_equipment_materials():
    from src.composition import load_part
    cases = {
        'enclosed_silo_block': {'mass_0': 'wall', 'mass_1': 'roof',
                                'mass_7': 'equipment'},
        'storage_tank_horizontal_high_01': {'vessel_0': 'tank_wall',
                                            'dorsal_pipe_0': 'pipe'},
        'silo_short': {'store_1_body': 'tank_wall',
                       'store_1_hopper': 'tank_wall'},
        'wrapped_process_rect_01_01': {'body_0': 'wall', 'coping_0': 'roof',
                                       'loop_0': 'pipe'},
        'liquid_pipe_terminal_inlet_01': {'pump_house': 'wall',
                                          'roof': 'roof', 'pipe0_0_0': 'pipe'},
    }
    for name, expected in cases.items():
        shapes = {shape['id']: shape['material'] for shape in load_part(name)['shapes']}
        for shape, material in expected.items():
            assert shapes[shape] == material, (name, shape, shapes[shape])


def test_all_materials_in_installed_assemblies_are_defined_and_compile():
    from src.composition import component_catalogue, load_part
    from src.mesh.compile import compile_scene
    for name in component_catalogue():
        part = load_part(name)
        assert part['shapes']
        for shape in part['shapes']:
            assert shape['material'] in MATERIAL_IDS, (name, shape['id'])
        compile_scene({'shapes':part['shapes']})


def test_recolours_the_enclosed_silo_building_and_horizontal_storage_vessel():
    from src.composition import load_part, rigid_place
    parts = [('enclosed_silo_block', (.36, .5)),
             ('storage_tank_horizontal_high_01', (.72, .5))]
    scene = {'shapes': [shape for name, centre in parts
                        for shape in rigid_place(load_part(name), name+'_', centre)]}
    mesh = compile_scene(scene)
    surfaces, _ = cast_mesh(mesh, 0)
    wall = surfaces.material == MATERIAL_IDS['wall']
    tank = surfaces.material == MATERIAL_IDS['tank_wall']
    assert wall.any() and tank.any()
    for style in STYLES:
        result = recolour(surfaces, 0, style)
        assert np.count_nonzero(result[wall] != surfaces.reference_pixels[wall]) > 40
        # The existing green tank ramp is a valid suggestion for brick walls.
        # Do not demand a colour difference when its indices are identical.
        reference_ramp = ramp(RAMPS['tank_wall'], load_palette())
        if tuple(STYLES[style]['tank_wall']) == tuple(reference_ramp):
            assert np.array_equal(result[tank], surfaces.reference_pixels[tank])
        else:
            assert np.count_nonzero(result[tank] != surfaces.reference_pixels[tank]) > 20
        assert np.array_equal(result == 0, surfaces.reference_pixels == 0)


@pytest.mark.parametrize('component', [
    'storage_tank_full_tile',
    'storage_tank_horizontal_low_01',
    'liquid_pipe_bund_rect_side_06',
])
@pytest.mark.parametrize('rotation', ROTATIONS)
def test_recolour_uses_exact_default_material_shading_bands(component, rotation):
    """Every tank pixel must retain its original eight-band shade assignment."""
    scene = {'shapes': rigid_place(load_part(component), '', (.5, .5))}
    surfaces, _ = cast_mesh(compile_scene(scene), rotation)
    tank = surfaces.material == MATERIAL_IDS['tank_wall']
    assert tank.any()
    palette = load_palette()
    default = ramp(RAMPS['tank_wall'], palette)
    assert len(default) == 8 and len(set(default)) == 8
    original = surfaces.reference_pixels.copy()
    assert np.array_equal(
        shade(surfaces, palette, light=rotate_xy(SUN_FIVE, rotation)), original)
    for style, spec in STYLES.items():
        actual = recolour(surfaces, rotation, style)
        assert len(spec['tank_wall']) == len(default)
        for band, default_index in enumerate(default):
            mask = tank & (original == default_index)
            assert np.all(actual[mask] == spec['tank_wall'][band]), (
                component, rotation, style, band)
        assert np.array_equal(actual == 0, original == 0)


def test_shader_rejects_wrong_length_or_invalid_palette_index():
    surfaces, _ = cast_mesh(compile_scene(sample_scene()), 0)
    palette = load_palette()
    with pytest.raises(ValueError, match='Invalid indexed ramp'):
        shade(surfaces, palette, index_ramps={'tank_wall': (16, 18, 20, 22)})
    with pytest.raises(ValueError, match='Invalid DOS palette indices'):
        shade(surfaces, palette, index_ramps={'roof': (0, 4, 6, 8)})
