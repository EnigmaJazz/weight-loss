"""Smoke tests for the PWA icon generator (static/icons/make_icons.py).

The generator is a standalone stdlib CLI; these tests pin that it produces
valid PNGs with the expected dimensions and an opaque alpha channel, so a
future edit cannot silently break the installable PWA icons.
"""

import importlib.util
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


def test_regenerated_icons_match_committed_artifacts(make_icons: ModuleType) -> None:
    # A committed icon must decode to the exact same content as what the
    # generator produces today (deterministic output, no timestamps), so the
    # installable PWA assets and the generator cannot drift apart.
    #
    # Compare the decompressed pixel payload, not the compressed file bytes:
    # different zlib implementations (e.g. zlib-ng vs stock zlib) can emit
    # different compressed streams for identical raw pixels, which would
    # otherwise make this test flaky across environments.
    for size in (192, 512):
        import io

        buf = io.BytesIO()
        make_icons.write_png(
            Path("/tmp") / f"icon-{size}.png", size, make_icons.render(size)
        )
        generated = Path("/tmp") / f"icon-{size}.png"
        make_icons.write_png(generated, size, make_icons.render(size))
        committed = ICON_DIR / f"icon-{size}.png"
        assert _decode_png(generated) == _decode_png(committed)

# ---- fox redraw pins (r2a-island-polish Unit 1, R-R2A-1/R-R2A-9) ----------
# Deterministic probes at both sizes pin the reference-style fox: oversized
# pointed ears, dark inner-ear shading, orange fur with a warm-brown contour,
# cream muzzle/chin, dark expressive eyes with cream gleams, nose and smile.
# Palette constants mirror make_icons.py (which mirrors the CSS fox tokens);
# the previous cartoon fox fails every probe (verified in the RED pass), so a
# regression cannot pass silently.

_FOX = (244, 124, 44)       # #f47c2c reference orange (--fox)
_FOX_DARK = (216, 102, 44)  # #d8662c inner-ear orange (--fox-dark)
_OUTLINE = (120, 55, 31)    # #78371f warm-brown contour (--fox-outline)
_CREAM = (255, 240, 207)    # #fff0cf cream muzzle / gleams (--island-fox-face)
_EYE = (58, 34, 20)         # #3a2214 dark eyes / nose (--island-fox-eye)
_BG = (47, 125, 84)         # #2f7d54 brand green (palette lockstep)

# 512-space probes -> (nx, ny, expected color), scaled by size/512. All points
# sit well inside their feature (interior probes, not boundary pixels), except
# the head-edge contour probe which pins the warm-brown outline itself.
_CARTOON_FOX_PROBES = [
    # oversized ears: orange fur + dark inner-ear shading
    (142, 60, _FOX), (184, 125, _FOX_DARK), (328, 125, _FOX_DARK),
    # face: orange fur; warm-brown contour at the right cheek's edge
    (256, 220, _FOX), (396, 300, _FOX), (427, 315, _OUTLINE),
    # cream muzzle/chin below the smile; eyes + cream gleams above the muzzle
    (256, 464, _CREAM), (200, 292, _EYE), (196, 285, _CREAM),
    # nose on the cream + the smile arc (outline-brown)
    (256, 415, _EYE), (256, 461, _OUTLINE),
    # brand green background untouched beside the fox
    (60, 300, _BG),
]


@pytest.mark.parametrize("size", (192, 512))
def test_cartoon_fox_face_geometry(make_icons: ModuleType, size: int) -> None:
    rgba = make_icons.render(size)
    s = size / 512.0
    for nx, ny, expected in _CARTOON_FOX_PROBES:
        i = (int(ny * s) * size + int(nx * s)) * 4
        assert (rgba[i], rgba[i + 1], rgba[i + 2]) == expected
