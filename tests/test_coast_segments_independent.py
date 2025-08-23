import numpy as np

from oceanmesh_tools.plot.boundary_fast import segments_to_linecollection


def test_segments_drawn_independently():
    # Two far apart segments should yield 2 independent lines in the collection
    nodes_xy = np.array([
        [0.0, 0.0],  # 0
        [1.0, 0.0],  # 1
        [100.0, 100.0],  # 2
        [101.0, 100.0],  # 3
    ], dtype=float)
    segments = [
        [0, 1],
        [2, 3],
    ]
    lc, n = segments_to_linecollection(nodes_xy, segments, color='r', zorder=5)
    assert n == 2
    segs = lc.get_segments()
    assert isinstance(segs, list) and len(segs) == 2
    # Ensure no concatenation: endpoints should match the two segments
    assert np.allclose(segs[0][0], nodes_xy[0]) and np.allclose(segs[0][-1], nodes_xy[1])
    assert np.allclose(segs[1][0], nodes_xy[2]) and np.allclose(segs[1][-1], nodes_xy[3])

