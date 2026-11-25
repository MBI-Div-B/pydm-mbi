"""Stylesheets generated from the design tokens."""

from pathlib import Path
from string import Template

from . import tokens

STYLE_DIR = Path(__file__).resolve().parent
TEMPLATE = STYLE_DIR / "mbi.qss.in"
OUTPUTS = {"dark": STYLE_DIR / "mbi.qss", "light": STYLE_DIR / "mbi-light.qss"}
DEFAULT_THEME = "dark"


def render(theme):
    """The stylesheet of a theme as a string."""
    values = {
        "theme": theme,
        "font_family": tokens.FONT_FAMILY,
        "weight_text": tokens.WEIGHT_TEXT,
        "weight_heading": tokens.WEIGHT_HEADING,
        "weight_emphasis": tokens.WEIGHT_EMPHASIS,
        **tokens.THEMES[theme],
    }
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(values)


def build():
    """Write mbi.qss (dark, default) and mbi-light.qss."""
    for theme, path in OUTPUTS.items():
        path.write_text(render(theme), encoding="utf-8")
        print(f"wrote {path}")
