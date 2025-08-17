from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class Fort14:
    title: str
    n_nodes: int
    n_elements: int
    nodes: List[Tuple[int, float, float, float]]  # (id, lon/x, lat/y, depth)
    elements: List[Tuple[int, int, int, int, int]]  # (id, n1, n2, n3, [n4 ignored])
    open_boundaries: List[List[int]]  # sequences of node ids for each open boundary
    land_boundaries: List[List[int]]

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        xs = [n[1] for n in self.nodes]
        ys = [n[2] for n in self.nodes]
        return (min(xs), min(ys), max(xs), max(ys))


def _parse_ints(line: str) -> List[int]:
    return [int(x) for x in line.strip().split()]


def parse_fort14(path: str | Path) -> Fort14:
    """Robust minimal ADCIRC fort.14 parser.

    Parses title, counts, nodes, elements, open/land boundaries, and bbox.
    Supports triangular elements; extra nodes per element are ignored.
    """
    p = Path(path)
    with p.open("r", encoding="utf-8", errors="ignore") as f:
        # Title
        title = f.readline().strip()
        # Counts: number of elements, nodes
        counts = _parse_ints(f.readline())
        if len(counts) < 2:
            raise ValueError("Invalid fort.14: missing counts line")
        n_elements, n_nodes = counts[0], counts[1]

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

        elements: List[Tuple[int, int, int, int, int]] = []
        for _ in range(n_elements):
            parts = f.readline().split()
            if len(parts) < 5:
                raise ValueError("Invalid fort.14: element line too short")
            eid = int(parts[0])
            # int(parts[1]) is number of nodes per element; ignore beyond first 3
            n1 = int(parts[2])
            n2 = int(parts[3])
            n3 = int(parts[4])
            n4 = int(parts[5]) if len(parts) > 5 else 0
            elements.append((eid, n1, n2, n3, n4))

        # Boundary info
        # Open boundaries
        line = f.readline()
        if not line:
            # No boundaries
            return Fort14(title, n_nodes, n_elements, nodes, elements, [], [])
        n_open = int(line.strip().split()[0])
        n_open_nodes = int(f.readline().strip().split()[0]) if n_open > 0 else 0
        open_boundaries: List[List[int]] = []
        for _ in range(n_open):
            nseg = int(f.readline().strip().split()[0])
            b_nodes: List[int] = []
            for _ in range(nseg):
                parts = _parse_ints(f.readline())
                # parts[0] is number of nodes in this segment
                seg_nodes = []
                for _ in range(parts[0]):
                    seg_nodes.append(int(f.readline().strip().split()[0]))
                b_nodes.extend(seg_nodes)
            open_boundaries.append(b_nodes)

        # Land boundaries
        n_land = int(f.readline().strip().split()[0])
        n_land_nodes = int(f.readline().strip().split()[0]) if n_land > 0 else 0
        land_boundaries: List[List[int]] = []
        for _ in range(n_land):
            nseg = int(f.readline().strip().split()[0])
            b_nodes: List[int] = []
            for _ in range(nseg):
                parts = _parse_ints(f.readline())
                seg_nodes = []
                for _ in range(parts[0]):
                    seg_nodes.append(int(f.readline().strip().split()[0]))
                b_nodes.extend(seg_nodes)
            land_boundaries.append(b_nodes)

        return Fort14(title, n_nodes, n_elements, nodes, elements, open_boundaries, land_boundaries)


def mesh_bbox_from_fort14(path: str | Path) -> Tuple[float, float, float, float]:
    return parse_fort14(path).bbox

