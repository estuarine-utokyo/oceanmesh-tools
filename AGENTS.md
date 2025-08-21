# Repository Guidelines

## Project Structure & Module Organization
- `src/oceanmesh_tools/`: Python package.
  - `cli.py`: CLI entrypoint (`omt`).
  - `scan/`: MATLAB input scanning and hint resolution.
  - `io/fort14.py`: ADCIRC `fort.14` parser and helpers.
  - `plot/viz.py`: Mesh and data visualization.
- `tests/`: Pytest suite with fixtures in `tests/fixtures/`.
- `notebooks/`: Quickstart and exploration.
- `figs/`: Example outputs written by `omt viz`.
- Optional config: `.oceanmesh-tools.yaml` in repo root or `$HOME`.

## Build, Test, and Development Commands
- `make install`: Editable install (`pip install -e .`).
- `make test` or `pytest -q`: Run tests.
- `make lint` or `ruff check .`: Lint with Ruff.
- `omt --help`: CLI help.
- Examples:
  - Scan: `omt scan --oceanmesh2d-dir $HOME/Github/OceanMesh2D --region Tokyo_Bay --out catalog.json`
  - Viz: `omt viz --fort14 $HOME/Github/OceanMesh2D/Tokyo_Bay/meshes/NAME.14 --catalog catalog.json --out figs/NAME`

## Coding Style & Naming Conventions
- Python 3.12+, PEP 8; Ruff enforces line length 100 (`pyproject.toml`).
- Functions/modules: `snake_case`; classes: `PascalCase`.
- Prefer type hints and concise, focused functions.
- Keep responsibilities separated: I/O in `io`, scanning in `scan`, plotting in `plot`; keep `cli` thin.

## Testing Guidelines
- Framework: `pytest`; tests named `test_*.py` under `tests/`.
- Place sample assets in `tests/fixtures/`.
- Add unit tests when changing parser logic, scanners, or CLI options.
- Focused runs: `pytest -q -k fort14`.

## Commit & Pull Request Guidelines
- Use Conventional Commit style seen in history: `feat:`, `fix:`, `chore(ci):`.
- PRs should include:
  - Clear description, motivation, and linked issues.
  - Before/after images (from `figs/`) when visual output changes.
  - Doc updates (e.g., `README.md`) when CLI or behavior changes.
- Keep diffs minimal; do not include generated data or large binaries.

## Security & Configuration Tips
- Do not commit datasets; reference paths via `.oceanmesh-tools.yaml` or env vars (`OMT_*`).
- Prefer conda/micromamba for the geospatial stack (see `environment.yml`).
- Avoid hard-coded user paths; ensure commands are cross-platform when feasible.

