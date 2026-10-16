#!/usr/bin/env python3
"""Generate PWA icons for the Weight Loss Tracker (pure stdlib, no deps).

Draws the island fox mascot on the app's green background by parsing the
shared <symbol id="island-fox-symbol"> straight out of static/index.html, so
the icon can never drift from the in-app fox: there is no second copy of
the geometry here. Each <path>/<ellipse>/<circle> is filled (or, for the
mouth, stroked) with the colour mapped from its CSS class, in document
order, on a supersampled canvas that is box-filtered down for smooth
anti-aliased edges. Writes a PNG with the stdlib zlib+struct writer.

Supported path commands are the absolute M, L, H, V, C, Q and Z the symbol
uses; anything else raises ValueError instead of rendering silently wrong.

Usage: python3 make_icons.py [output_dir]
"""

import functools
import logging
import math
import re
import struct
import sys
import zlib
from pathlib import Path

log = logging.getLogger("make_icons")

INDEX_HTML = Path(__file__).resolve().parents[1] / "index.html"
SYMBOL_ID = "island-fox-symbol"

# Fox palette (mirrors the light-theme CSS tokens; the background stays the
# brand accent #2f7d54 so the palette lockstep test keeps all four locations
# in agreement).
BG = (47, 125, 84)              # #2f7d54 brand green (palette lockstep)
FOX = (244, 124, 44)            # #f47c2c fur (--fox)
FOX_DARK = (216, 102, 44)       # #d8662c fur shade (--fox-dark)
OUTLINE = (120, 55, 31)         # #78371f mouth line (--fox-outline)
CREAM = (255, 240, 207)         # #fff0cf cheeks / chin (--island-fox-face)
CREAM_SHADE = (243, 217, 168)   # #f3d9a8 chin shade (--island-fox-face-shade)
EYE_WHITE = (255, 255, 255)     # #ffffff eye whites (--island-fox-eye-white)
EYE = (58, 34, 20)              # #3a2214 pupils / nose (--island-fox-eye)

CLASS_FILL: dict[str, tuple[int, int, int]] = {
    "island-fox-fur": FOX,
    "island-fox-shade": FOX_DARK,
    "island-fox-face": CREAM,
    "island-fox-face-shade": CREAM_SHADE,
    "island-fox-eye-white": EYE_WHITE,
    "island-fox-eye": EYE,
}
# Stroked classes: colour and stroke-width in 64-space (style.css).
CLASS_STROKE: dict[str, tuple[tuple[int, int, int], float]] = {
    "island-fox-mouth": (OUTLINE, 1.4),
}

VIEWBOX = 64.0
# The head's 64-space bbox is centred on x=32 but sits on y≈31; nudge it
# down one unit so the icon's vertical centre matches the canvas centre.
OFFSET_Y = 1.0
SUPERSAMPLE = 3
CURVE_STEPS = 16
ELLIPSE_STEPS = 48

Point = tuple[float, float]
Color = tuple[int, int, int]

_ELEMENT_RE = re.compile(r"<(path|ellipse|circle)\b([^>]*?)/>")
_ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
_PATH_TOKEN_RE = re.compile(r"[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?")


def load_symbol(html: str, symbol_id: str = SYMBOL_ID) -> str:
    """Return the inner markup of ``<symbol id=symbol_id>`` in ``html``."""
    match = re.search(
        rf'<symbol id="{re.escape(symbol_id)}"[^>]*>(.*?)</symbol>', html, re.S
    )
    if match is None:
        raise ValueError(f"symbol {symbol_id!r} not found")
    return match.group(1)


def _cubic(p0: Point, c1: Point, c2: Point, p1: Point) -> list[Point]:
    pts: list[Point] = []
    for i in range(1, CURVE_STEPS + 1):
        t = i / CURVE_STEPS
        mt = 1.0 - t
        pts.append(
            (
                mt**3 * p0[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * p1[0],
                mt**3 * p0[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * p1[1],
            )
        )
    return pts


def _quad(p0: Point, c: Point, p1: Point) -> list[Point]:
    pts: list[Point] = []
    for i in range(1, CURVE_STEPS + 1):
        t = i / CURVE_STEPS
        mt = 1.0 - t
        pts.append(
            (
                mt**2 * p0[0] + 2 * mt * t * c[0] + t**2 * p1[0],
                mt**2 * p0[1] + 2 * mt * t * c[1] + t**2 * p1[1],
            )
        )
    return pts


def parse_path(d: str) -> list[list[Point]]:
    """Flatten absolute path data into polylines, one per subpath."""
    tokens = _PATH_TOKEN_RE.findall(d)
    subpaths: list[list[Point]] = []
    current: list[Point] = []
    pos: Point = (0.0, 0.0)
    cmd = ""
    i = 0

    def nums(count: int) -> list[float]:
        nonlocal i
        values = [float(tok) for tok in tokens[i : i + count]]
        if len(values) != count:
            raise ValueError(f"truncated path data: {d!r}")
        i += count
        return values

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd == "Z":
                if current:
                    subpaths.append(current)
                current = []
                continue
        if cmd == "M":
            if current:
                subpaths.append(current)
            x, y = nums(2)
            pos = (x, y)
            current = [pos]
            cmd = "L"  # implicit lineto for further coordinate pairs
        elif cmd == "L":
            x, y = nums(2)
            pos = (x, y)
            current.append(pos)
        elif cmd == "H":
            (x,) = nums(1)
            pos = (x, pos[1])
            current.append(pos)
        elif cmd == "V":
            (y,) = nums(1)
            pos = (pos[0], y)
            current.append(pos)
        elif cmd == "C":
            x1, y1, x2, y2, x, y = nums(6)
            current.extend(_cubic(pos, (x1, y1), (x2, y2), (x, y)))
            pos = (x, y)
        elif cmd == "Q":
            x1, y1, x, y = nums(4)
            current.extend(_quad(pos, (x1, y1), (x, y)))
            pos = (x, y)
        else:
            raise ValueError(f"unsupported path command {cmd!r} in {d!r}")
    if current:
        subpaths.append(current)
    return subpaths


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> list[Point]:
    return [
        (cx + rx * math.cos(2 * math.pi * k / ELLIPSE_STEPS),
         cy + ry * math.sin(2 * math.pi * k / ELLIPSE_STEPS))
        for k in range(ELLIPSE_STEPS)
    ]


def parse_shapes(symbol: str) -> list[tuple[str, list[list[Point]]]]:
    """Return ``(css_class, polylines)`` for every shape, in paint order."""
    shapes: list[tuple[str, list[list[Point]]]] = []
    for tag, raw_attrs in _ELEMENT_RE.findall(symbol):
        attrs = dict(_ATTR_RE.findall(raw_attrs))
        cls = attrs.get("class", "")
        if tag == "path":
            polylines = parse_path(attrs["d"])
        elif tag == "ellipse":
            polylines = [_ellipse(float(attrs["cx"]), float(attrs["cy"]),
                                  float(attrs["rx"]), float(attrs["ry"]))]
        else:
            r = float(attrs["r"])
            polylines = [_ellipse(float(attrs["cx"]), float(attrs["cy"]), r, r)]
        shapes.append((cls, polylines))
    return shapes


def _fill(buf: bytearray, n: int, polys: list[list[Point]], index: int) -> None:
    """Even-odd scanline fill of closed polygons into the index buffer."""
    edges: list[tuple[float, float, float, float]] = []
    for poly in polys:
        for k, (x1, y1) in enumerate(poly):
            x2, y2 = poly[(k + 1) % len(poly)]
            if y1 != y2:
                edges.append((x1, y1, x2, y2))
    ys = [y for poly in polys for _, y in poly]
    row0 = max(0, int(min(ys)))
    row1 = min(n - 1, int(max(ys)) + 1)
    fill_byte = bytes((index,))
    for row in range(row0, row1 + 1):
        sy = row + 0.5
        xs = sorted(
            x1 + (sy - y1) * (x2 - x1) / (y2 - y1)
            for x1, y1, x2, y2 in edges
            if (y1 > sy) != (y2 > sy)
        )
        base = row * n
        for a, b in zip(xs[0::2], xs[1::2]):
            start = max(0, math.ceil(a - 0.5))
            stop = min(n, math.ceil(b - 0.5))
            if stop > start:
                buf[base + start : base + stop] = fill_byte * (stop - start)


def _dist_to_segment(px: float, py: float, a: Point, b: Point) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0.0:
        return math.hypot(px - a[0], py - a[1])
    t = max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / length_sq))
    return math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy))


def _stroke(buf: bytearray, n: int, polys: list[list[Point]], half: float, index: int) -> None:
    """Round-capped stroke of open polylines into the index buffer."""
    segments = [(p[k], p[k + 1]) for p in polys for k in range(len(p) - 1)]
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    x0 = max(0, int(min(xs) - half))
    x1 = min(n - 1, int(max(xs) + half) + 1)
    y0 = max(0, int(min(ys) - half))
    y1 = min(n - 1, int(max(ys) + half) + 1)
    for row in range(y0, y1 + 1):
        sy = row + 0.5
        for col in range(x0, x1 + 1):
            sx = col + 0.5
            if any(_dist_to_segment(sx, sy, a, b) <= half for a, b in segments):
                buf[row * n + col] = index


@functools.cache
def render(size: int) -> bytes:
    """Return raw RGBA pixels for the island fox icon at ``size`` square.

    The symbol lives in 64-space and scales with ``size / 64``, so the same
    face renders at 192 and 512 (pinned by tests/test_icons.py's probes).
    """
    shapes = parse_shapes(load_symbol(INDEX_HTML.read_text(encoding="utf-8")))
    n = size * SUPERSAMPLE
    unit = n / VIEWBOX

    palette: list[Color] = [BG]
    buf = bytearray(n * n)
    for cls, polylines in shapes:
        scaled = [[(x * unit, (y + OFFSET_Y) * unit) for x, y in poly] for poly in polylines]
        if cls in CLASS_STROKE:
            color, width = CLASS_STROKE[cls]
            palette.append(color)
            _stroke(buf, n, scaled, width * unit / 2, len(palette) - 1)
        elif cls in CLASS_FILL:
            palette.append(CLASS_FILL[cls])
            _fill(buf, n, scaled, len(palette) - 1)
        else:
            raise ValueError(f"no icon colour for class {cls!r}")

    # Box-filter each SUPERSAMPLE x SUPERSAMPLE block down to one pixel.
    area = SUPERSAMPLE * SUPERSAMPLE
    px = bytearray(size * size * 4)
    for y in range(size):
        rows = [buf[(y * SUPERSAMPLE + j) * n : (y * SUPERSAMPLE + j + 1) * n] for j in range(SUPERSAMPLE)]
        for x in range(size):
            r = g = b = 0
            lo = x * SUPERSAMPLE
            for row in rows:
                for idx in row[lo : lo + SUPERSAMPLE]:
                    cr, cg, cb = palette[idx]
                    r += cr
                    g += cg
                    b += cb
            o = (y * size + x) * 4
            px[o] = (r + area // 2) // area
            px[o + 1] = (g + area // 2) // area
            px[o + 2] = (b + area // 2) // area
            px[o + 3] = 255
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
