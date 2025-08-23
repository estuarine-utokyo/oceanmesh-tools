#!/usr/bin/env bash
set -euo pipefail

# One-mesh viz runner for Tokyo Bay.
# Edit only the line: MESH="..." to change target mesh.
# DEM/coastline are auto-detected by `omt scan` using the MATLAB script.

# ========= USER-EDITABLE =========
MESH="tb_uniform_400m"   # e.g., "tb_futtsu_5regions" / "tb_uniform_400m" / <your mesh>
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

abspath() {
  local p="$1"
  if command -v readlink >/dev/null 2>&1; then readlink -f "$p" 2>/dev/null || echo "$p"
  elif command -v realpath >/dev/null 2>&1; then realpath "$p" 2>/dev/null || echo "$p"
  else echo "$p"
  fi
}

err() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARN:  $*" >&2; }

echo "[omt] Region root: ${TB_DIR}"
mkdir -p "${TB_DIR}"

FORT14="${TB_DIR}/outputs/meshes/${MESH}.14"
[[ -f "${FORT14}" ]] || err "fort.14 not found: ${FORT14}
- Check MESH=\"${MESH}\"
- Expected: ${TB_DIR}/outputs/meshes/${MESH}.14"

# Resolve MATLAB script path:
SCRIPT=""
if [[ -n "${KNOWN_SCRIPT[${MESH}]:-}" && -f "${KNOWN_SCRIPT[${MESH}]}" ]]; then
  SCRIPT="${KNOWN_SCRIPT[${MESH}]}"
else
  # Heuristic search under scripts/: file name or content mentions the mesh key
  shopt -s nullglob
  mapfile -t CANDIDATES < <(grep -ilE "${MESH//_/[_-]}|${MESH}" "${TB_DIR}/scripts/"*.m 2>/dev/null || true)
  # Also consider filename match if grep finds none
  if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
    for f in "${TB_DIR}/scripts/"*.m; do
      [[ "${f##*/}" == *"${MESH}"*.m ]] && CANDIDATES+=("$f")
    done
  fi
  if   [[ ${#CANDIDATES[@]} -eq 1 ]]; then SCRIPT="${CANDIDATES[0]}"
  elif [[ ${#CANDIDATES[@]} -gt 1 ]]; then
    echo "Candidate MATLAB scripts for ${MESH}:"
    printf '  - %s\n' "${CANDIDATES[@]}"
    err "Multiple script candidates found. Please set KNOWN_SCRIPT[${MESH}] in this script."
  else
    err "No MATLAB script found for ${MESH} under ${TB_DIR}/scripts.
- Add it to KNOWN_SCRIPT[...] or place a script whose name or content mentions '${MESH}'."
  fi
fi

FORT14_ABS="$(abspath "${FORT14}")"
SCRIPT_ABS="$(abspath "${SCRIPT}")"

echo "[omt] Using fort14 : ${FORT14_ABS}"
echo "[omt] Using script : ${SCRIPT_ABS}"

# Write pairs.yaml (only this mesh)
echo "[omt] Writing pairs file: ${PAIRS_FILE}"
cat > "${PAIRS_FILE}" <<YAML
pairs:
  - fort14: ${FORT14_ABS}
    script: ${SCRIPT_ABS}
YAML

# Step 1/2: Scan (auto-detects DEM & coastline candidates)
echo "==> Step 1/2: Running omt scan..."
omt scan --pairs-file "${PAIRS_FILE}" --out catalog.json
echo "✓ scan done"

# Step 2/2: Viz
OUT_DIR="figs/${MESH}"
mkdir -p "${OUT_DIR}"
echo "==> Step 2/2: Visualizing ${MESH}..."
omt viz \
  --fort14 "${FORT14_ABS}" \
  --catalog catalog.json \
  --out "${OUT_DIR}" \
  "$@"
echo "✓ viz done"

echo "[omt] Done. Outputs under ${OUT_DIR}"

