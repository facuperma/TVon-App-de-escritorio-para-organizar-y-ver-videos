"""Configuración → Apariencia: la galería de temas, con una vista previa de cada uno. Se aplican al tocarlos."""
import re

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout

from .temas import TEMAS, Tema

ROL = Qt.UserRole


def pincel(qss: str, rect: QRectF) -> QBrush:
    """Un color o un «qlineargradient(...)» de la hoja de estilo, para pintarlo en la vista previa."""
    if not qss.startswith("qlineargradient"):
        return QBrush(QColor(qss))
    horizontal = "x2:1, y2:0" in qss
    g = QLinearGradient(rect.topLeft(), rect.topRight() if horizontal else rect.bottomLeft())
    for parada, color in re.findall(r"stop:([\d.]+)\s+(#[0-9a-fA-F]{6})", qss):
        g.setColorAt(float(parada), QColor(color))
    return QBrush(g)


def vista_previa(t: Tema, ancho: int = 236, alto: int = 140) -> QPixmap:
    """Una ventanita de TorrentVision dibujada con los colores del tema."""
    pm = QPixmap(ancho, alto)
    pm.fill(QColor(t.fondo))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r = min(t.radio, 8)
    barra = QRectF(0, 0, ancho, 22)
    p.fillRect(barra, pincel(t.barra, barra))
    p.setFont(QFont(t.letra, 7))
    p.setPen(QColor("#ffffff" if t.id in ("luna", "noventa") else t.texto))
    p.drawText(QPointF(8, 15), "🎞 Torrents  📱 ON  🎨")
    lcd = QRectF(0, 22, ancho, 16)
    p.fillRect(lcd, QColor(t.lcd_fondo))
    p.setPen(QColor(t.lcd_texto))
    p.setFont(QFont(t.lcd_letra, 7, QFont.Bold))
    p.drawText(QPointF(8, 34), "▶ Una película (1999)  1:23")
    # Panel izquierdo con categorías y la lista
    izq = QRectF(6, 44, 62, alto - 50)
    p.setPen(QColor(t.borde))
    p.setBrush(QColor(t.panel))
    p.drawRoundedRect(izq, r, r)
    for i in range(4):
        fila = QRectF(10, 50 + i * 14, 54, 10)
        if i == 1:
            p.fillRect(fila, QColor(t.seleccion))
        p.fillRect(QRectF(13, 54 + i * 14, 30 + (i * 7) % 18, 3), QColor("#ffffff" if i == 1 else t.tenue))
    centro = QRectF(74, 44, 80, alto - 50)
    p.setBrush(QColor(t.panel))
    p.drawRoundedRect(centro, r, r)
    for i in range(6):
        p.fillRect(QRectF(80, 52 + i * 12, 40 + (i * 11) % 28, 3), QColor(t.texto if i != 2 else t.acento))
    # Reproductor y botones
    video = QRectF(160, 44, ancho - 166, 52)
    p.fillRect(video, QColor("#000000"))
    p.setPen(QColor(t.acento))
    p.drawLine(QPointF(164, 102), QPointF(ancho - 10, 102))
    p.setBrush(QColor(t.acento))
    p.drawEllipse(QPointF(190, 102), 3, 3)
    for i, ancho_b in enumerate((20, 20, 26)):
        x = 160 + sum((20, 20, 26)[:i]) + i * 4
        b = QRectF(x, 110, ancho_b, 16)
        p.setPen(QColor(t.boton_borde))
        p.setBrush(pincel(t.boton, b))
        p.drawRoundedRect(b, min(r, 6), min(r, 6))
    p.end()
    return pm


class VentanaApariencia(QDialog):
    elegido = Signal(str, bool)  # id del tema, animaciones

    def __init__(self, actual: str, animada: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Apariencia — TorrentVision")
        self.resize(820, 620)
        self.lista = QListWidget(viewMode=QListWidget.IconMode, movement=QListWidget.Static,
                                 resizeMode=QListWidget.Adjust, spacing=10, wordWrap=True)
        self.lista.setIconSize(QSize(236, 140))
        self.lista.setGridSize(QSize(262, 196))
        for t in TEMAS:
            item = QListWidgetItem(QIcon(vista_previa(t)), f"{t.nombre}\n{t.epoca}")
            item.setData(ROL, t.id)
            item.setToolTip(t.descripcion)
            self.lista.addItem(item)
            if t.id == actual:
                self.lista.setCurrentItem(item)
        self.lista.currentItemChanged.connect(lambda *_: self._elegir())
        self.descripcion = QLabel(wordWrap=True, objectName="pista")
        self.chk_animada = QCheckBox("Animaciones en la banda de arriba (la pantallita con el título siempre se ve)")
        self.chk_animada.setChecked(animada)
        self.chk_animada.toggled.connect(lambda *_: self._elegir())
        cerrar = QPushButton("Listo", objectName="primario")
        cerrar.clicked.connect(self.accept)
        abajo = QHBoxLayout()
        abajo.addWidget(self.chk_animada, 1)
        abajo.addWidget(cerrar)
        capa = QVBoxLayout(self)
        titulo = QLabel("Elegí cómo se ve TorrentVision. Se aplica al tocarlo; el celular tiene los mismos temas "
                        "en su ⚙ Apariencia.", wordWrap=True)
        capa.addWidget(titulo)
        capa.addWidget(self.lista, 1)
        capa.addWidget(self.descripcion)
        capa.addLayout(abajo)
        self._mostrar_descripcion()

    def _mostrar_descripcion(self):
        item = self.lista.currentItem()
        t = next((x for x in TEMAS if item and x.id == item.data(ROL)), TEMAS[0])
        self.descripcion.setText(f"<b>{t.nombre}</b> · {t.epoca}<br>{t.descripcion}")

    def _elegir(self):
        item = self.lista.currentItem()
        if item is None:
            return
        self._mostrar_descripcion()
        self.elegido.emit(item.data(ROL), self.chk_animada.isChecked())
