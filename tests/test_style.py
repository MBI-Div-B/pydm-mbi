import pytest
from qtpy.QtSvg import QSvgRenderer

from pydm_mbi import STYLESHEETS, environment, logo
from pydm_mbi.paths import LOGO_DIR
from pydm_mbi.style import OUTPUTS, render


def test_default_theme_is_dark():
    assert environment(base={})["PYDM_STYLESHEET"] == str(STYLESHEETS["dark"])


@pytest.mark.parametrize("path", sorted(LOGO_DIR.glob("*.svg")), ids=lambda p: p.name)
def test_logos_render(qapp, path):
    assert QSvgRenderer(str(path)).isValid()


def test_logo_lookup():
    assert logo("C", "white", "en").name == "MBI-logo_white_C_en.svg"
    with pytest.raises(FileNotFoundError):
        logo("Z")


def test_stylesheets_up_to_date():
    """mbi*.qss must be regenerated (python -m pydm_mbi.style) after changing the template or tokens."""
    for theme, path in OUTPUTS.items():
        assert path.read_text(encoding="utf-8") == render(theme), f"{path.name} is outdated"


def test_environment():
    env = environment("dark", base={"PYDM_DISPLAYS_PATH": "/lab/displays"})
    assert env["PYDM_STYLESHEET"] == str(STYLESHEETS["dark"])
    assert env["PYDM_DISPLAYS_PATH"].endswith(":/lab/displays")
    assert env["PYDM_STYLESHEET_INCLUDE_DEFAULT"] == "1"


@pytest.mark.parametrize("theme, color", [("dark", "white"), ("light", "blue")])
def test_logo_widget_follows_theme(qtbot, monkeypatch, theme, color):
    from pydm_mbi.widgets import MbiLogo

    monkeypatch.setenv("PYDM_STYLESHEET", str(STYLESHEETS[theme]))
    widget = MbiLogo()
    qtbot.addWidget(widget)
    assert widget.path == logo("C", color, "en")
    widget.german = True
    widget.variant = "e"
    assert widget.path == logo("E", color, "de")
