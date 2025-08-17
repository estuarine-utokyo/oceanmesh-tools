from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


WRITE_RE = re.compile(r"write\s*\(\s*m\s*,\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)

# Matches geodata('shp','X',...,'dem','Y',...) in any order
GEODATA_ARG_RE = re.compile(
    r"geodata\s*\(.*?\)", re.IGNORECASE | re.DOTALL
)
GEODATA_PAIR_RE = re.compile(
    r"['\"](shp|dem)['\"]\s*,\s*['\"]([^'\"]+)['\"]", re.IGNORECASE
)

# Matches variable assignments like coastline_foo = 'path' or dem_bar = "path"
ASSIGN_RE = re.compile(
    r"(?:(?:coastline|shore|coast)_\w+|dem_\w+)\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


@dataclass
class ScriptInputs:
    script_path: Path
    mesh_names: List[str] = field(default_factory=list)  # names from write(m,'NAME')
    shp_hints: List[str] = field(default_factory=list)
    dem_hints: List[str] = field(default_factory=list)


def extract_from_text(text: str) -> Tuple[List[str], List[str], List[str]]:
    meshes = WRITE_RE.findall(text)
    # Normalize names (strip extension)
    meshes = [m[:-3] if m.lower().endswith(".14") else m for m in meshes]

    shp_hints: List[str] = []
    dem_hints: List[str] = []

    # geodata calls
    for m in GEODATA_ARG_RE.finditer(text):
        call = m.group(0)
        for k, v in GEODATA_PAIR_RE.findall(call):
            if k.lower() == "shp":
                shp_hints.append(v)
            elif k.lower() == "dem":
                dem_hints.append(v)

    # variable assignments
    for m in ASSIGN_RE.finditer(text):
        val = m.group(1)
        # Heuristics: paths or basenames; add to both lists accordingly
        if any(val.lower().endswith(ext) for ext in (".shp", ".dbf", ".shx")):
            shp_hints.append(val)
        elif any(val.lower().endswith(ext) for ext in (".nc", ".tif", ".tiff", ".img")):
            dem_hints.append(val)
        else:
            # Unknown extension; keep as generic hint
            if "dem" in val.lower():
                dem_hints.append(val)
            else:
                shp_hints.append(val)

    # Deduplicate preserving order
    def dedup(seq: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for s in seq:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    return dedup(meshes), dedup(shp_hints), dedup(dem_hints)


def extract_from_file(path: Path) -> ScriptInputs:
    text = path.read_text(encoding="utf-8", errors="ignore")
    meshes, shp_hints, dem_hints = extract_from_text(text)
    return ScriptInputs(script_path=path, mesh_names=meshes, shp_hints=shp_hints, dem_hints=dem_hints)


def scan_matlab_scripts(root: Path) -> List[ScriptInputs]:
    out: List[ScriptInputs] = []
    for p in root.rglob("*.m"):
        try:
            out.append(extract_from_file(p))
        except Exception:
            # Skip problematic files
            continue
    return out

