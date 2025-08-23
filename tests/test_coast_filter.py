import pytest

from oceanmesh_tools.plot.viz import _filter_coast_rings_near_openbnd


def _maybe_build_multiline(paths):
    try:
        from shapely.geometry import LineString
        from shapely.ops import unary_union
    except Exception:
        pytest.skip("shapely not available")
    return unary_union([LineString(p) for p in paths])


def test_filter_coast_rings_near_openbnd_basic():
    # One ring identical to open boundary, one far away
    open_path = [(0.0, 0.0), (1.0, 0.0)]
    far_ring = [(10.0, 10.0), (11.0, 10.0), (11.0, 11.0)]
    rings = [open_path, far_ring]
    ml = _maybe_build_multiline([open_path])

    out = _filter_coast_rings_near_openbnd(rings, ml, tol=0.01)
    # Expect that the identical ring is filtered and the far one remains
    assert out == [far_ring]

