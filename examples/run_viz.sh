#!/usr/bin/env bash
set -euo pipefail

# One-mesh visualizer for Tokyo Bay.
# Edit only MESH="..." to target another mesh. By default, only mesh.png is produced at DPI=600.
# Add --coastline / --openboundaries / --all to change what gets plotted.
#
# Pass additional 'omt viz' flags after a '--' separator, e.g.:
#   ./run_viz.sh --coastline -- --no-dem --dpi 300

# ========= USER-EDITABLE =========
MESH="tb_uniform_400m"    # e.g., tb_futtsu_5regions / tb_uniform_400m / <your mesh>
DEFAULT_DPI=600
# =================================

OM2D_DIR="${HOME}/Github/OceanMesh2D"
REGION="Tokyo_Bay"
TB_DIR="${OM2D_DIR}/${REGION}"
PAIRS_FILE="${TB_DIR}/pairs.yaml"

# Known mapping from mesh name -> MATLAB script (extend as needed)
declare -A KNOWN_SCRIPT=(
  [tb_futtsu_5regions]="${TB_DIR}/scripts/mesh_wide_futtsu_5r.m"
  [tb_uniform_400m]="${TB_DIR}/scripts/mesh_bay_uniform_400m.m"
)

usage() {
  cat <<USAGE
Usage: $(basename "$0") [figure switches] [-- extra-omt-viz-args]

Figure switches (default: mesh-only):
  --mesh             include mesh.png        (on by default)
  --coastline        include coastline_overlay.png
  --openboundaries   include open_boundaries.png
  --all              include all of the above

General:
  --dpi N            set DPI (default: ${DEFAULT_DPI})
  -h, --help         show this help

Pass additional 'omt viz' flags after --.
Examples:
  $(basename "$0")                           # mesh.png only (DPI=600)
  $(basename "$0") --coastline               # mesh + coastline
  $(basename "$0") --all                     # mesh + coastline + open boundaries
  $(basename "$0") --dpi 300 -- --no-dem     # mesh only, DPI=300, pass --no-dem to 'omt viz'
USAGE
}

abspath() {
  local p="$1"
  if command -v readlink >/dev/null 2>&1; then readlink -f "$p" 2>/dev/null || echo "$p"
  elif command -v realpath >/dev/null 2>&1; then realpath "$p" 2>/dev/null || echo "$p"
  else echo "$p"; fi
}

err() { echo "ERROR: $*" >&2; exit 1; }
warn(){ echo "WARN:  $*" >&2; }
info(){ echo "$*"; }

# -------- parse script options --------
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
    --dpi)             [[ $# -ge 2 ]] || err "--dpi requires a number"; DPI="$2"; shift 2 ;;
    --with-dem)        WITH_DEM=1; shift ;;
    -h|--help)         usage; exit 0 ;;
    --)                shift; EXTRA_ARGS=("$@"); break ;;   # pass-through to omt viz
    *)                 err "Unknown option: $1 (use --help)" ;;
  esac
done

# Default is mesh-only; if user didn't specify any figure switches, keep want_mesh=1
if (( want_mesh==0 && want_coast==0 && want_open==0 )); then
  want_mesh=1
fi

# -------- resolve inputs --------
mkdir -p "${TB_DIR}"

FORT14="${TB_DIR}/outputs/meshes/${MESH}.14"
[[ -f "${FORT14}" ]] || err "fort.14 not found: ${FORT14}
- Check MESH='${MESH}'
- Expected: ${TB_DIR}/outputs/meshes/${MESH}.14"

# Resolve MATLAB script (known mapping or heuristic search)
SCRIPT=""
if [[ -n "${KNOWN_SCRIPT[${MESH}]:-}" && -f "${KNOWN_SCRIPT[${MESH}]}" ]]; then
  SCRIPT="${KNOWN_SCRIPT[${MESH}]}"
else
  shopt -s nullglob
  mapfile -t CAND < <(grep -ilE "${MESH//_/[_-]}|${MESH}" "${TB_DIR}/scripts/"*.m 2>/dev/null || true)
  if [[ ${#CAND[@]} -eq 0 ]]; then
    for f in "${TB_DIR}/scripts/"*.m; do
      [[ "${f##*/}" == *"${MESH}"*.m ]] && CAND+=("$f")
    done
  fi
  if   [[ ${#CAND[@]} -eq 1 ]]; then SCRIPT="${CAND[0]}"
  elif [[ ${#CAND[@]} -gt 1 ]]; then
    printf "Candidate MATLAB scripts for %s:\n" "${MESH}"
    printf "  - %s\n" "${CAND[@]}"
    err "Multiple script candidates found. Set KNOWN_SCRIPT[${MESH}] in this script."
  else
    err "No MATLAB script found for ${MESH} under ${TB_DIR}/scripts."
  fi
fi

FORT14_ABS="$(abspath "${FORT14}")"
SCRIPT_ABS="$(abspath "${SCRIPT}")"
info "[omt] Using fort14 : ${FORT14_ABS}"
info "[omt] Using script : ${SCRIPT_ABS}"

# -------- write single-pair file --------
info "[omt] Writing pairs file: ${PAIRS_FILE}"
cat > "${PAIRS_FILE}" <<YAML
pairs:
  - fort14: ${FORT14_ABS}
    script: ${SCRIPT_ABS}
YAML

# -------- scan --------
info "==> Step 1/2: Running omt scan..."
omt scan --pairs-file "${PAIRS_FILE}" --out catalog.json
info "✓ scan done"

# -------- viz (direct driver; no CLI flags needed) --------
OUT_DIR="figs/${MESH}"
mkdir -p "${OUT_DIR}"

# Build requested list (strings)
declare -a FIGS=()
(( want_mesh )) && FIGS+=("mesh")
(( want_coast )) && FIGS+=("coastline")
(( want_open )) && FIGS+=("openboundaries")
# default (no switches) -> mesh only
if (( ${#FIGS[@]} == 0 )); then FIGS=("mesh"); fi

PYDRV="$(dirname "$0")/mesh_viz_driver.py"
[[ -x "${PYDRV}" ]] || chmod +x "${PYDRV}"

info "==> Step 2/2: Visualizing ${MESH} (direct driver)..."
"${PYDRV}" \
  --fort14 "${FORT14_ABS}" \
  --catalog catalog.json \
  --out "${OUT_DIR}" \
  --dpi "${DPI}" \
  ${WITH_DEM:+--dem} \
  --figs "${FIGS[@]}"
info "✓ viz done (direct)"

info "[omt] Done. Outputs under ${OUT_DIR}"
