"""
Building blocks for synoptic displays: vacuum chambers, device symbols and laser beams.

- ``MbiVacuumChamber``: a chamber outline, colored by its pressure (channel: the pressure attribute).
- ``MbiStateSymbol``: a valve, shutter, turbo pump, camera, ... symbol in the Tango color of the device state
  (channel: the device or its State attribute). Some symbols (mirror, sample) are decoration without a channel.
- ``MbiBeam``: a straight beam segment, animated while all its ``gates`` let it pass (e.g. the laser is ON
  and the shutter in front of the segment is OPEN), dimmed otherwise.

Place the beams first (below) and the symbols and chambers on top of them, in absolute positions on a
plain widget without layout.
"""

import functools

from pydm import PyDMChannel
from pydm.utilities import is_qt_designer
from pydm.widgets.base import PyDMWidget
from qtpy.QtCore import Property, QObject, QPointF, QRectF, QSize, Qt, QTimer
from qtpy.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from qtpy.QtWidgets import QSizePolicy, QWidget

from ..style.tokens import DISCONNECTED_COLOR, EXTENDED, THEMES
from .heartbeat import resolve_channel
from .logo import active_theme
from .state_led import decode_state, state_color

OUTLINE = QColor("#1B1918")
FRAME_INTERVAL = 33  # ms, ~30 frames per second while something moves


def _theme():
    return THEMES[active_theme()]


class MbiVacuumChamber(QWidget, PyDMWidget):
    """
    A vacuum chamber, filled and outlined in a color for its pressure:

    - green up to ``highVacuum``,
    - yellow up to ``roughVacuum``,
    - orange above (vented or pumping down),
    - grey without connection.

    The thresholds are in the unit of the pressure attribute (usually mbar). Properties: channel (the pressure
    attribute), title, highVacuum, roughVacuum.
    """

    def __init__(self, parent=None, init_channel=None):
        QWidget.__init__(self, parent)
        PyDMWidget.__init__(self, init_channel=init_channel)
        self.alarmSensitiveBorder = False
        self.alarmSensitiveContent = False
        self._title = ""
        self._pressure_unit = ""
        self._high_vacuum = 1e-5
        self._rough_vacuum = 1e-2

    def sizeHint(self):
        return QSize(160, 120)

    def pressure(self):
        if not self._connected or self.value is None:
            return None
        try:
            return float(self.value)
        except (TypeError, ValueError):
            return None

    def level(self):
        """'high', 'rough', 'vented', or None without connection."""
        pressure = self.pressure()
        if pressure is None:
            return None
        if pressure <= self._high_vacuum:
            return "high"
        if pressure <= self._rough_vacuum:
            return "rough"
        return "vented"

    def color(self):
        return QColor(
            {"high": EXTENDED["green"], "rough": EXTENDED["yellow"], "vented": EXTENDED["orange"]}.get(
                self.level(), DISCONNECTED_COLOR
            )
        )

    def value_changed(self, new_val):
        super().value_changed(new_val)
        self._update_tooltip()
        self.update()

    def connection_changed(self, connected):
        super().connection_changed(connected)
        self._update_tooltip()
        self.update()

    def unit_changed(self, new_unit):
        super().unit_changed(new_unit)
        self._pressure_unit = new_unit or ""
        self._update_tooltip()

    def _update_tooltip(self):
        pressure = self.pressure()
        text = "disconnected" if pressure is None else f"{pressure:.2e} {self._pressure_unit}".strip()
        self.setToolTip(f"{self._title}\n{self.channel}\n{text}".strip())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self.color()
        fill = QColor(color)
        fill.setAlphaF(0.16)
        pen = QPen(color, 2)
        if self.level() is None:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        if self._title:
            font = QFont(self.font())
            font.setWeight(QFont.Medium)
            painter.setFont(font)
            painter.setPen(QColor(_theme()["text"]))
            painter.drawText(QRectF(self.rect()).adjusted(10, 6, -10, -6), Qt.AlignTop | Qt.AlignLeft, self._title)
        painter.end()

    def readTitle(self):
        return self._title

    def setTitle(self, value):
        self._title = str(value)
        self._update_tooltip()
        self.update()

    title = Property(str, readTitle, setTitle)

    def readHighVacuum(self):
        return self._high_vacuum

    def setHighVacuum(self, value):
        self._high_vacuum = float(value)
        self.update()

    highVacuum = Property(float, readHighVacuum, setHighVacuum)

    def readRoughVacuum(self):
        return self._rough_vacuum

    def setRoughVacuum(self, value):
        self._rough_vacuum = float(value)
        self.update()

    roughVacuum = Property(float, readRoughVacuum, setRoughVacuum)


SYMBOLS = ("valve", "shutter", "pump", "camera", "monitor", "laser", "stage", "mirror", "sample")
DECORATION = ("mirror", "sample")  # no channel, no state


class MbiStateSymbol(QWidget, PyDMWidget):
    """
    A device symbol in the Tango color of the device state (OPEN green, CLOSE white, FAULT red, ...).

    Properties: channel (``tango://<device>`` or its State attribute), symbol (valve, shutter, pump, camera,
    monitor, laser, stage; mirror and sample without channel), vertical (rotate by 90 degrees), flipped
    (mirror: "\\" instead of "/").

    A running turbo pump (ON) turns its rotor, a pump ramping up or down (MOVING) turns it slowly.
    """

    def __init__(self, parent=None, init_channel=None):
        QWidget.__init__(self, parent)
        self._channel_input = None
        PyDMWidget.__init__(self, init_channel=init_channel)
        self.alarmSensitiveBorder = False
        self.alarmSensitiveContent = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._symbol = "valve"
        self._vertical = False
        self._flipped = False
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_INTERVAL)
        self._timer.timeout.connect(self._turn)

    def sizeHint(self):
        return QSize(32, 32)

    def state_name(self):
        if not self._connected:
            return None
        return decode_state(self.value, self.enum_strings)

    def color(self):
        return state_color(self.state_name())

    def value_changed(self, new_val):
        super().value_changed(new_val)
        self._state_changed()

    def connection_changed(self, connected):
        super().connection_changed(connected)
        self._state_changed()

    def _state_changed(self):
        rotating = self._symbol == "pump" and self.state_name() in ("ON", "MOVING", "RUNNING")
        if rotating and not is_qt_designer():
            self._timer.start()
        else:
            self._timer.stop()
        self.setToolTip(f"{self._channel_input or self.channel}\n{self.state_name() or 'disconnected'}")
        self.update()

    def _turn(self):
        self._angle = (self._angle + (12.0 if self.state_name() == "ON" else 3.0)) % 360
        self.update()

    # Painting

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self._vertical:
            painter.translate(w, 0)
            painter.rotate(90)
            w, h = h, w
        rect = QRectF(1.5, 1.5, w - 3, h - 3)
        decoration = self._symbol in DECORATION
        fill = QColor(_theme()["muted"]) if decoration else self.color()
        pen = QPen(OUTLINE, 1.2)
        if not decoration and self.state_name() is None:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        getattr(self, f"_paint_{self._symbol}", self._paint_valve)(painter, rect, fill)
        painter.end()

    def _paint_valve(self, painter, rect, fill):
        """Two triangles meeting in the middle (bow tie), the beam passing from left to right."""
        c = rect.center()
        top, bottom = rect.top() + 0.15 * rect.height(), rect.bottom() - 0.15 * rect.height()
        for x in (rect.left(), rect.right()):
            painter.drawPolygon(QPolygonF([QPointF(x, top), QPointF(c.x(), c.y()), QPointF(x, bottom)]))

    def _paint_shutter(self, painter, rect, fill):
        """A blade across the beam."""
        width = max(4.0, 0.3 * rect.width())
        painter.drawRoundedRect(QRectF(rect.center().x() - width / 2, rect.top(), width, rect.height()), 2, 2)

    def _paint_pump(self, painter, rect, fill):
        """A circle with a rotor."""
        size = min(rect.width(), rect.height())
        circle = QRectF(0, 0, size, size)
        circle.moveCenter(rect.center())
        painter.drawEllipse(circle)
        painter.save()
        painter.translate(circle.center())
        painter.rotate(self._angle)
        painter.setPen(QPen(OUTLINE, max(1.5, size / 14), Qt.SolidLine, Qt.RoundCap))
        for i in range(3):
            painter.rotate(120)
            painter.drawLine(QPointF(0, 0), QPointF(0, -0.36 * size))
        painter.restore()

    def _paint_camera(self, painter, rect, fill):
        """A body with a lens in the state color."""
        painter.setBrush(QBrush(QColor(_theme()["surface"])))
        body = rect.adjusted(0, 0.15 * rect.height(), 0, -0.15 * rect.height())
        painter.drawRoundedRect(body, 3, 3)
        lens = min(body.width(), body.height()) * 0.6
        lens_rect = QRectF(0, 0, lens, lens)
        lens_rect.moveCenter(body.center())
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(lens_rect)

    def _paint_monitor(self, painter, rect, fill):
        """A screen at 45 degrees in the beam (beam position monitor)."""
        c = rect.center()
        dx, dy = 0.5 * rect.width(), 0.5 * rect.height()
        painter.drawPolygon(
            QPolygonF([QPointF(c.x(), c.y() - dy), QPointF(c.x() + dx, c.y()), QPointF(c.x(), c.y() + dy),
                       QPointF(c.x() - dx, c.y())])
        )  # fmt: skip

    def _paint_laser(self, painter, rect, fill):
        """A box with a stripe in the state color and the exit aperture on the right."""
        painter.setBrush(QBrush(QColor(_theme()["surface"])))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(QRectF(rect.left() + 4, rect.top() + 4, 6, rect.height() - 8), 2, 2)
        aperture = QRectF(rect.right() - 5, rect.center().y() - 4, 5, 8)
        painter.setBrush(QBrush(OUTLINE))
        painter.drawRect(aperture)

    def _paint_stage(self, painter, rect, fill):
        """A linear stage: rail with a carriage in the state color."""
        painter.setBrush(QBrush(QColor(_theme()["surface"])))
        rail = QRectF(rect.left(), rect.center().y() - 0.15 * rect.height(), rect.width(), 0.3 * rect.height())
        painter.drawRoundedRect(rail, 2, 2)
        painter.setBrush(QBrush(fill))
        carriage = QRectF(0, 0, 0.35 * rect.width(), rect.height())
        carriage.moveCenter(rect.center())
        painter.drawRoundedRect(carriage, 3, 3)

    def _paint_mirror(self, painter, rect, fill):
        """A mirror at 45 degrees: "/" or, flipped, "\\"."""
        painter.setPen(QPen(fill, max(2.0, min(rect.width(), rect.height()) / 6), Qt.SolidLine, Qt.RoundCap))
        if self._flipped:
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        else:
            painter.drawLine(rect.bottomLeft(), rect.topRight())

    def _paint_sample(self, painter, rect, fill):
        """A thin sample plate across the beam."""
        width = max(3.0, 0.2 * rect.width())
        painter.drawRect(QRectF(rect.center().x() - width / 2, rect.top(), width, rect.height()))

    # Properties

    def readSymbol(self):
        return self._symbol

    def setSymbol(self, value):
        value = str(value).lower()
        if value in SYMBOLS:
            self._symbol = value
            self._state_changed()

    symbol = Property(str, readSymbol, setSymbol)

    def readVertical(self):
        return self._vertical

    def setVertical(self, value):
        self._vertical = bool(value)
        self.update()

    vertical = Property(bool, readVertical, setVertical)

    def readFlipped(self):
        return self._flipped

    def setFlipped(self, value):
        self._flipped = bool(value)
        self.update()

    flipped = Property(bool, readFlipped, setFlipped)

    # The channel property of PyDMWidget, extended to accept a device name (as MbiHeartbeat)

    def readChannel(self):
        return self._channel_input if self._channel_input is not None else PyDMWidget.readChannel(self)

    def setChannel(self, value):
        self._channel_input = value
        self.set_channel(resolve_channel(value))

    channel = Property(str, readChannel, setChannel)


DIRECTIONS = ("right", "left", "down", "up")
PASS_STATES = ("ON", "OPEN", "RUNNING", "EXTRACT")


class _Gate(QObject):
    """The channel of one gate of a beam, with bound methods as slots (PyDM disconnects them on destruction)."""

    def __init__(self, beam, address):
        super().__init__(beam)
        self.beam = beam
        self.address = address
        self.state = None
        self.enum_strings = None
        self.channel = PyDMChannel(
            address=address,
            connection_slot=self.connection_changed,
            value_slot=self.value_changed,
            enum_strings_slot=self.enum_strings_changed,
        )

    def connection_changed(self, connected):
        if not connected:
            self.state = None
            self.beam._refresh()

    def value_changed(self, value):
        self.state = decode_state(value, self.enum_strings)
        self.beam._refresh()

    def enum_strings_changed(self, enum_strings):
        self.enum_strings = enum_strings


def _disconnect(gates, destroying=False):
    for gate in gates:
        gate.channel.disconnect(destroying=destroying)
    gates.clear()


class MbiBeam(QWidget):
    """
    A horizontal or vertical beam segment through the middle of the widget.

    The beam is on, i.e. drawn bright with pulses running in its ``direction``, while every gate passes it:
    a gate is a device (``tango://<device>``, its State is used) or a State attribute, which passes in the
    ``passStates`` (default ON, OPEN, RUNNING, EXTRACT). Without gates, the beam is always on. While a gate
    blocks, the beam is drawn as a faint dashed path; while a gate is disconnected, in grey.

    Properties: gates, passStates, color, beamWidth, direction (right, left, down, up).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # beams lie below the symbols and their buttons
        self._gates = []  # addresses
        self._pass_states = list(PASS_STATES)
        self._connected_gates = []  # _Gate objects, empty in Designer
        self.destroyed.connect(functools.partial(_disconnect, self._connected_gates, True))
        self._color = QColor(EXTENDED["red"])
        self._beam_width = 3
        self._direction = "right"
        self._offset = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_INTERVAL)
        self._timer.timeout.connect(self._advance)

    def sizeHint(self):
        return QSize(120, 12)

    # Gates

    def gate_states(self):
        """{address: state name or None (disconnected)}; in Designer, every gate passes."""
        if is_qt_designer():
            return {gate: self._pass_states[0] if self._pass_states else "ON" for gate in self._gates}
        return {gate.address: gate.state for gate in self._connected_gates}

    def status(self):
        """'on', 'off' (a gate blocks) or 'unknown' (a gate is disconnected)."""
        states = list(self.gate_states().values())
        if any(state is None for state in states):
            return "unknown"
        return "on" if all(state in self._pass_states for state in states) else "off"

    def _connect(self):
        for gate in self._connected_gates:
            gate.deleteLater()
        _disconnect(self._connected_gates)
        if not is_qt_designer():
            for address in self._gates:
                gate = _Gate(self, address)
                self._connected_gates.append(gate)
                gate.channel.connect()
        self._refresh()

    def _refresh(self):
        if self.status() == "on" and not is_qt_designer():
            self._timer.start()
        else:
            self._timer.stop()
        lines = [f"{gate}: {state or 'disconnected'}" for gate, state in self.gate_states().items()]
        self.setToolTip("\n".join(["Beam " + self.status()] + lines))
        self.update()

    def _advance(self):
        self._offset = (self._offset + 1.5) % 1000.0
        self.update()

    # Painting

    def _line(self):
        w, h = self.width(), self.height()
        if self._direction in ("right", "left"):
            start, end = QPointF(0, h / 2), QPointF(w, h / 2)
        else:
            start, end = QPointF(w / 2, 0), QPointF(w / 2, h)
        return (end, start) if self._direction in ("left", "up") else (start, end)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        start, end = self._line()
        path = QPainterPath(start)
        path.lineTo(end)
        status = self.status()
        width = float(self._beam_width)
        if status == "on":
            glow = QColor(self._color)
            glow.setAlphaF(0.25)
            painter.setPen(QPen(glow, 3 * width, Qt.SolidLine, Qt.FlatCap))
            painter.drawPath(path)
            painter.setPen(QPen(self._color, width, Qt.SolidLine, Qt.FlatCap))
            painter.drawPath(path)
            # pulses: bright dashes moving along the beam
            pulse = QPen(QColor("#FFFFFF"), width * 0.6, Qt.CustomDashLine, Qt.RoundCap)
            pulse.setDashPattern([2.0, 10.0])  # in units of the pen width
            pulse.setDashOffset(-self._offset / max(0.1, width * 0.6))
            painter.setPen(pulse)
            painter.drawPath(path)
        else:
            color = QColor(self._color if status == "off" else DISCONNECTED_COLOR)
            color.setAlphaF(0.45)
            pen = QPen(color, max(1.0, width / 2), Qt.DashLine, Qt.FlatCap)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.end()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()

    # Properties

    def readGates(self):
        return list(self._gates)

    def setGates(self, gates):
        gates = [resolve_channel(str(gate).strip()) for gate in gates if str(gate).strip()]
        if gates != self._gates:
            self._gates = gates
            self._connect()

    gates = Property("QStringList", readGates, setGates)

    def readPassStates(self):
        return list(self._pass_states)

    def setPassStates(self, states):
        self._pass_states = [str(state).strip().upper() for state in states if str(state).strip()]
        self._refresh()

    passStates = Property("QStringList", readPassStates, setPassStates)

    def readColor(self):
        return self._color

    def setColor(self, value):
        self._color = QColor(value)
        self.update()

    color = Property(QColor, readColor, setColor)

    def readBeamWidth(self):
        return self._beam_width

    def setBeamWidth(self, value):
        self._beam_width = max(1, int(value))
        self.update()

    beamWidth = Property(int, readBeamWidth, setBeamWidth)

    def readDirection(self):
        return self._direction

    def setDirection(self, value):
        value = str(value).lower()
        if value in DIRECTIONS:
            self._direction = value
            self.update()

    direction = Property(str, readDirection, setDirection)
