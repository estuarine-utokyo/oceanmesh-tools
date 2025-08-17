import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - yaml is optional
    yaml = None


DEFAULT_REGION = "Tokyo_Bay"


def _read_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    if yaml is None:
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _split_paths(val: Optional[str]) -> List[str]:
    if not val:
        return []
    # Support comma or os.pathsep separated lists
    parts: List[str] = []
    for chunk in val.split(","):
        parts.extend([p for p in chunk.split(os.pathsep) if p])
    # Normalize and deduplicate
    seen = set()
    out: List[str] = []
    for p in parts:
        pp = str(Path(os.path.expanduser(p)).resolve())
        if pp not in seen:
            seen.add(pp)
            out.append(pp)
    return out


def load_config(cli_args: Optional[Dict] = None) -> Dict:
    """Load configuration with precedence: CLI > env > YAML > defaults.

    Recognized keys: oceanmesh2d_dir, search_paths.dem, search_paths.shp, default_region
    """
    cli_args = cli_args or {}

    # YAML from repo root or home
    repo_root = Path.cwd()
    yaml_paths = [
        repo_root / ".oceanmesh-tools.yaml",
        Path.home() / ".oceanmesh-tools.yaml",
    ]
    yaml_conf: Dict = {}
    for p in yaml_paths:
        yaml_conf.update(_read_yaml(p))

    # Env vars
    env_conf: Dict = {}
    if os.getenv("OMT_OCEANMESH2D_DIR"):
        env_conf["oceanmesh2d_dir"] = os.getenv("OMT_OCEANMESH2D_DIR")
    dem_paths = _split_paths(os.getenv("OMT_DEM_PATHS"))
    shp_paths = _split_paths(os.getenv("OMT_SHP_PATHS"))
    if dem_paths or shp_paths:
        env_conf["search_paths"] = {}
        if dem_paths:
            env_conf["search_paths"]["dem"] = dem_paths
        if shp_paths:
            env_conf["search_paths"]["shp"] = shp_paths
    if os.getenv("OMT_DEFAULT_REGION"):
        env_conf["default_region"] = os.getenv("OMT_DEFAULT_REGION")

    # Defaults
    defaults = {
        "default_region": DEFAULT_REGION,
    }

    def merge(a: Dict, b: Dict) -> Dict:
        out = dict(a)
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = merge(out[k], v)  # type: ignore
            else:
                out[k] = v
        return out

    conf = merge(defaults, yaml_conf)
    conf = merge(conf, env_conf)
    conf = merge(conf, cli_args)
    return conf


def region_paths(oceanmesh2d_dir: str, region: str) -> Tuple[Path, Path, Path]:
    """Return (region_root, region_data_dir, datasets_dir)."""
    base = Path(os.path.expanduser(oceanmesh2d_dir)).resolve()
    region_root = base / region
    region_data = region_root / "data"
    datasets = base / "datasets"
    return region_root, region_data, datasets

