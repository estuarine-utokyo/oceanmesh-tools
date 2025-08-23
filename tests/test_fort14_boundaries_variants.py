from pathlib import Path

import numpy as np

from oceanmesh_tools.io.fort14_boundaries import parse_fort14_boundaries


def _write_mesh(path: Path, header_variant: str) -> None:
    """Write a tiny fort.14 file with one open boundary and one land boundary.

    header_variant: 'same_line' uses "m ib" on one line; 'split' places ib on next line.
    """
    # Minimal 3 nodes, 2 elements
    lines = []
    lines.append("Tiny test")
    lines.append("2 3")
    # nodes: id x y depth
    lines.append("1 0.0 0.0 -1.0")
    lines.append("2 1.0 0.0 -1.0")
    lines.append("3 1.0 1.0 -1.0")
    # elements (triangles)
    lines.append("1 3 1 2 3")
    lines.append("2 3 1 3 2")
    # open boundaries: NOPE=1, NBOU=3; one boundary with 3 nodes: 1,2,3
    lines.append("1")
    lines.append("3")
    lines.append("3")
    lines.append("1")
    lines.append("2")
    lines.append("3")
    # land boundaries: NBOB=1, NBOBN=3; one boundary with 3 nodes and ibtype=20: 3,2,1
    lines.append("1")
    lines.append("3")
    if header_variant == 'same_line':
        lines.append("3 20")
    else:
        lines.append("3")
        lines.append("20")
    lines.append("3")
    lines.append("2")
    lines.append("1")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_land_header_variants_identical_lengths(tmp_path):
    f1 = tmp_path / 'v1.fort14'
    f2 = tmp_path / 'v2.fort14'
    _write_mesh(f1, 'same_line')
    _write_mesh(f2, 'split')
    b1 = parse_fort14_boundaries(f1)
    b2 = parse_fort14_boundaries(f2)
    land1 = [seg for _ib, seg in b1.land_segments]
    land2 = [seg for _ib, seg in b2.land_segments]
    assert len(land1) == len(land2) == 1
    assert len(land1[0]) == len(land2[0]) == 3
    assert len(b1.open_segments) == len(b2.open_segments) == 1
    assert len(b1.open_segments[0]) == len(b2.open_segments[0]) == 3

