from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from ..io.fort14 import mesh_bbox_from_fort14

try:
    import rasterio  # type: ignore
except Exception:  # pragma: no cover
    rasterio = None

try:
    import fiona  # type: ignore
except Exception:  # pragma: no cover
    fiona = None


SHAPE_EXTS = [".shp"]
DEM_EXTS = [".nc", ".tif", ".tiff", ".img"]


def _search_shapefiles(base_dirs: Sequence[Path], hint: str) -> List[Path]:
    out: List[Path] = []
    name = Path(hint).stem
    for base in base_dirs:
        # 1) exact file X.shp
        cand = base / f"{name}.shp"
        if cand.exists():
            out.append(cand)
        # 2) directory X/*.shp
        d = base / name
        if d.is_dir():
            out += sorted(d.glob("*.shp"))
        # 3) **/X*.shp
        out += [p for p in base.rglob("*.shp") if p.name.lower().startswith(name.lower())]
    # Deduplicate
    seen = set()
    uniq: List[Path] = []
    for p in out:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(rp)
    return uniq


def _search_dems(base_dirs: Sequence[Path], hint: str) -> List[Path]:
    out: List[Path] = []
    hint_path = Path(hint)
    name = hint_path.name
    stem = hint_path.stem
    # Exact file match across dirs
    for base in base_dirs:
        # If hint contains an extension, try exact
        if hint_path.suffix:
            cand = base / name
            if cand.exists():
                out.append(cand)
        # Try known DEM extensions
        for ext in DEM_EXTS:
            cand = base / f"{stem}{ext}"
            if cand.exists():
                out.append(cand)
        # Prefix match
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in DEM_EXTS and p.name.lower().startswith(stem.lower()):
                out.append(p)
    # Deduplicate
    seen = set()
    uniq: List[Path] = []
    for p in out:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            uniq.append(rp)
    return uniq


def _bbox_from_shapefile(path: Path) -> Optional[Tuple[float, float, float, float]]:
    if fiona is None:
        return None
    try:
        with fiona.open(path) as src:  # type: ignore
            b = src.bounds
            return (b[0], b[1], b[2], b[3])
    except Exception:
        return None


def _bbox_from_raster(path: Path) -> Optional[Tuple[float, float, float, float]]:
    if rasterio is None:
        return None
    try:
        with rasterio.open(path) as src:  # type: ignore
            b = src.bounds
            return (b.left, b.bottom, b.right, b.top)
    except Exception:
        return None


def _overlap_score(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    return inter / area_a if area_a > 0 else 0.0


def resolve_candidates(
    mesh_fort14: Optional[Path],
    shp_hints: Sequence[str],
    dem_hints: Sequence[str],
    base_priority_dirs: Sequence[Path],
    extra_shp_paths: Sequence[Path] = (),
    extra_dem_paths: Sequence[Path] = (),
) -> Tuple[List[Path], List[Path]]:
    """Resolve shapefile and DEM candidates using hints and search paths.

    If multiple candidates remain and mesh bbox is available, pick best by max overlap.
    Always return all candidates found (best-first ordering).
    """
    base_dirs = [Path(p) for p in base_priority_dirs]
    shp_dirs = list(base_dirs) + [Path(p) for p in extra_shp_paths]
    dem_dirs = list(base_dirs) + [Path(p) for p in extra_dem_paths]

    shp_cands: List[Path] = []
    dem_cands: List[Path] = []

    for h in shp_hints:
        shp_cands.extend(_search_shapefiles(shp_dirs, h))
    for h in dem_hints:
        dem_cands.extend(_search_dems(dem_dirs, h))

    # Deduplicate
    def dedup_keep_order(paths: List[Path]) -> List[Path]:
        seen = set()
        out: List[Path] = []
        for p in paths:
            rp = p.resolve()
            if rp not in seen and rp.exists():
                seen.add(rp)
                out.append(rp)
        return out

    shp_cands = dedup_keep_order(shp_cands)
    dem_cands = dedup_keep_order(dem_cands)

    # If we have a mesh bbox, sort by overlap score descending
    if mesh_fort14 and (shp_cands or dem_cands):
        try:
            mbbox = mesh_bbox_from_fort14(mesh_fort14)
        except Exception:
            mbbox = None  # type: ignore
        if mbbox:
            def sort_by_score(paths: List[Path], bbox_func):
                scored = []
                for p in paths:
                    b = bbox_func(p)
                    s = _overlap_score(mbbox, b) if b else 0.0
                    scored.append((s, p))
                scored.sort(key=lambda x: x[0], reverse=True)
                return [p for _, p in scored]

            shp_cands = sort_by_score(shp_cands, _bbox_from_shapefile)
            dem_cands = sort_by_score(dem_cands, _bbox_from_raster)

    return shp_cands, dem_cands

