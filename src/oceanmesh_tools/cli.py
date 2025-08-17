from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import load_config, region_paths
from .io.fort14 import mesh_bbox_from_fort14, parse_fort14
from .scan.matlab_inputs import scan_matlab_scripts
from .scan.resolve_paths import resolve_candidates
from .plot.viz import (
    plot_bathymetry_contours,
    plot_bathymetry_filled,
    plot_coastline_overlay,
    plot_mesh,
    plot_open_boundaries,
)


def _str_path(p: Path) -> str:
    return str(p)


def cmd_scan(args: argparse.Namespace) -> int:
    cli_conf = {
        "oceanmesh2d_dir": args.oceanmesh2d_dir,
        "default_region": args.region,
        "search_paths": {
            "shp": args.shp_path or [],
            "dem": args.dem_path or [],
        },
    }
    conf = load_config(cli_conf)
    oceanmesh2d_dir = conf.get("oceanmesh2d_dir") or os.path.join(str(Path.home()), "Github", "OceanMesh2D")
    region = conf.get("default_region")

    region_root, region_data, datasets = region_paths(oceanmesh2d_dir, region)
    scan_root = region_root

    scripts = scan_matlab_scripts(scan_root)
    catalog: Dict[str, Dict] = {}

    # Precompute region search dirs in priority
    base_priority = [region_data, datasets]
    extra_shp = [Path(p) for p in conf.get("search_paths", {}).get("shp", [])]
    extra_dem = [Path(p) for p in conf.get("search_paths", {}).get("dem", [])]

    # Find available .14 files
    existing_14: Dict[str, Path] = {}
    for p in region_root.rglob("*.14"):
        existing_14[p.stem] = p.resolve()

    for si in scripts:
        for mesh_name in si.mesh_names:
            key_path = existing_14.get(mesh_name)
            key = _str_path(key_path) if key_path else mesh_name
            shp_cands, dem_cands = resolve_candidates(
                key_path,
                si.shp_hints,
                si.dem_hints,
                base_priority,
                extra_shp_paths=extra_shp,
                extra_dem_paths=extra_dem,
            )
            # Merge if key already exists
            if key in catalog:
                entry = catalog[key]
                entry.setdefault("script_paths", [])
                entry["script_paths"].append(_str_path(si.script_path))
                entry["script_path"] = entry["script_paths"][0]
                entry["shp_candidates"] = sorted(list(set(entry["shp_candidates"]) | set(map(_str_path, shp_cands))))
                entry["dem_candidates"] = sorted(list(set(entry["dem_candidates"]) | set(map(_str_path, dem_cands))))
            else:
                catalog[key] = {
                    "script_path": _str_path(si.script_path),
                    "script_paths": [_str_path(si.script_path)],
                    "shp_candidates": list(map(_str_path, shp_cands)),
                    "dem_candidates": list(map(_str_path, dem_cands)),
                }

    out_path = Path(args.out).resolve()
    out_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Wrote catalog to {out_path}")
    return 0


def _resolve_from_catalog(catalog: Dict, fort14_path: Path) -> Tuple[Optional[Path], Optional[Path]]:
    key_path = str(fort14_path.resolve())
    base = fort14_path.stem
    entry = catalog.get(key_path) or catalog.get(base)
    shp = Path(entry["shp_candidates"][0]) if entry and entry.get("shp_candidates") else None
    dem = Path(entry["dem_candidates"][0]) if entry and entry.get("dem_candidates") else None
    return shp, dem


def _on_the_fly_detect(oceanmesh2d_dir: str, region: str, fort14_path: Path, extra_shp: List[str], extra_dem: List[str]) -> Tuple[Optional[Path], Optional[Path]]:
    region_root, region_data, datasets = region_paths(oceanmesh2d_dir, region)
    scripts = scan_matlab_scripts(region_root)
    base_priority = [region_data, datasets]
    # Find script hints matching this mesh name
    name = fort14_path.stem
    shp_hints: List[str] = []
    dem_hints: List[str] = []
    for si in scripts:
        if name in si.mesh_names:
            shp_hints.extend(si.shp_hints)
            dem_hints.extend(si.dem_hints)
    if not shp_hints and not dem_hints:
        # fallback: use basename as hint
        shp_hints = [name]
        dem_hints = [name]
    shp_cands, dem_cands = resolve_candidates(
        fort14_path,
        shp_hints,
        dem_hints,
        base_priority,
        extra_shp_paths=[Path(p) for p in extra_shp],
        extra_dem_paths=[Path(p) for p in extra_dem],
    )
    return (shp_cands[0] if shp_cands else None, dem_cands[0] if dem_cands else None)


def cmd_viz(args: argparse.Namespace) -> int:
    cli_conf = {
        "oceanmesh2d_dir": args.oceanmesh2d_dir,
        "default_region": args.region,
        "search_paths": {
            "shp": args.shp_path or [],
            "dem": args.dem_path or [],
        },
    }
    conf = load_config(cli_conf)
    oceanmesh2d_dir = conf.get("oceanmesh2d_dir") or os.path.join(str(Path.home()), "Github", "OceanMesh2D")
    region = conf.get("default_region")

    fort14 = Path(args.fort14).resolve()
    outdir = Path(args.out).resolve() if args.out else Path("figs") / fort14.stem
    outdir.mkdir(parents=True, exist_ok=True)

    shp_path: Optional[Path] = None
    dem_path: Optional[Path] = None

    # 1) Explicit overrides
    if args.shp and args.shp != "auto":
        shp_path = Path(args.shp).resolve()
    if args.dem and args.dem != "auto":
        dem_path = Path(args.dem).resolve()

    # 2) Catalog
    if (shp_path is None or dem_path is None) and args.catalog:
        try:
            catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
            shp_c, dem_c = _resolve_from_catalog(catalog, fort14)
            shp_path = shp_path or shp_c
            dem_path = dem_path or dem_c
        except Exception:
            pass

    # 3) On-the-fly detection
    if shp_path is None or dem_path is None:
        shp_c, dem_c = _on_the_fly_detect(
            oceanmesh2d_dir, region, fort14, conf.get("search_paths", {}).get("shp", []), conf.get("search_paths", {}).get("dem", [])
        )
        shp_path = shp_path or shp_c
        dem_path = dem_path or dem_c

    # Plot outputs; ignore failures for optional ones
    mesh_png = plot_mesh(fort14, outdir)
    ob_png = plot_open_boundaries(fort14, outdir)
    if dem_path and dem_path.exists():
        try:
            plot_bathymetry_filled(dem_path, outdir)
        except Exception as e:
            print(f"DEM filled plot skipped: {e}")
        try:
            plot_bathymetry_contours(dem_path, outdir)
        except Exception as e:
            print(f"DEM contours plot skipped: {e}")
    else:
        print("No DEM detected; skipping bathymetry plots")
    if shp_path and shp_path.exists():
        try:
            bbox = mesh_bbox_from_fort14(fort14)
            plot_coastline_overlay(shp_path, bbox, outdir)
        except Exception as e:
            print(f"Coastline overlay skipped: {e}")
    else:
        print("No shapefile detected; skipping coastline overlay")

    print(f"Saved figures to {outdir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="omt", description="oceanmesh-tools CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Common
    def add_common_scan(s):
        s.add_argument("--oceanmesh2d-dir", default=None, help="Path to local OceanMesh2D repo root")
        s.add_argument("--region", default=None, help="Region name (e.g., Tokyo_Bay)")
        s.add_argument("--shp-path", action="append", help="Additional shapefile search path", default=[])
        s.add_argument("--dem-path", action="append", help="Additional DEM search path", default=[])

    s_scan = sub.add_parser("scan", help="Scan MATLAB scripts and build input catalog")
    add_common_scan(s_scan)
    s_scan.add_argument("--out", required=True, help="Output catalog JSON path")
    s_scan.set_defaults(func=cmd_scan)

    s_viz = sub.add_parser("viz", help="Visualize mesh and detected inputs")
    add_common_scan(s_viz)
    s_viz.add_argument("--fort14", required=True, help="Path to fort.14 file")
    s_viz.add_argument("--catalog", help="Path to catalog.json from scan")
    s_viz.add_argument("--dem", help="DEM path or 'auto'", default="auto")
    s_viz.add_argument("--shp", help="Shapefile path/dir or 'auto'", default="auto")
    s_viz.add_argument("--out", help="Output directory for figures")
    s_viz.add_argument("--crs", help="Target CRS like EPSG:4326", default="EPSG:4326")
    s_viz.set_defaults(func=cmd_viz)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # Normalize region default if not provided
    if args.region is None:
        args.region = load_config({}).get("default_region")
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
