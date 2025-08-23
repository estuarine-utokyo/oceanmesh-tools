from __future__ import annotations

from typing import Iterable, List, Tuple, Optional, Dict

import numpy as np
from matplotlib.collections import LineCollection


def build_paths_from_segments(nodes_xy: np.ndarray, segments: Iterable[Iterable[int]]) -> List[np.ndarray]:
    out: List[np.ndarray] = []
    nmax = nodes_xy.shape[0]
    for seg in segments:
        idx = np.asarray(list(seg), dtype=int)
        if idx.size < 2:
            continue
        # Range check
        ok = (idx >= 0) & (idx < nmax)
        if not np.all(ok):
            idx = idx[(idx >= 0) & (idx < nmax)]
        if idx.size < 2:
            continue
        xy = nodes_xy[idx, :2].astype(float, copy=False)
        out.append(xy)
    return out


def classify_land_segments(land_segments: List[Tuple[Optional[int], List[int]]], include_ibtype: Tuple[int, ...] = (20, 21)) -> Dict[str, List[List[int]]]:
    coast: List[List[int]] = []
    other: List[List[int]] = []
    for ib, seg in land_segments:
        # If ibtype unknown, treat as coastline to avoid missing islands
        if ib is None or int(ib) in include_ibtype:
            coast.append(list(seg))
        else:
            other.append(list(seg))
    return {'coast': coast, 'other': other}


def segments_to_linecollection(
    nodes_xy: np.ndarray,
    segments: Iterable[Iterable[int]],
    color: str = 'k',
    zorder: int = 5,
):
    """Build a LineCollection from independent segments; no concatenation across segments.

    Returns (LineCollection, n_segments_plotted).
    """
    lines: List[np.ndarray] = []
    nmax = int(nodes_xy.shape[0])
    for seg in segments:
        idx = np.asarray(list(seg), dtype=int)
        if idx.size < 2:
            continue
        if (idx.min() < 0) or (idx.max() >= nmax):
            idx = idx[(idx >= 0) & (idx < nmax)]
            if idx.size < 2:
                continue
        arr = nodes_xy[idx, :2].astype(float, copy=False)
        if arr.shape[0] >= 2:
            lines.append(arr)
    lc = LineCollection(lines, colors=[color], linestyles='solid', zorder=zorder)
    lc.set_capstyle('round')
    lc.set_joinstyle('round')
    return lc, len(lines)
