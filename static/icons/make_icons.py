#!/usr/bin/env python3
"""Generate PWA icons for the Weight Loss Tracker (pure stdlib, no deps).

Draws the reference-style fox face on the app's green background
(r2a-island-polish Unit 1, R-R2A-1/R-R2A-9): oversized pointed ears with
dark inner shading, a broad rounded orange head, a wide cream muzzle/chin,
a warm-brown contour around the whole fox, and an expressive face — dark
eyes with cream gleams, a nose, and a simple smile. Colours mirror the CSS
fox token family (`--fox`, `--fox-dark`, `--fox-outline`,
`--island-fox-face`, `--island-fox-eye`); the brand background stays the
lockstep-pinned `#2f7d54`. Flat fills, no gradients, no shading.
Writes a PNG with the stdlib zlib+struct writer (zero-dependency approach).

Usage: python3 make_icons.py [output_dir]
"""

import logging
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


def _in_mouth(x: float, y: float, s: float) -> bool:
    """The fox's smile: a short connector under the nose plus a shallow arc
    (512-space geometry scaled by ``s``), drawn in the warm-brown outline."""
    half = max(1.0, 1.5 * s)
    if abs(x - 256 * s) <= half and 431 * s <= y <= 452 * s:
        return True
    if 228 * s - half <= x <= 284 * s + half:
        t = max(0.0, min(1.0, (x / s - 228.0) / 56.0))
        y_arc = (452.0 + 36.0 * t * (1.0 - t)) * s
        return abs(y - y_arc) <= half
    return False


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
    """Return raw RGBA pixels for the reference-style fox icon at `size` square.

    Geometry lives in 512-space and scales with ``size / 512.0``, so the
    same face renders identically at 192 and 512 (pinned by
    tests/test_icons.py's fox probes). A silhouette mask (ears + head +
    cheeks + muzzle) drives a 1px warm-brown contour around the fox.
    """
    s = size / 512.0

    # Oversized pointed ears with a flat base that sits inside the head.
    left_ear = [(120 * s, 26 * s), (170 * s, 175 * s), (262 * s, 175 * s)]
    right_ear = [(392 * s, 26 * s), (342 * s, 175 * s), (250 * s, 175 * s)]
    # Dark inner ear: smaller triangle inside each ear.
    left_inner = [(149 * s, 71 * s), (176 * s, 153 * s), (227 * s, 153 * s)]
    right_inner = [(363 * s, 71 * s), (336 * s, 153 * s), (285 * s, 153 * s)]
    # Broad rounded head: a big ellipse plus two bulging cheek circles.
    head = (256 * s, 300 * s, 150 * s, 160 * s)
    cheek_l = (165 * s, 315 * s, 80 * s)
    cheek_r = (347 * s, 315 * s, 80 * s)
    # Cream lower-face mask reaching the chin (part of the silhouette).
    muzzle = (256 * s, 388 * s, 100 * s, 84 * s)
    # Expressive eyes sit above the muzzle, each with a cream gleam.
    eye_l = (200 * s, 292 * s, 15 * s, 19 * s)
    eye_r = (312 * s, 292 * s, 15 * s, 19 * s)
    gleam_l = (196 * s, 285 * s, 5.5 * s)
    gleam_r = (308 * s, 285 * s, 5.5 * s)
    # Nose on the cream muzzle; the smile is drawn by _in_mouth.
    nose = (256 * s, 418 * s, 18 * s, 13 * s)

    # Pass 1: silhouette mask (ears + head + cheeks + muzzle).
    mask = bytearray(size * size)
    for y in range(size):
        base = y * size
        for x in range(size):
            if (
                point_in_triangle(x, y, *left_ear)
                or point_in_triangle(x, y, *right_ear)
                or in_ellipse(x, y, *head)
                or in_circle(x, y, *cheek_l)
                or in_circle(x, y, *cheek_r)
                or in_ellipse(x, y, *muzzle)
            ):
                mask[base + x] = 1

    # Pass 2: colour each pixel, features over the base fill, contour last.
    px = bytearray()
    for y in range(size):
        base = y * size
        for x in range(size):
            if not mask[base + x]:
                px += bytes(BG) + b"\xff"
                continue
            color = FOX
            if point_in_triangle(x, y, *left_inner) or point_in_triangle(x, y, *right_inner):
                color = FOX_DARK
            if in_ellipse(x, y, *muzzle):
                color = CREAM
            if in_ellipse(x, y, *eye_l) or in_ellipse(x, y, *eye_r):
                color = EYE
            if in_circle(x, y, *gleam_l) or in_circle(x, y, *gleam_r):
                color = CREAM
            if in_ellipse(x, y, *nose):
                color = EYE
            if _in_mouth(x, y, s):
                color = OUTLINE
            if _on_outline(x, y, size, mask):
                color = OUTLINE
            px += bytes(color) + b"\xff"
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
