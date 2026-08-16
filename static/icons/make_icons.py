#!/usr/bin/env python3
"""Generate PWA icons for the Weight Loss Tracker (pure stdlib, no deps).

Draws the island fox mascot — the exact <symbol id="island-fox-symbol">
geometry from static/index.html — on the app's green background. The SVG's
cubic body and muzzle paths are sampled into polygons, scaled from 64-space
onto the icon canvas, and painted with the token palette: warm fox-orange
fur, darker inner ears, a cream lower-face muzzle, dark oval eyes with cream
gleams, short curved brows, a small nose, and a smiling mouth, all wrapped
in the warm-brown contour. Flat token fills, no gradients, no shading.
Writes a PNG with the stdlib zlib+struct writer (zero-dependency approach).

Usage: python3 make_icons.py [output_dir]
"""

import logging
import math
import struct
import sys
import zlib
from pathlib import Path

log = logging.getLogger("make_icons")

# Fox palette (mirrors the CSS tokens; the background stays the brand accent
# #2f7d54 so the palette lockstep test keeps all four locations in agreement).
BG = (47, 125, 84)          # #2f7d54 brand green (palette lockstep)
FOX = (244, 124, 44)        # #f47c2c reference fox orange (--fox)
FOX_DARK = (216, 102, 44)   # #d8662c deeper inner-ear orange (--fox-dark)
OUTLINE = (120, 55, 31)     # #78371f warm-brown contour (--fox-outline)
CREAM = (255, 240, 207)     # #fff0cf cream muzzle / gleams (--island-fox-face)
EYE = (58, 34, 20)          # #3a2214 dark expressive eyes / nose (--island-fox-eye)

# --- island-fox-symbol geometry (64-space, static/index.html) ---------------
# The fox body and cream muzzle are closed cubic paths; each is sampled into
# a polygon with _closed_polygon(). The remaining features are the symbol's
# exact shapes scaled to the canvas.

# Body silhouette: left ear -> left cheek -> chin -> right cheek -> right ear
# -> crown between the ears -> back to the left ear tip.
BODY_CUBICS: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]] = [
    ((11, 4), (13, 5), (15, 9), (16, 15)),
    ((16, 15), (13, 18), (11, 25), (11, 32)),
    ((11, 32), (11, 42), (18, 52), (27, 54)),
    ((27, 54), (29, 55), (35, 55), (37, 54)),
    ((37, 54), (46, 52), (53, 42), (53, 32)),
    ((53, 32), (53, 25), (51, 18), (48, 15)),
    ((48, 15), (49, 9), (51, 5), (53, 4)),
    ((53, 4), (49, 5), (45, 9), (42, 16)),
    ((42, 16), (39, 21), (36, 23), (32, 23)),
    ((32, 23), (28, 23), (25, 21), (22, 16)),
    ((22, 16), (19, 9), (15, 5), (11, 4)),
]

# Cream lower-face mask tucked into the body (its own closed cubic path).
MUZZLE_CUBICS: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]] = [
    ((32, 38), (24, 36), (17, 39), (16, 45)),
    ((16, 45), (15, 51), (22, 54), (32, 54)),
    ((32, 54), (42, 54), (49, 51), (48, 45)),
    ((48, 45), (47, 39), (40, 36), (32, 38)),
]

# Dark inner-ear triangles (fill --fox-dark).
INNER_L = ((17, 14), (13, 7), (21, 13))
INNER_R = ((47, 14), (51, 7), (43, 13))

# Oval eyes, cream gleams, nose (fill --island-fox-eye / --island-fox-face).
EYE_L = (24.5, 34.5, 3.2, 4.0)      # (cx, cy, rx, ry)
EYE_R = (39.5, 34.5, 3.2, 4.0)
GLEAM_L = (23.4, 33.2, 1.35)        # (cx, cy, r)
GLEAM_R = (38.6, 33.2, 1.35)
NOSE = (32.0, 40.5, 2.8, 2.0)

# Brows and mouth: outline-brown strokes (stroke-width 1.4 in the symbol).
# Quadratic curves are (start, control, end); the mouth stem is a straight
# segment encoded as a degenerate quadratic.
BROW_L = ((20.5, 28.5), (24.5, 27.5), (28.5, 28.5))
BROW_R = ((35.5, 28.5), (39.5, 27.5), (43.5, 28.5))
MOUTH_STEM = ((32.0, 43.0), (32.0, 44.25), (32.0, 45.5))
MOUTH_L = ((32.0, 45.5), (28.0, 47.5), (26.0, 45.0))
MOUTH_R = ((32.0, 45.5), (36.0, 47.5), (38.0, 45.0))
STROKE_HALF = 0.7  # 64-space half-width of the symbol's 1.4-unit strokes


def point_in_triangle(
    px: float,
    py: float,
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    def sign(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> float:
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign((px, py), a, b)
    d2 = sign((px, py), b, c)
    d3 = sign((px, py), c, a)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def point_in_polygon(
    px: float, py: float, points: list[tuple[float, float]]
) -> bool:
    """Ray-casting point-in-polygon for arbitrary convex/concave polygons."""
    inside = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            x_cross = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < x_cross:
                inside = not inside
    return inside


def in_circle(
    px: float, py: float, cx: float, cy: float, r: float
) -> bool:
    return (px - cx) ** 2 + (py - cy) ** 2 <= r * r


def in_ellipse(
    px: float, py: float, cx: float, cy: float, rx: float, ry: float
) -> bool:
    return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1.0


def _cubic_points(
    p0: tuple[float, float],
    c1: tuple[float, float],
    c2: tuple[float, float],
    p1: tuple[float, float],
    steps: int,
) -> list[tuple[float, float]]:
    """Sample one cubic Bezier (64-space) into ``steps + 1`` points."""
    pts: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        pts.append(
            (
                mt**3 * p0[0] + 3.0 * mt**2 * t * c1[0] + 3.0 * mt * t**2 * c2[0] + t**3 * p1[0],
                mt**3 * p0[1] + 3.0 * mt**2 * t * c1[1] + 3.0 * mt * t**2 * c2[1] + t**3 * p1[1],
            )
        )
    return pts


def _closed_polygon(
    cubics: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]],
    steps: int,
) -> list[tuple[float, float]]:
    """Sample a closed cubic path into a polygon (shared endpoints deduped)."""
    pts: list[tuple[float, float]] = []
    for p0, c1, c2, p1 in cubics:
        pts.extend(_cubic_points(p0, c1, c2, p1, steps)[:-1])
    pts.append(pts[0])
    return pts


def _scale(
    points: list[tuple[float, float]], u: float, ox: float, oy: float
) -> list[tuple[float, float]]:
    return [(x * u + ox, y * u + oy) for x, y in points]


def _quad_points(
    p0: tuple[float, float],
    c: tuple[float, float],
    p1: tuple[float, float],
    steps: int = 8,
) -> list[tuple[float, float]]:
    """Sample one quadratic Bezier (64-space) into ``steps + 1`` points."""
    pts: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        pts.append(
            (
                mt**2 * p0[0] + 2.0 * mt * t * c[0] + t**2 * p1[0],
                mt**2 * p0[1] + 2.0 * mt * t * c[1] + t**2 * p1[1],
            )
        )
    return pts


def _dist_to_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _near_stroke(
    x: float, y: float, segments: list[tuple[float, float, float, float]], half: float
) -> bool:
    """True when (x, y) lies within ``half`` of any stroke segment."""
    for ax, ay, bx, by in segments:
        if _dist_to_segment(x, y, ax, ay, bx, by) <= half:
            return True
    return False


def _stroke_segments(
    quads: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]],
    u: float,
    ox: float,
    oy: float,
) -> list[tuple[float, float, float, float]]:
    """Sample the symbol's stroke curves into scaled line segments."""
    segments: list[tuple[float, float, float, float]] = []
    for p0, c, p1 in quads:
        pts = _scale(_quad_points(p0, c, p1), u, ox, oy)
        segments.extend(
            (pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            for i in range(len(pts) - 1)
        )
    return segments


def _on_outline(x: int, y: int, size: int, mask: bytearray) -> bool:
    """True when a fox pixel touches a non-fox pixel (warm-brown contour)."""
    for dy in (-1, 0, 1):
        ny = y + dy
        if ny < 0 or ny >= size:
            return True
        for dx in (-1, 0, 1):
            nx = x + dx
            if nx < 0 or nx >= size:
                return True
            if not mask[ny * size + nx]:
                return True
    return False


def render(size: int) -> bytes:
    """Return raw RGBA pixels for the island fox icon at `size` square.

    The symbol geometry lives in 64-space and scales with ``size / 64.0``,
    so the same face renders identically at 192 and 512 (pinned by
    tests/test_icons.py's fox probes). A silhouette mask (the sampled body
    polygon) drives a 1px warm-brown contour around the fox.
    """
    u = size / 64.0
    # The fox's 64-space bbox is x 11..53 (centred) and y 4..55; nudge it
    # down so the icon's vertical centre matches the canvas centre.
    ox = 0.0
    oy = 2.5 * u

    body = _scale(_closed_polygon(BODY_CUBICS, 24), u, ox, oy)
    muzzle = _scale(_closed_polygon(MUZZLE_CUBICS, 24), u, ox, oy)

    inner_l = _scale(list(INNER_L), u, ox, oy)
    inner_r = _scale(list(INNER_R), u, ox, oy)

    eye_l = (EYE_L[0] * u + ox, EYE_L[1] * u + oy, EYE_L[2] * u, EYE_L[3] * u)
    eye_r = (EYE_R[0] * u + ox, EYE_R[1] * u + oy, EYE_R[2] * u, EYE_R[3] * u)
    gleam_l = (GLEAM_L[0] * u + ox, GLEAM_L[1] * u + oy, GLEAM_L[2] * u)
    gleam_r = (GLEAM_R[0] * u + ox, GLEAM_R[1] * u + oy, GLEAM_R[2] * u)
    nose = (NOSE[0] * u + ox, NOSE[1] * u + oy, NOSE[2] * u, NOSE[3] * u)

    strokes = _stroke_segments([BROW_L, BROW_R, MOUTH_STEM, MOUTH_L, MOUTH_R], u, ox, oy)
    half_stroke = STROKE_HALF * u

    # Bounding box of the body polygon: everything outside is brand green.
    xs = [p[0] for p in body]
    ys = [p[1] for p in body]
    bx0 = max(0, int(min(xs)))
    bx1 = min(size - 1, int(max(xs)))
    by0 = max(0, int(min(ys)))
    by1 = min(size - 1, int(max(ys)))

    # Pass 1: silhouette mask (the fox body polygon).
    mask = bytearray(size * size)
    for y in range(by0, by1 + 1):
        base = y * size
        for x in range(bx0, bx1 + 1):
            if point_in_polygon(x, y, body):
                mask[base + x] = 1

    # Pass 2: colour each pixel, features over the base fill, contour last.
    bg_pixel = bytes(BG) + b"\xff"
    px = bytearray(bg_pixel * size * size)
    for y in range(by0, by1 + 1):
        base = y * size
        for x in range(bx0, bx1 + 1):
            idx = base + x
            if not mask[idx]:
                continue
            color = FOX
            if point_in_triangle(x, y, *inner_l) or point_in_triangle(x, y, *inner_r):
                color = FOX_DARK
            if point_in_polygon(x, y, muzzle):
                color = CREAM
            if in_ellipse(x, y, *eye_l) or in_ellipse(x, y, *eye_r):
                color = EYE
            if in_circle(x, y, *gleam_l) or in_circle(x, y, *gleam_r):
                color = CREAM
            if in_ellipse(x, y, *nose):
                color = EYE
            if _near_stroke(x, y, strokes, half_stroke):
                color = OUTLINE
            if _on_outline(x, y, size, mask):
                color = OUTLINE
            o = idx * 4
            px[o] = color[0]
            px[o + 1] = color[1]
            px[o + 2] = color[2]
    return bytes(px)


def write_png(path: Path, size: int, rgba: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return (
            struct.pack(">I", len(data))
            + c
            + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        )

    raw = b"".join(
        b"\x00" + rgba[y * size * 4 : (y + 1) * size * 4] for y in range(size)
    )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("static/icons")
    out.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        write_png(out / f"icon-{size}.png", size, render(size))
        log.info("wrote %s (%sx%s)", out / f"icon-{size}.png", size, size)


if __name__ == "__main__":
    main()
