from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple


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
