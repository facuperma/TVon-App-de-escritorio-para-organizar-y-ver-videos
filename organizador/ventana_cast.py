"""Panel de Chromecast: elegir la tele, mandarle el video abierto y manejarla."""
import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from .chromecast import Transmisor, buscar_ffmpeg

ROL = Qt.UserRole


def _tiempo(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 3600}:{s // 60 % 60:02}:{s % 60:02}" if s >= 3600 else f"{s // 60}:{s % 60:02}"


class VentanaCast(QWidget):
    def __init__(self, transmisor: Transmisor, video_actual):
        """video_actual: devuelve (ruta, posición en ms, subtítulo o None) del video abierto, o None."""
        super().__init__(None, Qt.Window)
        self.t = transmisor
        self.video_actual = video_actual
        self.setWindowTitle("📺 Chromecast — TorrentVision")
        self.resize(460, 420)

        self.lista = QListWidget()
        self.lista.itemDoubleClicked.connect(lambda _: self._transmitir())
        self.btn_buscar = QPushButton("🔄 Buscar")
        self.btn_buscar.clicked.connect(self.t.buscar)
        self.btn_transmitir = QPushButton("📺 Transmitir el video abierto", objectName="primario")
        self.btn_transmitir.clicked.connect(self._transmitir)
        fila = QHBoxLayout()
        fila.addWidget(self.btn_buscar)
        fila.addStretch()
        fila.addWidget(self.btn_transmitir)

        # Controles de la transmisión (se ven mientras se transmite)
        self.lbl_titulo = QLabel(objectName="titulo", wordWrap=True)
        self.barra = QSlider(Qt.Horizontal)
        self.barra.sliderReleased.connect(lambda: self.t.ir_a(self.barra.value()))
        self.lbl_tiempo = QLabel(objectName="pista")
        botones = QHBoxLayout()
        for texto, accion in (("↺ 15", lambda: self.t.adelantar(-15000)), ("⏯", self.t.play_pausa),
                              ("15 ↻", lambda: self.t.adelantar(15000))):
            b = QPushButton(texto)
            b.clicked.connect(accion)
            botones.addWidget(b)
        self.volumen = QSlider(Qt.Horizontal, maximum=100, toolTip="Volumen de la tele")
        self.volumen.sliderReleased.connect(lambda: self.t.volumen(self.volumen.value()))
        botones.addWidget(QLabel("🔊"))
        botones.addWidget(self.volumen, 1)
        btn_detener = QPushButton("⏹ Dejar de transmitir")
        btn_detener.clicked.connect(self.t.detener)
        botones.addWidget(btn_detener)
        self.controles = QWidget()
        capa_c = QVBoxLayout(self.controles)
        capa_c.setContentsMargins(0, 0, 0, 0)
        capa_c.addWidget(self.lbl_titulo)
        capa_c.addWidget(self.barra)
        capa_c.addWidget(self.lbl_tiempo)
        capa_c.addLayout(botones)

        self.estado = QLabel(objectName="pista", wordWrap=True)
        # Casi todo lo que baja por torrent es MKV: el Chromecast lo ve solo si ffmpeg lo convierte
        self.btn_ffmpeg = QPushButton("⚙ Instalar ffmpeg (para mandar MKV, AVI y otros formatos)")
        self.btn_ffmpeg.clicked.connect(self._instalar_ffmpeg)
        self.btn_ffmpeg.setVisible(not buscar_ffmpeg())
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel("Chromecast y teles con Google TV de la red de tu casa:"))
        capa.addWidget(self.lista, 1)
        capa.addLayout(fila)
        capa.addWidget(self.controles)
        capa.addWidget(self.btn_ffmpeg)
        capa.addWidget(self.estado)

        self.t.dispositivos_cambiados.connect(self._dispositivos)
        self.t.estado_cambiado.connect(self._actualizar)
        self.t.mensaje.connect(self.estado.setText)
        self._reloj = QTimer(self, interval=1000, timeout=self._actualizar)
        self._dispositivos(self.t.dispositivos)
        self._actualizar()

    def showEvent(self, evento):
        super().showEvent(evento)
        self._reloj.start()
        if not self.t.disponible():
            self.estado.setText("Falta el componente de Chromecast (pychromecast): reinstalá TorrentVision.")
        elif not self.t.dispositivos and not self.t.buscando:
            self.t.buscar()

    def hideEvent(self, evento):
        super().hideEvent(evento)
        self._reloj.stop()

    def _dispositivos(self, dispositivos: list):
        elegido = self.lista.currentItem().data(ROL) if self.lista.currentItem() else None
        self.lista.clear()
        for d in dispositivos:
            item = QListWidgetItem(f"📺 {d['nombre']}" + (f"  ·  {d['modelo']}" if d["modelo"] else ""))
            item.setData(ROL, d["id"])
            self.lista.addItem(item)
            if d["id"] == elegido or len(dispositivos) == 1:
                self.lista.setCurrentItem(item)

    def _transmitir(self):
        item = self.lista.currentItem()
        if item is None:
            return self.estado.setText("Elegí una tele de la lista (si no aparece, tocá 🔄 Buscar)")
        video = self.video_actual()
        if video is None:
            return self.estado.setText("Primero abrí un video en TorrentVision")
        ruta, posicion, subtitulo = video
        self.t.transmitir(item.data(ROL), ruta, posicion, subtitulo)

    def _instalar_ffmpeg(self):
        """Con winget (viene con Windows 10/11), en una consola a la vista para seguir el progreso."""
        subprocess.Popen(["cmd", "/c", "winget install --id Gyan.FFmpeg -e --accept-source-agreements "
                          "--accept-package-agreements & echo. & echo Listo: ya podes cerrar esta ventana. & pause"],
                         creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        self.estado.setText("Instalando ffmpeg en la ventana negra que se abrió. Al terminar, volvé a transmitir.")

    def _actualizar(self):
        if self.btn_ffmpeg.isVisible() and buscar_ffmpeg():
            self.btn_ffmpeg.hide()
        self.btn_buscar.setEnabled(not self.t.buscando)
        self.btn_buscar.setText("Buscando…" if self.t.buscando else "🔄 Buscar")
        info = self.t.estado()["transmision"] if self.t.transmision else None
        self.controles.setVisible(info is not None)
        if info:
            self.lbl_titulo.setText(f"Transmitiendo a {info['dispositivo']}: {info['titulo']}")
            if not self.barra.isSliderDown():
                self.barra.setMaximum(max(1, info["duracion"]))
                self.barra.setValue(info["posicion"])
            if not self.volumen.isSliderDown():
                self.volumen.setValue(info["volumen"])
            estado = {"pausa": " · en pausa", "cargando": " · cargando…"}.get(info["estado"], "")
            self.lbl_tiempo.setText(f"{_tiempo(info['posicion'])} / {_tiempo(info['duracion'])}{estado}")
