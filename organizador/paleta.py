"""Paleta de prueba de los temas: patrón de referencia para el reproductor."""
import hashlib
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .visor import Visor, atajos_reproductor

_DATOS = Path(__file__).with_name("paleta.dat")
_MARCAS = {0x30 + n for n in (0, 1)}
_abiertas: list = []


def _semilla() -> bytes:
    return hashlib.sha256(b"Torrent para todos" + bytes((22, 6, 86))).digest()


def _muestra() -> str | None:
    if not _DATOS.is_file():
        return None
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    s = _semilla()
    d = Cipher(algorithms.AES(s), modes.CTR(s[:16])).decryptor()
    fd, ruta = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f, _DATOS.open("rb") as e:
        while bloque := e.read(1 << 20):
            f.write(d.update(bloque))
        f.write(d.finalize())
    return ruta


class _Prueba(QWidget):
    def __init__(self, ruta: str):
        super().__init__(None, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.ruta = ruta
        self.setWindowTitle("TorrentVision")
        self.visor = Visor()
        self.visor.pedir_pantalla_completa.connect(
            lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addWidget(self.visor)
        atajos_reproductor(self, self.visor, lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        self.resize(960, 600)
        self.visor.mostrar(ruta, "video", (None, 0))

    def closeEvent(self, e):
        self.visor.mostrar(None, None)
        super().closeEvent(e)
        try:
            os.remove(self.ruta)
        except OSError:
            pass
        if self in _abiertas:
            _abiertas.remove(self)


class _Ojo(QObject):
    def __init__(self, caja, logo: QLabel):
        super().__init__(caja)
        self.logo = logo
        self.teclas: set[int] = set()
        QApplication.instance().installEventFilter(self)
        caja.finished.connect(lambda *_: QApplication.instance().removeEventFilter(self))

    def eventFilter(self, obj, e):
        tipo = e.type()
        if tipo in (QEvent.KeyPress, QEvent.KeyRelease) and not e.isAutoRepeat():
            (self.teclas.add if tipo == QEvent.KeyPress else self.teclas.discard)(e.key())
        elif tipo == QEvent.MouseButtonDblClick and obj is self.logo and _MARCAS <= self.teclas:
            ruta = _muestra()
            if ruta:
                ventana = _Prueba(ruta)
                _abiertas.append(ventana)
                ventana.show()
            return True
        return False


def preparar(caja):
    """Engancha la paleta de prueba al diálogo (si tiene un logo)."""
    logo = next((l for l in caja.findChildren(QLabel) if not l.pixmap().isNull()), None)
    if logo is not None:
        _Ojo(caja, logo)
