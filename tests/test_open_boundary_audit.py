from pathlib import Path

import numpy as np

from oceanmesh_tools.io.fort14 import parse_fort14
from oceanmesh_tools.mesh.boundary import (
    classify_outer_vs_holes,
    multi_from_paths,
    hausdorff,
    signed_distance_to_hull,
    compute_outer_loops,
)


def test_open_boundary_coincides_with_hull_after_snap():
    m = parse_fort14(Path('tests/fixtures/segments.fort14'))
    nodes_xy = {nid: (x, y) for nid, x, y, _ in m.nodes}
    loops = compute_outer_loops(m.elements)
    outer, holes = classify_outer_vs_holes(loops, nodes_xy)
    # Build geometries
    hull_ml = multi_from_paths(outer, nodes_xy)
    # OB geometry from nodes
    ob_paths = []
    for b in m.open_boundaries:
        ob_paths.append([(nodes_xy[n][0], nodes_xy[n][1]) for n in b])
    try:
        from shapely.geometry import MultiLineString
        from shapely.ops import unary_union
    except Exception:
        return  # skip if shapely unavailable
    ob_ml = MultiLineString(ob_paths)
    dH = hull_ml.hausdorff_distance(ob_ml)
    # Should be small for this synthetic case
    assert dH < 5e-3
    # inward offset (most negative) should be <= 0
    poly = None
    try:
        from shapely.geometry import Polygon
        poly = Polygon([(nodes_xy[i][0], nodes_xy[i][1]) for i in outer[0]])
    except Exception:
        pass
    if poly is not None:
        smin = signed_distance_to_hull(ob_ml, poly)
        assert smin <= 0.0
