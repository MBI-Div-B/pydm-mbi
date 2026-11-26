"""Synoptic widgets and the device footer, without Tango: beams use local (loc://) channels as gates."""

import pytest
from pydm.widgets.base import PyDMWidget
from qtpy.QtGui import QColor

from pydm_mbi.style.tokens import DISCONNECTED_COLOR, EXTENDED, STATE_COLORS
from pydm_mbi.widgets import MbiBeam, MbiDeviceFooter, MbiStateSymbol, MbiVacuumChamber
from pydm_mbi.widgets.state_led import DEV_STATES

ON, CLOSE, OPEN, FAULT = (DEV_STATES.index(name) for name in ("ON", "CLOSE", "OPEN", "FAULT"))


def connected(qtbot, widget, value=None):
    qtbot.addWidget(widget)
    widget.connection_changed(True)
    if value is not None:
        widget.value_changed(value)
    return widget


@pytest.mark.parametrize(
    "pressure, level, color",
    [(1e-7, "high", "green"), (1e-5, "high", "green"), (1e-3, "rough", "yellow"), (1000.0, "vented", "orange")],
)
def test_chamber_levels(qtbot, pressure, level, color):
    chamber = connected(qtbot, MbiVacuumChamber(), pressure)
    assert chamber.level() == level
    assert chamber.color() == QColor(EXTENDED[color])


def test_chamber_thresholds_and_disconnection(qtbot):
    chamber = connected(qtbot, MbiVacuumChamber(), 2e-4)
    chamber.highVacuum = 1e-3  # e.g. an HHG chamber with gas load
    assert chamber.level() == "high"
    chamber.connection_changed(False)
    assert chamber.level() is None
    assert chamber.color() == QColor(DISCONNECTED_COLOR)


@pytest.mark.parametrize("symbol", ["valve", "shutter", "pump", "camera", "monitor", "laser", "stage", "mirror"])
def test_symbols_paint(qtbot, symbol):
    widget = connected(qtbot, MbiStateSymbol(), FAULT)
    widget.symbol = symbol
    widget.vertical = True
    widget.resize(40, 30)
    assert not widget.grab().isNull()
    assert widget.color() == QColor(STATE_COLORS["FAULT"])


def test_symbol_accepts_device(qtbot):
    widget = MbiStateSymbol()
    qtbot.addWidget(widget)
    widget.channel = "tango://sys/tg_test/1"
    assert widget.channel == "tango://sys/tg_test/1"
    assert widget._channel == "tango://sys/tg_test/1/State"


def test_running_pump_turns(qtbot):
    pump = connected(qtbot, MbiStateSymbol())
    pump.symbol = "pump"
    pump.value_changed(ON)
    assert pump._timer.isActive()
    pump.value_changed(FAULT)
    assert not pump._timer.isActive()


def test_beam_without_gates_is_on(qtbot):
    beam = MbiBeam()
    qtbot.addWidget(beam)
    assert beam.status() == "on"


def beam_with_gates(qtbot, *states):
    """A beam with local gates, set to the given states (the local plugin does not keep them connected)."""
    beam = MbiBeam()
    qtbot.addWidget(beam)
    beam.gates = [f"loc://beam_gate_{i}?type=int&init=0" for i in range(len(states))]
    qtbot.wait(50)  # the local plugin sends its signals queued
    for gate, state in zip(beam._connected_gates, states):
        gate.connection_changed(True)
        gate.value_changed(state)
    return beam


def test_beam_gates(qtbot):
    beam = beam_with_gates(qtbot, ON, OPEN)
    assert beam.status() == "on"
    assert beam._timer.isActive()  # animated
    laser, shutter = beam._connected_gates
    shutter.value_changed(CLOSE)
    assert beam.status() == "off"
    assert not beam._timer.isActive()
    shutter.value_changed("OPEN")  # state names work as well
    assert beam.status() == "on"
    laser.connection_changed(False)
    assert beam.status() == "unknown"
    assert "disconnected" in beam.toolTip()


def test_beam_pass_states(qtbot):
    beam = beam_with_gates(qtbot, DEV_STATES.index("INSERT"))
    assert beam.status() == "off"
    beam.passStates = ["insert"]
    assert beam.status() == "on"


def test_beam_reconnects_gates(qtbot):
    beam = beam_with_gates(qtbot, ON, ON)
    beam.gates = ["tango://sys/tg_test/1"]
    assert len(beam._connected_gates) == 1
    assert beam.gates == ["tango://sys/tg_test/1/State"]


@pytest.mark.parametrize("direction", ["right", "left", "down", "up"])
def test_beam_paints(qtbot, direction):
    beam = MbiBeam()
    qtbot.addWidget(beam)
    beam.direction = direction
    beam.resize(60, 60)
    assert not beam.grab().isNull()


def test_footer_channels(qtbot):
    footer = MbiDeviceFooter()
    qtbot.addWidget(footer)
    footer.device = "sys/tg_test/1"
    assert footer.heartbeat.channel == "tango://sys/tg_test/1"
    assert footer.state_led.channel == "tango://sys/tg_test/1/State"
    assert footer.status.channel == "tango://sys/tg_test/1/Status"
    footer.device = "${DEVICE}"  # not substituted, e.g. in Designer
    assert not footer.state_led.channel
    assert all(isinstance(w, PyDMWidget) for w in (footer.heartbeat, footer.state_led, footer.status))
