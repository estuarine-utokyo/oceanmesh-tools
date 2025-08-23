from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, List, Iterable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

try:
    import geopandas as gpd  # type: ignore
except Exception:  # pragma: no cover
    gpd = None

try:
    import rasterio  # type: ignore
    from rasterio.enums import Resampling  # type: ignore
    from rasterio.warp import calculate_default_transform, reproject  # type: ignore
except Exception:  # pragma: no cover
    rasterio = None

try:
    import xarray as xr  # type: ignore
except Exception:  # pragma: no cover
    xr = None

from ..io.fort14 import Fort14, parse_fort14


def _split_polyline_on_gaps(arr: np.ndarray) -> List[np.ndarray]:
    """Split a polyline (N,2) into multiple parts at large gaps.

    Heuristic: compute consecutive distances; split where a jump is much larger
    than the typical step (median of non-zero distances times a factor).
    """
    if arr.shape[0] <= 1:
        return [arr]
    diffs = np.diff(arr, axis=0)
    dists = np.sqrt((diffs**2).sum(axis=1))
    finite = dists[np.isfinite(dists)]
    if finite.size == 0:
        return [arr]
    nonzero = finite[finite > 0]
    if nonzero.size == 0:
        # All steps zero; keep as one
        return [arr]
    med = float(np.median(nonzero))
    # Threshold: generous factor to avoid over-splitting
    thresh = med * 5.0
    break_idxs = np.where(dists > thresh)[0]
    if break_idxs.size == 0:
        return [arr]
    parts: List[np.ndarray] = []
    start = 0
    for bi in break_idxs:
        parts.append(arr[start : bi + 1])
        start = bi + 1
    if start < arr.shape[0]:
        parts.append(arr[start:])
    # Filter out trivial parts
    parts = [p for p in parts if p.shape[0] >= 2]
    return parts if parts else [arr]


def _build_open_boundary_segments(mesh: Fort14) -> List[np.ndarray]:
    """Return list of (N,2) arrays per open-boundary polyline (one per boundary).

    Preserves provided node order and does not join boundaries or infer splits.
    """
    id_to_xy = {nid: (x, y) for nid, x, y, _ in mesh.nodes}
    segments: List[np.ndarray] = []
    prev_last: Optional[np.ndarray] = None
    for b in mesh.open_boundaries:
        xs = [id_to_xy[n][0] for n in b if n in id_to_xy]
        ys = [id_to_xy[n][1] for n in b if n in id_to_xy]
        if len(xs) >= 1:
            arr = np.column_stack([np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)])
            # Avoid accidental implicit join: if the first point equals the previous
            # segment's last point, drop the duplicated first point. Keep even 1-point
            # segments to preserve boundary count semantics in tests.
            if prev_last is not None and arr.shape[0] >= 1 and np.allclose(arr[0], prev_last):
                arr = arr[1:, :]
            if arr.shape[0] >= 1:
                segments.append(arr)
                prev_last = arr[-1].copy()
            else:
                # If all points were dropped (fully duplicate), reset prev_last
                prev_last = None
    return segments


def _ensure_outdir(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)


def plot_mesh(
    f14_path: Path,
    outdir: Path,
    coastline_path: Optional[Path] = None,
    mesh_add_coastline: bool = True,
    mesh_add_open_boundaries: bool = True,
    include_holes: bool = True,
    target_crs: Optional[str] = None,
) -> Path:
    _ensure_outdir(outdir)
    mesh = parse_fort14(f14_path)
    xs = {nid: x for nid, x, y, d in mesh.nodes}
    ys = {nid: y for nid, x, y, d in mesh.nodes}
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    for _, n1, n2, n3, _ in mesh.elements:
        ax.plot([xs[n1], xs[n2]], [ys[n1], ys[n2]], color="k", linewidth=0.2)
        ax.plot([xs[n2], xs[n3]], [ys[n2], ys[n3]], color="k", linewidth=0.2)
        ax.plot([xs[n3], xs[n1]], [ys[n3], ys[n1]], color="k", linewidth=0.2)
    # Optional overlays
    if mesh_add_coastline and coastline_path is not None and coastline_path.exists():
        if gpd is not None:
            try:
                gdf = gpd.read_file(coastline_path)  # type: ignore
                try:
                    if target_crs:
                        gdf = gdf.to_crs(target_crs)  # type: ignore
                    else:
                        gdf = gdf.to_crs(epsg=4326)  # type: ignore
                except Exception:
                    pass
                # Plot each ring separately in red
                segs = _segments_from_geoms(gdf.geometry, include_holes=include_holes)  # type: ignore
                for s in segs:
                    if isinstance(s, np.ndarray) and s.ndim == 2 and s.shape[0] >= 2:
                        ax.plot(s[:, 0], s[:, 1], color="r", linestyle="-", zorder=5)
            except Exception:
                pass
        # If geopandas unavailable, silently skip coastline overlay
    if mesh_add_open_boundaries and mesh.open_boundaries:
        segs = _build_open_boundary_segments(mesh)
        for s in segs:
            if isinstance(s, np.ndarray) and s.ndim == 2 and s.shape[0] >= 2:
                ax.plot(s[:, 0], s[:, 1], color="b", linestyle="-", zorder=6)
    ax.set_title("Mesh")
    ax.set_xlabel("Lon/X")
    ax.set_ylabel("Lat/Y")
    ax.set_aspect("equal", adjustable="box")
    png = outdir / "mesh.png"
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return png


def plot_open_boundaries(f14_path: Path, outdir: Path) -> Path:
    _ensure_outdir(outdir)
    mesh = parse_fort14(f14_path)
    xs = {nid: x for nid, x, y, d in mesh.nodes}
    ys = {nid: y for nid, x, y, d in mesh.nodes}
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    # Plot mesh lightly
    for _, n1, n2, n3, _ in mesh.elements:
        ax.plot([xs[n1], xs[n2]], [ys[n1], ys[n2]], color="#cccccc", linewidth=0.1, zorder=1)
        ax.plot([xs[n2], xs[n3]], [ys[n2], ys[n3]], color="#cccccc", linewidth=0.1, zorder=1)
        ax.plot([xs[n3], xs[n1]], [ys[n3], ys[n1]], color="#cccccc", linewidth=0.1, zorder=1)
    # Highlight open boundaries: draw each polyline separately
    segments = _build_open_boundary_segments(mesh)
    if segments:
        lc = LineCollection(segments, colors="C0", linewidths=1.0, zorder=2)
        ax.add_collection(lc)
    ax.set_title("Open Boundaries")
    ax.set_xlabel("Lon/X")
    ax.set_ylabel("Lat/Y")
    ax.set_aspect("equal", adjustable="box")
    png = outdir / "open_boundaries.png"
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return png


def plot_bathymetry_filled(dem_path: Path, outdir: Path) -> Path:
    _ensure_outdir(outdir)
    # Try rasterio first
    if rasterio is not None:
        try:
            with rasterio.open(dem_path) as src:  # type: ignore
                data = src.read(1, masked=True)
                fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
                img = ax.imshow(
                    data,
                    extent=[src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top],
                    origin="upper",
                )
                cbar = fig.colorbar(img, ax=ax)
                cbar.set_label("Depth/Elevation")
                ax.set_title("Bathymetry (Filled)")
                ax.set_xlabel("Lon/X")
                ax.set_ylabel("Lat/Y")
                png = outdir / "bathymetry_filled.png"
                fig.tight_layout()
                fig.savefig(png)
                plt.close(fig)
                return png
        except Exception:
            if dem_path.suffix.lower() == ".nc" and xr is not None:
                print("rasterio could not read NetCDF; falling back to xarray.")
            else:
                raise
    # Fallback to xarray for NetCDF
    if dem_path.suffix.lower() == ".nc" and xr is not None:
        ds = xr.open_dataset(dem_path, decode_coords="all", decode_timedelta=True)  # type: ignore
        da = ds.to_array().squeeze()
        if da.ndim != 2:
            raise RuntimeError("xarray fallback requires a 2D variable")
        ny, nx = da.shape
        # Try to infer coordinates
        xcoord = None
        ycoord = None
        for cand in ("x", "lon", "longitude", "XC", "lon_rho"):
            if cand in da.coords:
                xcoord = da[cand].values
                break
        for cand in ("y", "lat", "latitude", "YC", "lat_rho"):
            if cand in da.coords:
                ycoord = da[cand].values
                break
        if xcoord is not None and ycoord is not None:
            xmin, xmax = float(np.min(xcoord)), float(np.max(xcoord))
            ymin, ymax = float(np.min(ycoord)), float(np.max(ycoord))
        else:
            xmin, xmax = 0.0, float(nx)
            ymin, ymax = 0.0, float(ny)
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        img = ax.imshow(
            da.values,
            extent=[xmin, xmax, ymin, ymax],
            origin="upper",
        )
        cbar = fig.colorbar(img, ax=ax)
        cbar.set_label("Depth/Elevation")
        ax.set_title("Bathymetry (Filled)")
        ax.set_xlabel("Lon/X")
        ax.set_ylabel("Lat/Y")
        png = outdir / "bathymetry_filled.png"
        fig.tight_layout()
        fig.savefig(png)
        plt.close(fig)
        return png
    raise RuntimeError("rasterio is required to plot bathymetry (xarray fallback available for .nc)")


def plot_bathymetry_contours(dem_path: Path, outdir: Path) -> Path:
    _ensure_outdir(outdir)
    # Try rasterio first
    if rasterio is not None:
        try:
            with rasterio.open(dem_path) as src:  # type: ignore
                data = src.read(1, masked=True)
                fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
                nx = data.shape[1]
                ny = data.shape[0]
                xs = np.linspace(src.bounds.left, src.bounds.right, nx)
                ys = np.linspace(src.bounds.bottom, src.bounds.top, ny)
                cs = ax.contour(xs, ys, data, levels=10, linewidths=0.5, colors="k")
                ax.clabel(cs, inline=True, fontsize=6)
                ax.set_title("Bathymetry (Contours)")
                ax.set_xlabel("Lon/X")
                ax.set_ylabel("Lat/Y")
                png = outdir / "bathymetry_contours.png"
                fig.tight_layout()
                fig.savefig(png)
                plt.close(fig)
                return png
        except Exception:
            if dem_path.suffix.lower() == ".nc" and xr is not None:
                print("rasterio could not read NetCDF; falling back to xarray.")
            else:
                raise
    # Fallback to xarray for NetCDF
    if dem_path.suffix.lower() == ".nc" and xr is not None:
        ds = xr.open_dataset(dem_path, decode_coords="all", decode_timedelta=True)  # type: ignore
        da = ds.to_array().squeeze()
        if da.ndim != 2:
            raise RuntimeError("xarray fallback requires a 2D variable")
        ny, nx = da.shape
        xcoord = None
        ycoord = None
        for cand in ("x", "lon", "longitude", "XC", "lon_rho"):
            if cand in da.coords:
                xcoord = da[cand].values
                break
        for cand in ("y", "lat", "latitude", "YC", "lat_rho"):
            if cand in da.coords:
                ycoord = da[cand].values
                break
        if xcoord is not None and ycoord is not None:
            xs = xcoord if xcoord.ndim == 1 else np.linspace(float(np.min(xcoord)), float(np.max(xcoord)), nx)
            ys = ycoord if ycoord.ndim == 1 else np.linspace(float(np.min(ycoord)), float(np.max(ycoord)), ny)
        else:
            xs = np.linspace(0.0, float(nx), nx)
            ys = np.linspace(0.0, float(ny), ny)
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        cs = ax.contour(xs, ys, da.values, levels=10, linewidths=0.5, colors="k")
        ax.clabel(cs, inline=True, fontsize=6)
        ax.set_title("Bathymetry (Contours)")
        ax.set_xlabel("Lon/X")
        ax.set_ylabel("Lat/Y")
        png = outdir / "bathymetry_contours.png"
        fig.tight_layout()
        fig.savefig(png)
        plt.close(fig)
        return png
    raise RuntimeError("rasterio is required to plot bathymetry contours (xarray fallback available for .nc)")


def iter_lines(geom, include_holes: bool = False) -> Iterable[np.ndarray]:
    """Yield (N,2) arrays for each independent line from a shapely geometry.

    - LineString → one array
    - MultiLineString → one per part
    - Polygon → exterior only by default; include interior rings if requested
    - MultiPolygon → for each polygon, apply Polygon logic
    - GeometryCollection → recurse into members
    - Fallback: use .boundary when available
    """
    try:
        from shapely.geometry import (
            LineString,
            MultiLineString,
            Polygon,
            MultiPolygon,
            GeometryCollection,
            LinearRing,
        )  # type: ignore
    except Exception:  # pragma: no cover
        return []

    if geom is None:
        return []
    if hasattr(geom, "is_empty") and geom.is_empty:  # type: ignore[attr-defined]
        return []

    def arr_from_coords(coords) -> Optional[np.ndarray]:
        if coords is None:
            return None
        a = np.asarray(coords)
        if a.ndim == 2 and a.shape[0] >= 2:
            return a[:, :2].astype(float)
        return None

    out: List[np.ndarray] = []
    if isinstance(geom, LineString):
        a = arr_from_coords(geom.coords)
        if a is not None:
            out.append(a)
    elif isinstance(geom, MultiLineString):
        for part in geom.geoms:
            a = arr_from_coords(part.coords)
            if a is not None:
                out.append(a)
    elif isinstance(geom, Polygon):
        if geom.exterior is not None:
            a = arr_from_coords(geom.exterior.coords)
            if a is not None:
                out.append(a)
        if include_holes and getattr(geom, "interiors", None):
            for ring in geom.interiors:  # type: ignore[attr-defined]
                if isinstance(ring, LinearRing):
                    a = arr_from_coords(ring.coords)
                else:
                    a = arr_from_coords(getattr(ring, "coords", None))
                if a is not None:
                    out.append(a)
    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            out.extend(iter_lines(poly, include_holes))
    elif isinstance(geom, GeometryCollection):
        for g in geom.geoms:
            out.extend(iter_lines(g, include_holes))
    else:
        b = getattr(geom, "boundary", None)
        if b is not None:
            out.extend(iter_lines(b, include_holes))
        else:
            a = arr_from_coords(getattr(geom, "coords", None))
            if a is not None:
                out.append(a)
    return out


def _segments_from_geoms(geoms, include_holes: bool = False) -> List[np.ndarray]:
    """Convert an iterable of shapely geometries to a list of (N,2) arrays."""
    segs: List[np.ndarray] = []
    for g in geoms:
        segs.extend(iter_lines(g, include_holes))
    # Filter degenerate/empty
    segs = [s for s in segs if isinstance(s, np.ndarray) and s.ndim == 2 and s.shape[0] >= 2]
    return segs


def _plot_lines(ax, lines: List[np.ndarray], color: str = "C0", lw: float = 0.5, zorder: int = 2):
    if not lines:
        return
    lc = LineCollection(lines, colors=color, linewidths=lw, zorder=zorder)
    ax.add_collection(lc)


def make_valid(geom):  # pragma: no cover - depends on shapely version
    try:
        from shapely.validation import make_valid as _mv  # type: ignore
        return _mv(geom)
    except Exception:
        try:
            return geom.buffer(0)
        except Exception:
            return geom


def iter_boundaries(geom, include_holes: bool = False):  # pragma: no cover - thin shim over shapely
    try:
        from shapely.geometry import (
            Polygon,
            MultiPolygon,
            LineString,
            MultiLineString,
            GeometryCollection,
        )  # type: ignore
    except Exception:
        return
    if geom is None or getattr(geom, "is_empty", False):
        return
    if isinstance(geom, Polygon):
        g = make_valid(geom)
        if getattr(g, "exterior", None):
            yield list(g.exterior.coords)
        if include_holes and getattr(g, "interiors", None):
            for r in g.interiors:
                yield list(r.coords)
    elif isinstance(geom, MultiPolygon):
        for g in geom.geoms:
            yield from iter_boundaries(g, include_holes)
    elif isinstance(geom, LineString):
        yield list(geom.coords)
    elif isinstance(geom, MultiLineString):
        for ln in geom.geoms:
            yield list(ln.coords)
    elif isinstance(geom, GeometryCollection):
        for g in geom.geometries:
            yield from iter_boundaries(g, include_holes)


def plot_geoms_as_lines(ax, geoms, include_holes: bool = False, **kw):
    for geom in geoms:
        for coords in iter_boundaries(geom, include_holes):
            if not coords:
                continue
            arr = np.asarray(coords)
            if arr.ndim == 2 and arr.shape[0] >= 2:
                ax.plot(arr[:, 0], arr[:, 1], **kw)


def plot_coastline_overlay(
    shp_path: Path,
    mesh_bbox: Tuple[float, float, float, float],
    outdir: Path,
    include_holes: bool = True,
    target_crs: Optional[str] = None,
) -> Path:
    if gpd is None:
        raise RuntimeError("geopandas is required to plot coastline overlay")
    _ensure_outdir(outdir)
    gdf = gpd.read_file(shp_path)  # type: ignore
    try:
        if target_crs:
            gdf = gdf.to_crs(target_crs)  # type: ignore
        else:
            # Default to geographic if possible
            gdf = gdf.to_crs(epsg=4326)  # type: ignore
    except Exception:
        pass
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    # Draw each boundary independently; no implicit joins
    try:
        plot_geoms_as_lines(ax, gdf.geometry, include_holes=include_holes, color="C0", linewidth=0.6, zorder=2)  # type: ignore
    except Exception:
        # Fallback via LineCollection if plotting as individual lines fails
        segments = _segments_from_geoms(gdf.geometry, include_holes=include_holes)  # type: ignore
        _plot_lines(ax, segments, color="C0", lw=0.5, zorder=2)
    ax.set_title("Coastline Overlay")
    ax.set_xlabel("Lon/X")
    ax.set_ylabel("Lat/Y")
    ax.set_xlim([mesh_bbox[0], mesh_bbox[2]])
    ax.set_ylim([mesh_bbox[1], mesh_bbox[3]])
    ax.set_aspect("equal", adjustable="box")
    png = outdir / "coastline_overlay.png"
    fig.tight_layout()
    fig.savefig(png)
    plt.close(fig)
    return png
