"""Ventana del modo ON: encenderlo, el QR para conectar el celular y los permisos."""
import segno
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QVBoxLayout,
)

from . import inicio_windows
from .remoto import Remoto


def pixmap_qr(texto: str, lado: int = 260) -> QPixmap:
    """El QR dibujado con módulos nítidos, negro sobre blanco (con su margen)."""
    filas = [list(fila) for fila in segno.make(texto, error="m").matrix_iter(border=4)]
    modulo = max(1, lado // len(filas))
    imagen = QImage(modulo * len(filas), modulo * len(filas), QImage.Format_RGB32)
    imagen.fill(QColor("white"))
    p = QPainter(imagen)
    for y, fila in enumerate(filas):
        for x, negro in enumerate(fila):
            if negro:
                p.fillRect(QRectF(x * modulo, y * modulo, modulo, modulo), QColor("black"))
    p.end()
    return QPixmap.fromImage(imagen)


def hace(segundos: float | None) -> str:
    if segundos is None:
        return "sin conectarse desde que se abrió TorrentVision"
    if segundos < 10:
        return "conectado ahora"
    if segundos < 3600:
        return f"visto hace {int(segundos // 60) or 1} min"
    return f"visto hace {int(segundos // 3600)} h"


class DialogoOn(QDialog):
    def __init__(self, remoto: Remoto, parent=None):
        super().__init__(parent)
        self.remoto = remoto
        self.setWindowTitle("ON — Manejar TorrentVision desde el celular")
        self.setMinimumWidth(520)

        self.btn_interruptor = QPushButton(objectName="interruptor", checkable=True)
        self.btn_interruptor.clicked.connect(self._alternar)
        self.lbl_estado = QLabel(wordWrap=True)
        self.lbl_qr = QLabel(alignment=Qt.AlignCenter)
        self.lbl_url = QLabel(alignment=Qt.AlignCenter, textInteractionFlags=Qt.TextSelectableByMouse)
        self.lbl_pasos = QLabel(wordWrap=True, objectName="pista")
        # Un paso por párrafo, con aire entre uno y otro (abajo del QR se leía todo junto)
        paso = "<p style='margin: 0 0 10px 0;'>{}</p>"
        self.lbl_pasos.setText("".join(paso.format(t) for t in (
            "<b>1.</b> Conectá el celular a la <b>misma red wifi</b> que esta PC.",
            "<b>2.</b> <b>Con la app:</b> tocá <b>Escanear el código QR</b>.",
            "<b>3.</b> <b>Sin la app:</b> escaneá el código con la cámara: te ofrece bajar la app o seguir en el navegador.",
            "<b>4.</b> En el navegador, si Chrome avisa «La conexión no es privada», tocá "
            "<b>Configuración avanzada → Continuar</b> (la conexión va cifrada).",
            "El código sirve <b>una sola vez</b>. Si Windows pregunta por el firewall, tocá <b>Permitir</b>.",
        )))
        self.lbl_huella = QLabel(wordWrap=True, objectName="pista", textInteractionFlags=Qt.TextSelectableByMouse)
        self.btn_remoto = QPushButton(checkable=True)
        self.btn_remoto.toggled.connect(self._mostrar)
        self.lbl_remoto = QLabel(wordWrap=True, objectName="pista", openExternalLinks=True)

        self.chk_pantalla = QCheckBox("Permitir compartir la pantalla de la PC con el celular")
        self.chk_control = QCheckBox("Permitir manejar el mouse y el teclado desde el celular (touchpad y teclado)")
        self.chk_inicio = QCheckBox("Encender ON cada vez que se abre TorrentVision (así los celulares vinculados "
                                    "se reconectan solos)")
        self.chk_pantalla.setChecked(remoto.permite_pantalla)
        self.chk_control.setChecked(remoto.permite_control)
        self.chk_inicio.setChecked(remoto.al_iniciar)
        self.chk_pantalla.toggled.connect(lambda v: self._opcion("on_pantalla", v))
        self.chk_control.toggled.connect(lambda v: self._opcion("on_control", v))
        self.chk_inicio.toggled.connect(lambda v: remoto.guardar_opcion("on_activo", v))
        # Con esto el celular siempre encuentra a TVon (aunque no lo hayas abierto) y puede abrirlo
        self.chk_windows = QCheckBox("Arrancar TorrentVision con Windows, escondido junto al reloj y con ON encendido")
        self.chk_windows.setToolTip("Así el celular siempre puede conectarse y abrir TorrentVision en la PC.\n"
                                    "Cerrar la ventana con ON encendido también lo deja junto al reloj.")
        self.chk_windows.setChecked(inicio_windows.activo())
        self.chk_windows.setEnabled(inicio_windows.DISPONIBLE)
        self.chk_windows.toggled.connect(self._arrancar_con_windows)
        grupo_opciones = QGroupBox("Opciones")
        capa_opciones = QVBoxLayout(grupo_opciones)
        for chk in (self.chk_pantalla, self.chk_control, self.chk_inicio, self.chk_windows):
            capa_opciones.addWidget(chk)

        self.lista_celulares = QListWidget()
        self.lista_celulares.setMaximumHeight(110)
        self.lista_celulares.setToolTip("Un celular vinculado se reconecta solo, sin volver a escanear el QR.\n"
                                        "Queda como dispositivo de confianza hasta que lo desvincules (o pase un año sin usarse).")
        self.lista_celulares.currentItemChanged.connect(lambda *_: self._elegido_cambiado())
        self.btn_desvincular = QPushButton("Desvincular")
        self.btn_desvincular.setToolTip("Ese celular tiene que volver a escanear el código para entrar")
        self.btn_desvincular.setEnabled(False)
        self.btn_desvincular.clicked.connect(self._desvincular)
        btn_desconectar = QPushButton("Desvincular todos")
        btn_desconectar.setToolTip("Los celulares tienen que volver a escanear el código")
        btn_desconectar.clicked.connect(remoto.desconectar_todos)
        btn_codigo = QPushButton("Cambiar el código QR")
        btn_codigo.setToolTip("Hace un código nuevo. Los celulares ya conectados siguen conectados")
        btn_codigo.clicked.connect(remoto.cambiar_codigo)
        grupo_celulares = QGroupBox("Dispositivos vinculados")
        capa_celulares = QVBoxLayout(grupo_celulares)
        capa_celulares.addWidget(self.lista_celulares)
        fila = QHBoxLayout()
        fila.addStretch()
        fila.addWidget(btn_codigo)
        fila.addWidget(self.btn_desvincular)
        fila.addWidget(btn_desconectar)
        capa_celulares.addLayout(fila)

        capa = QVBoxLayout(self)
        capa.addWidget(self.btn_interruptor)
        capa.addWidget(self.lbl_estado)
        capa.addWidget(self.lbl_qr)
        capa.addWidget(self.lbl_url)
        capa.addWidget(self.lbl_pasos)
        capa.addWidget(self.lbl_huella)
        capa.addWidget(self.btn_remoto)
        capa.addWidget(self.lbl_remoto)
        capa.addWidget(grupo_opciones)
        capa.addWidget(grupo_celulares)

        remoto.estado_cambiado.connect(self._mostrar)
        # «Visto hace…» se actualiza solo
        self._reloj = QTimer(self, interval=5000, timeout=self._mostrar_celulares)
        self._reloj.start()
        self._mostrar()

    def showEvent(self, evento):
        super().showEvent(evento)
        QTimer.singleShot(0, self._dentro_de_la_pantalla)

    def _opcion(self, clave: str, activa: bool):
        self.remoto.guardar_opcion(clave, activa)

    def _arrancar_con_windows(self, activa: bool):
        try:
            inicio_windows.activar(activa)
        except OSError as e:
            QMessageBox.warning(self, "Arrancar con Windows", f"No se pudo cambiar:\n{e}")
            self.chk_windows.blockSignals(True)
            self.chk_windows.setChecked(inicio_windows.activo())
            self.chk_windows.blockSignals(False)

    def _alternar(self):
        if self.remoto.activo:
            self.remoto.detener()
        else:
            self.remoto.iniciar()

    def _mostrar(self):
        activo = self.remoto.activo
        self.btn_interruptor.setChecked(activo)
        self.btn_interruptor.setText("● ON encendido — tocá para apagar" if activo else "○ OFF — tocá para encender")
        self.lbl_qr.setVisible(activo)
        self.lbl_url.setVisible(activo)
        self.lbl_pasos.setVisible(activo)
        self.lbl_huella.setVisible(activo)
        self.lbl_huella.setText(f"🔒 Huella del certificado (SHA-256): <b>{self.remoto.huella_certificado}</b>")
        self.btn_remoto.setVisible(activo)
        self.lbl_remoto.setVisible(activo)
        if activo:
            remota = self.remoto.url_remota()
            fuera = self.btn_remoto.isChecked()
            self.btn_remoto.setText("🏠 Volver al código para la wifi de casa" if fuera else "🌍 Usarlo fuera de casa…")
            if fuera and remota:
                self.lbl_estado.setText("Para fuera de casa (Tailscale): escaneá este código con el celular "
                                        "estando conectado a Tailscale. Queda como otra conexión, aparte de la de casa:")
                url, url_emparejar = remota, f"{remota}{self.remoto.consulta_emparejar()}"
            else:
                self.lbl_estado.setText("Usarlo fuera de casa:" if fuera else "Escaneá este código con el celular:")
                url, url_emparejar = self.remoto.url, self.remoto.url_emparejar
            qr = pixmap_qr(url_emparejar)
            self.lbl_qr.setPixmap(qr)
            self.lbl_qr.setMinimumSize(qr.size())  # que la ventana nunca lo aplaste
            self.lbl_url.setText(f"<span style='color:#9fc2ff'>{url}</span>")
            self.lbl_qr.setVisible(not fuera or bool(remota))
            self.lbl_url.setVisible(not fuera or bool(remota))
            self.lbl_pasos.setVisible(not fuera)
            self.lbl_remoto.setVisible(fuera)
            self.lbl_remoto.setText(
                "Tailscale está conectado en esta PC. En el celular instalá la app Tailscale, entrá con la misma "
                "cuenta y dejala conectada: así TorrentVision anda desde cualquier lado, con la conexión cifrada.<br>"
                "Si no conecta, permití TorrentVision también en redes públicas en el Firewall de Windows." if remota else
                "Para manejar TorrentVision desde fuera de casa hace falta <a href='https://tailscale.com/download' "
                "style='color:#9fc2ff'>Tailscale</a> (gratis): una red privada y cifrada entre tus dispositivos.<br>"
                "1. Instalalo en esta PC y en el celular (Play Store) y entrá con la misma cuenta en los dos.<br>"
                "2. Volvé a abrir esta ventana: aparece el código para fuera de casa.<br>"
                "No abras el puerto de TorrentVision en el router: TorrentVision rechaza conexiones que no vengan de tu casa "
                "o de Tailscale.")
        elif self.remoto.error:
            self.lbl_estado.setText(f"<span style='color:#ff8080'>No se pudo encender: {self.remoto.error}</span>")
        else:
            self.lbl_estado.setText(
                "Con ON encendido, desde el celular manejás TorrentVision: la biblioteca, el reproductor, la cola, "
                "los subtítulos, las categorías y las descargas. Y si hace falta, ves la pantalla de la PC y "
                "la manejás con el dedo.")
        self._mostrar_celulares()
        # adjustSize() deja la ventana en 2/3 de la pantalla y aplastaba el QR: se usa el alto que pide
        alto = min(self.sizeHint().height(), self.screen().availableGeometry().height())
        self.resize(max(self.sizeHint().width(), self.minimumWidth()), alto)
        self._dentro_de_la_pantalla()

    def _dentro_de_la_pantalla(self):
        """Al encender ON la ventana crece hacia abajo: se la corre para que el QR no quede cortado."""
        if not self.isVisible():
            return
        pantalla = self.screen().availableGeometry()
        marco = self.frameGeometry()
        x = max(pantalla.left(), min(marco.left(), pantalla.right() - marco.width() + 1))
        y = max(pantalla.top(), min(marco.top(), pantalla.bottom() - marco.height() + 1))
        if (x, y) != (marco.left(), marco.top()):
            self.move(x, y)

    def _mostrar_celulares(self):
        # Se rearma cada 5 s: el elegido tiene que seguir elegido
        elegido = self.lista_celulares.currentItem()
        huella = elegido.data(Qt.UserRole) if elegido else None
        self.lista_celulares.blockSignals(True)
        self.lista_celulares.clear()
        celulares = self.remoto.celulares()
        for c in celulares:
            item = QListWidgetItem(f"📱 {c['nombre']} — {hace(c['visto'])} · vinculado el {c['creada']} "
                                   f"· vence el {c['vence']} si no se usa")
            item.setData(Qt.UserRole, c["huella"])
            self.lista_celulares.addItem(item)
            if c["huella"] == huella:
                self.lista_celulares.setCurrentItem(item)
        if not celulares:
            self.lista_celulares.addItem("Ninguno todavía")
        self.lista_celulares.blockSignals(False)
        self._elegido_cambiado()

    def _elegido_cambiado(self):
        item = self.lista_celulares.currentItem()
        self.btn_desvincular.setEnabled(bool(item and item.data(Qt.UserRole)))

    def _desvincular(self):
        item = self.lista_celulares.currentItem()
        huella = item.data(Qt.UserRole) if item else None
        if not huella:
            return
        nombre = item.text().split(" — ")[0].removeprefix("📱 ")
        if QMessageBox.question(self, "Desvincular", f"¿Desvincular «{nombre}»?\n"
                                "Para volver a usarlo tiene que escanear el código QR.") == QMessageBox.Yes:
            self.remoto.desvincular(huella)
