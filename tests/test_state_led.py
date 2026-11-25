import pytest
from conftest import DEVICE
from qtpy.QtGui import QColor

from pydm_mbi.style.tokens import DISCONNECTED_COLOR, STATE_COLORS
from pydm_mbi.widgets import TangoStateLed


def test_disconnected_is_grey(qtbot):
    led = TangoStateLed()
    qtbot.addWidget(led)
    assert led.state_name() is None
    assert led.color() == QColor(DISCONNECTED_COLOR)


def test_color_from_enum_strings(qtbot):
    led = TangoStateLed()
    qtbot.addWidget(led)
    led.connection_changed(True)
    led.enum_strings_changed(("ON", "OFF", "FAULT"))
    led.value_changed(2)
    assert led.state_name() == "FAULT"
    assert led.color() == QColor(STATE_COLORS["FAULT"])


def test_color_without_enum_strings(qtbot):
    led = TangoStateLed()
    qtbot.addWidget(led)
    led.connection_changed(True)
    led.value_changed(10)  # DevState RUNNING
    assert led.state_name() == "RUNNING"


@pytest.mark.tango
def test_tangotest_state(qtbot):
    led = TangoStateLed(init_channel=f"tango://{DEVICE}/State")
    qtbot.addWidget(led)
    qtbot.waitUntil(lambda: led.state_name() is not None, timeout=10000)
    assert led.state_name() in STATE_COLORS
