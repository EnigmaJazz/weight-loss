#!/usr/bin/env python3
"""Generate PWA icons for the Weight Loss Tracker (pure stdlib, no deps).

Draws a friendly cartoon fox face on the app's green background (r2-completion
S1 cartoon rework): a ROUND head with bulging orange cheeks, a wide white
muzzle reaching the chin, and an expressive face — low eyes with white
catchlights, a dark nose, and a small mouth on the muzzle. Ears keep the
coherent tall-triangle language with dark inner shading and white tufts.
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
    """Return raw RGBA pixels for the cartoon-fox icon at `size` square.

    Geometry lives in 512-space and scales with ``size / 512.0``, so the
    same face renders identically at 192 and 512 (pinned by
    tests/test_icons.py's cartoon-fox geometry probes). Palette constants
    above are unchanged from the geometric fox.
    """
    px = bytearray()
    s = size / 512.0

    # Ears: tall triangles (coherent ear language kept from the geometric fox)
    # with a flat base that sits inside the round head's silhouette.
    left_ear = [(140 * s, 30 * s), (172 * s, 170 * s), (252 * s, 170 * s)]
    right_ear = [(372 * s, 30 * s), (340 * s, 170 * s), (260 * s, 170 * s)]
    left_ear_tip = [(150 * s, 50 * s), (142 * s, 98 * s), (196 * s, 84 * s)]
    right_ear_tip = [(362 * s, 50 * s), (370 * s, 98 * s), (316 * s, 84 * s)]
    # Dark inner ear: smaller triangle inside each ear.
    left_inner = [(200 * s, 160 * s), (168 * s, 104 * s), (214 * s, 124 * s)]
    right_inner = [(312 * s, 160 * s), (344 * s, 104 * s), (298 * s, 124 * s)]
    # White ear tuft: a small light triangle at the base of each inner ear.
    left_tuft = [(196 * s, 158 * s), (180 * s, 130 * s), (214 * s, 140 * s)]
    right_tuft = [(316 * s, 158 * s), (332 * s, 130 * s), (298 * s, 140 * s)]
    # Round cartoon head: a big ellipse plus two bulging cheek circles — the
    # cheeks push the silhouette out past the old triangle's taper.
    head_cx, head_cy, head_rx, head_ry = (256 * s, 310 * s, 140 * s, 150 * s)
    cheek_l = (160 * s, 320 * s, 72 * s)
    cheek_r = (352 * s, 320 * s, 72 * s)
    # Expressive white muzzle: a wide rounded ellipse reaching the chin.
    muzzle = (256 * s, 385 * s, 95 * s, 78 * s)
    # Eyes sit low on the face, each with a small white catchlight.
    eye_l = (205 * s, 295 * s, 14 * s)
    eye_r = (307 * s, 295 * s, 14 * s)
    gleam_l = (201 * s, 291 * s, 5 * s)
    gleam_r = (303 * s, 291 * s, 5 * s)
    # Nose + small mouth on the muzzle.
    nose = (256 * s, 420 * s, 16 * s, 11 * s)
    mouth = (256 * s, 456 * s, 13 * s, 5 * s)

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
            if in_ellipse(x, y, head_cx, head_cy, head_rx, head_ry):
                color = FOX
            if in_circle(x, y, cheek_l[0], cheek_l[1], cheek_l[2]):
                color = FOX
            if in_circle(x, y, cheek_r[0], cheek_r[1], cheek_r[2]):
                color = FOX
            if in_ellipse(x, y, muzzle[0], muzzle[1], muzzle[2], muzzle[3]):
                color = WHITE
            if in_ellipse(x, y, mouth[0], mouth[1], mouth[2], mouth[3]):
                color = NOSE
            if in_circle(x, y, eye_l[0], eye_l[1], eye_l[2]):
                color = NOSE
            if in_circle(x, y, eye_r[0], eye_r[1], eye_r[2]):
                color = NOSE
            if in_circle(x, y, gleam_l[0], gleam_l[1], gleam_l[2]):
                color = WHITE
            if in_circle(x, y, gleam_r[0], gleam_r[1], gleam_r[2]):
                color = WHITE
            if in_ellipse(x, y, nose[0], nose[1], nose[2], nose[3]):
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
