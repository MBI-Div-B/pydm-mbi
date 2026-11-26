"""The MBI logo, in the color that fits the active MBI stylesheet."""

import os

from qtpy.QtCore import Property, QRectF, QSize, Qt
from qtpy.QtGui import QPainter
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QWidget

from ..paths import STYLESHEETS, logo

VARIANTS = "ABCDEF"


def active_theme():
    """Return "light" if PyDM uses the light MBI stylesheet, otherwise "dark" (the default)."""
    stylesheets = os.environ.get("PYDM_STYLESHEET", "").split(os.pathsep)
    return "light" if str(STYLESHEETS["light"]) in stylesheets else "dark"


class MbiLogo(QWidget):
    """
    The MBI logo, scaled to the widget with its aspect ratio kept.

    Properties: variant (A to F, as in the design guide), german (German institute name), and
    color ("auto": white on the dark stylesheet, blue on the light one; or "white", "blue").
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._variant = "C"
        self._german = False
        self._color = "auto"
        self._renderer = None
        self._alignment = Qt.AlignLeft | Qt.AlignVCenter
        self._load()

    def _load(self):
        color = self._color if self._color in ("white", "blue") else ("blue" if active_theme() == "light" else "white")
        self.path = logo(self._variant, color, "de" if self._german else "en")
        self._renderer = QSvgRenderer(str(self.path), self)
        self.updateGeometry()
        self.update()

    def readVariant(self):
        return self._variant

    def setVariant(self, value):
        value = str(value).upper()
        if value in VARIANTS and value != self._variant:
            self._variant = value
            self._load()

    variant = Property(str, readVariant, setVariant)

    def readGerman(self):
        return self._german

    def setGerman(self, value):
        if bool(value) != self._german:
            self._german = bool(value)
            self._load()

    german = Property(bool, readGerman, setGerman)

    def readColor(self):
        return self._color

    def setColor(self, value):
        value = str(value).lower()
        if value in ("auto", "white", "blue") and value != self._color:
            self._color = value
            self._load()

    color = Property(str, readColor, setColor)

    def readAlignment(self):
        return self._alignment

    def setAlignment(self, value):
        self._alignment = Qt.Alignment(value)
        self.update()

    alignment = Property(Qt.Alignment, readAlignment, setAlignment)

    def sizeHint(self):
        size = self._renderer.defaultSize()
        return QSize(160, max(1, round(160 * size.height() / max(1, size.width()))))

    def paintEvent(self, event):
        size = self._renderer.defaultSize()
        if size.isEmpty():
            return
        scale = min(self.width() / size.width(), self.height() / size.height())
        w, h = size.width() * scale, size.height() * scale
        if self._alignment & Qt.AlignRight:
            x = self.width() - w
        elif self._alignment & Qt.AlignHCenter:
            x = (self.width() - w) / 2
        else:
            x = 0.0
        y = (self.height() - h) / 2
        painter = QPainter(self)
        self._renderer.render(painter, QRectF(x, y, w, h))
        painter.end()
