# oceanmesh-tools
Utilities for scanning OceanMesh2D MATLAB inputs and visualizing ADCIRC meshes.

Note: Local data are referenced in place — no data files are copied or moved by these tools.

Local Data Model

- OceanMesh2D root: `$HOME/Github/OceanMesh2D/` (lowercase `h`)
- Region example: `Tokyo_Bay/`
- Region data: `$HOME/Github/OceanMesh2D/Tokyo_Bay/data/`
- Shared datasets: `$HOME/Github/OceanMesh2D/datasets/`
- Optional `.oceanmesh-tools.yaml` in this repo or `$HOME`:

```
oceanmesh2d_dir: "/home/you/Github/OceanMesh2D"
default_region: "Tokyo_Bay"
search_paths:
  dem:
    - "/home/you/Github/OceanMesh2D/Tokyo_Bay/data"
  shp:
    - "/home/you/Github/OceanMesh2D/Tokyo_Bay/data"
```

Quickstart

- Install (editable): `pip install -e .`
- Scan Tokyo Bay scripts and build a catalog:
  - `omt scan --oceanmesh2d-dir $HOME/Github/OceanMesh2D --region Tokyo_Bay --out catalog.json`
- Visualize a mesh with auto-detected inputs:
  - `omt viz --fort14 $HOME/Github/OceanMesh2D/Tokyo_Bay/meshes/NAME.14 --catalog catalog.json --out figs/NAME`
- Override inputs explicitly:
  - `omt viz --fort14 /path/to/NAME.14 --dem /path/to/dem.tif --shp /path/to/coast.shp --out figs/NAME`

When .14 and .m Names Differ

- Use `--script` to pair a mesh with its generating MATLAB script and resolve inputs directly:
  - `omt viz --fort14 /path/to/tb_futtsu_5regions.14 --script /path/to/genMesh_futtsu.m --out figs/tb_futtsu_5regions`
- Build a catalog from explicit pairs for later runs:
  - Create `pairs.yaml`:
    
    - fort14: /abs/path/tb_futtsu_5regions.14
      script: /abs/path/genMesh_futtsu.m
  
  - `omt scan --pairs-file pairs.yaml --out catalog.json`
  - Then: `omt viz --fort14 /abs/path/tb_futtsu_5regions.14 --catalog catalog.json --out figs/tb_futtsu_5regions`

Notes on DEM Handling

- NetCDF DEMs: If GDAL/`rasterio` cannot open `.nc`, the tool automatically falls back to `xarray` (`ds.to_array().squeeze()`), with a warning: "rasterio could not read NetCDF; falling back to xarray." Rasterio + libgdal-netcdf is optional but recommended for performance.
- Summary shows both the chosen input and all detected candidates:
  - `DEMs: primary=<path> (used), candidates=[...]`
  - `Shapefiles: primary=<path> (used), candidates=[...]`


Configuration

- Optional `.oceanmesh-tools.yaml` in repo root or `$HOME` supports:
  - `oceanmesh2d_dir`, `search_paths.dem[]`, `search_paths.shp[]`, `default_region`.
- Env vars (override YAML): `OMT_OCEANMESH2D_DIR`, `OMT_DEM_PATHS`, `OMT_SHP_PATHS`, `OMT_DEFAULT_REGION`.

CLI Summary

- `omt scan`: Recursively scans MATLAB `.m` files under `<dir>/<Region>/` to detect mesh names (`write(m,'NAME')`) and input hints from `geodata(...)` or variable assignments. Resolves shapefile/DEM candidates from `<Region>/data/` then `datasets/`.
- `omt viz`: Plots `mesh.png`, `bathymetry_filled.png`, `bathymetry_contours.png`, `coastline_overlay.png`, `open_boundaries.png`. Handles CRS via geopandas/rasterio if available.
  - Flags: `--require-inputs` fails with non-zero exit if DEM/Shapefile cannot be resolved and prints a "Resolution attempts" summary.
  - Coastline options: `--coast-include-holes` includes polygon interior rings (holes) when drawing coastlines; by default only exteriors are drawn.

Fixes and Notes

- Coastline overlay: previously only a single outer ring could be drawn for some shapefiles, hiding islands. The plotter now iterates polygon boundaries and can include holes with `--coast-include-holes`.
- Open boundaries: previously disjoint segments could be connected by long straight chords. The plotter now splits per-boundary polylines on large spatial gaps to avoid spurious connections.

See also the quickstart notebook in `notebooks/00_quickstart.ipynb`.

**Usage Examples**

- End-to-end Tokyo Bay workflow:
  - Run: `bash examples/run_viz.sh`
  - The script:
    - Writes `$HOME/Github/OceanMesh2D/Tokyo_Bay/pairs.yaml` (overwrites if present) with:
      
      pairs:
        - fort14: $HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_futtsu_5regions.14
          script: $HOME/Github/OceanMesh2D/Tokyo_Bay/scripts/mesh_wide_futtsu_5r.m
        - fort14: $HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_uniform_400m.14
          script: $HOME/Github/OceanMesh2D/Tokyo_Bay/scripts/mesh_bay_uniform_400m.m
      
    - Builds a catalog: `omt scan --pairs-file $HOME/Github/OceanMesh2D/Tokyo_Bay/pairs.yaml --out catalog.json`
    - Visualizes two meshes to `figs/<meshname>`:
      - `tb_futtsu_5regions.14` → `figs/tb_futtsu_5regions`
      - `tb_uniform_400m.14` → `figs/tb_uniform_400m`
  - Requirements: OceanMesh2D data under `$HOME/Github/OceanMesh2D/Tokyo_Bay/` and `omt` installed (`make install`).
