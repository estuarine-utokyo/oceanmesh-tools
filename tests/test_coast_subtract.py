import pytest
import numpy as np

from oceanmesh_tools.plot.viz import _subtract_near_openbnd


def _ml_from_paths(paths):
    try:
        from shapely.geometry import LineString
        from shapely.ops import unary_union
    except Exception:
        pytest.skip("shapely not available")
    return unary_union([LineString(p) for p in paths])


def test_subtract_removes_overlap_but_keeps_rest():
    # Open boundary along x-axis from 0..2
    ob_path = [(0.0, 0.0), (2.0, 0.0)]
    ml = _ml_from_paths([ob_path])
    tol = 0.05
    eraser = ml.buffer(tol, cap_style=2, join_style=2)
    # Coastline ring that includes a segment overlapping the open boundary and one far away
    ring_overlap = [(0.5, 0.0), (1.5, 0.0)]
    ring_far = [(10.0, 10.0), (11.0, 10.0)]
    out = _subtract_near_openbnd([ring_overlap, ring_far], eraser)
    # The overlapping segment should be removed (fully inside eraser), far should remain
    assert any(np.allclose(seg, np.asarray(ring_far)) for seg in map(np.asarray, out))
    assert not any(np.allclose(seg, np.asarray(ring_overlap)) for seg in map(np.asarray, out))

