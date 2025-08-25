from __future__ import annotations
__version__ = "0.1.0"
import argparse
import sys
from pathlib import Path
from typing import Tuple, List
from dataclasses import dataclass
from ..io.fort14_boundaries import parse_fort14_boundaries
from ..plot.boundary_fast import classify_land_segments, segments_to_edges
import numpy as np
import plotly.graph_objects as go

def _parse_two_ints(s: str) -> Tuple[int, int]:
    toks = s.split()
    if len(toks) < 2:
        raise ValueError(f"Line does not contain two integers: {s!r}")
    try:
        return int(toks[0]), int(toks[1])
    except Exception:
        # allow trailing comments/tokens after two ints, but the first two must be ints
        i0 = int(toks[0]); i1 = int(toks[1])
        return i0, i1

def _looks_like_elem(ln: str) -> bool:
    p = ln.split()
    if len(p) < 4:
        return False
    try:
        int(p[0])
    except Exception:
        return False
    # ADCIRC typical: eid 3 n1 n2 n3 ...
    if len(p) >= 5 and p[1] == "3":
        try:
            int(p[2]); int(p[3]); int(p[4])
            return True
        except Exception:
            return False
    # Some variants: eid n1 n2 n3
    try:
        int(p[1]); int(p[2]); int(p[3])
        return True
    except Exception:
        return False

def _looks_like_node(ln: str) -> bool:
    p = ln.split()
    if len(p) < 3:
        return False
    try:
        int(p[0])
        # element lines have second token often '3'; node lines have float x
        if p[1] == "3":
            return False
        float(p[1]); float(p[2])
        return True
    except Exception:
        return False

@dataclass
class StyleConfig:
    coast_color: str = "red"
    openbdy_color: str = "blue"
    coast_width: float = 0.6
    openbdy_width: float = 0.6
    coast_visible: bool = True
    openbdy_visible: bool = True


def parse_fvcom_14(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    raw = Path(path).read_text().splitlines()
    # Keep all lines to preserve indexing
    lines = [ln.rstrip("\n") for ln in raw]
    if len(lines) < 2:
        raise ValueError("Not a valid fort.14: file has fewer than 2 lines.")
    # Line 1 = title, line 2 = two integers (counts, unknown order: NP NE or NE NP)
    title = lines[0]
    a, b = _parse_two_ints(lines[1])  # unknown order

    # Decide which block comes first by looking at line 3:
    first = lines[2] if len(lines) >= 3 else ""
    nodes_first = _looks_like_node(first)
    elems_first = _looks_like_elem(first)

    # Decide (NP, NE) from (a, b) and from the first-block type:
    def read_nodes_block(start: int, ncount: int) -> Tuple[np.ndarray, int]:
        end = start + ncount
        if end > len(lines):
            raise ValueError(f"File ended before reading {ncount} node lines (start={start+1}).")
        nodes_local = []
        for j, ln in enumerate(lines[start:end], start=start):
            parts = ln.split()
            if len(parts) < 3:
                raise ValueError(f"Node parse error at line {j+1}: expected 'id x y ...', got: {ln!r}")
            try:
                nid = int(parts[0]); x = float(parts[1]); y = float(parts[2])
            except Exception:
                raise ValueError(f"Node parse error at line {j+1}: {ln!r}")
            nodes_local.append((nid, x, y))
        return np.asarray(nodes_local, dtype=float), end

    def read_elems_block(start: int, mcount: int) -> Tuple[np.ndarray, int]:
        end = start + mcount
        if end > len(lines):
            raise ValueError(f"File ended before reading {mcount} element lines (start={start+1}).")
        elems_local = []
        for i in range(start, end):
            parts = lines[i].split()
            if len(parts) >= 4:
                try:
                    eid = int(parts[0])
                    if len(parts) >= 5 and parts[1] == "3":
                        n1 = int(parts[2]); n2 = int(parts[3]); n3 = int(parts[4])
                    else:
                        n1 = int(parts[1]); n2 = int(parts[2]); n3 = int(parts[3])
                    elems_local.append((eid, n1, n2, n3))
                except Exception:
                    pass
        if len(elems_local) != mcount:
            raise ValueError(f"Expected {mcount} element records, parsed {len(elems_local)}")
        return np.asarray(elems_local, dtype=int), end

    idx = 2
    if nodes_first and not elems_first:
        # First block are nodes; decide NP by testing which of (a,b) makes sense.
        # Prefer the smaller of (a,b) if both "look" plausible to avoid overruns.
        cand = sorted([(a, 'a'), (b, 'b')], key=lambda t: t[0])
        nodes_arr = elems_arr = None
        NP = NE = None
        for ncount, tag in cand:
            try:
                test_nodes, after = read_nodes_block(idx, ncount)
                # quick plausibility: last parsed line should NOT "look like elem"
                if _looks_like_elem(lines[after]) if after < len(lines) else True:
                    # assume the other count is elements
                    mcount = b if tag == 'a' else a
                    test_elems, end2 = read_elems_block(after, mcount)
                    nodes_arr, elems_arr = test_nodes, test_elems
                    NP, NE = ncount, mcount
                    parser_mode = f"nodes-first NP={NP} NE={NE}"
                    break
            except Exception:
                continue
        if nodes_arr is None:
            raise ValueError("Could not resolve nodes-first block sizes from header.")
    elif elems_first and not nodes_first:
        # First block are elements; decide NE by testing which of (a,b) matches.
        cand = sorted([(a, 'a'), (b, 'b')], key=lambda t: t[0])
        nodes_arr = elems_arr = None
        NP = NE = None
        for mcount, tag in cand:
            try:
                test_elems, after = read_elems_block(idx, mcount)
                # Next block should look like nodes
                test_nodes, end2 = read_nodes_block(after, (b if tag == 'a' else a))
                elems_arr, nodes_arr = test_elems, test_nodes
                NE, NP = mcount, (b if tag == 'a' else a)
                parser_mode = f"elems-first NP={NP} NE={NE}"
                break
            except Exception:
                continue
        if nodes_arr is None:
            raise ValueError("Could not resolve elems-first block sizes from header.")
    else:
        # Fallback: prefer nodes-first with 'a' as NP, else swap.
        try:
            nodes_arr, after = read_nodes_block(idx, a)
            elems_arr, _ = read_elems_block(after, b)
            NP, NE = a, b
            parser_mode = f"nodes-first(fallback) NP={NP} NE={NE}"
        except Exception:
            nodes_arr, after = read_nodes_block(idx, b)
            elems_arr, _ = read_elems_block(after, a)
            NP, NE = b, a
            parser_mode = f"nodes-first(fallback-swap) NP={NP} NE={NE}"

    # Optional debug banner
    if '--debug' in sys.argv:
        print(f"[debug] parser_mode={parser_mode}")

    return nodes_arr, elems_arr

def make_id_lookup(node_ids: np.ndarray) -> np.ndarray:
    max_id = int(node_ids.max()) if node_ids.size else 0
    L = np.full(max_id + 1, -1, dtype=int)
    if node_ids.size:
        L[node_ids.astype(int)] = np.arange(node_ids.size, dtype=int)
    return L

def build_edge_segments(nodes: np.ndarray, elems: np.ndarray) -> np.ndarray:
    node_ids = nodes[:, 0].astype(int)
    xy = nodes[:, 1:3]
    id2idx = make_id_lookup(node_ids)

    edges = set()
    tri_nodes = elems[:, 1:4].astype(int)
    for n1, n2, n3 in tri_nodes:
        for a, b in ((n1, n2), (n2, n3), (n3, n1)):
            e = (a, b) if a < b else (b, a)
            edges.add(e)

    segs = []
    for a, b in edges:
        ia = id2idx[a]; ib = id2idx[b]
        if ia < 0 or ib < 0:
            continue
        x0, y0 = xy[ia]; x1, y1 = xy[ib]
        segs.append((x0, y0, x1, y1))
    return np.asarray(segs, dtype=float)

def parse_polylines(path: Path) -> List[Tuple[np.ndarray, np.ndarray]]:
    txt_lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    # detect CSV via first non-empty line header
    header = ""
    header_idx = -1
    for i, ln in enumerate(txt_lines):
        if ln.strip():
            header = ln.strip().lstrip("\ufeff")
            header_idx = i
            break
    is_csv = ("," in header and ("x" in header.lower() and "y" in header.lower()))
    segs: List[Tuple[np.ndarray, np.ndarray]] = []
    if is_csv:
        import csv
        xs, ys = [], []
        # Build a DictReader starting at the detected header
        rdr = csv.DictReader([header] + txt_lines[header_idx + 1 :])
        for row in rdr:
            try:
                # case-insensitive key lookup
                kx = next((k for k in row.keys() if k is not None and k.lower() == "x"), None)
                ky = next((k for k in row.keys() if k is not None and k.lower() == "y"), None)
                if kx is None or ky is None:
                    continue
                xs.append(float((row[kx] or "").strip()))
                ys.append(float((row[ky] or "").strip()))
            except Exception:
                # ignore malformed rows
                continue
        if xs:
            segs.append((np.asarray(xs, float), np.asarray(ys, float)))
        return segs
    # whitespace format with blank-line separators
    curx: List[float] = []
    cury: List[float] = []
    def flush():
        nonlocal curx, cury, segs
        if curx:
            segs.append((np.asarray(curx, float), np.asarray(cury, float)))
            curx, cury = [], []
    for ln in txt_lines:
        s = ln.strip()
        if not s:
            flush()
            continue
        p = s.split()
        if len(p) >= 2:
            try:
                curx.append(float(p[0]))
                cury.append(float(p[1]))
            except Exception:
                # ignore bad line
                pass
    flush()
    return segs


## Removed heuristic boundary scanners in favor of robust parser (parse_fort14_boundaries)


def build_overlay_traces(
    polys: List[Tuple[np.ndarray, np.ndarray]],
    color: str,
    width: float,
    name: str,
    visible: bool = True,
) -> List[go.Scattergl]:
    traces: List[go.Scattergl] = []
    for k, (x, y) in enumerate(polys):
        traces.append(
            go.Scattergl(
                x=x,
                y=y,
                mode="lines",
                line=dict(color=color, width=float(width)),
                name=name,
                hoverinfo="skip",
                showlegend=(k == 0),
                visible=visible,
            )
        )
    return traces


def plot_mesh_interactive(
    nodes: np.ndarray,
    elems: np.ndarray,
    title: str,
    use_webgl: bool,
    style: StyleConfig,
    coast_polys: List[Tuple[np.ndarray, np.ndarray]],
    open_polys: List[Tuple[np.ndarray, np.ndarray]],
) -> go.Figure:
    segs = build_edge_segments(nodes, elems)

    # Edges (force WebGL for reliable rendering of many segments)
    xs, ys = [], []
    for x0, y0, x1, y1 in segs:
        xs += [x0, x1, None]
        ys += [y0, y1, None]

    edge_tr = go.Scattergl(
        x=xs, y=ys, mode="lines",
        line=dict(width=0.6, color="black"),
        name="Edges", hoverinfo="skip"
    )

    # Nodes (small red circles)
    ScatterPoint = go.Scattergl if use_webgl else go.Scatter
    node_ids = nodes[:, 0].astype(int)
    node_tr = ScatterPoint(
        x=nodes[:, 1], y=nodes[:, 2], mode="markers",
        marker=dict(size=2, color="red"),
        name="Nodes (hover for id)",
        text=[f"node: {i}" for i in node_ids], hoverinfo="text"
    )

    # Element centroids (legend toggle)
    id2idx = make_id_lookup(node_ids)
    tri = elems[:, 1:4].astype(int)
    valid = (tri > 0) & (tri <= id2idx.size - 1)
    valid = valid.all(axis=1)
    tri = tri[valid]
    # centroids only for valid triangles
    i1 = id2idx[tri[:, 0]]; i2 = id2idx[tri[:, 1]]; i3 = id2idx[tri[:, 2]]
    cx = (nodes[i1, 1] + nodes[i2, 1] + nodes[i3, 1]) / 3.0
    cy = (nodes[i1, 2] + nodes[i2, 2] + nodes[i3, 2]) / 3.0
    # Elements (small green crosses)
    elem_tr = ScatterPoint(
        x=cx, y=cy, mode="markers",
        marker=dict(size=3, symbol="cross", color="green"),
        name="Elements (hover for id)",
        text=[f"elem: {int(e)}" for e in elems[valid, 0]],
        hoverinfo="text",
        visible=True  # show by default
    )

    fig = go.Figure(data=[edge_tr, node_tr, elem_tr])
    # Overlays on top
    if coast_polys:
        for tr in build_overlay_traces(
            coast_polys, style.coast_color, style.coast_width, "Coastline", style.coast_visible
        ):
            fig.add_trace(tr)
    if open_polys:
        for tr in build_overlay_traces(
            open_polys, style.openbdy_color, style.openbdy_width, "Open Boundary", style.openbdy_visible
        ):
            fig.add_trace(tr)
    fig.update_layout(
        title=title,
        xaxis=dict(scaleanchor="y", scaleratio=1, title="x", zeroline=False, showgrid=False),
        yaxis=dict(title="y", zeroline=False, showgrid=False),
        plot_bgcolor="white",
        legend=dict(itemsizing="constant"),
        dragmode="pan",
    )
    return fig

def main():
    ap = argparse.ArgumentParser(description="Interactive FVCOM .14 mesh viewer (HTML output)")
    ap.add_argument("mesh14", type=Path, help=".14 mesh file (or .14.txt)")
    ap.add_argument("--out", type=Path, default=None, help="Output HTML path")
    ap.add_argument("--title", type=str, default=None, help="Plot title")
    ap.add_argument("--debug", action="store_true", help="Print counts and ranges for sanity check")
    ap.add_argument("--no-webgl", action="store_true", help="Use SVG (go.Scatter) instead of WebGL")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("XMIN","XMAX","YMIN","YMAX"),
                    help="Set axis ranges to the given bbox")
    # Overlays: files and styling
    ap.add_argument("--coast-file", action="append", type=Path, help="Coastline polyline file(s); whitespace 'x y' with blank-line segments, or CSV with header x,y")
    ap.add_argument("--openbdy-file", action="append", type=Path, help="Open-boundary polyline file(s); same formats as --coast-file")
    ap.add_argument("--openbdy-from-14", action="store_true", help="Extract open-boundary node chains from the .14 if present")
    ap.add_argument("--coast-from-14", action="store_true", help="Extract land-boundary node chains (coastline) from the .14")
    ap.add_argument("--no-coast-from-14", action="store_true", help="Disable coastline extraction from .14")
    ap.add_argument("--coast-color", type=str, default=None)
    ap.add_argument("--openbdy-color", type=str, default=None)
    ap.add_argument("--coast-width", type=float, default=None)
    ap.add_argument("--openbdy-width", type=float, default=None)
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args()

    nodes, elems = parse_fvcom_14(args.mesh14)
    if args.debug:
        import os
        print(f"[debug] script_path={__file__}")
        print(f"[debug] version={__version__}")
        nn, ne = nodes.shape[0], elems.shape[0]
        xs, ys = (nodes[:,1], nodes[:,2]) if nn else (np.array([]), np.array([]))
        print(f"[debug] nodes={nn}, elems={ne}")
        if nn:
            print(f"[debug] x: min={xs.min()} max={xs.max()}  y: min={ys.min()} max={ys.max()}")
        segs = build_edge_segments(nodes, elems)
        print(f"[debug] edges={segs.shape[0] if segs.size else 0}")
        if nn > 0:
            print(f"[debug] node sample: id={int(nodes[0,0])}, x={nodes[0,1]}, y={nodes[0,2]}")
        # extra sanity: max referenced node id vs max node id
        if ne:
            max_ref = int(np.max(elems[:,1:4]))
            max_id = int(np.max(nodes[:,0]))
            print(f"[debug] max_ref_node_id={max_ref}, max_node_id={max_id} (should be <=)")

    # Build style from CLI overrides
    style = StyleConfig()
    if args.coast_color:
        style.coast_color = args.coast_color
    if args.openbdy_color:
        style.openbdy_color = args.openbdy_color
    if args.coast_width is not None:
        style.coast_width = float(args.coast_width)
    if args.openbdy_width is not None:
        style.openbdy_width = float(args.openbdy_width)

    # Robust boundaries from fort.14 (default coastline on; open boundaries opt-in)
    b = None
    try:
        b = parse_fort14_boundaries(args.mesh14)
    except Exception:
        b = None

    # Coastline from .14 by default (unless disabled)
    coast_polys: List[Tuple[np.ndarray, np.ndarray]] = []
    if b is not None and (args.coast_from_14 or not args.no_coast_from_14):
        try:
            coast_ids = classify_land_segments(b.land_segments, include_ibtype=(0, 20, 21)).get('coast', [])
            for seg in coast_ids:
                if seg and len(seg) >= 2:
                    idx = np.asarray(seg, dtype=int)
                    xy = b.nodes_xy[idx, :2]
                    coast_polys.append((xy[:, 0], xy[:, 1]))
        except Exception:
            if args.debug:
                print("[debug] coastline extraction via robust parser failed; skipping.")

    # Open boundaries from .14 only if requested
    open_polys: List[Tuple[np.ndarray, np.ndarray]] = []
    if b is not None and args.openbdy_from_14:
        try:
            for seg in b.open_segments:
                if seg and len(seg) >= 2:
                    idx = np.asarray(seg, dtype=int)
                    xy = b.nodes_xy[idx, :2]
                    open_polys.append((xy[:, 0], xy[:, 1]))
        except Exception:
            if args.debug:
                print("[debug] open-boundary extraction via robust parser failed; skipping.")

    # Append external overlays (files can add detail)
    if args.coast_file:
        for p in args.coast_file:
            segs = []
            try:
                segs = parse_polylines(p)
            except Exception:
                segs = []
            if not segs:
                print(f"[warn] No valid coastline segments in file: {p}", file=sys.stderr)
            coast_polys += segs
    if args.openbdy_file:
        for p in args.openbdy_file:
            segs = []
            try:
                segs = parse_polylines(p)
            except Exception:
                segs = []
            if not segs:
                print(f"[warn] No valid open-boundary segments in file: {p}", file=sys.stderr)
            open_polys += segs

    if args.debug:
        print(f"[debug] coastline segments: {len(coast_polys)}  open-boundary segments: {len(open_polys)}")

    title = args.title or args.mesh14.name
    fig = plot_mesh_interactive(
        nodes,
        elems,
        title=title,
        use_webgl=(not args.no_webgl),
        style=style,
        coast_polys=coast_polys,
        open_polys=open_polys,
    )
    if args.bbox:
        xmin, xmax, ymin, ymax = args.bbox
        fig.update_layout(
            xaxis=dict(range=[xmin, xmax], scaleanchor="y", scaleratio=1, title="x", zeroline=False),
            yaxis=dict(range=[ymin, ymax], title="y", zeroline=False),
        )

    outpath = args.out or Path("mesh_interactive.html")
    # Embed plotly.js to avoid CDN/network dependency
    fig.write_html(str(outpath), include_plotlyjs=True, full_html=True)
    print(f"Wrote {outpath}")

if __name__ == "__main__":
    main()
