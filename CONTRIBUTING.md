Contributing to oceanmesh-tools

Environment

- Requires Python 3.12+.
- Create and activate the Conda environment with micromamba/conda:
  - micromamba: `micromamba create -f environment.yml && micromamba activate omtool`
  - conda: `conda env create -f environment.yml && conda activate omtool`

Install

- Editable install for development:
  - `pip install -e .`

Test and Lint

- Run tests: `pytest -q`
- Lint (lightweight): `ruff check .`

CLI

- The CLI entry point is `omt` with subcommands `scan` and `viz`.
- Show help: `omt --help`

Local Data Model

- This project references data in-place from a separate OceanMesh2D checkout.
- No data are copied; paths are resolved against:
  - `$HOME/Github/OceanMesh2D/<Region>/data/`
  - `$HOME/Github/OceanMesh2D/datasets/`
- Optionally create `.oceanmesh-tools.yaml` in this repo or in `$HOME`:

```
oceanmesh2d_dir: "/home/you/Github/OceanMesh2D"
default_region: "Tokyo_Bay"
search_paths:
  dem:
    - "/home/you/Github/OceanMesh2D/Tokyo_Bay/data"
  shp:
    - "/home/you/Github/OceanMesh2D/Tokyo_Bay/data"
```

