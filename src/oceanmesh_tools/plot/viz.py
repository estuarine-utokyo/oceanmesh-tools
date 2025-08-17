from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt

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

from ..io.fort14 import Fort14, parse_fort14


def _ensure_outdir(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)


def plot_mesh(f14_path: Path, outdir: Path) -> Path:
    _ensure_outdir(outdir)
    mesh = parse_fort14(f14_path)
    xs = {nid: x for nid, x, y, d in mesh.nodes}
    ys = {nid: y for nid, x, y, d in mesh.nodes}
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    for _, n1, n2, n3, _ in mesh.elements:
        ax.plot([xs[n1], xs[n2]], [ys[n1], ys[n2]], color="k", linewidth=0.2)
        ax.plot([xs[n2], xs[n3]], [ys[n2], ys[n3]], color="k", linewidth=0.2)
        ax.plot([xs[n3], xs[n1]], [ys[n3], ys[n1]], color="k", linewidth=0.2)
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
    # Highlight open boundaries
    for i, b in enumerate(mesh.open_boundaries, start=1):
        bx = [xs[n] for n in b]
        by = [ys[n] for n in b]
        ax.plot(bx, by, linewidth=1.0, label=f"Open {i}", zorder=2)
    ax.legend()
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
    if rasterio is None:
        raise RuntimeError("rasterio is required to plot bathymetry")
    _ensure_outdir(outdir)
    with rasterio.open(dem_path) as src:  # type: ignore
        data = src.read(1, masked=True)
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        img = ax.imshow(data, extent=[src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top], origin="upper")
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


def plot_bathymetry_contours(dem_path: Path, outdir: Path) -> Path:
    if rasterio is None:
        raise RuntimeError("rasterio is required to plot bathymetry contours")
    _ensure_outdir(outdir)
    with rasterio.open(dem_path) as src:  # type: ignore
        data = src.read(1, masked=True)
        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        cs = ax.contour(
            [src.bounds.left, src.bounds.right],
            [src.bounds.bottom, src.bounds.top],
            data,
            levels=10,
            linewidths=0.5,
            colors="k",
        )
        ax.clabel(cs, inline=True, fontsize=6)
        ax.set_title("Bathymetry (Contours)")
        ax.set_xlabel("Lon/X")
        ax.set_ylabel("Lat/Y")
        png = outdir / "bathymetry_contours.png"
        fig.tight_layout()
        fig.savefig(png)
        plt.close(fig)
        return png


def plot_coastline_overlay(shp_path: Path, mesh_bbox: Tuple[float, float, float, float], outdir: Path) -> Path:
    if gpd is None:
        raise RuntimeError("geopandas is required to plot coastline overlay")
    _ensure_outdir(outdir)
    gdf = gpd.read_file(shp_path)  # type: ignore
    try:
        gdf = gdf.to_crs(epsg=4326)  # type: ignore
    except Exception:
        pass
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    gdf.plot(ax=ax, color="none", edgecolor="C0", linewidth=0.5)  # type: ignore
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

