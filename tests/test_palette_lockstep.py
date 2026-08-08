"""Drift-guard: the brand accent #2f7d54 must stay identical across the four
places that carry it.

- static/style.css :root --accent
- static/index.html <meta name="theme-color">
- static/manifest.webmanifest theme_color
- static/icons/make_icons.py BG literal

This is a guard, not a behavior change: it asserts the current invariant and
fails loudly the day any single location drifts (a common source of
PWA-tab/icon/theme mismatch bugs).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_ACCENT = "#2f7d54"


def _normalize(hex_color: str) -> str:
    """Canonical lowercase #rrggbb so #2F7D54 and #2f7d54 compare equal."""
    return hex_color.lower()


def _accent_from_css() -> str:
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    match = re.search(r"--accent\s*:\s*(#[0-9a-fA-F]{6})", css)
    assert match is not None, "style.css :root must declare --accent"
    return _normalize(match.group(1))


def _accent_from_html() -> str:
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    match = re.search(r'name="theme-color"\s+content="(#[0-9a-fA-F]{6})"', html)
    assert match is not None, "index.html must carry a theme-color meta tag"
    return _normalize(match.group(1))


def _accent_from_manifest() -> str:
    manifest = (ROOT / "static" / "manifest.webmanifest").read_text(encoding="utf-8")
    match = re.search(r'"theme_color"\s*:\s*"(#[0-9a-fA-F]{6})"', manifest)
    assert match is not None, "manifest.webmanifest must declare theme_color"
    return _normalize(match.group(1))


def _accent_from_icon_script() -> str:
    script = (ROOT / "static" / "icons" / "make_icons.py").read_text(encoding="utf-8")
    match = re.search(r"BG\s*=\s*\((\d+),\s*(\d+),\s*(\d+)\)", script)
    assert match is not None, "make_icons.py must define BG as an RGB tuple"
    r, g, b = (int(part) for part in match.groups())
    return _normalize(f"#{r:02x}{g:02x}{b:02x}")


def test_four_accent_locations_each_equal_brand_accent() -> None:
    """Every location individually must carry the exact #2f7d54 brand accent."""
    assert _accent_from_css() == EXPECTED_ACCENT
    assert _accent_from_html() == EXPECTED_ACCENT
    assert _accent_from_manifest() == EXPECTED_ACCENT
    assert _accent_from_icon_script() == EXPECTED_ACCENT


def test_four_accent_locations_are_lockstep() -> None:
    """The four locations must agree with each other (no cross-file drift)."""
    accents = {
        _accent_from_css(),
        _accent_from_html(),
        _accent_from_manifest(),
        _accent_from_icon_script(),
    }
    assert accents == {EXPECTED_ACCENT}
