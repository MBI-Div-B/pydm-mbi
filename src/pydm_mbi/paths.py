"""Locations of the package data and the PyDM environment variables that use them."""

import os
from pathlib import Path

from .style import DEFAULT_THEME, OUTPUTS

PACKAGE_DIR = Path(__file__).resolve().parent
COMPONENTS_DIR = PACKAGE_DIR / "components"
LOGO_DIR = PACKAGE_DIR / "assets" / "logos"
STYLESHEETS = dict(OUTPUTS)


def logo(variant="C", color="white", language="en"):
    """
    Path of an MBI logo SVG (text converted to paths, no fonts needed).

    variant: A to F as in the design guide, e.g. "A" triangle with small word mark,
    "C" triangle with MAX BORN INSTITUTE, "E" with the full institute name;
    "symbol" for the triangle alone (no language).
    color: "white" for dark backgrounds, "blue" for light ones. language: "en" or "de".
    """
    if variant == "symbol":
        path = LOGO_DIR / f"MBI-logo_{color}_symbol.svg"
    else:
        path = LOGO_DIR / f"MBI-logo_{color}_{variant}_{language}.svg"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def environment(theme=DEFAULT_THEME, base=None):
    """
    Environment variables for PyDM (and Qt Designer with the PyDM plugin):

    - PYDM_STYLESHEET: the MBI stylesheet of the theme (dark by default),
    - PYDM_STYLESHEET_INCLUDE_DEFAULT: keep PyDM's default stylesheet (alarm colors) below it,
    - PYDM_DISPLAYS_PATH: the components folder first, so displays embed e.g. "tangotest/compact.ui".

    Returns a copy of `base` (default: os.environ) with these variables set.
    """
    env = dict(os.environ if base is None else base)
    env["PYDM_STYLESHEET"] = str(STYLESHEETS[theme])
    env["PYDM_STYLESHEET_INCLUDE_DEFAULT"] = "1"
    paths = [str(COMPONENTS_DIR)] + [p for p in env.get("PYDM_DISPLAYS_PATH", "").split(os.pathsep) if p]
    env["PYDM_DISPLAYS_PATH"] = os.pathsep.join(dict.fromkeys(paths))
    return env
