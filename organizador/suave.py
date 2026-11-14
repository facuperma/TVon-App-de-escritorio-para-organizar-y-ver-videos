"""Desplazamiento suave con la rueda del mouse: en vez de saltar de a una fila, la lista se desliza unos píxeles
con una animación corta que frena al final (como en el navegador). Si se gira la rueda varias veces seguidas,
los giros se suman y la animación sigue desde donde iba."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtWidgets import QAbstractItemView, QAbstractScrollArea

PIXELES_POR_PASO = 110      # un «clic» de la rueda
DURACION_MS = 260


class _Suave(QObject):
    def __init__(self, area: QAbstractScrollArea):
        super().__init__(area)
        self.area = area
        self.barra = area.verticalScrollBar()
        self.animacion = QPropertyAnimation(self.barra, b"value", self)
        self.animacion.setEasingCurve(QEasingCurve.OutCubic)
        self.animacion.setDuration(DURACION_MS)
        self.destino = None
        area.viewport().installEventFilter(self)

    def eventFilter(self, objeto, e):
        if e.type() != QEvent.Wheel or e.modifiers():
            return False                      # con Ctrl/Shift, lo de siempre (zoom, horizontal…)
        delta = e.angleDelta().y()
        if not delta:
            return False
        if self.animacion.state() != QPropertyAnimation.Running:
            self.destino = self.barra.value()
        self.destino = max(self.barra.minimum(), min(self.barra.maximum(),
                                                     self.destino - delta / 120 * PIXELES_POR_PASO))
        self.animacion.stop()
        self.animacion.setStartValue(self.barra.value())
        self.animacion.setEndValue(int(self.destino))
        self.animacion.start()
        return True


def activar(area: QAbstractScrollArea):
    """Desplazamiento suave para una lista, grilla o área con barra de desplazamiento."""
    if isinstance(area, QAbstractItemView):
        area.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    if not hasattr(area, "_suave"):
        area._suave = _Suave(area)
