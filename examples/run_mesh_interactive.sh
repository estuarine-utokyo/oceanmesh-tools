#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${SCRIPT_DIR}/interactive_mesh.py"

# --- User-editable default ---
# Same ergonomics as run_viz.sh:
# - No args -> use DEFAULT_MESH (or auto-search)
# - One arg -> mesh path override
# - Two args -> mesh path + explicit output path
DEFAULT_MESH="${DEFAULT_MESH:-auto}"

CANDIDATES=(
  "$HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_futtsu_5regions.14"
  "$HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_futtsu_5regions.14.txt"
  "$HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_uniform_400m.14"
  "$HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_uniform_400m.14.txt"
  # fallback locations within this repo for tests
  "examples/data/tb_futtsu_5regions.14"
  "examples/data/tb_futtsu_5regions.14.txt"
  "examples/data/tb_uniform_400m.14"
  "examples/data/tb_uniform_400m.14.txt"
)

usage() {
  cat 1>&2 <<'EOS'
Usage:
  run_mesh_interactive.sh                # zero-arg default; uses DEFAULT_MESH or auto
  run_mesh_interactive.sh MESH14         # specify input .14 (or .14.txt)
  run_mesh_interactive.sh MESH14 OUTHTML # specify explicit output path

Notes:
  - By default, output goes under THIS repo: examples/figs/<meshname>/<meshname>.interactive.html
  - Set DEFAULT_MESH=/abs/path/NAME.14 to override default without editing this file.
EOS
}

pick_auto() {
  for p in "${CANDIDATES[@]}"; do
    [[ -f "$p" ]] && { echo "$p"; return 0; }
  done
  return 1
}

[[ "${1-}" == "-h" || "${1-}" == "--help" ]] && { usage; exit 0; }

MESH="${1-}"
OUT="${2-}"

if [[ -z "${MESH}" ]]; then
  if [[ "${DEFAULT_MESH}" == "auto" ]]; then
    if ! MESH="$(pick_auto)"; then
      echo "[ERROR] DEFAULT_MESH=auto but no candidate was found." 1>&2
      usage; exit 2
    fi
  else
    MESH="${DEFAULT_MESH}"
  fi
fi

if [[ ! -f "${MESH}" ]]; then
  echo "[ERROR] mesh not found: ${MESH}" 1>&2
  exit 3
fi

base="$(basename "${MESH}")"
stem="${base%.14}"; stem="${stem%.txt}"
TITLE="${base}"

if [[ -z "${OUT}" ]]; then
  # Same design as run_viz.sh -> examples/figs/<meshname>/<meshname>.interactive.html
  OUT_DIR="${SCRIPT_DIR}/figs/${stem}"
  mkdir -p "${OUT_DIR}"
  OUT="${OUT_DIR}/${stem}.interactive.html"
else
  mkdir -p "$(dirname "${OUT}")"
fi

echo "[run] mesh : ${MESH}"
echo "[run] out  : ${OUT}"
echo "[run] title: ${TITLE}"

ARGS=()
[[ "${DEBUG:-0}" = "1" ]] && ARGS+=("--debug")
[[ "${NO_WEBGL:-0}" = "1" ]] && ARGS+=("--no-webgl")
if [[ -n "${BBOX:-}" ]]; then
  # BBOX should be: "xmin xmax ymin ymax"
  ARGS+=("--bbox" ${BBOX})
fi
# Prefer installed console script; fallback to python -m if not found
if command -v omesh14-view >/dev/null 2>&1; then
  omesh14-view "${MESH}" --out "${OUT}" --title "${TITLE}" "${ARGS[@]}"
else
  python -m oceanmesh_tools.vis.interactive_mesh "${MESH}" --out "${OUT}" --title "${TITLE}" "${ARGS[@]}"
fi

echo "[ok] wrote ${OUT}"
