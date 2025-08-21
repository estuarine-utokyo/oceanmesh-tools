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


def _peek_exact_int_lines(f, n: int) -> Optional[List[int]]:
    """Return ints from next n non-empty lines iff each line has exactly one int; do not advance file pointer.

    Returns None if any line missing or has 0/multiple integer tokens.
    """
    if n <= 0:
        return []
    pos = f.tell()
    vals: List[int] = []
    try:
        for _ in range(n):
            s = _read_nonempty_line(f)
            if s is None:
                f.seek(pos)
                return None
            ints = _parse_ints(s)
            if len(ints) != 1:
                f.seek(pos)
                return None
            vals.append(ints[0])
        f.seek(pos)
        return vals
    except Exception:
        f.seek(pos)
        return None


def _read_exact_int_lines(f, n: int) -> List[int]:
    """Consume next n non-empty lines, each must contain exactly one integer; return collected ints (may be < n on EOF)."""
    vals: List[int] = []
    for _ in range(max(0, n)):
        s = _read_nonempty_line(f)
        if s is None:
            break
        ints = _parse_ints(s)
        if len(ints) != 1:
            # Stop if format deviates; caller decides fallback
            break
        vals.append(ints[0])
    return vals


def _parse_one_boundary(
    f,
    known_node_ids: Set[int],
    total_hint: Optional[int] = None,
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

    # Build candidates without committing pointer
    a_nodes: Optional[List[int]] = None
    a_H = None
    if len(header_ints) == 1 and header_ints[0] >= 1:
        H = header_ints[0]
        peek = _peek_exact_int_lines(f, H)
        if peek is not None and len(peek) == H:
            a_nodes = list(peek)
            a_H = H

    # Candidate B: peek by simulating read and rewinding
    f.seek(pos_after_header)
    b_nodes: List[int] = []
    S = header_ints[0] if (len(header_ints) == 1 and header_ints[0] >= 1) else 1
    pos_before_b = f.tell()
    for _ in range(S):
        line = _read_nonempty_line(f)
        if line is None:
            break
        seg_ints = _parse_ints(line)
        if len(seg_ints) == 1 and seg_ints[0] >= 1:
            N = seg_ints[0]
            vals = _peek_exact_int_lines(f, N)
            if vals is not None and len(vals) == N:
                b_nodes.extend(vals)
                # advance peeked
                _ = _read_exact_int_lines(f, N)
            else:
                # salvage: read as many single-int lines as available
                b_nodes.extend(_read_exact_int_lines(f, N))
        elif len(seg_ints) >= 1:
            b_nodes.extend(seg_ints)
        else:
            continue
    # Rewind to after header; we will commit by re-reading chosen path
    f.seek(pos_after_header)

    # Selection with total_hint awareness
    if total_hint is not None:
        if a_nodes is not None and len(a_nodes) == total_hint and len(b_nodes) != total_hint:
            # Commit A
            return _read_exact_int_lines(f, a_H or 0)
        if len(b_nodes) == total_hint and (a_nodes is None or len(a_nodes) != total_hint):
            # Commit B: re-read to consume
            nodes_out: List[int] = []
            S = header_ints[0] if (len(header_ints) == 1 and header_ints[0] >= 1) else 1
            for _ in range(S):
                line = _read_nonempty_line(f)
                if line is None:
                    break
                seg_ints = _parse_ints(line)
                if len(seg_ints) == 1 and seg_ints[0] >= 1:
                    nodes_out.extend(_read_exact_int_lines(f, seg_ints[0]))
                elif len(seg_ints) >= 1:
                    nodes_out.extend(seg_ints)
            return nodes_out

    # Default deterministic: prefer A if available, else B
    if a_nodes is not None:
        return _read_exact_int_lines(f, a_H or 0)
    # Commit B
    nodes_out: List[int] = []
    S = header_ints[0] if (len(header_ints) == 1 and header_ints[0] >= 1) else 1
    for _ in range(S):
        line = _read_nonempty_line(f)
        if line is None:
            break
        seg_ints = _parse_ints(line)
        if len(seg_ints) == 1 and seg_ints[0] >= 1:
            nodes_out.extend(_read_exact_int_lines(f, seg_ints[0]))
        elif len(seg_ints) >= 1:
            nodes_out.extend(seg_ints)
    return nodes_out


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

        # Optional total nodes line; if present and simple int, consume; else rewind
        pos_after_n_open = f.tell()
        open_total_nodes: Optional[int] = None
        open_pos_before_total = None
        ints, pos_before = _read_nonempty_ints(f)
        # Always rewind after peeking; do not consume here
        if ints is not None and len(ints) == 1:
            open_total_nodes = ints[0]
            open_pos_before_total = pos_before
        # Rewind to position after n_open to let boundary parsing consume correctly
        if ints is not None:
            f.seek(pos_before)
        else:
            f.seek(pos_after_n_open)

        # Parse each open boundary independently with dual strategy
        known_ids = {nid for (nid, _, _, _) in nodes}
        open_boundaries: List[List[int]] = []
        if n_open == 1:
            # First attempt with header after total (if any)
            pos_before_boundary = f.tell()
            b = _parse_one_boundary(f, known_ids, open_total_nodes)
            if open_total_nodes is not None and len(b) != open_total_nodes and open_pos_before_total is not None:
                # Retry treating the 'total' line as the boundary header
                f.seek(open_pos_before_total)
                b = _parse_one_boundary(f, known_ids, None)
            open_boundaries.append(b)
        else:
            for _ in range(max(0, n_open)):
                b = _parse_one_boundary(f, known_ids, open_total_nodes)
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
        land_total_nodes: Optional[int] = None
        land_pos_before_total = None
        ints, pos_before = _read_nonempty_ints(f)
        # Always rewind after peeking; do not consume here
        if ints is not None and len(ints) == 1:
            land_total_nodes = ints[0]
            land_pos_before_total = pos_before
        # Rewind to position after n_land to let boundary parsing consume correctly
        if ints is not None:
            f.seek(pos_before)
        else:
            f.seek(pos_after_n_land)

        land_boundaries: List[List[int]] = []
        if n_land == 1:
            b = _parse_one_boundary(f, known_ids, land_total_nodes)
            if land_total_nodes is not None and len(b) != land_total_nodes and land_pos_before_total is not None:
                f.seek(land_pos_before_total)
                b = _parse_one_boundary(f, known_ids, None)
            land_boundaries.append(b)
        else:
            for _ in range(max(0, n_land)):
                b = _parse_one_boundary(f, known_ids, land_total_nodes)
                land_boundaries.append(b)

        return Fort14(title, n_nodes, n_elements, nodes, elements, open_boundaries, land_boundaries)


def mesh_bbox_from_fort14(path: str | Path) -> Tuple[float, float, float, float]:
    """Return (xmin, ymin, xmax, ymax) from node coordinates."""
    m = parse_fort14(path)
    xs = [x for (_, x, _, _) in m.nodes]
    ys = [y for (_, _, y, _) in m.nodes]
    return (min(xs), min(ys), max(xs), max(ys))
