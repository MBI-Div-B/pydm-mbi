"""
Heartbeat in the MBI logo: a light pulse propagates through the pulse-shaped gap of the triangle.

Two questions, two signals:

- Is the panel alive? The pulse runs every ``interval`` ms on the GUI's own timer. If the panel freezes,
  the pulse stops.
- Is the control system connection alive? With a channel, the gap turns red while it is disconnected.
  The Tango plugin detects this for event-driven attributes too (Tango's event heartbeat), so it works for
  attributes that rarely change, e.g. ``State``.

With ``beatOnUpdate``, the pulses come from the updates of the channel instead of the timer, and the gap
turns orange when no update arrived for ``staleTimeout`` seconds. Use it for channels that update
regularly, e.g. a heartbeat counter of a device server or a client-polled attribute: for Tango every read
counts (the timestamp changes even if the value does not).
"""

import time
import xml.etree.ElementTree as ET

from pydm.utilities import is_qt_designer
from pydm.widgets.base import PyDMWidget
from qtpy.QtCore import Property, QElapsedTimer, QPointF, QRectF, QSize, QTimer
from qtpy.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPolygonF
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QSizePolicy, QWidget

from ..paths import logo
from ..style.tokens import EXTENDED, HIGHLIGHT
from .logo import active_theme

OK, STALE, DISCONNECTED, FREE = "ok", "stale", "disconnected", "free running"
STATUS_COLORS = {STALE: EXTENDED["orange"], DISCONNECTED: EXTENDED["red"]}
FRAME_INTERVAL = 16  # ms, only while a pulse is running


def _first_path_id(path):
    for element in ET.parse(path).getroot().iter("{http://www.w3.org/2000/svg}path"):
        if element.get("id"):
            return element.get("id")
    return None


class MbiHeartbeat(QWidget, PyDMWidget):
    """
    The MBI logo symbol as a heartbeat indicator for PyDM panels, see the module documentation.

    Properties: channel, interval (ms), beatOnUpdate, staleTimeout (s, with beatOnUpdate), pulseDuration (ms),
    color ("auto", "white", "blue"), pulseColor.
    """

    def __init__(self, parent=None, init_channel=None):
        QWidget.__init__(self, parent)
        PyDMWidget.__init__(self, init_channel=init_channel)
        self.alarmSensitiveBorder = False
        self.alarmSensitiveContent = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._interval = 1500
        self._beat_on_update = False
        self._stale_timeout = 5.0
        self._pulse_duration = 900
        self._color = "auto"
        self._pulse_color = QColor(HIGHLIGHT["cyan"])
        self._last_update = None  # time.monotonic() of the last update of the channel
        self._progress = None  # 0..1 while a pulse runs
        self._status = FREE
        self.beats = 0

        self._clock = QElapsedTimer()
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(FRAME_INTERVAL)
        self._frame_timer.timeout.connect(self._next_frame)
        self._beat_timer = QTimer(self)
        self._beat_timer.timeout.connect(self.beat)
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(250)
        self._watch_timer.timeout.connect(self._update_status)

        self._load_logo()
        if not is_qt_designer():
            self._watch_timer.start()
            self._update_beat_timer()

    # Logo

    def _load_logo(self):
        color = self._color if self._color in ("white", "blue") else ("blue" if active_theme() == "light" else "white")
        path = logo("symbol", color)
        self._renderer = QSvgRenderer(str(path), self)
        # Crop to the triangle itself (the only path of the symbol), so that its corners are the corners of the bounds
        element = _first_path_id(path)
        if element and self._renderer.elementExists(element):
            bounds = self._renderer.transformForElement(element).mapRect(self._renderer.boundsOnElement(element))
            self._renderer.setViewBox(bounds)
        self.update()

    def _logo_rect(self):
        box = self._renderer.viewBoxF()
        scale = min(self.width() / box.width(), self.height() / box.height())
        w, h = box.width() * scale, box.height() * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    # Beats

    def beat(self):
        """Start a pulse: called by the timer, or for every update of the channel with beatOnUpdate."""
        self.beats += 1
        self._clock.start()
        self._progress = 0.0
        if not self._frame_timer.isActive():
            self._frame_timer.start()

    def _next_frame(self):
        progress = self._clock.elapsed() / max(1, self._pulse_duration)
        if progress >= 1.0:
            self._progress = None
            self._frame_timer.stop()
        else:
            self._progress = progress
        self.update()

    def _updated(self):
        self._last_update = time.monotonic()
        if self._beat_on_update and self.channel:
            self.beat()
        self._update_status()

    def timestamp_changed(self, new_timestamp):
        changed = new_timestamp != self.timestamp
        super().timestamp_changed(new_timestamp)
        if changed:
            self._updated()

    def value_changed(self, new_val):
        super().value_changed(new_val)
        # channels without timestamps (e.g. other data plugins) count values
        if self.timestamp is None:
            self._updated()

    def connection_changed(self, connected):
        super().connection_changed(connected)
        self._update_status()

    def _update_beat_timer(self):
        if is_qt_designer() or (self._beat_on_update and self.channel):
            self._beat_timer.stop()
        else:
            self._beat_timer.start(self._interval)

    def status(self):
        """"ok", "stale", "disconnected" or "free running" (no channel)."""
        return self._status

    def _update_status(self):
        if not self.channel:
            status = FREE
        elif not self._connected:
            status = DISCONNECTED
        elif self._beat_on_update and (
            self._last_update is None or time.monotonic() - self._last_update > self._stale_timeout
        ):
            status = STALE
        else:
            status = OK
        if status != self._status:
            self._status = status
            self.update()
        self._update_tooltip()

    def _update_tooltip(self):
        if not self.channel:
            text = f"Panel heartbeat every {self._interval} ms"
        else:
            text = f"{self.channel}\n{self._status}"
            if self._last_update is not None:
                text += f", last update {time.monotonic() - self._last_update:.1f} s ago"
        self.setToolTip(text)

    # Painting

    def sizeHint(self):
        return QSize(32, 28)

    def paintEvent(self, event):
        rect = self._logo_rect()
        if rect.isEmpty():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        triangle = QPainterPath()
        apex = QPointF(rect.center().x(), rect.top())
        triangle.addPolygon(QPolygonF([apex, rect.bottomRight(), rect.bottomLeft(), apex]))

        # Behind the logo, clipped to the triangle: only the pulse-shaped gap shows it
        painter.save()
        painter.setClipPath(triangle)
        status_color = STATUS_COLORS.get(self._status)
        if status_color is not None and not is_qt_designer():
            painter.fillRect(rect, QColor(status_color))
        if self._progress is not None:
            painter.fillRect(rect, QBrush(self._pulse_gradient(rect, self._progress)))
        painter.restore()

        self._renderer.render(painter, rect)
        painter.end()

    def _pulse_gradient(self, rect, progress):
        """A bright band moving through the gap from left to right, fading out at the end."""
        eased = progress * progress * (3 - 2 * progress)  # smoothstep
        width = 0.3 * rect.width()
        # the gap runs from the left edge to about 80 % of the width (right edge at its height)
        start, end = rect.left() - 0.5 * width, rect.left() + 0.8 * rect.width() + 0.5 * width
        x = start + eased * (end - start)
        fade = min(1.0, 5 * (1 - progress))
        gradient = QLinearGradient(x - width, 0, x + width, 0)
        transparent = QColor(self._pulse_color)
        transparent.setAlpha(0)
        glow = QColor(self._pulse_color)
        glow.setAlphaF(0.9 * fade)
        core = QColor("#FFFFFF")
        core.setAlphaF(fade)
        gradient.setColorAt(0.0, transparent)
        gradient.setColorAt(0.35, glow)
        gradient.setColorAt(0.5, core)
        gradient.setColorAt(0.65, glow)
        gradient.setColorAt(1.0, transparent)
        return gradient

    # Properties

    def readInterval(self):
        return self._interval

    def setInterval(self, value):
        self._interval = max(100, int(value))
        if self._beat_timer.isActive():
            self._beat_timer.setInterval(self._interval)

    interval = Property(int, readInterval, setInterval)

    def readBeatOnUpdate(self):
        return self._beat_on_update

    def setBeatOnUpdate(self, value):
        self._beat_on_update = bool(value)
        if not is_qt_designer():
            self._update_beat_timer()
        self._update_status()

    beatOnUpdate = Property(bool, readBeatOnUpdate, setBeatOnUpdate)

    def readStaleTimeout(self):
        return self._stale_timeout

    def setStaleTimeout(self, value):
        self._stale_timeout = max(0.0, float(value))

    staleTimeout = Property(float, readStaleTimeout, setStaleTimeout)

    def readPulseDuration(self):
        return self._pulse_duration

    def setPulseDuration(self, value):
        self._pulse_duration = max(100, int(value))

    pulseDuration = Property(int, readPulseDuration, setPulseDuration)

    def readColor(self):
        return self._color

    def setColor(self, value):
        value = str(value).lower()
        if value in ("auto", "white", "blue") and value != self._color:
            self._color = value
            self._load_logo()

    color = Property(str, readColor, setColor)

    def readPulseColor(self):
        return self._pulse_color

    def setPulseColor(self, value):
        self._pulse_color = QColor(value)

    pulseColor = Property(QColor, readPulseColor, setPulseColor)

    # The channel property of PyDMWidget, extended to switch the free running timer

    def readChannel(self):
        return PyDMWidget.readChannel(self)

    def setChannel(self, value):
        self.set_channel(value)
        if hasattr(self, "_beat_timer"):  # also called from PyDMWidget.__init__ with init_channel
            if not is_qt_designer():
                self._update_beat_timer()
            self._update_status()

    channel = Property(str, readChannel, setChannel)
