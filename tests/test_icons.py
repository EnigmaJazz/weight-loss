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
