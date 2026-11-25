"""Every component loads, and with Tango running, every channel connects."""

import xml.etree.ElementTree as ET

import pytest
from conftest import DEVICE
from pydm.display import load_file
from pydm.widgets.base import PyDMWidget
from qtpy.QtWidgets import QWidget

from pydm_mbi import COMPONENTS_DIR

COMPONENTS = sorted(COMPONENTS_DIR.rglob("*.ui"))
MACROS = {"DEVICE": DEVICE}


def load(qtbot, path):
    display = load_file(str(path), macros=MACROS, target=None)
    qtbot.addWidget(display)
    return display


def channel_widgets(display):
    return [w for w in display.findChildren(QWidget) if isinstance(w, PyDMWidget) and w.channels()]


@pytest.mark.parametrize("path", COMPONENTS, ids=lambda p: str(p.relative_to(COMPONENTS_DIR)))
def test_component_loads(qtbot, path):
    display = load(qtbot, path)
    widgets = channel_widgets(display)
    assert widgets, "component without channels"
    for widget in widgets:
        for channel in widget.channels():
            assert "${" not in channel.address, f"macro not substituted in {widget.objectName()}"


@pytest.mark.parametrize("path", COMPONENTS, ids=lambda p: str(p.relative_to(COMPONENTS_DIR)))
def test_object_names_do_not_shadow_methods(path):
    """uic sets every object name as an attribute: a layout named "layout" hides QWidget.layout()."""
    names = {e.get("name") for e in ET.parse(path).iter() if e.tag in ("widget", "layout", "spacer", "action")}
    shadowing = sorted(n for n in names if n and hasattr(QWidget, n))
    assert not shadowing, f"object names hide QWidget attributes: {shadowing}"


@pytest.mark.tango
@pytest.mark.parametrize("path", COMPONENTS, ids=lambda p: str(p.relative_to(COMPONENTS_DIR)))
def test_component_connects(qtbot, path):
    display = load(qtbot, path)
    widgets = channel_widgets(display)
    qtbot.waitUntil(lambda: all(w._connected for w in widgets), timeout=10000)
