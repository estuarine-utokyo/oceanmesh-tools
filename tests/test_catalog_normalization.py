from pathlib import Path
import os
import json
import tempfile

import pytest

from oceanmesh_tools.cli import _load_pairs_file, _resolve_from_catalog


def test_pairs_yaml_env_and_tilde_expansion(tmp_path: Path, monkeypatch):
    # Set HOME to tmp to ensure $HOME and ~ resolve predictably
    monkeypatch.setenv("HOME", str(tmp_path))
    om2d = tmp_path / "Github" / "OceanMesh2D" / "Tokyo_Bay"
    scripts = om2d / "scripts"
    meshes = om2d / "outputs" / "meshes"
    scripts.mkdir(parents=True)
    meshes.mkdir(parents=True)
    f14 = meshes / "mesh_a.14"
    f14.write_text("# dummy fort14\n")
    m = scripts / "genMesh_a.m"
    m.write_text("% dummy script\n")

    yaml = om2d / "pairs.yaml"
    yaml.write_text(
        """
pairs:
  - fort14: $HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/mesh_a.14
    script: ~/Github/OceanMesh2D/Tokyo_Bay/scripts/genMesh_a.m
""",
        encoding="utf-8",
    )

    pairs = _load_pairs_file(yaml)
    assert len(pairs) == 1
    pf14, pscript = pairs[0]
    assert pf14 == f14.resolve()
    assert pscript == m.resolve()


def test_symlinked_mesh_looks_up_realpath(tmp_path: Path):
    # Create a real fort14 file and a symlink to it
    real = (tmp_path / "mesh_x.14").resolve()
    real.write_text("# fort14\n")
    link = tmp_path / "link.14"
    link.symlink_to(real)

    # Catalog is keyed by the real path
    catalog = {
        str(real): {
            "fort14_path": str(real),
            "script_path": str(tmp_path / "gen.m"),
            "shp_candidates": [str(tmp_path / "coast.shp")],
            "dem_candidates": [str(tmp_path / "dem.tif")],
            "shp_resolved": str(tmp_path / "coast.shp"),
            "dem_resolved": str(tmp_path / "dem.tif"),
        }
    }

    shp, dem, shp_c, dem_c = _resolve_from_catalog(catalog, link)
    assert shp and dem
    assert shp.name == "coast.shp"
    assert dem.name == "dem.tif"


def test_ambiguous_basename_fallback_raises(tmp_path: Path):
    # Two entries with same stem
    a = (tmp_path / "same.14").resolve()
    b = (tmp_path / "same.14").with_name("same_copy.14").resolve()
    catalog = {
        str(a): {"fort14_path": str(a), "shp_candidates": [], "dem_candidates": []},
        str(b): {"fort14_path": str(b), "shp_candidates": [], "dem_candidates": []},
    }
    # Lookup by a path whose stem is 'same' should not fall back ambiguously
    with pytest.raises(RuntimeError):
        _resolve_from_catalog(catalog, Path("same.14"))

