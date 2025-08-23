from pathlib import Path

import numpy as np

from oceanmesh_tools.io.fort14 import mesh_bbox_from_fort14
from oceanmesh_tools.plot.viz import plot_coastline_overlay


def test_boundary_debug_dumps_written(tmp_path):
    f14 = Path('tests/fixtures/segments.fort14')
    outdir = tmp_path / 'out'
    outdir.mkdir(parents=True, exist_ok=True)
    bbox = mesh_bbox_from_fort14(f14)
    # Force mesh14 path; this should also emit boundary_debug_edges.npz
    plot_coastline_overlay(
        shp_path=f14,  # not used in mesh14 path
        mesh_bbox=bbox,
        outdir=outdir,
        include_holes=False,
        target_crs=None,
        coast_clip_to_domain=False,
        fort14_path=f14,
        coast_clip_eps=1e-6,
        coast_subtract_near_ob=False,
        coast_subtract_tol=0.0,
        coast_source='mesh14',
        coast_shp_background=None,
        debug_boundaries=False,
    )
    npz_path = outdir / 'boundary_debug_edges.npz'
    assert npz_path.exists(), 'boundary_debug_edges.npz not written'
    data = np.load(npz_path)
    land_edges = data['land_edges']
    open_edges = data['open_edges']
    # Verify counts match sum(len(seg)-1)
    # Load fort14 again to compute expected sums via parser in viz path
    from oceanmesh_tools.io.fort14_boundaries import parse_fort14_boundaries
    b = parse_fort14_boundaries(f14)
    coast_ids = [seg for _ib, seg in b.land_segments]
    expected_land = sum(max(0, len(seg) - 1) for seg in coast_ids)
    expected_open = sum(max(0, len(seg) - 1) for seg in b.open_segments)
    assert land_edges.shape[0] == expected_land
    assert open_edges.shape[0] == expected_open

