from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .config import load_config, region_paths, DEFAULT_REGION
from .io.fort14 import mesh_bbox_from_fort14, parse_fort14
from .scan.matlab_inputs import scan_matlab_scripts, extract_from_file
from .scan.resolve_paths import resolve_candidates, pick_best_by_iou
from .plot.viz import (
    plot_bathymetry_contours,
    plot_bathymetry_filled,
    plot_coastline_overlay,
    plot_mesh,
    plot_open_boundaries,
)


def _norm_path(p: str | Path) -> Path:
    s = str(p)
    s = os.path.expandvars(s)
    s = os.path.expanduser(s)
    return Path(s).resolve()


def _str_path(p: Path) -> str:
    return str(_norm_path(p))


def _merge_catalog_entry(
    catalog: Dict[str, Dict[str, Any]],
    key_id: str,
    fort14_path: Optional[Path],
    script_path: Path,
    shp_cands: List[Path],
    dem_cands: List[Path],
    shp_res: Optional[Path],
    dem_res: Optional[Path],
) -> None:
    key_str = key_id
    if key_str in catalog:
        entry = catalog[key_str]
        entry.setdefault("script_paths", [])
        entry["script_paths"].append(_str_path(script_path))
        entry["script_path"] = entry["script_paths"][0]
        entry["shp_candidates"] = sorted(list(set(entry.get("shp_candidates", [])) | set(map(_str_path, shp_cands))))
        entry["dem_candidates"] = sorted(list(set(entry.get("dem_candidates", [])) | set(map(_str_path, dem_cands))))
        if shp_res is not None:
            entry["shp_resolved"] = _str_path(shp_res)
        if dem_res is not None:
            entry["dem_resolved"] = _str_path(dem_res)
    else:
        catalog[key_str] = {
            "fort14_path": _str_path(fort14_path) if fort14_path else key_id,
            "script_path": _str_path(script_path),
            "script_paths": [_str_path(script_path)],
            "shp_candidates": list(map(_str_path, shp_cands)),
            "dem_candidates": list(map(_str_path, dem_cands)),
            "shp_resolved": _str_path(shp_res) if shp_res else None,
            "dem_resolved": _str_path(dem_res) if dem_res else None,
        }


def _parse_pair_arg(s: str) -> Optional[Tuple[Path, Path]]:
    # format: fort14=<path>:script=<path>
    try:
        parts = s.split(":")
        kv = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k.strip()] = v.strip()
        if "fort14" in kv and "script" in kv:
            return _norm_path(kv["fort14"]), _norm_path(kv["script"])
    except Exception:
        return None
    return None


def _load_pairs_file(path: Path) -> List[Tuple[Path, Path]]:
    pairs: List[Tuple[Path, Path]] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = path.suffix.lower()
    if lower in (".json",):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    f = _norm_path(item.get("fort14"))
                    s = _norm_path(item.get("script"))
                    pairs.append((f, s))
        except Exception:
            pass
    elif lower in (".csv",):
        import csv

        from io import StringIO

        reader = csv.DictReader(StringIO(text))
        for row in reader:
            if row.get("fort14") and row.get("script"):
                pairs.append((_norm_path(row["fort14"]), _norm_path(row["script"])) )
    elif lower in (".yaml", ".yml"):
        # Minimal YAML: list of items with fort14 and script keys
        # Example:
        # - fort14: /abs/path/mesh.14
        #   script: /abs/path/gen.m
        cur: Dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-"):
                if cur.get("fort14") and cur.get("script"):
                    pairs.append((_norm_path(cur["fort14"]), _norm_path(cur["script"])) )
                cur = {}
                line = line[1:].strip()
                if not line:
                    continue
            if ":" in line:
                k, v = line.split(":", 1)
                val = v.strip().strip("'\"")
                # Do not expand here; we expand at append time to tolerate order
                cur[k.strip()] = val
        if cur.get("fort14") and cur.get("script"):
            pairs.append((_norm_path(cur["fort14"]), _norm_path(cur["script"])) )
    return pairs


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
    region = conf.get("default_region") or DEFAULT_REGION

    region_root, region_data, datasets = region_paths(oceanmesh2d_dir, region)
    scan_root = region_root

    scripts = scan_matlab_scripts(scan_root)
    catalog: Dict[str, Dict] = {}

    # Precompute region search dirs in priority
    base_priority = [region_data, datasets]
    extra_shp = [_norm_path(p) for p in conf.get("search_paths", {}).get("shp", [])]
    extra_dem = [_norm_path(p) for p in conf.get("search_paths", {}).get("dem", [])]

    # Find available .14 files
    existing_14: Dict[str, Path] = {}
    for p in region_root.rglob("*.14"):
        existing_14[p.stem] = p.resolve()

    # Handle explicit pairs first (highest precedence)
    explicit_pairs: List[Tuple[Path, Path]] = []
    for p in (args.pair or []):
        pr = _parse_pair_arg(p)
        if pr is not None:
            explicit_pairs.append(pr)
    if args.pairs_file:
        try:
            explicit_pairs.extend(_load_pairs_file(_norm_path(args.pairs_file)))
        except Exception:
            pass

    for f14_path, script_path in explicit_pairs:
        try:
            si = extract_from_file(script_path)
            shp_cands, dem_cands = resolve_candidates(
                _norm_path(f14_path),
                si.shp_hints,
                si.dem_hints,
                base_priority,
                extra_shp_paths=extra_shp,
                extra_dem_paths=extra_dem,
            )
            shp_res, dem_res = pick_best_by_iou(_norm_path(f14_path), shp_cands, dem_cands)
            # Logging
            print(f"[scan] Pair: fort14={_norm_path(f14_path)} script={_norm_path(script_path)}")
            print(f"[scan]   shapefiles: {len(shp_cands)} candidates; DEMs: {len(dem_cands)} candidates")
            if not shp_cands and not dem_cands:
                roots = ", ".join(str(p) for p in base_priority + extra_shp + extra_dem)
                print(f"[scan]   No candidates found. Searched roots: {roots}")
            else:
                if shp_res:
                    print(f"[scan]   selected shapefile: {shp_res}")
                if dem_res:
                    print(f"[scan]   selected DEM: {dem_res}")
            _merge_catalog_entry(catalog, str(_norm_path(f14_path)), _norm_path(f14_path), _norm_path(script_path), shp_cands, dem_cands, shp_res, dem_res)
        except Exception:
            continue

    # Then, regular discovery
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
            shp_res, dem_res = (None, None)
            if key_path:
                shp_res, dem_res = pick_best_by_iou(key_path, shp_cands, dem_cands)
            # Logging for discovery
            what = key_path if key_path else mesh_name
            print(f"[scan] Discovered mesh: {what}")
            print(f"[scan]   shapefiles: {len(shp_cands)} candidates; DEMs: {len(dem_cands)} candidates")
            if not shp_cands and not dem_cands:
                roots = ", ".join(str(p) for p in base_priority + extra_shp + extra_dem)
                print(f"[scan]   No candidates found. Searched roots: {roots}")
            else:
                if shp_res:
                    print(f"[scan]   selected shapefile: {shp_res}")
                if dem_res:
                    print(f"[scan]   selected DEM: {dem_res}")
            _merge_catalog_entry(catalog, key, key_path, si.script_path, shp_cands, dem_cands, shp_res, dem_res)

    out_path = Path(args.out).resolve()
    out_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Wrote catalog to {out_path}")
    return 0


def _resolve_from_catalog(catalog: Dict, fort14_path: Path) -> Tuple[Optional[Path], Optional[Path], List[Path], List[Path]]:
    # Try exact normalized absolute key
    key_path = str(_norm_path(fort14_path))
    base = _norm_path(fort14_path).stem
    entry = catalog.get(key_path)
    if not entry:
        # Try realpath equivalence on catalog keys
        for k, v in catalog.items():
            try:
                if os.path.isabs(k) and str(_norm_path(k)) == key_path:
                    entry = v
                    break
            except Exception:
                continue
    if not entry:
        # Do not silently fallback by basename; this is ambiguous across environments
        candidates = []
        for k, v in catalog.items():
            try:
                k_base = Path(v.get("fort14_path", k)).stem
            except Exception:
                k_base = Path(k).stem
            if k_base == base:
                candidates.append(v)
        if candidates:
            raise RuntimeError(
                f"Ambiguous basename '{base}' in catalog; use absolute --fort14 or re-scan to normalize keys."
            )
        return None, None, [], []
    # Prefer resolved paths when available, otherwise first candidate
    shp = None
    dem = None
    if entry.get("shp_resolved"):
        try:
            shp = Path(entry["shp_resolved"]) if entry["shp_resolved"] else None
        except Exception:
            shp = None
    if entry.get("dem_resolved"):
        try:
            dem = Path(entry["dem_resolved"]) if entry["dem_resolved"] else None
        except Exception:
            dem = None
    shp_candidates = [_norm_path(p) for p in entry.get("shp_candidates", [])]
    dem_candidates = [_norm_path(p) for p in entry.get("dem_candidates", [])]
    if shp is None and shp_candidates:
        shp = shp_candidates[0]
    if dem is None and dem_candidates:
        dem = dem_candidates[0]
    return shp, dem, shp_candidates, dem_candidates


def _on_the_fly_detect(oceanmesh2d_dir: str, region: str, fort14_path: Path, extra_shp: List[str], extra_dem: List[str]) -> Tuple[Optional[Path], Optional[Path], List[Path], List[Path]]:
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
    shp_res, dem_res = pick_best_by_iou(fort14_path, shp_cands, dem_cands)
    return (shp_res or (shp_cands[0] if shp_cands else None), dem_res or (dem_cands[0] if dem_cands else None), shp_cands, dem_cands)


def _resolve_viz_inputs(
    fort14: Path,
    conf: Dict,
    script_path: Optional[Path],
    catalog_path: Optional[Path],
    explicit_shp: Optional[Path],
    explicit_dem: Optional[Path],
) -> Tuple[Optional[Path], Optional[Path], List[Path], List[Path]]:
    """Resolve shapefile and DEM for viz with precedence:
    explicit > script > catalog > auto-detect.
    """
    oceanmesh2d_dir = conf.get("oceanmesh2d_dir") or os.path.join(str(Path.home()), "Github", "OceanMesh2D")
    region = conf.get("default_region") or DEFAULT_REGION
    extra_shp = conf.get("search_paths", {}).get("shp", [])
    extra_dem = conf.get("search_paths", {}).get("dem", [])

    shp_primary: Optional[Path] = explicit_shp
    dem_primary: Optional[Path] = explicit_dem
    shp_candidates: List[Path] = []
    dem_candidates: List[Path] = []

    # Script hints
    if script_path is not None:
        try:
            si = extract_from_file(script_path)
            # Build base priority from region
            from .config import region_paths as _region_paths  # local import to avoid cycle

            region_root, region_data, datasets = _region_paths(oceanmesh2d_dir, region)
            base_priority = [region_data, datasets]
            shp_cands, dem_cands = resolve_candidates(
                _norm_path(fort14),
                si.shp_hints,
                si.dem_hints,
                base_priority,
                extra_shp_paths=[_norm_path(p) for p in extra_shp],
                extra_dem_paths=[_norm_path(p) for p in extra_dem],
            )
            shp_candidates += shp_cands
            dem_candidates += dem_cands
            shp_res, dem_res = pick_best_by_iou(fort14, shp_cands, dem_cands)
            shp_primary = shp_primary or shp_res or (shp_cands[0] if shp_cands else None)
            dem_primary = dem_primary or dem_res or (dem_cands[0] if dem_cands else None)
        except Exception:
            pass

    # Catalog fallback
    if catalog_path is not None and catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            shp_c, dem_c, shp_cands, dem_cands = _resolve_from_catalog(catalog, fort14)
            shp_candidates += shp_cands
            dem_candidates += dem_cands
            shp_primary = shp_primary or shp_c
            dem_primary = dem_primary or dem_c
        except Exception:
            pass

    # Auto-detect
    if shp_primary is None or dem_primary is None or not (shp_candidates and dem_candidates):
        shp_c, dem_c, shp_cands, dem_cands = _on_the_fly_detect(
            oceanmesh2d_dir,
            region,
            fort14,
            extra_shp,
            extra_dem,
        )
        shp_candidates += shp_cands
        dem_candidates += dem_cands
        shp_primary = shp_primary or shp_c
        dem_primary = dem_primary or dem_c

    # Deduplicate and include explicit choices
    def dedup(seq: List[Path]) -> List[Path]:
        seen = set()
        out: List[Path] = []
        for p in seq:
            rp = _norm_path(p)
            if rp not in seen:
                seen.add(rp)
                out.append(rp)
        return out

    if explicit_shp:
        shp_candidates = [explicit_shp] + shp_candidates
    if explicit_dem:
        dem_candidates = [explicit_dem] + dem_candidates
    shp_candidates = dedup(shp_candidates)
    dem_candidates = dedup(dem_candidates)

    return shp_primary, dem_primary, shp_candidates, dem_candidates


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

    fort14 = _norm_path(args.fort14)
    outdir = Path(args.out).resolve() if args.out else Path("figs") / fort14.stem
    outdir.mkdir(parents=True, exist_ok=True)

    explicit_shp = _norm_path(args.shp) if args.shp and args.shp != "auto" else None
    explicit_dem = _norm_path(args.dem) if args.dem and args.dem != "auto" else None
    script_path = _norm_path(args.script) if getattr(args, "script", None) else None
    catalog_path = _norm_path(args.catalog) if args.catalog else None

    shp_path, dem_path, shp_candidates, dem_candidates = _resolve_viz_inputs(
        fort14,
        conf,
        script_path,
        catalog_path,
        explicit_shp,
        explicit_dem,
    )

    # Plot outputs; ignore failures for optional ones
    # Mesh figure with optional overlays
    add_all = getattr(args, "mesh_add_all", False)
    add_coast = getattr(args, "mesh_add_coastline", True) or add_all
    add_open = getattr(args, "mesh_add_open_boundaries", True) or add_all
    # Build kwargs and filter by viz.plot_mesh signature to avoid TypeError when CLI/viz evolve
    import inspect as _inspect
    from .plot import viz as _viz_mod
    _sig = _inspect.signature(_viz_mod.plot_mesh)
    _kw = dict(
        f14_path=fort14,
        outdir=outdir,
        coastline_path=shp_path if add_coast else None,
        mesh_add_coastline=add_coast,
        mesh_add_open_boundaries=add_open,
        include_holes=getattr(args, "coast_include_holes", True),
        target_crs=getattr(args, "crs", None),
        coast_skip_near_openbnd=getattr(args, "coast_skip_near_openbnd", True),
        coast_skip_tol=(getattr(args, "coast_clip_eps", 1e-6) or getattr(args, "coast_skip_tol", 0.01)),
        ob_snap_to_hull=getattr(args, "ob_snap_to_hull", True),
        ob_snap_tol=getattr(args, "ob_snap_tol", 1e-3),
        audit_boundary=getattr(args, "audit_boundary", False),
        coast_clip_to_domain=getattr(args, "coast_clip_to_domain", True),
        coast_subtract_near_ob=getattr(args, "coast_subtract_near_ob", True),
        coast_subtract_tol=getattr(args, "coast_subtract_tol", 0.002),
    )
    _kw = {k: v for k, v in _kw.items() if k in _sig.parameters}
    mesh_png = _viz_mod.plot_mesh(**_kw)
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
            plot_coastline_overlay(
                shp_path,
                bbox,
                outdir,
                include_holes=getattr(args, "coast_include_holes", False),
                target_crs=getattr(args, "crs", None),
                coast_clip_to_domain=getattr(args, "coast_clip_to_domain", True),
                fort14_path=fort14,
                coast_clip_eps=getattr(args, "coast_clip_eps", 1e-6),
                coast_subtract_near_ob=getattr(args, "coast_subtract_near_ob", True),
                coast_subtract_tol=getattr(args, "coast_subtract_tol", 0.002),
            )
        except Exception as e:
            print(f"Coastline overlay skipped: {e}")
    else:
        print("No shapefile detected; skipping coastline overlay")

    print("\nSummary:")
    print(f"  fort14: {fort14}")
    # Show primary and all candidates for transparency
    dem_candidates_str = ", ".join(str(p) for p in dem_candidates) if dem_candidates else "[]"
    shp_candidates_str = ", ".join(str(p) for p in shp_candidates) if shp_candidates else "[]"
    print(f"  DEMs: primary={dem_path if dem_path else 'None'} (used), candidates=[{dem_candidates_str}]")
    print(f"  Shapefiles: primary={shp_path if shp_path else 'None'} (used), candidates=[{shp_candidates_str}]")
    print(f"  Output: {outdir}")
    if (dem_path is None or shp_path is None) and catalog_path and catalog_path.exists():
        print(f"Catalog entry not found or incomplete for {fort14}. Check pairs.yaml/env expansion or re-run scan.")
    if (dem_path is None or shp_path is None) and script_path is None and not args.catalog and not (explicit_shp or explicit_dem):
        print("Hint: Inputs may be defined in the generating MATLAB script. Use --script or provide --dem/--shp explicitly.")
    if getattr(args, "require_inputs", False) and (dem_path is None or shp_path is None):
        print("\nResolution attempts:")
        dem_candidates_str = ", ".join(str(p) for p in dem_candidates) if dem_candidates else "[]"
        shp_candidates_str = ", ".join(str(p) for p in shp_candidates) if shp_candidates else "[]"
        print(f"  DEM candidates: [{dem_candidates_str}]")
        print(f"  Shapefile candidates: [{shp_candidates_str}]")
        return 2
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
    s_scan.add_argument("--pair", action="append", default=[], help="Explicit fort14<=>script pair: fort14=<path>:script=<path>")
    s_scan.add_argument("--pairs-file", help="YAML/JSON/CSV file listing fort14,script pairs")
    s_scan.set_defaults(func=cmd_scan)

    s_viz = sub.add_parser("viz", help="Visualize mesh and detected inputs")
    add_common_scan(s_viz)
    s_viz.add_argument("--fort14", required=True, help="Path to fort.14 file")
    s_viz.add_argument("--catalog", help="Path to catalog.json from scan")
    s_viz.add_argument("--script", help="Path to generating MATLAB script (.m)")
    s_viz.add_argument("--dem", help="DEM path or 'auto'", default="auto")
    s_viz.add_argument("--shp", help="Shapefile path/dir or 'auto'", default="auto")
    # Boolean optional action support (Python >=3.9); fallback to store_true on older/limited argparse
    try:
        BooleanOptionalAction_not_used = None
    except Exception:  # pragma: no cover
        bool_action = 'store_true'
    s_viz.add_argument(
        "--coast-include-holes",
        action="store_true",
        default=True,
        help="Include interior rings (holes) from polygons when plotting coastlines",
    )
    s_viz.add_argument(
        "--coast-subtract-near-ob",
        action=BoolAction,  # type: ignore[arg-type]
        default=True,
        help="Subtract a thin buffer around open boundary from coastline to avoid overlap",
    )
    s_viz.add_argument(
        "--coast-subtract-tol",
        type=float,
        default=0.002,
        help="Tolerance for subtracting coastline near open boundary (mesh CRS units)",
    )
    s_viz.add_argument(
        "--coast-clip-to-domain",
        action="store_true",
        default=True,
        help="Clip coastline to mesh domain polygon to avoid bridging across open boundaries",
    )
    s_viz.add_argument(
        "--coast-clip-eps",
        type=float,
        default=1e-6,
        help="Epsilon buffer for polygon clipping to keep boundary-coincident segments",
    )
    # Mesh overlays on mesh.png
    try:
        BooleanOptionalAction_not_used = None
    except Exception:  # pragma: no cover
        bool_action = 'store_true'
    s_viz.add_argument(
        "--mesh-add-coastline",
        action=BoolAction,  # type: ignore[arg-type]
        default=True,
        help="Overlay coastline (red) on mesh.png",
    )
    s_viz.add_argument(
        "--mesh-add-open-boundaries",
        action=BoolAction,  # type: ignore[arg-type]
        default=True,
        help="Overlay open boundaries (blue) on mesh.png",
    )
    s_viz.add_argument(
        "--mesh-add-all",
        action="store_true",
        help="Shorthand to enable both coastline and open-boundary overlays",
    )
    s_viz.add_argument(
        "--coast-skip-near-openbnd",
        action=BoolAction,  # type: ignore[arg-type]
        default=True,
        help="Skip coastline rings that lie within tolerance of open boundary when overlaying on mesh",
    )
    s_viz.add_argument(
        "--coast-skip-tol",
        type=float,
        default=0.01,
        help="Tolerance in mesh CRS units for coastline-vs-open-boundary proximity filter",
    )
    s_viz.add_argument("--out", help="Output directory for figures")
    s_viz.add_argument("--crs", help="Target CRS like EPSG:4326", default="EPSG:4326")
    s_viz.add_argument("--require-inputs", action="store_true", help="Fail (non-zero) if DEM/Shape unresolved and show resolution attempts")
    s_viz.add_argument("--audit-boundary", action="store_true", default=False, help="Write boundary audit figure")
    # Open-boundary snapping options
    try:
        from argparse import BooleanOptionalAction  # type: ignore
        bool_action2 = BooleanOptionalAction
    except Exception:
        bool_action2 = 'store_true'
    s_viz.add_argument("--ob-snap-to-hull", action=bool_action2, default=True, help="Snap open boundary to mesh hull when close enough")
    s_viz.add_argument("--ob-snap-tol", type=float, default=1e-3, help="Tolerance for snapping (mesh CRS units)")
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
"""Argparse boolean optional action polyfill.

Uses argparse.BooleanOptionalAction when available; otherwise defines a minimal
BoolAction that sets the value to True when the flag is present.
"""
try:  # Python 3.9+
    from argparse import BooleanOptionalAction as BoolAction  # type: ignore
except Exception:  # pragma: no cover
    class BoolAction(argparse.Action):  # type: ignore
        def __init__(self, option_strings, dest, default=None, **kwargs):
            kwargs.pop("nargs", None)
            super().__init__(option_strings, dest, nargs=0, default=default, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, True)
