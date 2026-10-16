"""Drift-guards for the art library (static/art/): future island themes and
collectible plants that the live app does not load yet.

Pins the catalogue (five island themes, twenty plants, four per theme),
key uniqueness against the live plant set, token-only colour (no hex in the
SVG; hex in library.css only inside custom-property declarations), that
every class the art uses has a stylesheet rule, and that each theme defines
every scenery token it paints in both light and dark.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"
ART = STATIC / "art"
SVG_NS = "{http://www.w3.org/2000/svg}"

ISLAND_KEYS = ["dune", "frost", "lagoon", "maple", "blossom"]


def _library() -> ET.Element:
    return ET.parse(ART / "library.svg").getroot()


def _group(root: ET.Element, group_id: str) -> ET.Element:
    found = root.find(f".//{SVG_NS}g[@id='{group_id}']")
    assert found is not None, f"library.svg must contain <g id={group_id!r}>"
    return found


def _islands() -> list[ET.Element]:
    return list(_group(_library(), "island-theme-defs"))


def _plants() -> list[ET.Element]:
    return list(_group(_library(), "plant-library-defs"))


def _classes(element: ET.Element) -> set[str]:
    return {
        cls
        for node in element.iter()
        for cls in (node.get("class") or "").split()
    }


def _library_css() -> str:
    return (ART / "library.css").read_text(encoding="utf-8")


def _css_blocks(css: str) -> list[tuple[str, str]]:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css)]


def test_library_ships_five_themed_islands_in_order() -> None:
    islands = _islands()
    assert [i.get("data-island-key") for i in islands] == ISLAND_KEYS
    for island in islands:
        key = island.get("data-island-key")
        assert island.get("data-island-theme") == key
        assert island.get("data-island-name"), f"{key} needs a display name"
        # Same backdrop layers as the live island so themes swap in place.
        assert {"island-sky", "island-sea", "island-sand", "island-ground"} <= _classes(island), key


def test_library_ships_twenty_unique_plants_four_per_theme() -> None:
    plants = _plants()
    keys = [p.get("data-plant-key") for p in plants]
    assert len(keys) == 20 and len(set(keys)) == 20
    themes = [p.get("data-plant-theme") for p in plants]
    assert {t: themes.count(t) for t in ISLAND_KEYS} == {t: 4 for t in ISLAND_KEYS}
    live = set(re.findall(r'data-plant-key="([^"]+)"', (STATIC / "index.html").read_text(encoding="utf-8")))
    assert len(live) == 16
    assert not live & set(keys), "library plant keys must not collide with live plants"


def test_library_svg_is_token_only() -> None:
    svg = (ART / "library.svg").read_text(encoding="utf-8")
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", svg) is None
    assert re.search(r"\b(fill|stroke)=", svg) is None, "colour comes from CSS classes only"


def test_every_library_class_has_a_stylesheet_rule() -> None:
    css = (STATIC / "style.css").read_text(encoding="utf-8") + _library_css()
    # Drawn shapes only: <g> wrappers such as .island-stars carry no paint.
    used = {
        cls
        for node in _library().iter()
        if node.tag != f"{SVG_NS}g"
        for cls in (node.get("class") or "").split()
    }
    missing = sorted(cls for cls in used if re.search(rf"\.{re.escape(cls)}(?![\w-])", css) is None)
    assert missing == []


def test_library_css_keeps_hex_inside_token_declarations() -> None:
    for selector, body in _css_blocks(_library_css()):
        for decl in body.split(";"):
            if re.search(r"#[0-9a-fA-F]{3,8}\b", decl):
                assert re.match(r"\s*--[\w-]+\s*:", decl), f"raw hex outside a token in {selector}: {decl.strip()}"


def test_each_theme_defines_its_scenery_tokens_in_light_and_dark() -> None:
    blocks = dict(_css_blocks(_library_css()))
    for island in _islands():
        key = island.get("data-island-key")
        light = blocks.get(f'[data-island-theme="{key}"]')
        dark = blocks.get(f'[data-theme="dark"] [data-island-theme="{key}"]')
        assert light is not None and dark is not None, f"{key} needs light + dark token blocks"
        light_tokens = set(re.findall(r"(--[\w-]+)\s*:", light))
        dark_tokens = set(re.findall(r"(--[\w-]+)\s*:", dark))
        assert light_tokens == dark_tokens, key
        needed = {f"--{cls}" for cls in _classes(island) if cls.startswith("isl-")}
        assert needed <= light_tokens, f"{key} paints undefined tokens: {sorted(needed - light_tokens)}"


def test_gallery_previews_the_library() -> None:
    html = (ART / "gallery.html").read_text(encoding="utf-8")
    assert "/static/art/library.svg" in html
    assert "/static/art/library.css" in html
    assert "/static/style.css" in html
