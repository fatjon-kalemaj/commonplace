"""Render a vault's wikilink graph to a standalone SVG, so the README can show
the demo graph without a screenshot of anyone's real vault. Deterministic
force-directed layout, no dependencies."""

from __future__ import annotations

import math
import random
import re
from html import escape
from pathlib import Path

LINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
COLORS = {
    "People": "#4E79A7", "Companies": "#E15759", "Projects": "#59A14F", "Meetings": "#F28E2B",
    "Decisions": "#B07AA1", "Emails": "#76B7B2", "Sessions": "#EDC948", "Daily": "#BAB0AC",
    "Documents": "#9C755F", "Notes": "#FF9DA7", "Tasks": "#8CD17D",
}
LABELLED = {"People", "Companies", "Projects"}


def load_graph(vault: Path, exclude: tuple[str, ...] = ()) -> tuple[dict[str, str], set[tuple[str, str]]]:
    nodes: dict[str, str] = {}
    texts: dict[str, str] = {}
    for p in vault.rglob("*.md"):
        rel = p.relative_to(vault)
        if rel.parts[0].startswith(".") or rel.parts[0] in exclude:
            continue
        nodes[p.stem] = rel.parts[0] if len(rel.parts) > 1 else ""
        texts[p.stem] = p.read_text()
    edges = set()
    for src, text in texts.items():
        for target in LINK.findall(text):
            target = target.strip()
            if target in nodes and target != src:
                edges.add(tuple(sorted((src, target))))
    return nodes, edges


def layout(nodes: list[str], edges: set[tuple[str, str]], size: float, iters: int = 400) -> dict[str, tuple[float, float]]:
    rng = random.Random(7)
    pos = {n: [rng.uniform(-1, 1) * size / 3, rng.uniform(-1, 1) * size / 3] for n in nodes}
    k = size / math.sqrt(max(len(nodes), 1)) * 1.3
    for i in range(iters):
        t = size / 10 * (1 - i / iters) + 1
        disp = {n: [0.0, 0.0] for n in nodes}
        for a_i, a in enumerate(nodes):
            for b in nodes[a_i + 1:]:
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                d = math.hypot(dx, dy) or 0.01
                f = k * k / d
                disp[a][0] += dx / d * f; disp[a][1] += dy / d * f
                disp[b][0] -= dx / d * f; disp[b][1] -= dy / d * f
        for a, b in edges:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 0.01
            f = d * d / k
            disp[a][0] -= dx / d * f; disp[a][1] -= dy / d * f
            disp[b][0] += dx / d * f; disp[b][1] += dy / d * f
        for n in nodes:
            # gentle pull to the centre keeps disconnected notes on the canvas
            disp[n][0] -= pos[n][0] * 0.05; disp[n][1] -= pos[n][1] * 0.05
            d = math.hypot(*disp[n]) or 0.01
            pos[n][0] += disp[n][0] / d * min(d, t)
            pos[n][1] += disp[n][1] / d * min(d, t)
    return {n: (p[0], p[1]) for n, p in pos.items()}


def render_svg(vault: Path, out: Path, width: int = 1200, height: int = 900,
               exclude: tuple[str, ...] = ("Daily",)) -> tuple[int, int]:
    nodes, edges = load_graph(vault, exclude)
    names = sorted(nodes)
    pos = layout(names, edges, size=min(width, height))
    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    pad = 70
    sx = (width - 2 * pad) / ((max(xs) - min(xs)) or 1)
    sy = (height - 2 * pad - 40) / ((max(ys) - min(ys)) or 1)
    s = min(sx, sy)
    ox = (width - (max(xs) - min(xs)) * s) / 2
    oy = 40 + (height - 40 - (max(ys) - min(ys)) * s) / 2

    def xy(n: str) -> tuple[float, float]:
        return (pos[n][0] - min(xs)) * s + ox, (pos[n][1] - min(ys)) * s + oy

    degree = {n: 0 for n in names}
    for a, b in edges:
        degree[a] += 1; degree[b] += 1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'font-family="Helvetica, Arial, sans-serif">',
             f'<rect width="{width}" height="{height}" fill="#1e1e24"/>']
    for a, b in sorted(edges):
        (x1, y1), (x2, y2) = xy(a), xy(b)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#5c5c66" stroke-width="0.8" stroke-opacity="0.7"/>')
    for n in names:
        x, y = xy(n)
        r = 3 + math.sqrt(degree[n]) * 1.6
        color = COLORS.get(nodes[n], "#cccccc")
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}"><title>{escape(n)}</title></circle>')
        if nodes[n] in LABELLED:
            parts.append(f'<text x="{x:.1f}" y="{y - r - 3:.1f}" font-size="11" fill="#dcdcdc" text-anchor="middle">{escape(n)}</text>')
    lx = 20
    for folder, color in COLORS.items():
        if folder not in nodes.values():
            continue
        parts.append(f'<circle cx="{lx + 6}" cy="22" r="6" fill="{color}"/>')
        parts.append(f'<text x="{lx + 16}" y="26" font-size="12" fill="#dcdcdc">{folder}</text>')
        lx += 22 + len(folder) * 7
    parts.append("</svg>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts))
    return len(names), len(edges)
