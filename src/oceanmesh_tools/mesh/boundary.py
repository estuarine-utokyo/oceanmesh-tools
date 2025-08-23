from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple
import numpy as np


def build_edge_counts(elements: Sequence[Tuple[int, int, int, int, int]]) -> Dict[Tuple[int, int], int]:
    counts: Dict[Tuple[int, int], int] = defaultdict(int)
    for _, a, b, c, _ in elements:
        for i, j in ((a, b), (b, c), (c, a)):
            e = (i, j) if i < j else (j, i)
            counts[e] += 1
    return counts


def boundary_edges_from_counts(counts: Dict[Tuple[int, int], int]) -> List[Tuple[int, int]]:
    return [e for e, c in counts.items() if c == 1]


def walk_closed_loops(boundary_edges: Sequence[Tuple[int, int]]) -> List[List[int]]:
    # Build adjacency for boundary graph
    nbrs: Dict[int, List[int]] = defaultdict(list)
    for i, j in boundary_edges:
        nbrs[i].append(j)
        nbrs[j].append(i)
    # Track used edges
    used = set()
    def key(i: int, j: int) -> Tuple[int, int]:
        return (i, j) if i < j else (j, i)

    loops: List[List[int]] = []
    for start in list(nbrs.keys()):
        # Skip if all incident edges used
        if all(key(start, v) in used for v in nbrs[start]):
            continue
        # Start a new loop: pick an arbitrary neighbor
        if not nbrs[start]:
            continue
        prev = None
        cur = start
        # choose initial next neighbor deterministically (min id)
        nexts = sorted(nbrs[cur])
        if not nexts:
            continue
        nxt = nexts[0]
        loop = [cur]
        while True:
            used.add(key(cur, nxt))
            prev, cur = cur, nxt
            loop.append(cur)
            # pick next neighbor that is not prev and edge not used
            candidates = [v for v in sorted(nbrs[cur]) if v != prev and key(cur, v) not in used]
            if not candidates:
                # If we returned to start, it's a closed loop
                if cur == loop[0]:
                    break
                # Otherwise, try to close to start if edge exists
                if key(cur, loop[0]) not in used and loop[0] in nbrs[cur]:
                    nxt = loop[0]
                    continue
                break
            nxt = candidates[0]
            if cur == start and nxt == loop[1]:  # closed
                break
        # Close if start is not included at end
        if loop[0] != loop[-1] and loop[0] in nbrs.get(loop[-1], []):
            loop.append(loop[0])
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def compute_outer_loops(elements: Sequence[Tuple[int, int, int, int, int]]) -> List[List[int]]:
    """Return outer boundary candidate loops from elements.

    Falls back to a simple ring over unique node ids if no boundary edges are detected
    (useful for minimal test meshes where triangles duplicate all edges).
    """
    be = boundary_edges_from_counts(build_edge_counts(elements))
    loops = walk_closed_loops(be)
    if loops:
        return loops
    # Fallback: unique node ids from elements, closed ring
    seen = []
    have = set()
    for _, a, b, c, _ in elements:
        for n in (a, b, c):
            if n not in have:
                have.add(n)
                seen.append(n)
    if len(seen) >= 3:
        return [seen + [seen[0]]]
    return []


def boundary_edges_from_tris(tris: np.ndarray) -> np.ndarray:
    """Return undirected boundary edges from triangulation (0-based indices).

    tris: (M,3) int array of node indices (0-based).
    Returns: (K,2) int32 array of undirected edges with count==1.
    """
    if tris.size == 0:
        return np.empty((0, 2), dtype=np.int32)
    e = np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]).astype(np.int32)
    e.sort(axis=1)
    uniq, cnt = np.unique(e, axis=0, return_counts=True)
    return uniq[cnt == 1].astype(np.int32)


def chain_edges_to_paths(edges: np.ndarray) -> List[List[int]]:
    """Chain undirected edges (K,2) into ordered paths of node indices (0-based).

    Produces both open paths (start/end degree==1) and closed loops.
    """
    if edges.size == 0:
        return []
    nbrs: Dict[int, List[int]] = defaultdict(list)
    for i, j in edges.tolist():
        nbrs[i].append(j)
        nbrs[j].append(i)
    used = set()
    def ek(i: int, j: int) -> Tuple[int, int]:
        return (i, j) if i < j else (j, i)

    paths: List[List[int]] = []
    # Start with open chains (degree==1)
    starts = [n for n, vs in nbrs.items() if len(vs) == 1]
    for s in starts:
        if all(ek(s, v) in used for v in nbrs[s]):
            continue
        path = [s]
        cur = s
        prev = None
        while True:
            nexts = [v for v in nbrs[cur] if ek(cur, v) not in used and v != prev]
            if not nexts:
                break
            v = nexts[0]
            used.add(ek(cur, v))
            path.append(v)
            prev, cur = cur, v
        if len(path) >= 2:
            paths.append(path)
    # Remaining cycles
    for n in list(nbrs.keys()):
        for v in nbrs[n]:
            if ek(n, v) in used:
                continue
            # start a loop
            path = [n]
            cur = n
            prev = None
            while True:
                nexts = [w for w in nbrs[cur] if ek(cur, w) not in used and w != prev]
                if not nexts:
                    break
                w = nexts[0]
                used.add(ek(cur, w))
                path.append(w)
                prev, cur = cur, w
                if cur == path[0]:
                    break
            if len(path) >= 2:
                # ensure closed loop repeats start
                if path[0] != path[-1] and path[0] in nbrs.get(path[-1], []):
                    path.append(path[0])
                paths.append(path)
    return paths


def classify_open_boundary_edges(
    paths: List[List[int]],
    ob_segments: List[List[int]],
) -> Tuple[List[List[int]], List[List[int]]]:
    """Split boundary paths into (open_paths, coast_paths) by edge membership.

    Any consecutive edge (i,j) that appears in fort.14 open-boundary segments
    (1-based node ids) is labeled as 'open'; others as 'coast'. Paths are split
    when label changes to keep homogenous polylines.
    """
    ob_edges: set[Tuple[int, int]] = set()
    for seg in ob_segments:
        if not seg:
            continue
        for a, b in zip(seg[:-1], seg[1:]):
            i, j = int(a) - 1, int(b) - 1
            if i == j:
                continue
            t = (i, j) if i < j else (j, i)
            ob_edges.add(t)
    open_paths: List[List[int]] = []
    coast_paths: List[List[int]] = []
    for path in paths:
        if len(path) < 2:
            continue
        cur_label = None
        cur_seq: List[int] = [path[0]]
        def commit(seq: List[int], lbl):
            if len(seq) >= 2:
                (open_paths if lbl == 'open' else coast_paths).append(seq.copy())
        for u, v in zip(path[:-1], path[1:]):
            e = (u, v) if u < v else (v, u)
            lbl = 'open' if e in ob_edges else 'coast'
            if cur_label is None:
                cur_label = lbl
            if lbl != cur_label:
                commit(cur_seq, cur_label)
                cur_seq = [u, v]
                cur_label = lbl
            else:
                cur_seq.append(v)
        commit(cur_seq, cur_label)
    return open_paths, coast_paths


def classify_outer_vs_holes(loops: Sequence[List[int]], nodes_xy: Dict[int, Tuple[float, float]]) -> Tuple[List[List[int]], List[List[int]]]:
    def ring_area(path: List[int]) -> float:
        xs = [nodes_xy[i][0] for i in path]
        ys = [nodes_xy[i][1] for i in path]
        s = 0.0
        for i in range(len(path) - 1):
            s += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
        return 0.5 * s
    if not loops:
        return [], []
    areas = [abs(ring_area(r)) for r in loops]
    if not areas:
        return [], []
    max_idx = max(range(len(areas)), key=lambda i: areas[i])
    outer = [loops[max_idx]]
    holes = [loops[i] for i in range(len(loops)) if i != max_idx]
    return outer, holes


def to_linestring(path: List[int], nodes_xy: Dict[int, Tuple[float, float]]):  # pragma: no cover - thin wrapper
    try:
        from shapely.geometry import LineString  # type: ignore
    except Exception:
        return None
    coords = [(float(nodes_xy[i][0]), float(nodes_xy[i][1])) for i in path]
    return LineString(coords)


def multi_from_paths(paths: Sequence[List[int]], nodes_xy: Dict[int, Tuple[float, float]]):  # pragma: no cover - thin wrapper
    try:
        from shapely.geometry import MultiLineString, LineString  # type: ignore
    except Exception:
        return None
    lines = []
    for p in paths:
        ls = to_linestring(p, nodes_xy)
        if ls is not None:
            lines.append(ls)
    if not lines:
        return None
    return MultiLineString(lines)


def hausdorff(a, b) -> float:
    try:
        return float(a.hausdorff_distance(b))  # type: ignore[attr-defined]
    except Exception:
        return float("inf")


def signed_distance_to_hull(path, hull_polygon) -> float:
    """Return minimum signed distance of path vertices to hull polygon.

    Negative means inside the polygon (inward), positive means outside.
    """
    try:
        from shapely.geometry import LineString, Point  # type: ignore
    except Exception:
        return 0.0
    if path is None or hull_polygon is None:
        return 0.0
    pts = []
    # Try multipart first
    try:
        geoms = getattr(path, "geoms", None)
        if geoms is not None:
            for g in geoms:  # type: ignore[attr-defined]
                try:
                    pts.extend(list(g.coords))
                except Exception:
                    pass
        else:
            try:
                pts = list(path.coords)  # type: ignore[attr-defined]
            except Exception:
                pts = []
    except Exception:
        pts = []
    if not pts:
        return 0.0
    min_signed = float("inf")
    boundary = getattr(hull_polygon, "boundary", None)
    for x, y in pts:
        inside = bool(hull_polygon.contains(Point(x, y)))
        d = boundary.distance(Point(x, y)) if boundary is not None else 0.0
        sd = -d if inside else d
        if sd < min_signed:
            min_signed = sd
    return min_signed if min_signed != float("inf") else 0.0


def make_domain_polygon(nodes_xy: Dict[int, Tuple[float, float]], loops: Sequence[List[int]]):  # pragma: no cover - thin wrapper
    """Return a shapely Polygon from loops: outer by max area, remaining as holes.

    Returns None if shapely is unavailable or inputs invalid.
    """
    try:
        from shapely.geometry import Polygon  # type: ignore
    except Exception:
        return None
    if not loops:
        return None
    # Compute areas to choose outer
    def area(coords: List[Tuple[float, float]]) -> float:
        s = 0.0
        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            s += x1 * y2 - x2 * y1
        return 0.5 * abs(s)
    rings_xy: List[List[Tuple[float, float]] ] = []
    for loop in loops:
        rings_xy.append([(float(nodes_xy[i][0]), float(nodes_xy[i][1])) for i in loop])
    if not rings_xy:
        return None
    areas = [area(r) for r in rings_xy]
    max_idx = max(range(len(areas)), key=lambda i: areas[i])
    outer = rings_xy[max_idx]
    holes = [rings_xy[i] for i in range(len(rings_xy)) if i != max_idx]
    try:
        return Polygon(outer, holes=holes if holes else None)
    except Exception:
        try:
            # Invalid rings may be fixed by buffer(0)
            return Polygon(outer).buffer(0)
        except Exception:
            return None
