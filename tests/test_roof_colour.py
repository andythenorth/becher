import numpy as np
from src.roof_colour import apply, roof_assignments
from src.architectures import generate, library
from src.mesh.render import cast
from src.palette import load_palette
from src.edge_contrast import apply as edges
from src.semantic_colour import apply as wall_colour
from src.geometry import MATERIAL_IDS


def test_roof_colour_only_changes_secondary_roof_pixels():
    model=generate(1267,0,families=library())
    palette=load_palette()
    surfaces,metrics=cast(model,90)
    shaded,mask=edges(surfaces,palette)
    walls,_=wall_colour(surfaces,metrics['primitive_components'],model,palette,
                        base_pixels=shaded,contrast_mask=mask)
    original,_=apply(surfaces,metrics['primitive_components'],model,palette,
                     enabled=False,base_pixels=walls,contrast_mask=mask)
    altered,_=apply(surfaces,metrics['primitive_components'],model,palette,
                    enabled=True,base_pixels=walls,contrast_mask=mask)
    changed=original!=altered
    assert changed.any()
    assert np.all(surfaces.material[changed]==MATERIAL_IDS['roof'])
    assert np.array_equal(original!=0,altered!=0)


def test_main_monitor_roof_inherits_primary_hue():
    families=library()
    for i in range(12):
        model=generate(1267,i,families=families)
        labels=roof_assignments(model)
        for c in model.components:
            if c.role=='roof' and c.parent=='main:monitor':
                assert labels[c.id]==0
