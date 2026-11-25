import pytest
from conftest import DEVICE

from pydm_mbi.widgets import MbiHeartbeat
from pydm_mbi.widgets.heartbeat import DISCONNECTED, FREE, OK, STALE


def heartbeat(qtbot, fake_channel=False, **properties):
    widget = MbiHeartbeat()
    qtbot.addWidget(widget)
    if fake_channel:
        # pretend a channel is set, without connecting to a data plugin
        widget._channel = "fake://heartbeat"
        widget.get_address = lambda: widget._channel  # PyDM reads it from the connected channels otherwise
    for name, value in properties.items():
        setattr(widget, name, value)
    widget._update_beat_timer()
    return widget


def test_timer_beats_without_channel(qtbot):
    widget = heartbeat(qtbot, interval=100)
    qtbot.waitUntil(lambda: widget.beats >= 3, timeout=2000)
    assert widget.status() == FREE


def test_timer_beats_with_channel_and_red_when_disconnected(qtbot):
    widget = heartbeat(qtbot, fake_channel=True, interval=100)
    widget.connection_changed(True)
    assert widget.status() == OK
    widget.connection_changed(False)
    assert widget.status() == DISCONNECTED
    beats = widget.beats
    qtbot.waitUntil(lambda: widget.beats >= beats + 2, timeout=2000)  # the panel is still alive


def test_beat_on_update_counts_new_timestamps_only(qtbot):
    widget = heartbeat(qtbot, fake_channel=True, beatOnUpdate=True, interval=100)
    widget.connection_changed(True)
    beats = widget.beats
    widget.timestamp_changed(1.0)
    widget.timestamp_changed(1.0)
    widget.timestamp_changed(2.0)
    qtbot.wait(300)  # no timer beats in this mode
    assert widget.beats == beats + 2
    assert widget.status() == OK


def test_beat_on_update_goes_stale(qtbot):
    widget = heartbeat(qtbot, fake_channel=True, beatOnUpdate=True, staleTimeout=0.1)
    widget.connection_changed(True)
    widget.timestamp_changed(1.0)
    assert widget.status() == OK
    qtbot.waitUntil(lambda: widget.status() == STALE, timeout=2000)


def test_pulse_runs_and_ends(qtbot):
    widget = heartbeat(qtbot, pulseDuration=200)
    widget.beat()
    assert widget._progress is not None
    qtbot.waitUntil(lambda: widget._progress is None, timeout=2000)


@pytest.mark.tango
def test_tangotest_state(qtbot):
    widget = MbiHeartbeat(init_channel=f"tango://{DEVICE}/State")
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget.status() == OK, timeout=10000)


@pytest.mark.tango
def test_tangotest_beat_on_update(qtbot):
    """double_scalar changes on every data cycle of TangoTest (Sleep_period, default 2 s)."""
    widget = MbiHeartbeat(init_channel=f"tango://{DEVICE}/double_scalar")
    widget.beatOnUpdate = True
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget.beats >= 2, timeout=10000)
    assert widget.status() == OK
