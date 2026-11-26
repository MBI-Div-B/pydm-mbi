"""
Footer of a device panel: heartbeat, state LED and status text of one Tango device, in one row.

In a .ui file, set the property ``device`` to ``${DEVICE}``; the children connect to
``tango://<device>`` (heartbeat), ``.../State`` (LED) and ``.../Status`` (text).
"""

from pydm.widgets.label import PyDMLabel
from qtpy.QtCore import Property, Qt
from qtpy.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from .heartbeat import MbiHeartbeat
from .state_led import TangoStateLed


class MbiDeviceFooter(QWidget):
    """The common footer of the device panels, see the module documentation. Property: device."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device = ""

        self.separator = QFrame(self)
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setProperty("mbiRole", "separator")

        self.heartbeat = MbiHeartbeat(self)
        self.state_led = TangoStateLed(self)
        self.status = PyDMLabel(self)
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.status.setProperty("mbiRole", "message")

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self.heartbeat, 0, Qt.AlignVCenter)
        row.addWidget(self.state_led, 0, Qt.AlignVCenter)
        row.addWidget(self.status, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.separator)
        layout.addLayout(row)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def readDevice(self):
        return self._device

    def setDevice(self, value):
        value = str(value).strip().rstrip("/")
        if value == self._device:
            return
        self._device = value
        if value and "${" not in value:  # a macro not substituted (yet), e.g. in Designer
            self.heartbeat.channel = f"tango://{value}"
            self.state_led.channel = f"tango://{value}/State"
            self.status.channel = f"tango://{value}/Status"
        else:
            for widget in (self.heartbeat, self.state_led, self.status):
                widget.channel = ""

    device = Property(str, readDevice, setDevice)
