#!/usr/bin/env bash
set -euo pipefail

# One-mesh visualizer (single-file).
# Default: mesh.png only, DPI=600, DEM OFF, with coastline/open-boundary overlays.
# Add --coastline / --openboundaries / --all / --with-dem as needed.

# ========= USER-EDITABLE =========
MESH="tb_uniform_400m"   # e.g., tb_futtsu_5regions / tb_uniform_400m / <your mesh>
DEFAULT_DPI=600
# =================================

OM2D_DIR="${HOME}/Github/OceanMesh2D"
REGION="Tokyo_Bay"
TB_DIR="${OM2D_DIR}/${REGION}"
PAIRS_FILE="${TB_DIR}/pairs.yaml"

# Known mapping (extend as needed)
declare -A KNOWN_SCRIPT=(
  [tb_futtsu_5regions]="${TB_DIR}/scripts/mesh_wide_futtsu_5r.m"
  [tb_uniform_400m]="${TB_DIR}/scripts/mesh_bay_uniform_400m.m"
)

usage() {
  cat <<USAGE
Usage: $(basename "$0") [figure switches] [-- passthrough-args]

Figure switches (default: mesh-only):
  --mesh             include mesh.png          (default ON)
  --coastline        include coastline_overlay.png
  --openboundaries   include open_boundaries.png
  --all              include all figures

General:
  --with-dem         enable DEM underlay for mesh figure (default OFF)
  --dpi N            set DPI (default: ${DEFAULT_DPI})
  -h, --help         show this help
USAGE
}

abspath() {
  local p="$1"
  if command -v readlink >/dev/null 2>&1; then readlink -f "$p" 2>/dev/null || echo "$p"
  elif command -v realpath >/dev/null 2>&1; then realpath "$p" 2>/dev/null || echo "$p"
  else echo "$p"; fi
}
err()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "$*"; }

# ---- parse options ----
want_mesh=1
want_coast=0
want_open=0
WITH_DEM=0
DPI="${DEFAULT_DPI}"
EXTRA_ARGS=()

while (( $# )); do
  case "$1" in
    --mesh)            want_mesh=1; shift ;;
    --coastline)       want_coast=1; shift ;;
    --openboundaries)  want_open=1; shift ;;
    --all)             want_mesh=1; want_coast=1; want_open=1; shift ;;
    --with-dem)        WITH_DEM=1; shift ;;
    --dpi)             [[ $# -ge 2 ]] || err "--dpi requires a number"; DPI="$2"; shift 2 ;;
    -h|--help)         usage; exit 0 ;;
    --)                shift; EXTRA_ARGS=("$@"); break ;;
    *)                 err "Unknown option: $1 (use --help)";;
  esac
done
# default to mesh-only if nothing selected
if (( want_mesh==0 && want_coast==0 && want_open==0 )); then want_mesh=1; fi

# ---- resolve inputs ----
mkdir -p "${TB_DIR}"

FORT14="${TB_DIR}/outputs/meshes/${MESH}.14"
[[ -f "${FORT14}" ]] || err "fort.14 not found: ${FORT14}"

# MATLAB script (for scan)
SCRIPT=""
if [[ -n "${KNOWN_SCRIPT[${MESH}]:-}" && -f "${KNOWN_SCRIPT[${MESH}]}" ]]; then
  SCRIPT="${KNOWN_SCRIPT[${MESH}]}"
else
  shopt -s nullglob
  mapfile -t CAND < <(grep -ilE "${MESH//_/[_-]}|${MESH}" "${TB_DIR}/scripts/"*.m 2>/dev/null || true)
  if [[ ${#CAND[@]} -eq 0 ]]; then
    for f in "${TB_DIR}/scripts/"*.m; do [[ "${f##*/}" == *"${MESH}"*.m ]] && CAND+=("$f"); done
  fi
  if   [[ ${#CAND[@]} -eq 1 ]]; then SCRIPT="${CAND[0]}"
  elif [[ ${#CAND[@]} -gt 1 ]]; then printf "Candidate MATLAB scripts for %s:\n" "${MESH}"; printf "  - %s\n" "${CAND[@]}"; err "Multiple scripts found. Edit KNOWN_SCRIPT."
  else err "No MATLAB script found for ${MESH} under ${TB_DIR}/scripts."; fi
fi

FORT14_ABS="$(abspath "${FORT14}")"
SCRIPT_ABS="$(abspath "${SCRIPT}")"
info "[omt] Using fort14 : ${FORT14_ABS}"
info "[omt] Using script : ${SCRIPT_ABS}"

# ---- scan (auto-select shapefile/DEM candidates) ----
info "[omt] Writing pairs file: ${PAIRS_FILE}"
cat > "${PAIRS_FILE}" <<YAML
pairs:
  - fort14: ${FORT14_ABS}
    script: ${SCRIPT_ABS}
YAML

info "==> Step 1/2: Running omt scan..."
omt scan --pairs-file "${PAIRS_FILE}" --out catalog.json
info "✓ scan done"

# ---- viz (direct call; no 'omt viz') ----
OUT_DIR="figs/${MESH}"
mkdir -p "${OUT_DIR}"

# Requested figures (default: mesh)
FIGS=()
(( want_mesh )) && FIGS+=("mesh")
(( want_coast )) && FIGS+=("coastline")
(( want_open )) && FIGS+=("openboundaries")
if (( ${#FIGS[@]} == 0 )); then FIGS=("mesh"); fi

info "==> Step 2/2: Visualizing ${MESH} (direct)..."
MESH_FORT14="${FORT14_ABS}" \
MESH_OUT="${OUT_DIR}" \
MESH_DPI="${DPI}" \
MESH_DEM="${WITH_DEM}" \
MESH_FIGS="${FIGS[*]}" \
python - "$@" <<'PY'
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
from oceanmesh_tools.plot import viz as V

fort14 = os.environ["MESH_FORT14"]
out    = Path(os.environ["MESH_OUT"])  # must be Path-like
dpi    = int(os.environ.get("MESH_DPI","600"))
dem_on = os.environ.get("MESH_DEM","0") in ("1","true","True","YES","yes","on")
figs   = os.environ.get("MESH_FIGS","mesh").split()

if "mesh" in figs:
    V.plot_mesh(f14_path=fort14, outdir=out, mesh_add_coastline=True, mesh_add_open_boundaries=True, dem_enable=dem_on, dem_path=None, dpi=dpi)
if "coastline" in figs:
    V.plot_coastline_overlay(shp_path=fort14, mesh_bbox=V.mesh_bbox_from_fort14(fort14) if hasattr(V, 'mesh_bbox_from_fort14') else (0,0,0,0), outdir=out, fort14_path=fort14, coast_source="mesh14", dpi=dpi)
if "openboundaries" in figs:
    V.plot_open_boundaries(f14_path=fort14, outdir=out, dpi=dpi)
PY

info "✓ viz done"
info "[omt] Done. Outputs under ${OUT_DIR}"
