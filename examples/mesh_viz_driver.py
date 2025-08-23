#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from oceanmesh_tools.plot import viz as vizmod
from oceanmesh_tools.io.fort14 import mesh_bbox_from_fort14


def main() -> int:
    ap = argparse.ArgumentParser(description="Direct driver for mesh/coastline/open-boundaries figures")
    ap.add_argument("--fort14", required=True, help="Path to fort.14 file")
    ap.add_argument("--catalog", required=False, default=None, help="Path to catalog.json (unused in direct driver)")
    ap.add_argument("--out", required=True, help="Output directory")
    ap.add_argument("--dpi", type=int, default=600, help="Savefig DPI (default: 600)")
    ap.add_argument("--figs", nargs="+", default=["mesh"], choices=["mesh", "coastline", "openboundaries"], help="Figures to render")
    ap.add_argument("--dem", action="store_true", default=False, help="Enable DEM underlay on mesh figure (default: off)")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    f14 = Path(args.fort14)

    # Mesh figure with overlays; DEM is opt-in
    if "mesh" in args.figs:
        vizmod.plot_mesh(
            f14_path=f14,
            outdir=outdir,
            mesh_add_coastline=True,
            mesh_add_open_boundaries=True,
            dem_enable=bool(args.dem),
            dem_path=None,
            dpi=int(args.dpi) if args.dpi else None,
        )

    # Coastline-only overlay via mesh14 path (no shapefile)
    if "coastline" in args.figs:
        bbox = mesh_bbox_from_fort14(f14)
        vizmod.plot_coastline_overlay(
            shp_path=f14,  # unused when coast_source='mesh14'
            mesh_bbox=bbox,
            outdir=outdir,
            fort14_path=f14,
            coast_source="mesh14",
            dpi=int(args.dpi) if args.dpi else None,
        )

    # Open-boundaries-only figure
    if "openboundaries" in args.figs:
        vizmod.plot_open_boundaries(f14_path=f14, outdir=outdir, dpi=int(args.dpi) if args.dpi else None)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

