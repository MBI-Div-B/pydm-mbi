"""
The laser lab example: every display loads, every device it uses is simulated, and with the simulator
running (examples/laserlab/simulator.py), every channel connects.
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydm.display import load_file
from pydm.widgets.base import PyDMWidget
from pydm.widgets.image import PyDMImageView
from qtpy.QtWidgets import QWidget

from pydm_mbi.widgets import MbiBeam, MbiStateSymbol

LAB = Path(__file__).resolve().parents[1] / "examples" / "laserlab"
DISPLAYS = sorted(LAB.rglob("*.ui"))
LISTS = {path.stem: json.loads(path.read_text()) for path in sorted((LAB / "lists").glob("*.json"))}
DEVICES = {row["DEVICE"]: row for rows in LISTS.values() for row in rows}
GROUP = {"TITLE": "Pressure gauges", "ROW": "panels/pressuregauge/row.ui", "DEVICES": "lists/pressure_gauges.json"}


def macros_for(path):
    """Macros to open a display with: a device of its class for the device panels and rows."""
    if path.name == "group.ui":
        return GROUP
    if path.parent.parent.name == "panels":  # panels/<class>/panel.ui and row.ui
        row = next(row for row in DEVICES.values() if row["CLASS"].lower() == path.parent.name)
        return {"DEVICE": row["DEVICE"], "LABEL": row["LABEL"]}
    if path.name == "simulation_row.ui":
        return {"DEVICE": "laserlab/laser/1", "LABEL": "Laser"}
    return {}


# Deleting displays with time plots while their Tango channels connect crashes now and then (pyqtgraph ViewBox
# callbacks on deleted objects). The displays are hidden after each test instead, and deleted at the end.
LOADED = []


@pytest.fixture(autouse=True)
def hide_displays():
    yield
    for display in LOADED:
        display.hide()


def load(qtbot, path):
    display = load_file(str(path), macros=macros_for(path), target=None)
    LOADED.append(display)
    return display


def channels(widget):
    return [channel for channel in widget.channels() or [] if channel]  # PyDMImageView lists unused channels as None


def is_connected(widget):
    if isinstance(widget, PyDMImageView):  # tracks the connection of its image channel by its redraw timer
        return widget.redraw_timer.isActive()
    return widget._connected


def channel_widgets(display):
    return [w for w in display.findChildren(QWidget) if isinstance(w, PyDMWidget) and channels(w)]


ids = {"ids": lambda p: str(p.relative_to(LAB))}


def test_lists():
    for name, rows in LISTS.items():
        assert rows, name
        for row in rows:
            assert set(row) == {"DEVICE", "LABEL", "CLASS"}, row


def test_every_device_is_simulated():
    """Every Tango device a display uses is in lists/*.json, from which the simulator registers its devices."""
    used = set()
    for path in DISPLAYS:
        used.update(re.findall(r"tango://(\w+/\w+/\w+)", path.read_text()))
    assert used, "no devices found"
    assert used <= set(DEVICES), sorted(used - set(DEVICES))


def test_every_class_has_a_panel():
    classes = {row["CLASS"].lower() for row in DEVICES.values()}
    assert classes == {path.parent.name for path in LAB.glob("panels/*/panel.ui")}


@pytest.mark.parametrize("path", DISPLAYS, **ids)
def test_display_loads(qtbot, path):
    display = load(qtbot, path)
    for widget in channel_widgets(display):
        for channel in channels(widget):
            assert "${" not in channel.address, f"macro not substituted in {widget.objectName()}"


@pytest.mark.parametrize("path", DISPLAYS, **ids)
def test_object_names_do_not_shadow_methods(path):
    names = {e.get("name") for e in ET.parse(path).iter() if e.tag in ("widget", "layout", "spacer", "action")}
    shadowing = sorted(n for n in names if n and hasattr(QWidget, n))
    assert not shadowing, f"object names hide QWidget attributes: {shadowing}"


def test_group_rows(qtbot):
    display = load(qtbot, LAB / "group.ui")
    rows = [w for w in display.findChildren(QWidget) if w.objectName() == "PressureGaugeRow"]
    assert len(rows) == len(LISTS["pressure_gauges"])


@pytest.mark.laserlab
@pytest.mark.parametrize("path", [p for p in DISPLAYS if p.name != "group.ui"], **ids)
def test_display_connects(qtbot, path):
    display = load(qtbot, path)
    widgets = channel_widgets(display)
    qtbot.waitUntil(lambda: all(is_connected(w) for w in widgets), timeout=15000)
    beams = display.findChildren(MbiBeam)
    qtbot.waitUntil(lambda: all(beam.status() != "unknown" for beam in beams), timeout=15000)


@pytest.mark.laserlab
def test_fault_shows_in_synoptic(qtbot):
    import tango

    display = load(qtbot, LAB / "laserlab.ui")
    valve = next(w for w in display.findChildren(MbiStateSymbol) if w.objectName() == "v1_symbol")
    qtbot.waitUntil(lambda: valve.state_name() is not None, timeout=15000)
    proxy = tango.DeviceProxy("laserlab/valve/hhg_tm")
    proxy.SimulateFault("test")
    try:
        qtbot.waitUntil(lambda: valve.state_name() == "FAULT", timeout=10000)
    finally:
        proxy.Reset()
    qtbot.waitUntil(lambda: valve.state_name() != "FAULT", timeout=10000)
