#!/usr/bin/env bash
set -euo pipefail

# Clean generated and debug artifacts from git tracking (and optionally from disk).
# - Without args: untrack files if they are tracked (git rm --cached); keep local copies.
# - With --purge: also remove working tree copies.

MODE="untrack"
if [[ "${1:-}" == "--purge" ]]; then
  MODE="purge"
fi

root_dir="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
if [[ -z "$root_dir" ]]; then
  echo "Not in a git repository. Aborting." >&2
  exit 1
fi
cd "$root_dir"

patterns=(
  "figs/"
  "**/figs/"
  "catalog.json"
  "pairs.yaml"
  "examples/catalog.json"
  "examples/pairs.yaml"
  "examples/**/figs/"
  "**/boundary_debug_edges.npz"
  "**/boundary_readback.txt"
  "**/suspicious_coast_edges.csv"
  "**/suspicious_open_edges.csv"
  "**/boundary_debug.png"
  "**/*.boundary.npz"
)

echo "[clean] Mode: $MODE"

# Untrack if tracked
tracked=$(git ls-files -z | tr '\0' '\n')
for pat in "${patterns[@]}"; do
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    echo "$tracked" | grep -Fx -- "$f" >/dev/null 2>&1 || continue
    echo "[clean] git rm --cached -- $f"
    git rm --cached --quiet -- "$f" || true
  done < <(git ls-files -z -- "$pat" | tr '\0' '\n')
done

if [[ "$MODE" == "purge" ]]; then
  # Remove working tree copies
  for pat in "${patterns[@]}"; do
    # Use globstar to expand ** patterns
    shopt -s globstar nullglob
    for f in $pat; do
      # Skip directories that don't exist
      if [[ -d "$f" ]]; then
        echo "[clean] rm -rf -- $f"
        rm -rf -- "$f"
      elif [[ -f "$f" ]]; then
        echo "[clean] rm -f -- $f"
        rm -f -- "$f"
      fi
    done
    shopt -u globstar nullglob
  done
fi

echo "[clean] Done. Consider running: git status"

