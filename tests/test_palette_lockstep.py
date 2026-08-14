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
NON_DEFAULT_ACCENTS = ("purple", "teal", "blue", "orange")
HEX_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b")


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


def test_non_default_accent_tokens_ship_in_light_and_dark_contexts() -> None:
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    for accent in NON_DEFAULT_ACCENTS:
        light = re.search(
            rf'\[data-accent="{accent}"\]\s*\{{([^}}]*)\}}', css
        )
        assert light is not None, f"missing light token block for {accent}"
        assert re.search(r"--accent\s*:", light.group(1))
        assert re.search(r"--accent-dark\s*:", light.group(1))

        dark = re.search(
            rf'\[data-theme="dark"\]\[data-accent="{accent}"\]\s*\{{([^}}]*)\}}',
            css,
        )
        assert dark is not None, f"missing dark token block for {accent}"
        assert re.search(r"--accent-dark\s*:", dark.group(1))


def test_green_uses_default_palette_without_an_override_block() -> None:
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert '[data-accent="green"]' not in css


def test_component_files_do_not_carry_hex_colour_literals() -> None:
    for relative in ("static/index.html", "static/app.js", "static/format.js"):
        body = (ROOT / relative).read_text(encoding="utf-8")
        if relative == "static/index.html":
            # The pinned PWA theme-color and legacy inline fox mascot predate
            # accent selection and are separately gate-locked brand assets.
            body = body.replace(f'content="{EXPECTED_ACCENT}"', 'content="brand-accent"')
            body = re.sub(
                r'<span class="mascot"[^>]*>.*?</span>',
                '<span class="mascot"></span>',
                body,
                flags=re.DOTALL,
            )
        assert HEX_LITERAL.search(body) is None, f"hex literal escaped into {relative}"
