from pathlib import Path

from oceanmesh_tools.scan.resolve_paths import resolve_candidates


def touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_resolve_candidates_prefix(tmp_path: Path):
    region_data = tmp_path / 'Region' / 'data'
    datasets = tmp_path / 'datasets'
    # Create shapefile candidates
    touch(region_data / 'coastline.shp')
    touch(datasets / 'coast/coastline_tokyo.shp')
    # Create DEM candidates
    touch(region_data / 'tokyo_dem.tif')
    touch(datasets / 'tokyo_dem_highres.tif')

    shp_cands, dem_cands = resolve_candidates(
        mesh_fort14=None,
        shp_hints=['coastline_tokyo', 'coastline'],
        dem_hints=['tokyo_dem'],
        base_priority_dirs=[region_data, datasets],
    )

    # Should find shapefiles and dems
    assert any(p.name.endswith('.shp') for p in shp_cands)
    assert any(p.name.endswith('.tif') for p in dem_cands)

