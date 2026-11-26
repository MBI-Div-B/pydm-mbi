import pytest
from conftest import DEVICE
from pydm.widgets.base import PyDMWidget

from pydm_mbi.widgets import MbiHeartbeat
from pydm_mbi.widgets.heartbeat import ALARM, DISCONNECTED, FREE, OK, resolve_channel


def heartbeat(qtbot, channel=None, **properties):
    widget = MbiHeartbeat()
    qtbot.addWidget(widget)
    if channel:
        # pretend a channel is set, without connecting to a data plugin
        widget._channel = channel
        widget.get_address = lambda: widget._channel  # PyDM reads it from the connected channels otherwise
    for name, value in properties.items():
        setattr(widget, name, value)
    return widget


def test_defaults(qtbot):
    widget = heartbeat(qtbot)
    assert widget.interval == 10000
    assert widget.pulseDuration == 1800


@pytest.mark.parametrize(
    "address, resolved",
    [
        ("tango://sys/tg_test/1", "tango://sys/tg_test/1/State"),
        ("tango://sys/tg_test/1/", "tango://sys/tg_test/1/State"),
        ("tango://db:10000/sys/tg_test/1", "tango://db:10000/sys/tg_test/1/State"),
        ("tango://sys/tg_test/1/double_scalar", "tango://sys/tg_test/1/double_scalar"),
        ("ca://SOME:PV", "ca://SOME:PV"),
        ("", ""),
    ],
)
def test_resolve_channel(address, resolved):
    assert resolve_channel(address) == resolved


def test_timer_beats_without_channel(qtbot):
    widget = heartbeat(qtbot, interval=100)
    qtbot.waitUntil(lambda: widget.beats >= 3, timeout=2000)
    assert widget.status() == FREE


def test_pulse_runs_and_ends(qtbot):
    widget = heartbeat(qtbot, pulseDuration=200)
    widget.beat()
    assert widget._progress is not None
    qtbot.waitUntil(lambda: widget._progress is None, timeout=2000)
    assert not widget._frame_timer.isActive()


@pytest.mark.parametrize(
    "state, status",
    [(0, OK), (6, OK), (7, OK), (8, ALARM), (11, ALARM), (12, OK), ("FAULT", ALARM), ("ON", OK)],
)
def test_device_states(qtbot, state, status):
    """ON, MOVING, STANDBY, DISABLE are fine; FAULT and ALARM are not."""
    widget = heartbeat(qtbot, channel="tango://sys/tg_test/1/State")
    widget.connection_changed(True)
    widget.value_changed(state)
    assert widget.status() == status


def test_attribute_quality(qtbot):
    widget = heartbeat(qtbot, channel="tango://sys/tg_test/1/double_scalar")
    widget.connection_changed(True)
    widget.value_changed(1.0)
    assert widget.status() == OK
    widget.alarm_severity_changed(PyDMWidget.ALARM_MINOR)  # ATTR_WARNING
    assert widget.status() == ALARM
    widget.alarm_severity_changed(PyDMWidget.ALARM_MAJOR)  # ATTR_ALARM
    assert widget.status() == ALARM
    widget.alarm_severity_changed(PyDMWidget.ALARM_NONE)
    assert widget.status() == OK


def test_alarm_keeps_pulsing(qtbot):
    widget = heartbeat(qtbot, channel="tango://sys/tg_test/1/State", interval=100)
    widget.connection_changed(True)
    widget.value_changed(11)
    beats = widget.beats
    qtbot.waitUntil(lambda: widget.beats >= beats + 1 and widget._progress is not None, timeout=2000)


def test_disconnected_blinks_without_pulse(qtbot):
    widget = heartbeat(qtbot, channel="tango://sys/tg_test/1/State", interval=100, pulseDuration=200)
    widget.connection_changed(True)
    widget.beat()
    widget.connection_changed(False)
    assert widget.status() == DISCONNECTED
    assert widget._progress is None
    beats = widget.beats
    qtbot.waitUntil(lambda: widget.beats >= beats + 2, timeout=2000)  # the panel is still alive ...
    assert widget._progress is None  # ... but no pulse
    assert widget._frame_timer.isActive()  # the gap blinks instead
    levels = set()
    qtbot.waitUntil(lambda: levels.add(round(widget._blink_level(), 1)) or len(levels) > 3, timeout=2000)
    widget.interval = 60000  # no further beats: after the last pulse, nothing is animated any more
    widget.connection_changed(True)
    assert widget.status() == OK
    qtbot.waitUntil(lambda: not widget._frame_timer.isActive(), timeout=4000)


def test_device_channel_property(qtbot):
    widget = MbiHeartbeat()
    qtbot.addWidget(widget)
    widget.channel = f"tango://{DEVICE}"
    assert widget.channel == f"tango://{DEVICE}"  # Designer shows what was entered
    assert widget._channel == f"tango://{DEVICE}/State"


@pytest.mark.tango
def test_tangotest_device(qtbot):
    widget = MbiHeartbeat(init_channel=f"tango://{DEVICE}")
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget.status() == OK, timeout=10000)
    assert widget.state_name() in ("RUNNING", "ON", "STANDBY")


@pytest.mark.tango
def test_tangotest_attribute(qtbot):
    widget = MbiHeartbeat(init_channel=f"tango://{DEVICE}/double_scalar")
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget.status() == OK, timeout=10000)
