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
    """Extract boundaries from fort.14 with robust header handling and IBTYPE capture.

    Strategy:
    - Parse nodes via existing parser for coordinates.
    - Re-read file to extract boundary groups using integer-only scanning to tolerate
      comments and layout variations (e.g., "m ib" on one line or split over two lines).
    - Convert node ids to 0-based indices.
    - On failure, fall back to segments derived from parse_fort14 (ibtype=None).
    """
    p = Path(path)
    m = parse_fort14(p)
    nodes_xy = np.asarray([(x, y) for (_nid, x, y, _d) in m.nodes], dtype=float)

    def _ints(line: str) -> List[int]:
        import re
        return [int(x) for x in re.findall(r"[-+]?\d+", line)]

    def _read_n_ints(f, need: int) -> List[int]:
        vals: List[int] = []
        while len(vals) < need:
            line = f.readline()
            if not line:
                raise EOFError("Unexpected EOF while reading boundary section")
            ints = _ints(line)
            if not ints:
                continue
            vals.extend(ints)
        return vals[:need]

    try:
        with p.open('r', encoding='utf-8', errors='ignore') as f:
            # Skip title
            _ = f.readline()
            # Read counts (elements, nodes)
            _ = _read_n_ints(f, 2)
            # Skip nodes and elements blocks
            # Nodes: one per line (id, x, y, depth)
            for _ in range(int(m.n_nodes)):
                _ = f.readline()
            # Elements: variable fields but at least 5 tokens; read one line per element
            for _ in range(int(m.n_elements)):
                _ = f.readline()
            # Open boundaries: NOPE, NBOU
            NOPE = _read_n_ints(f, 1)[0]
            NBOU = _read_n_ints(f, 1)[0]
            open_segments: List[List[int]] = []
            for _k in range(max(0, NOPE)):
                m_nodes = _read_n_ints(f, 1)[0]
                seg = [(_read_n_ints(f, 1)[0] - 1) for _ in range(max(0, m_nodes))]
                open_segments.append(seg)
            # Land boundaries: NBOB, NBOBN
            NBOB = _read_n_ints(f, 1)[0]
            NBOBN = _read_n_ints(f, 1)[0]
            land_segments: List[Tuple[Optional[int], List[int]]] = []
            for _k in range(max(0, NBOB)):
                # Accept "m ib" on one line OR split across lines
                m_ib = _read_n_ints(f, 2)
                m_nodes, ib = m_ib[0], m_ib[1]
                seg = [(_read_n_ints(f, 1)[0] - 1) for _ in range(max(0, m_nodes))]
                land_segments.append((int(ib), seg))
        meta = {
            'NOPE': int(NOPE),
            'NBOU': int(NBOU),
            'NBOB': int(NBOB),
            'NBOBN': int(NBOBN),
            'NNODES': int(m.n_nodes),
            'NELEMS': int(m.n_elements),
        }
    except Exception:
        # Fallback to segments from robust parse_fort14 (no IBTYPE info)
        open_segments = [[int(n) - 1 for n in seg if int(n) - 1 >= 0] for seg in m.open_boundaries]
        land_segments = [(None, [int(n) - 1 for n in seg if int(n) - 1 >= 0]) for seg in m.land_boundaries]
        meta = {
            'NOPE': len(m.open_boundaries),
            'NBOU': sum(len(seg) for seg in m.open_boundaries),
            'NBOB': len(m.land_boundaries),
            'NBOBN': sum(len(seg) for seg in m.land_boundaries),
            'NNODES': int(m.n_nodes),
            'NELEMS': int(m.n_elements),
        }
    # Basic sanity (range check) — leave detailed checks to validate_segments
    nmax = int(nodes_xy.shape[0])
    def _in_range(seg: List[int]) -> bool:
        return (len(seg) == 0) or ((min(seg) >= 0) and (max(seg) < nmax))
    open_segments = [seg for seg in open_segments if _in_range(seg)]
    land_segments = [(ib, seg) for (ib, seg) in land_segments if _in_range(seg)]
    return Fort14Boundaries(nodes_xy=nodes_xy, open_segments=open_segments, land_segments=land_segments, meta=meta)


def validate_segments(nodes_xy: np.ndarray, segments: List[List[int]]) -> None:
    """Validate that segments reference valid node indices and have length >= 2.

    Raises ValueError with informative message on first violation.
    """
    nmax = int(nodes_xy.shape[0])
    for i, seg in enumerate(segments):
        if seg is None:
            raise ValueError(f"Segment {i} is None")
        if len(seg) < 2:
            raise ValueError(f"Segment {i} too short: len={len(seg)}; head={seg[:5]}")
        # Range check
        mi = min(seg)
        ma = max(seg)
        if mi < 0 or ma >= nmax:
            raise ValueError(
                f"Segment {i} index out of range: min={mi}, max={ma}, allowed=[0,{nmax-1}]; head={seg[:5]}"
            )
