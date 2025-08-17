from pathlib import Path

from oceanmesh_tools.io.fort14 import parse_fort14


def test_parse_tiny_fort14():
    f = Path('tests/fixtures/tiny.fort14')
    m = parse_fort14(f)
    assert m.n_nodes == 3
    assert m.n_elements == 2
    assert len(m.open_boundaries) == 1
    assert len(m.open_boundaries[0]) == 4
    # bbox
    xmin, ymin, xmax, ymax = m.bbox
    assert xmin == 0.0 and ymin == 0.0 and xmax == 1.0 and ymax == 1.0

