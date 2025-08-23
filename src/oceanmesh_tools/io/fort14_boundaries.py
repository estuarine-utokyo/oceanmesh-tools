from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np

from .fort14 import parse_fort14


@dataclass
class Fort14Boundaries:
    nodes_xy: np.ndarray  # (N,2)
    open_segments: List[List[int]]  # 0-based node ids
    land_segments: List[Tuple[Optional[int], List[int]]]  # (ibtype, 0-based node ids)
    meta: Dict[str, int]


def parse_fort14_boundaries(path: str | Path) -> Fort14Boundaries:
    """Fast boundary extraction via existing fort.14 parser.

    Note: The current fort.14 parser returns land boundaries as node lists only
    (IBTYPE not captured). We emit ibtype=None for those. Open boundaries are
    sequences of node ids. All node ids are converted to 0-based indices.
    """
    m = parse_fort14(Path(path))
    # nodes_xy
    nodes_xy = np.asarray([(x, y) for (_nid, x, y, _d) in m.nodes], dtype=float)
    # Convert segments to 0-based
    open_segments = [[int(n) - 1 for n in seg if int(n) - 1 >= 0] for seg in m.open_boundaries]
    # Land segments with ibtype unknown
    land_segments: List[Tuple[Optional[int], List[int]]] = []
    for seg in m.land_boundaries:
        land_segments.append((None, [int(n) - 1 for n in seg if int(n) - 1 >= 0]))
    # Validate indices are in range
    nmax = nodes_xy.shape[0]
    def _check_segment(seg: List[int], kind: str):
        if not seg:
            return
        mi, ma = min(seg), max(seg)
        if mi < 0 or ma >= nmax:
            raise ValueError(f"{kind} segment index out of range: min={mi}, max={ma}, n={nmax}")
    for seg in open_segments:
        _check_segment(seg, "open")
    for _ib, seg in land_segments:
        _check_segment(seg, "land")

    meta = {
        'NOPE': len(m.open_boundaries),
        'NBOU': sum(len(seg) for seg in m.open_boundaries),
        'NBOB': len(m.land_boundaries),
        'NBOBN': sum(len(seg) for seg in m.land_boundaries),
        'NNODES': int(m.n_nodes),
        'NELEMS': int(m.n_elements),
    }
    return Fort14Boundaries(nodes_xy=nodes_xy, open_segments=open_segments, land_segments=land_segments, meta=meta)
