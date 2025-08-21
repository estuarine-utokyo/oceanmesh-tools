from pathlib import Path
import numpy as np

from oceanmesh_tools.io.fort14 import parse_fort14
from oceanmesh_tools.plot.viz import _build_open_boundary_segments


def write_two_boundary_f14(tmp_path: Path) -> Path:
    # Minimal fort14 with 3 nodes, 1 triangle, and two open boundaries
    # Open boundaries use nodes-in-boundary style with counts
    content = """Tiny two boundaries
1 3
1 0.0 0.0 -5.0
2 1.0 0.0 -5.0
3 0.0 1.0 -5.0
1 3 1 2 3
2
2
1
2
2
2
3
0
0
"""
    p = tmp_path / "two_open.fort14"
    p.write_text(content)
    return p


def test_open_boundary_segments_are_separate(tmp_path: Path):
    f14 = write_two_boundary_f14(tmp_path)
    mesh = parse_fort14(f14)
    segs = _build_open_boundary_segments(mesh)
    # Expect two separate polylines
    assert len(segs) == 2
    a, b = segs
    assert a.shape[1] == 2 and b.shape[1] == 2
    # Ensure last of first is not equal to first of second to avoid accidental join
    assert not np.allclose(a[-1], b[0])

