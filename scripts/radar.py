#!/usr/bin/env python3
"""
radar.py - Matrix / GitHub-native green radar chart generator. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

THEMES = {
    "dark": {
        "grid": "#194a26",
        "spoke": "#123019",
        "label": "#7ee787",
        "value": "#aff5b4",
        "title": "#3fb950",
        "fill": "#238636",
        "stroke": "#3fb950",
        "vertex": "#56d364",
        "bg": "none",
    },
    "light": {
        "grid": "#bbf7d0",
        "spoke": "#86efac",
        "label": "#14532d",
        "value": "#166534",
        "title": "#15803d",
        "fill": "#16a34a",
        "stroke": "#16a34a",
        "vertex": "#15803d",
        "bg": "none",
    },
}

UA = {"User-Agent": "radar-matrix.py"}
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Courier New', monospace"
LBL, VAL, TTL = 12, 10, 14


def from_json(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    axes = [(a["label"], float(a["value"])) for a in d["axes"]]
    return d.get("title", "AI ENGINEERING // RADAR"), axes


def _api(url, token):
    req = urllib.request.Request(url, headers=dict(UA))
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def from_github(user: str, token: str | None, limit: int, exclude: set[str], curve: float):
    totals: dict[str, int] = {}
    page = 1
    while True:
        repos = _api(
            f"https://api.github.com/users/{user}/repos?per_page=100&page={page}&type=owner&sort=pushed",
            token,
        )
        if not repos:
            break
        for repo in repos:
            if repo.get("fork") or repo.get("archived"):
                continue
            try:
                langs = _api(repo["languages_url"], token)
            except urllib.error.HTTPError:
                continue
            for name, count in langs.items():
                if name.lower() in exclude:
                    continue
                totals[name] = totals.get(name, 0) + count
        if len(repos) < 100:
            break
        page += 1

    if not totals:
        sys.exit(f"no language data found for '{user}'")

    top = sorted(totals.items(), key=lambda kv: -kv[1])[:limit]
    peak = top[0][1]
    axes = [(n, round(100 * (c / peak) ** curve, 1)) for n, c in top]
    return f"CODE TELEMETRY // {user.upper()}", axes


def ring(radius, n, start=-math.pi / 2):
    return [
        (radius * math.cos(start + i * 2 * math.pi / n),
         radius * math.sin(start + i * 2 * math.pi / n))
        for i in range(n)
    ]


def text_width(s, font_size):
    return len(s) * font_size * 0.62


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(title, axes, theme: str, size: int, rings: int, show_values: bool, animate: bool) -> str:
    c = THEMES[theme]
    n = len(axes)
    r = size / 2 - 8
    gap = 20

    vals = [max(0.0, min(100.0, v)) for _, v in axes]
    outer = ring(r, n)

    labels = []
    for i, (label, _) in enumerate(axes):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        cosv, sinv = math.cos(ang), math.sin(ang)
        lx, ly = (r + gap) * cosv, (r + gap) * sinv
        anchor = "middle" if abs(cosv) < 0.25 else ("start" if cosv > 0 else "end")
        dy = 4 if abs(sinv) < 0.25 else (14 if sinv > 0 else -5)
        labels.append((lx, ly + dy, anchor, label, vals[i]))

    minx, maxx, miny, maxy = -r, r, -r, r
    for lx, ly, anchor, label, v in labels:
        w = max(text_width(label, LBL),
                text_width(f"{v:g}", VAL) if show_values else 0.0)
        if anchor == "start":
            x0, x1 = lx, lx + w
        elif anchor == "end":
            x0, x1 = lx - w, lx
        else:
            x0, x1 = lx - w / 2, lx + w / 2
        y0 = ly - LBL
        y1 = ly + 4 + (VAL + 4 if show_values else 0)
        minx, maxx = min(minx, x0), max(maxx, x1)
        miny, maxy = min(miny, y0), max(maxy, y1)

    pad = 12
    title_h = TTL + 16 if title else 0
    W = round((maxx - minx) + 2 * pad)
    H = round((maxy - miny) + 2 * pad + title_h)
    ox, oy = -minx + pad, -miny + pad + title_h

    if title:
        need = round(text_width(title, TTL) + 2 * pad)
        if need > W:
            ox += (need - W) / 2
            W = need

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="{esc(title) or "radar chart"}" font-family="{FONT}">'
    ]

    parts.append("""<defs>
      <filter id="matrix-glow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="2" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>""")

    if c["bg"] != "none":
        parts.append(f'<rect width="100%" height="100%" fill="{c["bg"]}"/>')

    if title:
        parts.append(
            f'<text x="{W / 2:.1f}" y="{pad + TTL:.0f}" text-anchor="middle" '
            f'font-size="{TTL}" font-weight="700" fill="{c["title"]}" filter="url(#matrix-glow)">'
            f'{esc(title)}</text>'
        )

    parts.append(f'<g transform="translate({ox:.1f},{oy:.1f})">')

    # concentric rings
    for k in range(rings, 0, -1):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in ring(r * k / rings, n))
        parts.append(
            f'<polygon points="{d}" fill="none" stroke="{c["grid"]}" '
            f'stroke-width="1.2" opacity="{0.4 + 0.5 * k / rings:.2f}"/>'
        )

    # spokes
    for x, y in outer:
        parts.append(
            f'<line x1="0" y1="0" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="{c["spoke"]}" stroke-width="1.2" stroke-dasharray="2 3"/>'
        )

    # data shape
    shape = [(px * v / 100, py * v / 100) for (px, py), v in zip(outer, vals)]
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in shape)
    parts.append("<g>")
    if animate:
        parts.append(
            '<animateTransform attributeName="transform" type="scale" '
            'values="0.04;1" dur="1.1s" calcMode="spline" keyTimes="0;1" '
            'keySplines="0.22 1 0.36 1" fill="freeze"/>'
        )
    parts.append(
        f'<polygon points="{d}" fill="{c["fill"]}" fill-opacity="0.22" '
        f'stroke="{c["stroke"]}" stroke-width="2.2" stroke-linejoin="round" filter="url(#matrix-glow)"/>'
    )
    for x, y in shape:
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.8" fill="{c["vertex"]}" '
            f'stroke="{c["stroke"]}" stroke-width="1"/>'
        )
    parts.append("</g>")

    # axis labels
    for lx, ly, anchor, label, v in labels:
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="{LBL}" font-weight="600" fill="{c["label"]}">'
            f'{esc(label)}</text>'
        )
        if show_values:
            parts.append(
                f'<text x="{lx:.1f}" y="{ly + VAL + 4:.1f}" text-anchor="{anchor}" '
                f'font-size="{VAL}" fill="{c["value"]}">{v:g}%</text>'
            )

    parts.append("</g></svg>")
    return "".join(parts)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--data", type=Path, default=Path("assets/skills.json"))
    src.add_argument("--github", metavar="USER")
    p.add_argument("-o", "--out", type=Path, default=Path("assets/radar-skills"))
    p.add_argument("--title", help="override the chart title")
    p.add_argument("--size", type=int, default=400)
    p.add_argument("--rings", type=int, default=4)
    p.add_argument("--limit", type=int, default=6)
    p.add_argument("--exclude", default="html,css,shell,makefile,dockerfile,batchfile")
    p.add_argument("--curve", type=float, default=0.5)
    p.add_argument("--values", action="store_true", default=True)
    p.add_argument("--no-animate", dest="animate", action="store_false")
    args = p.parse_args(argv)

    if args.github:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        excl = {s.strip().lower() for s in args.exclude.split(",") if s.strip()}
        title, axes = from_github(args.github, token, args.limit, excl, args.curve)
    else:
        if not args.data.exists():
            sys.exit(f"no data file: {args.data}")
        title, axes = from_json(args.data)

    if args.title is not None:
        title = args.title

    args.out.parent.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = render(title, axes, theme, args.size, args.rings, args.values, args.animate)
        dest = args.out.with_name(f"{args.out.name}-{theme}.svg")
        dest.write_text(svg, encoding="utf-8")
        print(f"wrote {dest} ({len(axes)} axes)")


if __name__ == "__main__":
    main()
