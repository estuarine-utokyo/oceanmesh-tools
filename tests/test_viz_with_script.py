from pathlib import Path

from oceanmesh_tools.cli import _resolve_viz_inputs, _resolve_from_catalog, _load_pairs_file


def touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_resolve_viz_inputs_with_script(tmp_path: Path):
    # Prepare fake inputs
    fort14 = Path('tests/fixtures/tiny.fort14').resolve()
    shp = tmp_path / 'Futtsu_coastline.shp'
    dem = tmp_path / 'tokyo_dem.tif'
    touch(shp)
    touch(dem)
    script = tmp_path / 'gen.m'
    script.write_text("""
    % MATLAB script
    coastline_05 = 'Futtsu_coastline';
    dem_05       = 'tokyo_dem.tif';
    """, encoding='utf-8')

    conf = {
        'oceanmesh2d_dir': str(tmp_path),
        'default_region': 'Region',
        'search_paths': {
            'shp': [str(tmp_path)],
            'dem': [str(tmp_path)],
        },
    }

    shp_res, dem_res, shp_cands, dem_cands = _resolve_viz_inputs(
        fort14=fort14,
        conf=conf,
        script_path=script,
        catalog_path=None,
        explicit_shp=None,
        explicit_dem=None,
    )

    assert shp_res and shp_res.resolve() == shp.resolve()
    assert dem_res and dem_res.resolve() == dem.resolve()
    # candidates include detected paths
    assert any(p.resolve() == shp.resolve() for p in shp_cands)
    assert any(p.resolve() == dem.resolve() for p in dem_cands)


def test_catalog_resolution_prefers_resolved():
    from tempfile import TemporaryDirectory
    import json

    with TemporaryDirectory() as d:
        dpath = Path(d)
        fort14 = Path('tests/fixtures/tiny.fort14').resolve()
        cat = {
            str(fort14): {
                'shp_resolved': str(dpath / 'a.shp'),
                'dem_resolved': str(dpath / 'b.tif'),
                'shp_candidates': [str(dpath / 'c.shp')],
                'dem_candidates': [str(dpath / 'd.tif')],
            }
        }
        shp, dem, shp_cands, dem_cands = _resolve_from_catalog(cat, fort14)
        assert shp.name == 'a.shp'
        assert dem.name == 'b.tif'
        assert any(p.name == 'c.shp' for p in shp_cands)
        assert any(p.name == 'd.tif' for p in dem_cands)


def test_load_pairs_file_yaml(tmp_path: Path):
    yaml = tmp_path / 'pairs.yaml'
    yaml.write_text(
        """
        - fort14: /abs/path/mesh1.14
          script: /abs/path/gen1.m
        - fort14: /abs/path/mesh2.14
          script: /abs/path/gen2.m
        """,
        encoding='utf-8',
    )
    pairs = _load_pairs_file(yaml)
    assert len(pairs) == 2
    assert pairs[0][0].name == 'mesh1.14' and pairs[0][1].name == 'gen1.m'
