"""LED for a Tango DevState attribute (usually State) in the usual Tango state colors."""

from pydm.widgets.base import PyDMWidget
from qtpy.QtCore import QPointF, QSize
from qtpy.QtGui import QBrush, QColor, QPainter, QPen
from qtpy.QtWidgets import QSizePolicy, QWidget

from ..style.tokens import DISCONNECTED_COLOR, STATE_COLORS

# DevState values in the order of the Tango enum, used if the channel sends no enum strings
DEV_STATES = list(STATE_COLORS)


def decode_state(value, enum_strings=None):
    """The DevState name of a channel value (index or name), or None without value."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        index = int(value)
    except (TypeError, ValueError):
        return str(value)
    names = enum_strings or DEV_STATES
    return names[index] if 0 <= index < len(names) else "UNKNOWN"


def state_color(name):
    """The Tango color of a state name, grey for None (disconnected)."""
    if name is None:
        return QColor(DISCONNECTED_COLOR)
    return QColor(STATE_COLORS.get(name, STATE_COLORS["UNKNOWN"]))


class TangoStateLed(QWidget, PyDMWidget):
    """
    A round LED showing a Tango DevState, e.g. channel ``tango://sys/tg_test/1/State``.

    The color follows the Tango convention (ON green, FAULT red, ...). While the channel is
    disconnected, the LED is grey. The tooltip shows the channel and the state name.
    """

    def __init__(self, parent=None, init_channel=None):
        QWidget.__init__(self, parent)
        PyDMWidget.__init__(self, init_channel=init_channel)
        self.alarmSensitiveBorder = False
        self.alarmSensitiveContent = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(14, 14)

    def minimumSizeHint(self):
        return QSize(6, 6)

    def state_name(self):
        """Name of the current state, or None while disconnected or without value."""
        if not self._connected:
            return None
        return decode_state(self.value, self.enum_strings)

    def color(self):
        return state_color(self.state_name())

    def value_changed(self, new_val):
        super().value_changed(new_val)
        self._update_tooltip()
        self.update()

    def connection_changed(self, connected):
        super().connection_changed(connected)
        self._update_tooltip()
        self.update()

    def _update_tooltip(self):
        self.setToolTip(f"{self.channel}\n{self.state_name() or 'disconnected'}")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        diameter = min(self.width(), self.height()) - 2
        painter.setPen(QPen(QColor("#1B1918"), 1))
        painter.setBrush(QBrush(self.color()))
        painter.drawEllipse(QPointF(self.width() / 2, self.height() / 2), diameter / 2, diameter / 2)
        painter.end()
