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


def segments_to_edges(segments: List[List[int]]) -> np.ndarray:
    """Return edges as (M,2) int32 from list of node-id sequences.

    Each edge is the consecutive pair (u,v) within a segment; segments are not connected across.
    """
    out = []
    for seg in segments:
        if seg and len(seg) >= 2:
            a = np.asarray(seg, dtype=np.int32)
            out.append(np.column_stack([a[:-1], a[1:]]))
    return np.vstack(out) if out else np.empty((0, 2), dtype=np.int32)


def edges_to_linecollection(
    nodes_xy: np.ndarray,
    edges: np.ndarray,
    color: str = 'k',
    zorder: int = 5,
):
    """Build a LineCollection for given edges (M,2) using nodes_xy (no concatenation)."""
    if edges.size == 0:
        return LineCollection([], colors=[color], zorder=zorder), 0
    # Ensure valid dtype and bounds
    e = np.asarray(edges, dtype=np.int64)
    nmax = int(nodes_xy.shape[0])
    mask = (e[:, 0] >= 0) & (e[:, 1] >= 0) & (e[:, 0] < nmax) & (e[:, 1] < nmax)
    if not np.all(mask):
        e = e[mask]
    if e.size == 0:
        return LineCollection([], colors=[color], zorder=zorder), 0
    segs = np.stack([nodes_xy[e[:, 0]], nodes_xy[e[:, 1]]], axis=1)
    lc = LineCollection(segs, colors=[color], linestyles='solid', zorder=zorder)
    lc.set_capstyle('round')
    lc.set_joinstyle('round')
    return lc, segs.shape[0]
