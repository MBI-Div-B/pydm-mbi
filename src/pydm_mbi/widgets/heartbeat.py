"""
Heartbeat in the MBI logo: a light pulse propagates through the pulse-shaped gap of the triangle.

Two questions, one glance:

- Is the panel alive? The pulse runs every ``interval`` ms on the GUI's own timer. If the panel freezes,
  the pulse (or the blinking, see below) stops.
- Is the device fine? With a channel, the gap behind the pulse shows the device:

  ========================  ==========================  ==============
  device                    gap                         pulse
  ========================  ==========================  ==============
  fine (ON, MOVING, ...)    dark                        cyan
  ALARM / WARNING           steady magenta              keeps running
  no connection             blinking magenta            none
  ========================  ==========================  ==============

The channel is a device (``tango://sys/tg_test/1``, its ``State`` is used) or any attribute. For ``State``,
the states ALARM and FAULT count as alarm; for any other attribute its quality (ATTR_WARNING, ATTR_ALARM).
The Tango plugin detects a lost connection for event-driven attributes too (Tango's event heartbeat), so
rarely changing attributes such as ``State`` are fine.
"""

import math
import xml.etree.ElementTree as ET

from pydm.utilities import is_qt_designer
from pydm.widgets.base import PyDMWidget
from qtpy.QtCore import Property, QElapsedTimer, QPointF, QRectF, QSize, QTimer
from qtpy.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPolygonF
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QSizePolicy, QWidget

from ..paths import logo
from ..style.tokens import HIGHLIGHT, STATE_COLORS
from .logo import active_theme

OK, ALARM, DISCONNECTED, FREE = "ok", "alarm", "disconnected", "free running"
ALARM_STATES = {"ALARM", "FAULT"}
DEV_STATES = list(STATE_COLORS)  # DevState values in the order of the Tango enum
ALARM_COLOR = HIGHLIGHT["magenta"]
FRAME_INTERVAL = 16  # ms, only while a pulse runs or the gap blinks
BLINK_PERIOD = 1000  # ms


def _first_path_id(path):
    for element in ET.parse(path).getroot().iter("{http://www.w3.org/2000/svg}path"):
        if element.get("id"):
            return element.get("id")
    return None


def resolve_channel(address):
    """``tango://<domain>/<family>/<member>`` (a device) becomes its ``State`` attribute, others stay."""
    if not address or not address.startswith("tango://"):
        return address
    path = address[len("tango://") :].split("?")[0]
    parts = [part for part in path.split("/") if part]
    if parts and ":" in parts[0]:  # database host:port
        parts = parts[1:]
    if len(parts) == 3:
        return address.rstrip("/") + "/State"
    return address


class MbiHeartbeat(QWidget, PyDMWidget):
    """
    The MBI logo symbol as a heartbeat indicator for PyDM panels, see the module documentation.

    Properties: channel (device or attribute), interval (ms), pulseDuration (ms), color ("auto", "white",
    "blue"), pulseColor.
    """

    def __init__(self, parent=None, init_channel=None):
        QWidget.__init__(self, parent)
        self._channel_input = None  # the channel as set, before resolving a device to its State
        PyDMWidget.__init__(self, init_channel=init_channel)
        self.alarmSensitiveBorder = False
        self.alarmSensitiveContent = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._interval = 5000
        self._pulse_duration = 1500
        self._color = "auto"
        self._pulse_color = QColor(HIGHLIGHT["cyan"])
        self._progress = None  # 0..1 while a pulse runs
        self._status = FREE
        self.beats = 0

        self._pulse_clock = QElapsedTimer()
        self._blink_clock = QElapsedTimer()
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(FRAME_INTERVAL)
        self._frame_timer.timeout.connect(self._next_frame)
        self._beat_timer = QTimer(self)
        self._beat_timer.timeout.connect(self.beat)

        self._load_logo()
        self._update_status()
        if not is_qt_designer():
            self._beat_timer.start(self._interval)

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
        """Called by the timer: start a pulse, unless the connection is lost (then the gap blinks instead)."""
        self.beats += 1
        if self._status == DISCONNECTED:
            return
        self._pulse_clock.start()
        self._progress = 0.0
        self._frame_timer.start()

    def _next_frame(self):
        if self._progress is not None:
            progress = self._pulse_clock.elapsed() / max(1, self._pulse_duration)
            self._progress = progress if progress < 1.0 else None
        if self._progress is None and self._status != DISCONNECTED:
            self._frame_timer.stop()
        self.update()

    def _blink_level(self):
        """0..1, a soft fade in and out once per BLINK_PERIOD."""
        phase = (self._blink_clock.elapsed() % BLINK_PERIOD) / BLINK_PERIOD
        return 0.5 - 0.5 * math.cos(2 * math.pi * phase)

    # Channel

    def value_changed(self, new_val):
        super().value_changed(new_val)
        self._update_status()

    def connection_changed(self, connected):
        super().connection_changed(connected)
        self._update_status()

    def alarm_severity_changed(self, new_alarm_severity):
        super().alarm_severity_changed(new_alarm_severity)
        self._update_status()

    def _is_state(self):
        return bool(self._channel) and self._channel.rstrip("/").rsplit("/", 1)[-1].lower() == "state"

    def state_name(self):
        """The DevState name for a State channel, else None."""
        if not self._is_state() or not self._connected or self.value is None:
            return None
        if isinstance(self.value, str):
            return self.value
        try:
            index = int(self.value)
        except (TypeError, ValueError):
            return str(self.value)
        names = self.enum_strings or DEV_STATES
        return names[index] if 0 <= index < len(names) else "UNKNOWN"

    def status(self):
        """One of OK, ALARM, DISCONNECTED or FREE (no channel)."""
        return self._status

    def _update_status(self):
        if not hasattr(self, "_frame_timer"):  # called from PyDMWidget.__init__
            return
        if not self._channel:
            status = FREE
        elif not self._connected:
            status = DISCONNECTED
        elif self._is_state():
            status = ALARM if self.state_name() in ALARM_STATES else OK
        elif self._alarm_state in (PyDMWidget.ALARM_MINOR, PyDMWidget.ALARM_MAJOR):
            status = ALARM
        else:
            status = OK
        if status != self._status:
            self._status = status
            if status == DISCONNECTED and not is_qt_designer():
                self._progress = None
                self._blink_clock.start()
                self._frame_timer.start()
            self.update()
        self._update_tooltip()

    def _update_tooltip(self):
        if not self._channel:
            self.setToolTip(f"Panel heartbeat every {self._interval / 1000:g} s")
            return
        detail = self.state_name() if self._status == OK and self._is_state() else self._status
        if self._status == ALARM and self._is_state():
            detail = f"alarm ({self.state_name()})"
        self.setToolTip(f"{self._channel_input or self._channel}\n{detail}")

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
        if not is_qt_designer():
            if self._status == ALARM:
                painter.fillRect(rect, QColor(ALARM_COLOR))
            elif self._status == DISCONNECTED:
                color = QColor(ALARM_COLOR)
                color.setAlphaF(self._blink_level())
                painter.fillRect(rect, color)
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
        self._update_tooltip()

    interval = Property(int, readInterval, setInterval)

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

    # The channel property of PyDMWidget, extended to accept a device name

    def readChannel(self):
        return self._channel_input if self._channel_input is not None else PyDMWidget.readChannel(self)

    def setChannel(self, value):
        self._channel_input = value
        self.set_channel(resolve_channel(value))
        self._update_status()

    channel = Property(str, readChannel, setChannel)
