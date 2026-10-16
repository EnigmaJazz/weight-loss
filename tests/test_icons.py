"""Smoke tests for the PWA icon generator (static/icons/make_icons.py).

The generator is a standalone stdlib CLI; these tests pin that it produces
valid PNGs with the expected dimensions and an opaque alpha channel, so a
future edit cannot silently break the installable PWA icons.
"""

import importlib.util
import re
import struct
import zlib
from pathlib import Path
from types import ModuleType

import pytest

ICON_DIR = Path(__file__).resolve().parents[1] / "static" / "icons"


@pytest.fixture(scope="module")
def make_icons() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "make_icons", ICON_DIR / "make_icons.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decode_png(path: Path) -> tuple[int, bytes]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    size = struct.unpack(">I", data[16:20])[0]
    pos = 8
    idat = b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        if tag == b"IDAT":
            idat += data[pos + 8 : pos + 8 + ln]
        pos += 12 + ln
    return size, zlib.decompress(idat)


def test_render_produces_full_rgba(make_icons: ModuleType) -> None:
    for size in (192, 512):
        rgba = make_icons.render(size)
        assert len(rgba) == size * size * 4
        # Alpha channel fully opaque.
        assert all(rgba[i + 3] == 255 for i in range(0, len(rgba), 4))


def test_committed_icons_decode_to_expected_size(make_icons: ModuleType) -> None:
    for size in (192, 512):
        decoded_size, raw = _decode_png(ICON_DIR / f"icon-{size}.png")
        assert decoded_size == size
        assert len(raw) == size * (size * 4 + 1)


def test_regenerated_icons_match_committed_artifacts(
    make_icons: ModuleType, tmp_path: Path
) -> None:
    # A committed icon must decode to the exact same content as what the
    # generator produces today (deterministic output, no timestamps), so the
    # installable PWA assets and the generator cannot drift apart.
    #
    # Compare the decompressed pixel payload, not the compressed file bytes:
    # different zlib implementations (e.g. zlib-ng vs stock zlib) can emit
    # different compressed streams for identical raw pixels, which would
    # otherwise make this test flaky across environments.
    for size in (192, 512):
        generated = tmp_path / f"icon-{size}.png"
        make_icons.write_png(generated, size, make_icons.render(size))
        committed = ICON_DIR / f"icon-{size}.png"
        assert _decode_png(generated) == _decode_png(committed)

# ---- island fox pins (Duolingo-style redraw) ------------------------------
# Deterministic probes at both sizes pin the island-fox-symbol face: big
# pointed ears with darker inner fur, a brow tuft, cream cheeks/chin with a
# chin shade, large white eyes with dark pupils and gleams, a nose and a
# warm-brown smile, with no contour (flat Duolingo-style shapes). Palette
# constants mirror the CSS fox tokens; the previous outlined fox fails these
# probes, so a regression cannot pass silently.

_FOX = (244, 124, 44)          # #f47c2c fur (--fox)
_FOX_DARK = (216, 102, 44)     # #d8662c fur shade (--fox-dark)
_OUTLINE = (120, 55, 31)       # #78371f mouth line (--fox-outline)
_CREAM = (255, 240, 207)       # #fff0cf cheeks / chin (--island-fox-face)
_CREAM_SHADE = (243, 217, 168) # #f3d9a8 chin shade (--island-fox-face-shade)
_WHITE = (255, 255, 255)       # #ffffff eye whites (--island-fox-eye-white)
_EYE = (58, 34, 20)            # #3a2214 pupils / nose (--island-fox-eye)
_BG = (47, 125, 84)            # #2f7d54 brand green (palette lockstep)

# 64-space probes -> (nx, ny, expected color), scaled by size/64 with the
# renderer's vertical offset (+1 unit). Every point sits well inside its
# feature, so anti-aliased edges never touch a probe pixel.
_ISLAND_FOX_PROBES = [
    # ears: orange outer fur, darker inner fur
    (11.5, 18, _FOX), (16, 16, _FOX_DARK), (48, 16, _FOX_DARK),
    # brow tuft, forehead and cheek fur
    (32, 19.5, _FOX_DARK), (32, 26, _FOX), (14, 36, _FOX), (50, 36, _FOX),
    # eye whites, pupils and gleams
    (19.5, 30, _WHITE), (44.5, 30, _WHITE),
    (25, 35.5, _EYE), (39, 35.5, _EYE),
    (26.19, 32.06, _WHITE), (40.27, 32.06, _WHITE),
    # nose, mouth stem, cream chin and its shade
    (32, 42, _EYE), (32, 45.6, _OUTLINE), (32, 50, _CREAM), (32, 54.5, _CREAM_SHADE),
    # brand green background around and between the ears
    (3, 3, _BG), (32, 8, _BG), (60, 60, _BG),
]


@pytest.mark.parametrize("size", (192, 512))
def test_island_fox_face_geometry(make_icons: ModuleType, size: int) -> None:
    rgba = make_icons.render(size)
    s = size / 64.0
    for nx, ny, expected in _ISLAND_FOX_PROBES:
        x = int(nx * s)
        y = int((ny + 1) * s)
        i = (y * size + x) * 4
        assert (rgba[i], rgba[i + 1], rgba[i + 2]) == expected, (nx, ny)


def test_icon_palette_matches_css_fox_tokens(make_icons: ModuleType) -> None:
    """Each fox class the icon paints must use the same light-theme colour
    the stylesheet gives that class, so the icon and the in-app fox cannot
    drift apart in colour (the geometry is already shared via index.html)."""
    css = (ICON_DIR.parent / "style.css").read_text(encoding="utf-8")
    root = re.search(r":root\s*\{(.*?)\}", css, re.S)
    assert root is not None
    tokens = dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})", root.group(1)))

    def css_rgb(cls: str, prop: str) -> tuple[int, int, int]:
        rule = re.search(rf"\.{cls}\s*\{{([^}}]*)\}}", css)
        assert rule is not None, cls
        var = re.search(rf"{prop}\s*:\s*var\((--[\w-]+)\)", rule.group(1))
        assert var is not None, (cls, prop)
        hex_value = tokens[var.group(1)]
        return tuple(int(hex_value[k : k + 2], 16) for k in (1, 3, 5))  # type: ignore[return-value]

    for cls, color in make_icons.CLASS_FILL.items():
        assert css_rgb(cls, "fill") == color, cls
    for cls, (color, _width) in make_icons.CLASS_STROKE.items():
        assert css_rgb(cls, "stroke") == color, cls


def test_icon_renders_every_shape_of_the_shared_symbol(make_icons: ModuleType) -> None:
    """The generator reads the fox from index.html; every shape class in the
    symbol must have an icon colour (render raises otherwise)."""
    html = (ICON_DIR.parent / "index.html").read_text(encoding="utf-8")
    shapes = make_icons.parse_shapes(make_icons.load_symbol(html))
    assert len(shapes) >= 10
    known = make_icons.CLASS_FILL.keys() | make_icons.CLASS_STROKE.keys()
    assert {cls for cls, _ in shapes} <= known
