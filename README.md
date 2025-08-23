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

What's New

- Fast coastline and open-boundary overlays directly from `fort.14` (mesh14 path):
  - Reads boundary sections and renders strictly per edge using Matplotlib `LineCollection`.
  - No accidental concatenation across segments; safeguards and validations added.
  - Optional debug mode writes NPZ/CSV/PNG artifacts and fail-fast on suspicious edges.

Quick Start: Mesh14 Overlays

```bash
cd examples
./run_viz.sh -- --coast-source mesh14 --include-ibtype 0 20 21
# or manually
omt viz \
  --fort14 $HOME/Github/OceanMesh2D/Tokyo_Bay/meshes/NAME.14 \
  --catalog catalog.json \
  --coast-source mesh14 \
  --include-ibtype 0 20 21 \
  --out figs/NAME
```

- Outputs:
  - `mesh.png` with coastline (red) and open boundaries (blue) overlays.
  - `coastline_overlay.png` showing only coastline (plus optional thin gray shapefile background).

CLI Options (selected)

- `--coast-source {mesh14, mesh, shp}`: coastline source (default: `mesh14`).
- `--include-ibtype INT...`: land IBTYPEs treated as coastline (default: `0 20 21`).
- `--mesh-add-coastline` / `--mesh-add-open-boundaries`: enable overlays on `mesh.png` (default: on).
- `--coast-shp-background PATH`: optional shapefile drawn as thin gray background.
- `--debug-boundaries` / `--no-debug-boundaries`: write debug artifacts and fail-fast on suspicious edges (default: off).
- `--edge-length-threshold-deg FLOAT`: flag edges longer than threshold (deg) in debug (default: 1.5).
- `--progress` is on by default; progress steps print:
  - `[1/2] Reading fort.14 boundaries ...`
  - `[2/2] Building polylines ...`

Debugging Boundaries

- With `--debug-boundaries`, the tool writes to your `--out` directory:
  - `boundary_debug_edges.npz`: nodes, edges, segments, and per-edge lengths.
  - `boundary_readback.txt`: NOPE/NBOU and NBOB/NBOBN plus a summary of first segments.
  - `suspicious_coast_edges.csv` / `suspicious_open_edges.csv`: first 200 long edges.
  - `boundary_debug.png`: highlights suspicious edges.
- The viz may fail-fast with a clear error when suspicious coastline edges are found.

Performance

- The mesh14 path runs in O(number of boundary nodes), using `LineCollection` to efficiently plot edges.
- Typical timing is printed in the progress logs.

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
- `omt viz`: Plots `mesh.png`, optionally `coastline_overlay.png` and `open_boundaries.png`. DEM plots are opt-in.
  - New: `--figs {mesh,coastline,openboundaries}...` to select which figures to render; `--dpi INT` to set save DPI; `--dem/--no-dem` to enable/disable DEM plots (default: off).
  - Flags: `--require-inputs` fails with non-zero exit if DEM/Shapefile cannot be resolved and prints a "Resolution attempts" summary.
  - Coastline options: `--coast-include-holes` includes polygon interior rings (holes) when drawing coastlines; by default only exteriors are drawn.

Fixes and Notes

- Coastline overlay: previously only a single outer ring could be drawn for some shapefiles, hiding islands. The plotter now iterates polygon boundaries and can include holes with `--coast-include-holes`.
- Open boundaries: previously disjoint segments could be connected by long straight chords. The plotter now splits per-boundary polylines on large spatial gaps to avoid spurious connections.

Known Pitfalls

- Shapefile validity: invalid polygons may render oddly. The coastline plotter attempts to "make valid" geometries or uses a zero-width buffer fallback. If artifacts persist, repair the shapefile in a GIS tool and try again.
- CRS handling: if the shapefile CRS differs from the mesh coordinate system, provide an explicit CRS via `--crs` so the coastline is reprojected accordingly.

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

Examples (CLI):

```bash
# Only mesh.png, at DPI=600
omt viz --fort14 /path/to/mesh.14 --out figs/NAME --figs mesh --dpi 600

# Mesh + coastline overlays (coastline_overlay.png)
omt viz --fort14 /path/to/mesh.14 --out figs/NAME --figs mesh coastline

# Open boundaries only, DPI=300
omt viz --fort14 /path/to/mesh.14 --out figs/NAME --figs openboundaries --dpi 300
```

Housekeeping

```bash
make clean        # untrack generated files (keeps local copies)
make clean-purge  # also delete generated/debug artifacts in working tree
```

- Generated artifacts (e.g., `figs/`, `catalog.json`, `pairs.yaml`, and debug dumps) are git-ignored.

### One-mesh runner (mesh-only by default, DPI=600, DEM off)

```bash
cd examples
./run_viz.sh                       # mesh.png only (DPI=600), DEM off
./run_viz.sh --with-dem            # mesh.png only, DEM on
./run_viz.sh --coastline           # mesh + coastline
./run_viz.sh --openboundaries      # mesh + open boundaries
./run_viz.sh --all                 # mesh + coastline + open boundaries
./run_viz.sh --dpi 300 -- --no-dem # pass extra flags to 'omt viz'
```

Edit `MESH="..."` at the top of the script to target a different mesh. The script auto-detects the matching MATLAB script; if ambiguous or missing, it prints a helpful message and exits.

Defaults

- Mesh figure overlays: coastline (red) and open-boundary (blue) are on by default.
- DEM is off by default; enable with `--dem` (or `--with-dem` in the example script).

Note: The example runner now uses a direct Python driver to render only the requested figures (faster, no warnings). It still uses `omt scan` to build `catalog.json` for convenience.
