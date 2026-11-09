"""La tarjeta del Protagonista: aparece sobre el reproductor al pasar el mouse por su botón (arriba a la derecha) y
muestra cómo es, su nombre y sus puntos. No recibe clics: el mouse sigue en el botón."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from . import vista3d


class PasoDelMouse(QObject):
    """Avisa cuando el mouse entra o sale de los widgets en los que se instala. Junta los avisos seguidos (pasar de
    uno al de al lado no cuenta como salir), así la tarjeta no titila."""
    cambio = Signal(bool)   # True = el mouse está encima

    def __init__(self, padre: QObject, espera_entrar: int = 180, espera_salir: int = 220):
        super().__init__(padre)
        self._encima = False
        self._espera = (espera_entrar, espera_salir)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(lambda: self.cambio.emit(self._encima))

    def instalar(self, *widgets):
        for w in widgets:
            w.installEventFilter(self)
            w.setAttribute(Qt.WA_Hover, True)

    def eventFilter(self, _objeto, evento):
        if evento.type() in (QEvent.Enter, QEvent.HoverEnter):
            self._encima = True
            self._timer.start(self._espera[0])
        elif evento.type() in (QEvent.Leave, QEvent.HoverLeave):
            self._encima = False
            self._timer.start(self._espera[1])
        return False


class TarjetaProtagonista(QFrame):
    ANCHO, ALTO_VISTA = 230, 250

    def __init__(self, padre):
        super().__init__(padre)
        self.setObjectName("tarjetaProtagonista")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("#tarjetaProtagonista { background: rgba(14, 22, 38, 235); border: 1px solid #34486f; "
                           "border-radius: 14px; } #tarjetaProtagonista QLabel { background: transparent; }")
        self.vista = vista3d.crear(None, "cuerpo", parent=self)
        self.vista.setFixedSize(self.ANCHO - 24, self.ALTO_VISTA)
        self.vista.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.nombre = QLabel(alignment=Qt.AlignCenter, wordWrap=True)
        self.nombre.setStyleSheet("font-size: 15pt; font-weight: 700; color: #ffffff;")
        self.rango = QLabel(alignment=Qt.AlignCenter)
        self.rango.setStyleSheet("color: #9fc2ff;")
        self.puntos = QLabel(alignment=Qt.AlignCenter, wordWrap=True)
        self.puntos.setStyleSheet("font-size: 12pt; color: #ffd24a;")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(12, 10, 12, 14)
        capa.setSpacing(2)
        capa.addWidget(self.vista, 0, Qt.AlignHCenter)
        capa.addWidget(self.nombre)
        capa.addWidget(self.rango)
        capa.addWidget(self.puntos)
        self.setFixedWidth(self.ANCHO)
        self.hide()

    def mostrar(self, spec: dict, nombre: str, rango: str, puntos: str):
        self.vista.poner(spec)
        self.vista.pose(vaiven=1, inclinacion=0, empuje=0, giroMano=0, mira=0) if hasattr(self.vista, "pose") else None
        self.nombre.setText(nombre)
        self.rango.setText(rango)
        self.rango.setVisible(bool(rango))
        self.puntos.setText(puntos)
        self.adjustSize()
        padre = self.parentWidget()
        self.move(max(8, padre.width() - self.width() - 14), 14)
        self.show()
        self.raise_()

    def ocultar(self):
        self.hide()
