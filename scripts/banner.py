#!/usr/bin/env python3
"""
banner.py - render the animated profile banner as SVG. Stdlib only.

A terminal window where a cloud of particles keeps morphing between three
shapes: a neural network, a processor chip and a </> code glyph.

    python scripts/banner.py --out assets

Writes <out>/banner-dark.svg and <out>/banner-light.svg.
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

W, H = 1200, 420
CX, CY = 600, 232          # centre of the drawing area
N = 520                    # particles
DUR = 15                   # seconds per full loop
SEED = 1596

THEMES = {
    "dark": {
        "bg": "#0d1117", "panel": "#161b22", "border": "#30363d",
        "muted": "#8b949e", "text": "#c9d1d9",
        "particles": ["#58a6ff", "#58a6ff", "#79c0ff", "#a5d6ff", "#e6edf3"],
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de",
        "muted": "#57606a", "text": "#24292f",
        "particles": ["#0969da", "#0969da", "#218bff", "#54aeff", "#0550ae"],
    },
}

LABELS = ["neural_network", "processor", "source_code"]


# ---------------------------------------------------------------- sampling --

def seg_len(s):
    (x1, y1), (x2, y2) = s
    return math.hypot(x2 - x1, y2 - y1)


def sample_segments(segs, n, rng, thick=0.0):
    """Spread n points along the segments, proportional to their length."""
    total = sum(seg_len(s) for s in segs)
    pts = []
    for s in segs:
        k = max(1, round(n * seg_len(s) / total))
        (x1, y1), (x2, y2) = s
        L = seg_len(s) or 1
        nx, ny = -(y2 - y1) / L, (x2 - x1) / L
        for i in range(k):
            t = (i + rng.random()) / k
            off = (rng.random() - 0.5) * thick
            pts.append((x1 + (x2 - x1) * t + nx * off, y1 + (y2 - y1) * t + ny * off))
    rng.shuffle(pts)
    while len(pts) < n:
        pts.append(rng.choice(pts))
    return pts[:n]


def circle_segs(x, y, r, k=10):
    p = [(x + r * math.cos(2 * math.pi * i / k), y + r * math.sin(2 * math.pi * i / k)) for i in range(k)]
    return [(p[i], p[(i + 1) % k]) for i in range(k)]


def rect_segs(x, y, w, h):
    a, b, c, d = (x, y), (x + w, y), (x + w, y + h), (x, y + h)
    return [(a, b), (b, c), (c, d), (d, a)]


# ------------------------------------------------------------------ shapes --

NN_EDGES = []


def neural_network(rng):
    layers = [3, 5, 5, 2]
    xs = [CX - 210, CX - 70, CX + 70, CX + 210]
    nodes = []
    for x, k in zip(xs, layers):
        gap = 52
        top = CY - gap * (k - 1) / 2
        nodes.append([(x, top + gap * i) for i in range(k)])
    node_segs = [s for layer in nodes for (x, y) in layer for s in circle_segs(x, y, 13, 14)]
    edge_segs = []
    for a, b in zip(nodes, nodes[1:]):
        for p in a:
            for q in b:
                # stop the edge at the node border
                d = math.hypot(q[0] - p[0], q[1] - p[1])
                ux, uy = (q[0] - p[0]) / d, (q[1] - p[1]) / d
                edge_segs.append(((p[0] + ux * 17, p[1] + uy * 17), (q[0] - ux * 17, q[1] - uy * 17)))
    NN_EDGES[:] = edge_segs
    return sample_segments(node_segs, 300, rng, 1.5) + sample_segments(edge_segs, N - 300, rng, 0)


def processor(rng):
    s = 190
    x, y = CX - s / 2, CY - s / 2
    body = rect_segs(x, y, s, s)
    core = rect_segs(CX - 48, CY - 48, 96, 96)
    pins = []
    for i in range(6):
        t = x + 25 + i * (s - 50) / 5
        pins += [((t, y - 34), (t, y - 4)), ((t, y + s + 4), (t, y + s + 34))]
        v = y + 25 + i * (s - 50) / 5
        pins += [((x - 34, v), (x - 4, v)), ((x + s + 4, v), (x + s + 34, v))]
    # a small "AI" inside the core
    ai = [((CX - 28, CY + 22), (CX - 14, CY - 22)), ((CX - 14, CY - 22), (CX, CY + 22)),
          ((CX - 22, CY + 6), (CX - 6, CY + 6)), ((CX + 20, CY - 22), (CX + 20, CY + 22))]
    return (sample_segments(body, 170, rng, 3) + sample_segments(core, 100, rng, 2)
            + sample_segments(pins, 170, rng, 2) + sample_segments(ai, N - 440, rng, 3))


def source_code(rng):
    h = 210
    t, b = CY - h / 2, CY + h / 2
    segs = [((CX - 120, t + 25), (CX - 230, CY)), ((CX - 230, CY), (CX - 120, b - 25)),   # <
            ((CX + 45, t), (CX - 45, b)),                                                 # /
            ((CX + 120, t + 25), (CX + 230, CY)), ((CX + 230, CY), (CX + 120, b - 25))]  # >
    return sample_segments(segs, N, rng, 16)


def scatter(rng):
    return [(rng.uniform(60, W - 60), rng.uniform(70, H - 40)) for _ in range(N)]


def by_angle(pts):
    return sorted(pts, key=lambda p: (math.atan2(p[1] - CY, p[0] - CX), math.hypot(p[0] - CX, p[1] - CY)))


# --------------------------------------------------------------------- svg --

def render(theme: str) -> str:
    rng = random.Random(SEED)
    c = THEMES[theme]
    shapes = [by_angle(f(rng)) for f in (neural_network, processor, source_code)]
    # Every particle visits shape 0 -> 1 -> 2 -> 0, holding each one for a while.
    key_times = "0;0.24;0.33;0.57;0.66;0.9;1"
    order = [0, 0, 1, 1, 2, 2, 0]
    spline = ";".join(["0 0 1 1", "0.65 0 0.35 1"] * 3)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="JetBrains Mono, Fira Code, Consolas, monospace">',
           f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="14" fill="{c["bg"]}" stroke="{c["border"]}"/>',
           f'<path d="M1 15a14 14 0 0 1 14-14h{W - 30}a14 14 0 0 1 14 14v29H1z" fill="{c["panel"]}"/>',
           f'<line x1="1" y1="44" x2="{W - 1}" y2="44" stroke="{c["border"]}"/>']
    for i, col in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        out.append(f'<circle cx="{26 + i * 22}" cy="23" r="6.5" fill="{col}"/>')
    out.append(f'<text x="{W / 2}" y="28" text-anchor="middle" font-size="14" fill="{c["muted"]}">'
               f'emilio@loja: ~/profile</text>')

    # faint connections, only visible while the network is on screen
    out.append(f'<g stroke="{c["particles"][0]}" stroke-width="1" opacity="0.18">'
               f'<animate attributeName="opacity" values="0.18;0.18;0;0;0.18;0.18" '
               f'keyTimes="0;0.25;0.28;0.9;0.93;1" dur="{DUR}s" repeatCount="indefinite"/>')
    for (x1, y1), (x2, y2) in NN_EDGES:
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    out.append('</g>')

    out.append('<g>')
    for i in range(N):
        pts = [shapes[k][i] for k in order]
        col = c["particles"][i % len(c["particles"])]
        r = 1.5 + (i % 3) * 0.45
        xs = ";".join(f"{p[0]:.1f}" for p in pts)
        ys = ";".join(f"{p[1]:.1f}" for p in pts)
        begin = f"{-(i % 7) * 0.012:.3f}s"
        anim = (f'dur="{DUR}s" begin="{begin}" repeatCount="indefinite" calcMode="spline" '
                f'keyTimes="{key_times}" keySplines="{spline}"')
        out.append(f'<circle cx="{pts[0][0]:.1f}" cy="{pts[0][1]:.1f}" r="{r:.2f}" fill="{col}">'
                   f'<animate attributeName="cx" values="{xs}" {anim}/>'
                   f'<animate attributeName="cy" values="{ys}" {anim}/></circle>')
    out.append('</g>')

    # prompt line with the current shape name, in sync with the particles
    y = H - 26
    out.append(f'<text x="34" y="{y}" font-size="15" fill="{c["particles"][0]}">$</text>')
    out.append(f'<text x="54" y="{y}" font-size="15" fill="{c["text"]}">./profile.sh --live</text>')
    # (opacity values, keyTimes) so each label shows while its shape is on screen
    timing = [("1;1;0;0;1;1", "0;0.28;0.29;0.94;0.95;1"),
              ("0;0;1;1;0;0", "0;0.31;0.32;0.6;0.61;1"),
              ("0;0;1;1;0;0", "0;0.64;0.65;0.89;0.9;1")]
    for label, (vals, kt) in zip(LABELS, timing):
        out.append(f'<text x="{W - 34}" y="{y}" text-anchor="end" font-size="15" fill="{c["muted"]}" '
                   f'opacity="{vals[0]}">rendering {label}...<animate attributeName="opacity" values="{vals}" '
                   f'keyTimes="{kt}" dur="{DUR}s" repeatCount="indefinite"/></text>')
    out.append(f'<rect x="232" y="{y - 13}" width="9" height="16" fill="{c["particles"][0]}">'
               f'<animate attributeName="opacity" values="1;0;1" dur="1.1s" repeatCount="indefinite"/></rect>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        path = out / f"banner-{theme}.svg"
        path.write_text(render(theme), encoding="utf-8")
        print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
