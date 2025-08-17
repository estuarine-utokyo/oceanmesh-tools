# oceanmesh-tools
Utilities for scanning OceanMesh2D MATLAB inputs and visualizing ADCIRC meshes.

Note: Local data are referenced in place — no data files are copied or moved by these tools.

Quickstart

- Install (editable): `pip install -e .`
- Scan Tokyo Bay scripts and build a catalog:
  - `omt scan --oceanmesh2d-dir $HOME/Github/OceanMesh2D --region Tokyo_Bay --out catalog.json`
- Visualize a mesh with auto-detected inputs:
  - `omt viz --fort14 $HOME/Github/OceanMesh2D/Tokyo_Bay/meshes/NAME.14 --catalog catalog.json --out figs/NAME`
- Override inputs explicitly:
  - `omt viz --fort14 /path/to/NAME.14 --dem /path/to/dem.tif --shp /path/to/coast.shp --out figs/NAME`

Configuration

- Optional `.oceanmesh-tools.yaml` in repo root or `$HOME` supports:
  - `oceanmesh2d_dir`, `search_paths.dem[]`, `search_paths.shp[]`, `default_region`.
- Env vars (override YAML): `OMT_OCEANMESH2D_DIR`, `OMT_DEM_PATHS`, `OMT_SHP_PATHS`, `OMT_DEFAULT_REGION`.

CLI Summary

- `omt scan`: Recursively scans MATLAB `.m` files under `<dir>/<Region>/` to detect mesh names (`write(m,'NAME')`) and input hints from `geodata(...)` or variable assignments. Resolves shapefile/DEM candidates from `<Region>/data/` then `datasets/`.
- `omt viz`: Plots `mesh.png`, `bathymetry_filled.png`, `bathymetry_contours.png`, `coastline_overlay.png`, `open_boundaries.png`. Handles CRS via geopandas/rasterio if available.
