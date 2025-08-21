#!/usr/bin/env bash
set -euo pipefail

# Sample end-to-end workflow for scanning and visualizing Tokyo Bay meshes.
#
# Prereqs:
# - OceanMesh2D data available under: $HOME/Github/OceanMesh2D/Tokyo_Bay/
# - This repo installed editable: make install  (or: pip install -e .)
# - CLI available on PATH: omt --help

OM2D_DIR="${HOME}/Github/OceanMesh2D"
REGION="Tokyo_Bay"
TB_DIR="${OM2D_DIR}/${REGION}"
PAIRS_FILE="${TB_DIR}/pairs.yaml"

# Mesh names and paths
MESH1="tb_futtsu_5regions"
MESH2="tb_uniform_400m"
FORT14_1="${TB_DIR}/outputs/meshes/${MESH1}.14"
FORT14_2="${TB_DIR}/outputs/meshes/${MESH2}.14"

echo "[omt] Ensuring region directory exists: ${TB_DIR}"
mkdir -p "${TB_DIR}"

echo "[omt] Writing pairs file: ${PAIRS_FILE} (overwriting if present)"
cat > "${PAIRS_FILE}" <<'YAML'
pairs:
  - fort14: $HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_futtsu_5regions.14
    script: $HOME/Github/OceanMesh2D/Tokyo_Bay/scripts/mesh_wide_futtsu_5r.m
  - fort14: $HOME/Github/OceanMesh2D/Tokyo_Bay/outputs/meshes/tb_uniform_400m.14
    script: $HOME/Github/OceanMesh2D/Tokyo_Bay/scripts/mesh_bay_uniform_400m.m
YAML

# Step 1/3: Scan
echo "==> Step 1/3: Running omt scan..."
omt scan \
  --pairs-file "${PAIRS_FILE}" \
  --out catalog.json
echo "✓ done"

# Step 2/3: Viz 1
echo "==> Step 2/3: Visualizing ${MESH1}..."
mkdir -p "figs/${MESH1}"
echo "[omt] Using fort14: $(readlink -f "${FORT14_1}" 2>/dev/null || echo "${FORT14_1}")"
omt viz \
  --fort14 "${FORT14_1}" \
  --catalog catalog.json \
  --out "figs/${MESH1}"
echo "✓ done"

# Step 3/3: Viz 2
echo "==> Step 3/3: Visualizing ${MESH2}..."
mkdir -p "figs/${MESH2}"
echo "[omt] Using fort14: $(readlink -f "${FORT14_2}" 2>/dev/null || echo "${FORT14_2}")"
omt viz \
  --fort14 "${FORT14_2}" \
  --catalog catalog.json \
  --out "figs/${MESH2}"
echo "✓ done"

echo "[omt] Done. Outputs under figs/${MESH1} and figs/${MESH2}"
