#!/usr/bin/env python3
"""Generate PWA icons for the Weight Loss Tracker (pure stdlib, no deps).

Draws a fox face on the app's green background: tall pointed ears with dark
tips, white cheek patches, a white muzzle with a dark nose, and dark eyes.
Writes a PNG with the stdlib zlib+struct writer (zero-dependency approach).

Usage: python3 make_icons.py [output_dir]
"""

import logging
import struct
import sys
import zlib
from pathlib import Path

log = logging.getLogger("make_icons")

# App palette (matches manifest theme_color)
BG = (47, 125, 84)       # #2f7d54
FOX = (235, 137, 44)     # #eb892c vivid fox orange
FOX_DARK = (180, 92, 22)  # #b45c16 deeper orange for ear shading
WHITE = (252, 248, 240)  # #fcf8f0 muzzle / cheek / eye whites
NOSE = (38, 32, 30)      # #26201e near-black nose / eyes


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


def render(size: int) -> bytes:
    """Return raw RGBA pixels for a fox-face icon at `size` square."""
    px = bytearray()
    s = size / 512.0

    # Head: a clean triangle — top edge under the ears, sides tapering
    # directly to the pointed chin (no cheek bulge).
    head = [
        (164 * s, 140 * s),   # left top
        (348 * s, 140 * s),   # right top
        (332 * s, 300 * s),   # right mid (pulled in)
        (284 * s, 402 * s),   # lower right
        (256 * s, 424 * s),   # pointed chin
        (228 * s, 402 * s),   # lower left
        (180 * s, 300 * s),   # left mid (pulled in)
    ]
    # Ears: tall triangles with a FLAT base below the head's top edge, so the
    # base sits inside the head silhouette and there is no floating gap.
    left_ear = [(118 * s, 26 * s), (160 * s, 165 * s), (250 * s, 165 * s)]
    right_ear = [(394 * s, 26 * s), (262 * s, 165 * s), (352 * s, 165 * s)]
    left_ear_tip = [(140 * s, 58 * s), (132 * s, 108 * s), (186 * s, 94 * s)]
    right_ear_tip = [(372 * s, 58 * s), (380 * s, 108 * s), (326 * s, 94 * s)]
    # Dark inner ear: smaller triangle inside each ear.
    left_inner = [(172 * s, 132 * s), (160 * s, 86 * s), (206 * s, 106 * s)]
    right_inner = [(340 * s, 132 * s), (352 * s, 86 * s), (306 * s, 106 * s)]
    # White ear tuft: a small light triangle at the base of each inner ear.
    left_tuft = [(170 * s, 130 * s), (163 * s, 108 * s), (196 * s, 118 * s)]
    right_tuft = [(342 * s, 130 * s), (349 * s, 108 * s), (316 * s, 118 * s)]
    # White lower face: a clean triangle tapering to the pointed chin,
    # wider at the top than before.
    face = [(212 * s, 255 * s), (300 * s, 255 * s), (256 * s, 414 * s)]
    # Eyes and nose.
    eye_l = (212 * s, 196 * s)
    eye_r = (300 * s, 196 * s)
    eye_radius = 11 * s
    nose = (256 * s, 356 * s)
    nose_rx = 13 * s
    nose_ry = 9 * s

    for y in range(size):
        for x in range(size):
            color = BG
            if point_in_triangle(x, y, *left_ear):
                color = FOX
            if point_in_triangle(x, y, *right_ear):
                color = FOX
            if point_in_triangle(x, y, *left_ear_tip):
                color = FOX_DARK
            if point_in_triangle(x, y, *right_ear_tip):
                color = FOX_DARK
            if point_in_triangle(x, y, *left_inner):
                color = FOX_DARK
            if point_in_triangle(x, y, *right_inner):
                color = FOX_DARK
            if point_in_triangle(x, y, *left_tuft):
                color = WHITE
            if point_in_triangle(x, y, *right_tuft):
                color = WHITE
            if point_in_polygon(x, y, head):
                color = FOX
            if point_in_polygon(x, y, face):
                color = WHITE
            if in_circle(x, y, eye_l[0], eye_l[1], eye_radius):
                color = NOSE
            if in_circle(x, y, eye_r[0], eye_r[1], eye_radius):
                color = NOSE
            if in_ellipse(x, y, nose[0], nose[1], nose_rx, nose_ry):
                color = NOSE
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
