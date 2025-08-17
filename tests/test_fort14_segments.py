from pathlib import Path

from oceanmesh_tools.io.fort14 import parse_fort14


def test_parse_segments_style():
    f = Path('tests/fixtures/segments.fort14')
    m = parse_fort14(f)
    assert len(m.open_boundaries) == 1
    assert m.open_boundaries[0] == [1, 2, 3, 1]

