from pathlib import Path
import os

from oceanmesh_tools.cli import main as omt_main


def test_figs_mesh_only_and_dpi(tmp_path):
    # Use tiny fixture
    f14 = Path('tests/fixtures/segments.fort14').resolve()
    outdir = tmp_path / 'out1'
    # Render only mesh
    rc = omt_main([
        'viz',
        '--fort14', str(f14),
        '--out', str(outdir),
        '--figs', 'mesh',
        '--dpi', '200',
    ])
    assert rc == 0
    mesh_png = outdir / 'mesh.png'
    coast_png = outdir / 'coastline_overlay.png'
    open_png = outdir / 'open_boundaries.png'
    assert mesh_png.exists()
    assert not coast_png.exists()
    assert not open_png.exists()

    # Compare DPI proxy by file size: higher DPI should produce larger PNG
    outdir2 = tmp_path / 'out2'
    rc2 = omt_main([
        'viz',
        '--fort14', str(f14),
        '--out', str(outdir2),
        '--figs', 'mesh',
        '--dpi', '300',
    ])
    assert rc2 == 0
    mesh_png2 = outdir2 / 'mesh.png'
    assert mesh_png2.exists()
    s1 = os.path.getsize(mesh_png)
    s2 = os.path.getsize(mesh_png2)
    # Allow equality if compression quirks, but generally s2 >= s1
    assert s2 >= s1

