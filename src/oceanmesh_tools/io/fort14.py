# src/oceanmesh_tools/io/fort14.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional, Set


@dataclass
class Fort14:
    title: str
    n_nodes: int
    n_elements: int
    nodes: List[Tuple[int, float, float, float]]           # (id, x, y, depth)
    elements: List[Tuple[int, int, int, int, int]]         # (eid, n1, n2, n3, n4_or_0)
    open_boundaries: List[List[int]]                        # list of node-id lists
    land_boundaries: List[List[int]]                        # list of node-id lists

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        xs = [x for (_, x, _, _) in self.nodes]
        ys = [y for (_, _, y, _) in self.nodes]
        return (min(xs), min(ys), max(xs), max(ys))


def _is_int_like(tok: str) -> bool:
    try:
        int(tok)
        return True
    except Exception:
        return False


def _parse_ints(line: str) -> List[int]:
    return [int(tok) for tok in line.strip().split() if _is_int_like(tok)]


def _read_nonempty_line(f) -> str | None:
    while True:
        line = f.readline()
        if not line:
            return None
        s = line.strip()
        if s == "":
            continue
        return s


def _read_nonempty_ints(f) -> tuple[List[int] | None, int]:
    while True:
        pos = f.tell()
        line = f.readline()
        if not line:
            return None, pos
        s = line.strip()
        if s == "":
            continue
        ints = _parse_ints(s)
        if len(ints) == 0:
            # Skip malformed non-integer lines silently
            continue
        return ints, pos


def _read_one_node_id(f) -> Optional[int]:
    """Read next non-empty line and return the first integer, or None on EOF."""
    s = _read_nonempty_line(f)
    if s is None:
        return None
    ints = _parse_ints(s)
    return ints[0] if ints else None


def _collect_node_ids_exact_lines(f, count: int) -> List[int]:
    """Collect exactly 'count' node ids by reading one id per line (first int)."""
    out: List[int] = []
    for _ in range(max(0, count)):
        nid = _read_one_node_id(f)
        if nid is None:
            break
        out.append(nid)
    return out


def _parse_one_boundary(
    f,
    known_node_ids: Set[int],
) -> List[int]:
    """Parse a single boundary using dual strategies and heuristics.

    Consumes the boundary header line and then attempts:
    - Style A (nodes-in-boundary): header H = total nodes; read H lines of node ids
      (tolerate multiple ints per line; append all, truncate to H).
      If header has multiple ints, treat them as node ids directly.
    - Style B (segments): header S = segment count; for each segment, next line either
      is single int N (then read N lines of one node-id) or contains multiple ints which
      are taken as the segment's node ids directly. If the line has leading count N
      followed by ids on the same line, include those and only read remaining (N - inline) lines.

    Select the better candidate by:
    1) longer length, 2) closed ring (last==first), 3) membership in known_node_ids,
    4) prefer Style B.
    Leaves the file pointer at the end of the chosen parse.
    """
    header_ints, pos_header = _read_nonempty_ints(f)
    if header_ints is None:
        return []
    pos_after_header = f.tell()

    # Candidate A: nodes-in-boundary
    f.seek(pos_after_header)
    a_nodes: List[int] = []
    try:
        if len(header_ints) == 1:
            H = header_ints[0]
            # Read until we have at least H node ids; each line may contain multiple ints
            while len(a_nodes) < H:
                s = _read_nonempty_line(f)
                if s is None:
                    break
                ints = _parse_ints(s)
                if ints:
                    a_nodes.extend(ints)
            # Trim to exactly H if over-collected
            a_nodes = a_nodes[: max(0, H)]
        else:
            # Treat header ints themselves as node ids (direct list)
            a_nodes = list(header_ints)
    except Exception:
        a_nodes = []
    pos_after_a = f.tell()

    # Candidate B: segments
    f.seek(pos_after_header)
    b_nodes: List[int] = []
    try:
        if len(header_ints) == 1:
            S = header_ints[0]
            for _ in range(max(0, S)):
                seg_ints, _pos = _read_nonempty_ints(f)
                if seg_ints is None:
                    break
                if len(seg_ints) == 1:
                    N = seg_ints[0]
                    b_nodes.extend(_collect_node_ids_exact_lines(f, N))
                else:
                    # If first token is a count, include inline ids and read remaining
                    N = seg_ints[0]
                    inline_ids = seg_ints[1:]
                    if N > 0 and len(inline_ids) > 0:
                        b_nodes.extend(inline_ids)
                        rem = max(0, N - len(inline_ids))
                        if rem > 0:
                            b_nodes.extend(_collect_node_ids_exact_lines(f, rem))
                    else:
                        # No clear count; treat all as node ids directly for this segment
                        b_nodes.extend(seg_ints)
        else:
            # Header lists node ids directly; treat as a single-segment list
            b_nodes = list(header_ints)
    except Exception:
        b_nodes = []
    pos_after_b = f.tell()

    # Heuristics to choose candidate
    def score(nodes: List[int]) -> tuple:
        length = len(nodes)
        closed = 1 if (length > 1 and nodes[0] == nodes[-1]) else 0
        membership = 1 if all((nid in known_node_ids) for nid in nodes) else 0
        return (length, closed, membership)

    score_a = score(a_nodes)
    score_b = score(b_nodes)

    if score_b > score_a:
        f.seek(pos_after_b)
        return b_nodes
    if score_a > score_b:
        f.seek(pos_after_a)
        return a_nodes
    # Tie: prefer segments (B)
    f.seek(pos_after_b)
    return b_nodes


def _parse_boundary_group_nodes_in_boundary(f, n_boundaries: int, total_nodes_hint: int | None) -> List[List[int]] | None:
    start_pos = f.tell()
    boundaries: List[List[int]] = []
    total = 0
    try:
        for _ in range(n_boundaries):
            head, _ = _read_nonempty_ints(f)
            if head is None or len(head) != 1:
                return None
            count = head[0]
            nodes = _collect_node_ids(f, count)
            if len(nodes) < count:
                return None
            total += len(nodes)
            boundaries.append(nodes)
        if total_nodes_hint is not None and total != total_nodes_hint:
            return None
        return boundaries
    except Exception:
        return None


def _parse_boundary_group_segments_or_direct(f, n_boundaries: int, total_nodes_hint: int | None) -> List[List[int]]:
    boundaries: List[List[int]] = []
    if n_boundaries == 1 and total_nodes_hint is not None:
        nodes: List[int] = []
        while len(nodes) < total_nodes_hint:
            ints, _ = _read_nonempty_ints(f)
            if ints is None:
                break
            nodes.extend(ints)
        boundaries.append(nodes[:total_nodes_hint])
        return boundaries

    for _ in range(n_boundaries):
        b_nodes: List[int] = []
        head, _ = _read_nonempty_ints(f)
        if head is None:
            boundaries.append(b_nodes)
            continue
        if len(head) != 1:
            # No segment count; treat as direct node list for this boundary
            b_nodes.extend(head)
            boundaries.append(b_nodes)
            continue
        nseg = head[0]
        for _s in range(nseg):
            seg_head, _ = _read_nonempty_ints(f)
            if seg_head is None:
                break
            if len(seg_head) == 1:
                k = seg_head[0]
                seg_nodes = _collect_node_ids(f, k)
            else:
                seg_nodes = seg_head
            b_nodes.extend(seg_nodes)
        boundaries.append(b_nodes)
    return boundaries


def parse_fort14(path: str | Path) -> Fort14:
    """
    Robust minimal ADCIRC fort.14 parser.

    Parses: title, counts, nodes, elements, open/land boundaries (defensive),
    and returns a Fort14 object. Tri elements are assumed; extra nodes in a
    line are ignored after the first 3.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        # --- Title ---
        title = f.readline().strip()

        # --- Counts: number of elements, nodes ---
        counts = _parse_ints(f.readline())
        if len(counts) < 2:
            raise ValueError("Invalid fort.14: missing counts line")
        n_elements, n_nodes = counts[0], counts[1]

        # --- Nodes ---
        nodes: List[Tuple[int, float, float, float]] = []
        for _ in range(n_nodes):
            parts = f.readline().split()
            if len(parts) < 4:
                raise ValueError("Invalid fort.14: node line too short")
            nid = int(parts[0])
            x = float(parts[1])
            y = float(parts[2])
            depth = float(parts[3])
            nodes.append((nid, x, y, depth))

        # --- Elements ---
        elements: List[Tuple[int, int, int, int, int]] = []
        for _ in range(n_elements):
            parts = f.readline().split()
            if len(parts) < 5:
                raise ValueError("Invalid fort.14: element line too short")
            eid = int(parts[0])
            # parts[1] is number of nodes per element; ignore beyond 3 nodes
            n1 = int(parts[2])
            n2 = int(parts[3])
            n3 = int(parts[4])
            n4 = int(parts[5]) if len(parts) > 5 else 0
            elements.append((eid, n1, n2, n3, n4))

        # --- Open boundaries (robust) ---
        n_open_line = _read_nonempty_line(f)
        if n_open_line is None:
            return Fort14(title, n_nodes, n_elements, nodes, elements, [], [])
        try:
            n_open = int(n_open_line.split()[0])
        except Exception:
            return Fort14(title, n_nodes, n_elements, nodes, elements, [], [])

        # Optional total nodes line; rewind if not a simple int
        pos_after_n_open = f.tell()
        ints, pos_before = _read_nonempty_ints(f)
        if ints is not None and len(ints) == 1:
            # total nodes hint; we don't rely on it for parsing selection
            pass
        else:
            if ints is not None:
                f.seek(pos_before)
            else:
                f.seek(pos_after_n_open)

        # Parse each open boundary independently with dual strategy
        known_ids = {nid for (nid, _, _, _) in nodes}
        open_boundaries: List[List[int]] = []
        for _ in range(max(0, n_open)):
            b = _parse_one_boundary(f, known_ids)
            open_boundaries.append(b)

        # --- Land boundaries (robust) ---
        n_land_line = _read_nonempty_line(f)
        if n_land_line is None:
            return Fort14(title, n_nodes, n_elements, nodes, elements, open_boundaries, [])
        try:
            n_land = int(n_land_line.split()[0])
        except Exception:
            return Fort14(title, n_nodes, n_elements, nodes, elements, open_boundaries, [])

        pos_after_n_land = f.tell()
        ints, pos_before = _read_nonempty_ints(f)
        if ints is not None and len(ints) == 1:
            pass
        else:
            if ints is not None:
                f.seek(pos_before)
            else:
                f.seek(pos_after_n_land)

        land_boundaries: List[List[int]] = []
        for _ in range(max(0, n_land)):
            b = _parse_one_boundary(f, known_ids)
            land_boundaries.append(b)

        return Fort14(title, n_nodes, n_elements, nodes, elements, open_boundaries, land_boundaries)


def mesh_bbox_from_fort14(path: str | Path) -> Tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) from node coordinates."""
    m = parse_fort14(path)
    xs = [x for (_, x, _, _) in m.nodes]
    ys = [y for (_, _, y, _) in m.nodes]
    return (min(xs), min(ys), max(xs), max(ys))
