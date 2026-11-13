"""Panel que muestra una imagen o reproduce un video con sus controles y subtítulos."""
import math
import time
import re
from pathlib import Path

from PySide6.QtCore import QLocale, QPoint, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QBrush, QColor, QConicalGradient, QCursor, QFont, QFontMetrics, QKeySequence, QPainter, QPainterPath, QPen, QPixmap,
    QShortcut,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaMetaData, QMediaPlayer, QVideoSink
from PySide6.QtWidgets import (
    QCheckBox,
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton,
    QSizePolicy, QSlider, QSpinBox, QStackedWidget, QStyle, QStyleOptionSlider, QToolButton, QToolTip,
    QVBoxLayout, QWidget,
)

from . import sincronia
from .db import RETOMAR_DESDE_MS
from .tareas import en_segundo_plano
from .subtitulos import Subtitulos, buscar_junto_a, descripcion, subtitulos_junto_a

TAMANOS_SUB = [("Chico", 0.75), ("Normal", 1.0), ("Grande", 1.3), ("Muy grande", 1.6)]

# Cómo arranca un video al mostrarlo
REPRODUCIR = "reproducir"
VISTA_PREVIA = "vista_previa"   # un cuadro de muestra, hasta que se aprieta reproducir
SI_ES_LARGO = "si_es_largo"     # vista previa, salvo que dure más que DURACION_LARGA_MS
DURACION_LARGA_MS = 3_600_000
# Volumen con el que arranca TVon (antes 70 %: ahora 20 puntos menos)
VOLUMEN_INICIAL = 50

LOGO = Path(__file__).parent / "icono.png"

# Líneas que los sitios agregan al final de los subtítulos: no son diálogo
PUBLICIDAD_SUB = re.compile(
    r"(?i)opensubtitles|subdivx|addic7ed|www\.|\.com\b|\.org\b|\.net\b|subt[ií]tul|subtitle|"
    r"traduc|sincroniza|synced|corrected|ripped|advertise|support us")


def texto_sincronia(ms: int) -> str:
    """-1500 -> «1,5 s antes», 300 -> «0,3 s después», 0 -> «sincronizados»."""
    if not ms:
        return "sincronizados"
    segundos = f"{abs(ms) / 1000:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{segundos} s {'después' if ms > 0 else 'antes'}"


def atajos_reproductor(ventana: QWidget, visor: "Visor", alternar_completa):
    """Atajos de teclado del reproductor, propios de cada ventana."""
    for tecla, accion in (
        ("Space", visor.alternar_play),
        ("Right", lambda: visor.adelantar(5000)),
        ("Left", lambda: visor.adelantar(-5000)),
        ("Shift+Right", lambda: visor.adelantar(15000)),
        ("Shift+Left", lambda: visor.adelantar(-15000)),
        ("F", alternar_completa),
        # La ventana principal decide (puede estar en su modo Fullscreen); las otras, como siempre
        ("Escape", lambda: ventana.al_escape() if hasattr(ventana, "al_escape")
         else ventana.isFullScreen() and alternar_completa()),
        # Como en VLC: G muestra los subtítulos antes, H después
        ("G", lambda: visor.ajustar_retraso(-100)),
        ("H", lambda: visor.ajustar_retraso(100)),
        ("N", visor.siguiente_capitulo),
        ("I", visor.saltar_intro),
        ("Home", lambda: visor.ir_a(0)),
    ):
        QShortcut(QKeySequence(tecla), ventana).activated.connect(accion)


def formato_tiempo(ms: int) -> str:
    s = ms // 1000
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def texto_progreso(progreso: tuple[int, int, bool] | None) -> str:
    """Columna «Visto»: ✓, dónde quedó o vacío."""
    if not progreso:
        return ""
    posicion, duracion, visto = progreso
    if visto:
        return "✓"
    if posicion >= RETOMAR_DESDE_MS and duracion:
        return f"{posicion * 100 // duracion} % · {formato_tiempo(posicion)}"
    return ""


def _envolver(texto: str, fm: QFontMetrics, ancho: float) -> list[str]:
    lineas = []
    for parrafo in texto.split("\n"):
        actual = ""
        for palabra in parrafo.split():
            prueba = f"{actual} {palabra}".strip()
            if actual and fm.horizontalAdvance(prueba) > ancho:
                lineas.append(actual)
                actual = palabra
            else:
                actual = prueba
        lineas.append(actual)
    return lineas


class PantallaVideo(QWidget):
    """Dibuja los cuadros del video, los subtítulos con contorno y avisos en pantalla."""
    doble_clic = Signal()
    clic = Signal()
    mouse_movido = Signal()

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        # Tocar el video le saca el foco al buscador: así Espacio pausa en vez de escribir
        self.setFocusPolicy(Qt.ClickFocus)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.portada = False  # vista previa: dibuja el botón de reproducir encima
        self._frame = None
        self._texto = ""
        self._osd = ""
        self.escala_sub = 1.0
        self.panel: QWidget | None = None  # aviso flotante abajo a la derecha
        self.boton_intro: QWidget | None = None  # «Saltar intro», abajo a la izquierda
        self._timer_osd = QTimer(self, singleShot=True, interval=1500)
        self._timer_osd.timeout.connect(lambda: self._set_osd(""))
        self._aviso: tuple[str, str] | None = None
        self._timer_aviso = QTimer(self, singleShot=True)
        self._timer_aviso.timeout.connect(lambda: (setattr(self, "_aviso", None), self.update()))
        # El clic simple espera por si llega el segundo de un doble clic (pantalla completa),
        # así el doble clic no pausa y reanuda de paso
        self._timer_clic = QTimer(self, singleShot=True, interval=QApplication.doubleClickInterval())
        self._timer_clic.timeout.connect(self.clic)

    def set_frame(self, frame):
        self._frame = frame
        self.update()

    def set_texto(self, texto: str):
        if texto != self._texto:
            self._texto = texto
            self.update()

    def mostrar_osd(self, texto: str):
        self._set_osd(texto)
        self._timer_osd.start()

    def mostrar_aviso(self, titulo: str, detalle: str = "", segundos: float = 12):
        """Un aviso importante: grande, en el medio de arriba, con borde ámbar, y que dura varios segundos."""
        self._aviso = (titulo, detalle)
        self._timer_aviso.start(int(segundos * 1000))
        self.update()

    def _set_osd(self, texto: str):
        self._osd = texto
        self.update()

    def limpiar(self):
        self._frame = None
        self._texto = ""
        self.update()

    def cuadro(self):
        """El cuadro que se está mostrando, como QImage (o None)."""
        if self._frame is None or not self._frame.isValid():
            return None
        img = self._frame.toImage()
        return None if img.isNull() else img

    def colocar_panel(self):
        if self.panel is not None:
            self.panel.adjustSize()
            self.panel.move(self.width() - self.panel.width() - 24, self.height() - self.panel.height() - 24)
        if self.boton_intro is not None:
            self.boton_intro.adjustSize()
            self.boton_intro.move(32, self.height() - self.boton_intro.height() - 40)

    def resizeEvent(self, e):
        self.colocar_panel()

    def mouseDoubleClickEvent(self, e):
        self._timer_clic.stop()
        self.doble_clic.emit()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._timer_clic.start()

    def mouseMoveEvent(self, e):
        self.mouse_movido.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        zona = QRectF(self.rect())
        if self._frame is not None and self._frame.isValid():
            img = self._frame.toImage()
            if not img.isNull():
                tam = img.size().scaled(self.size(), Qt.KeepAspectRatio)
                zona = QRectF((self.width() - tam.width()) / 2, (self.height() - tam.height()) / 2,
                              tam.width(), tam.height())
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                p.drawImage(zona, img)
        p.setRenderHint(QPainter.Antialiasing)
        if self.portada:
            self._dibujar_portada(p)
        elif self._texto:
            self._dibujar_subtitulo(p, zona)
        if self._osd:
            self._dibujar_osd(p)
        if self._aviso:
            self._dibujar_aviso(p)

    def _dibujar_subtitulo(self, p: QPainter, zona: QRectF):
        fuente = QFont(self.font())
        fuente.setPixelSize(max(14, int(zona.height() * 0.055 * self.escala_sub)))
        fuente.setWeight(QFont.DemiBold)
        fm = QFontMetrics(fuente)
        lineas = _envolver(self._texto, fm, zona.width() * 0.9)
        contorno = QPen(QColor(0, 0, 0, 230), max(2.0, fuente.pixelSize() / 7),
                        Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        y = zona.bottom() - zona.height() * 0.06 - fm.descent()
        for linea in reversed(lineas):
            camino = QPainterPath()
            x = zona.center().x() - fm.horizontalAdvance(linea) / 2
            camino.addText(x, y, fuente, linea)
            p.strokePath(camino, contorno)
            p.fillPath(camino, QColor("white"))
            y -= fm.lineSpacing()

    def _dibujar_portada(self, p: QPainter):
        p.fillRect(self.rect(), QColor(0, 0, 0, 90))
        radio = max(28, min(self.width(), self.height()) // 9)
        centro = QPointF(self.width() / 2, self.height() / 2)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(61, 123, 253, 220))
        p.drawEllipse(centro, radio, radio)
        r = radio * 0.45
        p.setBrush(QColor("white"))
        p.drawPolygon([QPointF(centro.x() - r * 0.6, centro.y() - r), QPointF(centro.x() - r * 0.6, centro.y() + r),
                       QPointF(centro.x() + r, centro.y())])
        fuente = QFont(self.font())
        fuente.setPixelSize(max(12, radio // 3))
        p.setFont(fuente)
        p.setPen(QColor("white"))
        p.drawText(QRectF(0, centro.y() + radio + 8, self.width(), radio), Qt.AlignHCenter | Qt.AlignTop,
                   "Clic o Espacio para reproducir")

    def _dibujar_aviso(self, p: QPainter):
        titulo, detalle = self._aviso
        alto_letra = max(16, self.height() // 22)
        f_tit = QFont(self.font()); f_tit.setPixelSize(alto_letra); f_tit.setBold(True)
        f_det = QFont(self.font()); f_det.setPixelSize(max(13, int(alto_letra * 0.66)))
        ancho = min(self.width() - 40, max(420, self.width() * 0.6))
        fm_t, fm_d = QFontMetrics(f_tit), QFontMetrics(f_det)
        lineas = _envolver(detalle, fm_d, ancho - 48) if detalle else []
        alto = 24 + fm_t.height() + (10 + len(lineas) * fm_d.height() if lineas else 0) + 22
        caja = QRectF((self.width() - ancho) / 2, max(16, self.height() * 0.12), ancho, alto)
        p.setPen(QPen(QColor("#ffb020"), 3))
        p.setBrush(QColor(20, 14, 4, 235))
        p.drawRoundedRect(caja, 12, 12)
        p.setFont(f_tit)
        p.setPen(QColor("#ffc640"))
        y = caja.top() + 20
        p.drawText(QRectF(caja.left() + 16, y, ancho - 32, fm_t.height()), Qt.AlignCenter, "⚠  " + titulo)
        y += fm_t.height() + 10
        p.setFont(f_det)
        p.setPen(QColor("white"))
        for linea in lineas:
            p.drawText(QRectF(caja.left() + 24, y, ancho - 48, fm_d.height()), Qt.AlignCenter, linea)
            y += fm_d.height()

    def _dibujar_osd(self, p: QPainter):
        fuente = QFont(self.font())
        fuente.setPixelSize(max(13, self.height() // 30))
        p.setFont(fuente)
        fm = QFontMetrics(fuente)
        caja = QRectF(0, 0, fm.horizontalAdvance(self._osd) + 24, fm.height() + 14)
        caja.moveTopRight(QPointF(self.width() - 16, 16))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 170))
        p.drawRoundedRect(caja, 6, 6)
        p.setPen(QColor("white"))
        p.drawText(caja, Qt.AlignCenter, self._osd)


class ImagenEscalada(QLabel):
    """Etiqueta que reescala la imagen al tamaño disponible."""
    doble_clic = Signal()

    def __init__(self):
        super().__init__(alignment=Qt.AlignCenter)
        self._pixmap = QPixmap()
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def mostrar(self, ruta: str):
        self._pixmap = QPixmap(ruta)
        if self._pixmap.isNull():
            self.setText("No se pudo abrir la imagen")
        self._reescalar()

    def mouseDoubleClickEvent(self, e):
        self.doble_clic.emit()

    def resizeEvent(self, e):
        self._reescalar()

    def _reescalar(self):
        if not self._pixmap.isNull():
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


class LogoAnimado(QWidget):
    """El logo de la pantalla sin archivo, vivo: respira (el brillo sube y baja), flota apenas y una
    estela de luz celeste gira alrededor del anillo. Solo se anima mientras se ve."""

    LADO = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.LADO + 40, self.LADO + 40)
        escala = QApplication.instance().devicePixelRatio()
        self._logo = QPixmap(str(LOGO)).scaled(round(self.LADO * escala), round(self.LADO * escala),
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._logo.setDevicePixelRatio(escala)
        self._t = 0.0
        self._reloj = QTimer(self, interval=33, timeout=self._tic)
        # Efectos que le pone la escena del Protagonista: tamaño, giro (grados) y destello del golpe (0 a 1)
        self.efecto_escala = 1.0
        self.efecto_giro = 0.0
        self.efecto_destello = 0.0

    def showEvent(self, e):
        super().showEvent(e)
        self._reloj.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._reloj.stop()
        if getattr(self, "_reloj_nada", None) is not None:
            self._reloj_nada.stop()

    def _tic(self):
        if self.window().isMinimized():
            return
        self._t += 0.033
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        centro = QPointF(self.width() / 2, self.height() / 2 + 4 * math.sin(self._t * 1.1))
        p.save()
        if self.efecto_escala != 1.0 or self.efecto_giro:
            p.translate(centro)
            p.rotate(self.efecto_giro)
            p.scale(self.efecto_escala, self.efecto_escala)
            p.translate(-centro)
        # El logo, respirando
        p.setOpacity(min(1.0, 0.32 + 0.12 * math.sin(self._t * 1.6) + 0.5 * self.efecto_destello))
        p.drawPixmap(QPointF(centro.x() - self.LADO / 2, centro.y() - self.LADO / 2), self._logo)
        # La estela que gira alrededor del anillo: un arco que se desvanece hacia la cola
        p.setOpacity(1.0)
        radio = self.LADO * 0.335
        caja = QRectF(centro.x() - radio, centro.y() - radio, 2 * radio, 2 * radio)
        angulo = (self._t * 80) % 360
        cola = QConicalGradient(centro, -angulo)
        cola.setColorAt(0.0, QColor(190, 235, 255, 230))
        cola.setColorAt(0.18, QColor(79, 195, 247, 110))
        cola.setColorAt(0.2, QColor(79, 195, 247, 0))
        cola.setColorAt(1.0, QColor(79, 195, 247, 0))
        p.setPen(QPen(QBrush(cola), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(caja, int(-angulo * 16), int(-72 * 16))
        # La «cabeza» del cometa
        cabeza = math.radians(angulo)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(220, 245, 255, 220))
        p.drawEllipse(QPointF(centro.x() + radio * math.cos(cabeza), centro.y() + radio * math.sin(cabeza)), 3, 3)
        p.restore()
        if self.efecto_destello > 0.01:
            # El golpe: un anillo que se abre y rayitas que salen del logo
            d = self.efecto_destello
            apertura = 1.0 - d
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(200, 240, 255, int(220 * d)), 4 * d + 1))
            r = self.LADO * (0.38 + 0.28 * apertura)
            p.drawEllipse(centro, r, r)
            p.setPen(QPen(QColor(255, 230, 140, int(240 * d)), 3, Qt.SolidLine, Qt.RoundCap))
            for i in range(10):
                ang = math.radians(i * 36 + 18)
                desde, hasta = self.LADO * (0.46 + 0.12 * apertura), self.LADO * (0.54 + 0.22 * apertura)
                p.drawLine(QPointF(centro.x() + desde * math.cos(ang), centro.y() + desde * math.sin(ang)),
                           QPointF(centro.x() + hasta * math.cos(ang), centro.y() + hasta * math.sin(ang)))
        p.end()


def _suave(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


class Bienvenida(QWidget):
    """Pantalla sin archivo: el logo de TorrentVision (animado, tenue) sobre el aviso. Si se quiere, el Protagonista
    está apoyado en el logo; de vez en cuando lo empuja, el logo lo empuja de vuelta y lo saca del recuadro, y después
    vuelve caminando (poner_protagonista)."""

    PERIODO = 21.0          # segundos que dura una vuelta de la escena
    ALTO_PROTA, ANCHO_PROTA = 240, 270      # holgado: con la cabeza grande, al girar por el aire se cortaba en el borde

    def __init__(self, texto: str):
        super().__init__(objectName="vacio")
        self.setAttribute(Qt.WA_StyledBackground)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.logo = LogoAnimado(self)
        self.texto = QLabel(texto, self, alignment=Qt.AlignCenter, wordWrap=True)
        self._prota = None
        self._spec: dict | None = None
        self._t = 0.0
        self._ultimo = 0.0
        self._base_logo = (0.0, 0.0)
        self._base_prota = (0.0, 0.0)
        # Se mueve con el tiempo real (no con la cuenta de cuadros) y a lo sumo 30 veces por segundo
        self._reloj = QTimer(self, interval=15, timeout=self._tic)
        self._reloj.setTimerType(Qt.PreciseTimer)
        self._acomodar()

    def setText(self, texto: str):
        self.texto.setText(texto)
        self._acomodar()

    # --- El Protagonista ----------------------------------------------------------------------------------

    def poner_protagonista(self, spec: dict | None, animar: bool = True):
        """spec = cómo es; None = que no aparezca. animar=False: se queda apoyado en el logo, sin moverse."""
        self._spec = spec
        self._animar = animar
        if spec is None:
            if self._prota is not None:
                self._prota.hide()
            self._reloj.stop()
            self._acomodar()
            return
        if self._prota is None:
            from . import vista3d
            self._prota = vista3d.crear(spec, "cuerpo", parent=self, con_pose=False)
            self._prota.setAttribute(Qt.WA_TransparentForMouseEvents)
            self._prota.setFixedSize(self.ANCHO_PROTA, self.ALTO_PROTA)
        else:
            self._prota.poner(spec)
        self._pose(liviano=True, vaiven=0, **self._pose_de_reposo(0.0))
        if self.isVisible() and animar:
            self._arrancar()
        else:
            self._reloj.stop()
            self._acomodar()
            self._logo_quieto()
        self._acomodar()

    # --- BiriBiri nadando por detrás del logo ---------------------------------------------------------------

    ANCHO_NADA, ALTO_NADA = 340, 215

    def poner_nadador(self, spec: dict | None):
        """spec = cómo es; None = que no nade. Cruza la pantalla de lado a lado, por abajo, detrás del logo y del texto."""
        self._nada_activo = spec is not None
        if spec is not None:
            spec = {**spec, "mascota": "ninguna", "interaccion": "ninguna"}
        if spec is None:
            if getattr(self, "_nada", None) is not None:
                self._nada.hide()
            if getattr(self, "_reloj_nada", None) is not None:
                self._reloj_nada.stop()
            return
        if getattr(self, "_nada", None) is None:
            from . import vista3d
            self._nada = vista3d.crear(spec, "cuerpo", parent=self, con_pose=True, lugar="nadando")
            self._nada.setAttribute(Qt.WA_TransparentForMouseEvents)
            self._nada.setFixedSize(self.ANCHO_NADA, self.ALTO_NADA)
            self._nada.pose(liviano=True, vaiven=0.0, sombra=False)
            self._nada_x = -self.ANCHO_NADA
            self._reloj_nada = QTimer(self, interval=33, timeout=self._nadar)
            self._t_nada = time.perf_counter()
        else:
            self._nada.poner(spec)
        # Cruza la pantalla solo si la pose es de nadar o volar; con cualquier otra (la que elegiste) hace su animación
        # en el lugar, abajo a la izquierda
        from . import avatar3d, poses
        pose = poses.resolver(avatar3d.normalizar(spec)["pose"], "nadando")
        self._nada_cruza = pose in ("nadando", "volando")
        if poses.es_horizontal(pose):
            self._nada.setFixedSize(self.ANCHO_NADA, self.ALTO_NADA)
        else:
            self._nada.setFixedSize(190, 240)
        if self.isVisible():
            self._reloj_nada.start()
        self._nadar()

    def _nadar(self):
        nada = getattr(self, "_nada", None)
        if nada is None or not getattr(self, "_nada_activo", True):
            return
        cabe = self.height() >= 300 and self.width() >= 360
        nada.setVisible(cabe)
        if not cabe:
            return
        if not getattr(self, "_nada_cruza", True):
            ancho, alto = nada.width(), nada.height()
            nada.move(round(self.width() * 0.14), round(self.height() - alto - 14))
            nada.lower()
            self.logo.raise_()
            self.texto.raise_()
            return
        ahora = time.perf_counter()
        dt, self._t_nada = min(0.1, ahora - self._t_nada), ahora
        self._nada_x += 55 * dt
        if self._nada_x > self.width():
            self._nada_x = -self.ANCHO_NADA
        y = self.height() * 0.62 + 18 * math.sin(self._nada_x / 70.0)
        nada.move(round(self._nada_x), round(min(y, self.height() - nada.height())))
        nada.lower()
        self.logo.raise_()
        self.texto.raise_()

    def _arrancar(self):
        self._ultimo = time.perf_counter()
        self._reloj.start()

    def showEvent(self, e):
        super().showEvent(e)
        if getattr(self, "_nada", None) is not None and getattr(self, "_nada_activo", True):
            self._reloj_nada.start()
        if self._spec is not None and getattr(self, "_animar", True):
            self._arrancar()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._reloj.stop()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._acomodar()

    def _pose(self, **valores):
        pose = getattr(self._prota, "pose", None)
        if pose:
            pose(**valores)

    # --- Posiciones ---------------------------------------------------------------------------------------

    def _acomodar(self):
        """El logo y el texto en el centro (como antes); el Protagonista a su izquierda, apoyado en el logo."""
        ancho_texto = max(120, min(self.width() - 40, 560))
        self.texto.setFixedWidth(ancho_texto)
        alto_texto = self.texto.heightForWidth(ancho_texto) if self.texto.hasHeightForWidth() else self.texto.sizeHint().height()
        bloque = self.logo.height() + 12 + alto_texto
        arriba = max(0, (self.height() - bloque) / 2)
        centro_x = self.width() / 2
        self._base_logo = (centro_x - self.logo.width() / 2, arriba)
        self.texto.setGeometry(round(centro_x - ancho_texto / 2), round(arriba + self.logo.height() + 12), ancho_texto, alto_texto)
        if self._prota is not None:
            cabe = self._spec is not None and self.height() >= 300 and self.width() >= 360
            self._prota.setVisible(cabe)
            # Apoyado en el borde izquierdo del anillo, con los pies a la altura de la base del logo
            self._base_prota = (centro_x - 92 - self.ANCHO_PROTA / 2,
                                arriba + self.logo.height() / 2 + 82 - self.ALTO_PROTA * 0.96)
        self._mover(0.0, (0.0, 0.0))

    def _mover(self, desplazamiento_logo: float, protagonista: tuple[float, float]):
        self.logo.move(round(self._base_logo[0] + desplazamiento_logo), round(self._base_logo[1]))
        if self._prota is not None and self._prota.isVisible():
            self._prota.move(round(self._base_prota[0] + protagonista[0]), round(self._base_prota[1] + protagonista[1]))

    def _logo_quieto(self):
        self.logo.efecto_escala, self.logo.efecto_giro, self.logo.efecto_destello = 1.0, 0.0, 0.0
        self.logo.update()

    def _pose_de_reposo(self, t: float) -> dict:
        """Apoyado de costado en el logo (de espaldas a él), mirando para el que mira, con una respiración suave."""
        respira = math.sin(t * 1.4)
        return dict(giroMano=-68, mira=64 + 5 * math.sin(t * 0.5), inclinacion=-12 + 1.2 * respira, empuje=0.12,
                    manos=0.0, vuelo=0.0, sombra=True, esc=0.78)      # esc: más chico dentro de la vista, para que entre al girar

    def _tic(self):
        if self.window().isMinimized() or self._prota is None or self._spec is None:
            return
        ahora = time.perf_counter()
        paso = ahora - self._ultimo
        if paso < 0.0285:           # como mucho 30 cuadros por segundo
            return
        self._ultimo = ahora
        self._t += min(paso, 0.2)
        t = self._t
        u = t % self.PERIODO
        bx, by = self._base_prota
        pose = self._pose_de_reposo(t)
        d_logo, d_x, d_y = 0.0, 0.0, 0.0
        escala, giro_logo, destello = 1.0, 0.0, 0.0
        salida_x = -(bx + self.ANCHO_PROTA + 30)           # afuera del recuadro, por la izquierda
        if u < 5.5:                                         # 1) apoyado de costado, de espaldas al logo
            pass
        elif u < 6.7:                                       # 2) se da vuelta, para quedar frente al logo
            k = _suave((u - 5.5) / 1.2)
            pose.update(giroMano=-68 + 150 * k, mira=(64 + 5) * (1 - k) - 18 * k, inclinacion=-12 + 6 * k, empuje=0.12 * (1 - k))
        elif u < 7.6:                                       # 3) toma impulso: se echa un poco para atrás y levanta las manos
            k = _suave((u - 6.7) / 0.9)
            pose.update(giroMano=82, mira=-18, inclinacion=-6 + 10 * k, empuje=0.0, manos=0.85 * k)
            d_x = -6 * k
        elif u < 11.6:                                      # 4) empuja con las dos manos, como algo muy pesado
            k = (u - 7.6) / 4.0
            avance = _suave(k)
            # Se mueve a tirones: el logo cede un poco, se frena y vuelve a ceder
            tirones = avance + 0.045 * math.sin(k * 34) * (1 - abs(2 * k - 1) * 0.3)
            d_logo = 50 * max(0.0, tirones)
            esfuerzo = 1.6 * math.sin(t * 17) * (0.4 + 0.6 * math.sin(math.pi * k))
            pose.update(giroMano=82, mira=-12, inclinacion=-16 + esfuerzo + 3 * math.sin(k * 34), empuje=0.0, manos=1.0)
            d_x = -6 + 0.82 * d_logo + 2.0 * math.sin(t * 17)
            giro_logo = 4 * math.sin(k * 34) * k
            escala = 1.0 - 0.03 * math.sin(math.pi * k)
        elif u < 12.1:                                      # 5) el logo se frena, tiembla, se está cargando…
            k = (u - 11.6) / 0.5
            d_logo = 50 - 6 * k + 2.5 * math.sin(t * 60)
            pose.update(giroMano=82, mira=-12, inclinacion=-16 + 5 * k, empuje=0.0, manos=1.0 - 0.2 * k)
            d_x = -6 + 0.82 * 50 - 6 * k
            escala = 1.0 - 0.10 * k
            giro_logo = 3 * math.sin(t * 60)
        elif u < 14.2:                                      # 6) ¡PAM!: el logo explota hacia atrás y lo manda a volar
            T = 2.1
            k = (u - 12.1) / T
            golpe = min(1.0, (u - 12.1) / 0.12)
            d_logo = 44 - 80 * _suave(min(1.0, (u - 12.1) / 0.18)) + 36 * _suave((u - 12.3) / 1.4)
            escala = 0.90 + 0.42 * math.sin(math.pi * min(1.0, golpe)) if k < 0.1 else 1.0 + 0.12 * math.exp(-5 * (k - 0.1)) * math.cos(26 * (k - 0.1))
            giro_logo = -12 * math.exp(-4 * k) * math.cos(22 * k)
            destello = max(0.0, 1.0 - k * 2.2)
            # Sale volando en arco, girando como una hélice, hacia arriba y a la izquierda
            km = min(1.0, k * 1.1)
            d_x = (-6 + 0.82 * 44) + (salida_x - (-6 + 0.82 * 44)) * (km ** 1.15)
            d_y = -(105 * 4 * km * (1 - km)) + 80 * km * km
            pose.update(giroMano=82 + 700 * km, mira=0, inclinacion=-18 * (1 - km), empuje=0.3, manos=max(0.0, 1.0 - km * 3),
                        vuelo=-1100 * (km ** 0.9), sombra=False)
        elif u < 16.8:                                      # 7) el logo solo, se acomoda (y se «ríe» un poquito)
            k = (u - 14.2) / 2.6
            d_logo = 36 * (1 - _suave(k * 1.6)) * math.cos(k * 9)
            escala = 1.0 + 0.04 * math.sin(k * 18) * (1 - k)
            d_x, d_y = salida_x - 20, -80
            pose.update(sombra=False, vuelo=0.0)
        elif u < 19.8:                                      # 8) vuelve caminando, masajeándose el hombro
            k = _suave((u - 16.8) / 3.0)
            d_x = (salida_x - 20) * (1 - k)
            d_y = -9 * abs(math.sin((u - 16.8) * 5.2)) * (1 - k * 0.8)
            pose.update(giroMano=70 - 138 * k, mira=20 + 40 * k, inclinacion=14 * (1 - k) - 12 * k, empuje=0.12 * k, manos=0.0,
                        vuelo=0.0, sombra=True)
        # (de 19,8 a 21 queda apoyado, como al principio)
        self._pose(vaiven=0, **pose)
        self.logo.efecto_escala, self.logo.efecto_giro, self.logo.efecto_destello = escala, giro_logo, destello
        self._mover(d_logo, (d_x, d_y))


class BarraTiempo(QSlider):
    """La barra del video: clic en cualquier parte salta ahí (y se puede seguir arrastrando);
    al pasar el mouse muestra un cartelito con el minuto de ese punto."""

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setMouseTracking(True)

    def _valor_en(self, x: float) -> int:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        canal = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        manija = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        inicio = canal.x() + manija.width() / 2
        largo = max(1, canal.width() - manija.width())
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                              int(min(max(x - inicio, 0), largo)), largo)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.maximum() > 0:
            v = self._valor_en(e.position().x())
            self.setValue(v)
            self.sliderMoved.emit(v)      # el reproductor salta ahí
        super().mousePressEvent(e)        # la manija ya quedó bajo el mouse: se puede arrastrar

    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        if self.maximum() <= 0:
            return
        x = e.position().x()
        v = self.value() if self.isSliderDown() else self._valor_en(x)
        QToolTip.showText(self.mapToGlobal(QPoint(int(x) - 20, -38)), formato_tiempo(v), self)

    def leaveEvent(self, e):
        QToolTip.hideText()
        super().leaveEvent(e)


class Visor(QWidget):
    pedir_pantalla_completa = Signal()
    # (ruta del video, ruta del subtítulo o None, retraso en ms)
    subtitulos_cambiados = Signal(str, object, int)
    avance_sincronia = Signal(int)  # % del análisis de audio (desde un hilo de fondo)
    # Ruta del capítulo que hay que reproducir a continuación
    reproducir_siguiente = Signal(str)
    # Pide buscar subtítulos en internet para este video (lo resuelve quien usa el visor)
    buscar_subtitulos_online = Signal(str)
    buscar_subtitulos_subdivx = Signal(str)
    # Terminó el video con «Apagar al terminar» marcado
    pedir_apagado = Signal()
    # (ruta del video, posición ms, duración ms): hasta dónde se vio, para retomarlo
    progreso = Signal(str, int, int)
    # Tamaño en píxeles del video que se acaba de abrir (con el primer cuadro)
    tamano_video = Signal(QSize)

    # El aviso del siguiente capítulo aparece cuando falta esto para el final
    AVISO_SIGUIENTE_MS = 5_000
    # Con subtítulos, aparece antes: cuando termina el último diálogo (arrancan los créditos),
    # si después quedan al menos estos milisegundos de video
    CREDITOS_MINIMO_MS = 20_000

    def __init__(self):
        super().__init__()
        # Función (ruta del video) -> ruta del siguiente capítulo o None; la asigna quien usa el visor
        self.buscar_siguiente = None
        self._ruta_siguiente: str | None = None
        self._siguiente_cancelado = False
        # Videos pedidos a mano para después del actual: van antes que el siguiente capítulo
        self.cola: list[str] = []
        self.apagar_al_terminar = False
        self.ruta_video: str | None = None
        self._posicion_pendiente = 0
        self._ultimo_guardado = 0
        self._modo = REPRODUCIR
        self._vista_previa = False
        self._inicio_ms = 0  # desde dónde arranca al salir de la vista previa
        self.subs: Subtitulos | None = None
        self.ruta_sub: str | None = None
        self.retraso_ms = 0
        self._fin_dialogo: int | None = None  # fin del último subtítulo que es diálogo
        self._tamano_avisado = False
        self._es_video = False
        self._modo_completo = False

        self.reproductor = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.reproductor.setAudioOutput(self.audio)
        self.audio.setVolume(VOLUMEN_INICIAL / 100)
        self.sink = QVideoSink(self)
        self.reproductor.setVideoSink(self.sink)
        # Sin esto, al cambiar la salida de Windows (auriculares, parlantes, HDMI)
        # el sonido sigue yendo a la anterior hasta reiniciar TVon
        self._dispositivos = QMediaDevices(self)
        self._dispositivos.audioOutputsChanged.connect(self._salida_audio_cambiada)

        self.pantalla = PantallaVideo()
        self.imagen = ImagenEscalada()
        self.vacio = Bienvenida("Elegí un archivo de la lista")
        self.pila = QStackedWidget()
        for w in (self.vacio, self.imagen, self.pantalla):
            self.pila.addWidget(w)

        # Controles de reproducción
        estilo = self.style()
        self.btn_play = QPushButton(icon=estilo.standardIcon(QStyle.SP_MediaPlay), objectName="play", toolTip="Reproducir / pausar (Espacio o clic en el video)")
        self.btn_stop = QPushButton(icon=estilo.standardIcon(QStyle.SP_MediaStop), toolTip="Detener")
        self.btn_siguiente = QPushButton(icon=estilo.standardIcon(QStyle.SP_MediaSkipForward),
                                         toolTip="Siguiente de la cola o capítulo de la categoría (N)")
        self.btn_atras15 = QPushButton("↺ 15", toolTip="Retroceder 15 segundos (Shift+←)")
        self.btn_adelante15 = QPushButton("15 ↻", toolTip="Adelantar 15 segundos (Shift+→)")
        self.barra = BarraTiempo()
        self.lbl_tiempo = QLabel("0:00 / 0:00")
        self.btn_mute = QPushButton(icon=estilo.standardIcon(QStyle.SP_MediaVolume), toolTip="Silenciar")
        self.volumen = QSlider(Qt.Horizontal, maximum=100, value=VOLUMEN_INICIAL)
        self.volumen.setFixedWidth(60)
        self.lbl_volumen = QLabel(f"{VOLUMEN_INICIAL} %", toolTip="Volumen", objectName="volumen")
        negrita = QFont(self.lbl_volumen.font())
        negrita.setBold(True)  # va en negrita (tema.py)
        self.lbl_volumen.setMinimumWidth(QFontMetrics(negrita).horizontalAdvance("100 %") + 2)
        self.btn_subs = QToolButton(text="CC", toolTip="Subtítulos", popupMode=QToolButton.InstantPopup)
        self.menu_subs = QMenu(self)
        self.menu_subs.aboutToShow.connect(self._armar_menu_subs)
        self.btn_subs.setMenu(self.menu_subs)
        self.btn_completa = QPushButton("⛶", toolTip="Pantalla completa (F o doble clic)")
        self.btn_cola = QToolButton(toolTip="Videos en cola para después de este",
                                    popupMode=QToolButton.InstantPopup)
        self.menu_cola = QMenu(self)
        self.menu_cola.aboutToShow.connect(self._armar_menu_cola)
        self.btn_cola.setMenu(self.menu_cola)

        # Los controles, en dos filas para que no queden apretados: arriba la barra del video con el tiempo; abajo lo
        # esencial (saltos, play, siguiente, volumen, pantalla completa) y el menú «⋯» con todo lo demás (subtítulos,
        # Chromecast, apagar al terminar…). Sin ancho mínimo: la ventana se puede achicar todo lo que se quiera
        self.btn_mas = QToolButton(text="⋯", toolTip="Más opciones: subtítulos, tele, apagar al terminar…",
                                   popupMode=QToolButton.InstantPopup)
        self.menu_mas = QMenu(self)
        self.menu_mas.aboutToShow.connect(self._armar_menu_mas)
        self.btn_mas.setMenu(self.menu_mas)
        self._extras: list[QWidget] = []          # botones que suman otros (Chromecast, apagar…): van en el menú «⋯»
        self.controles = QWidget(objectName="controles")
        self.controles.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        dos_filas = QVBoxLayout(self.controles)
        dos_filas.setContentsMargins(8, 6, 8, 4)
        dos_filas.setSpacing(4)
        fila_tiempo = QHBoxLayout()
        fila_tiempo.setSpacing(10)
        fila_tiempo.addWidget(self.barra, 1)
        fila_tiempo.addWidget(self.lbl_tiempo)
        dos_filas.addLayout(fila_tiempo)
        self._fila_controles = fila = QHBoxLayout()
        fila.setSpacing(6)
        dos_filas.addLayout(fila)
        for w in (self.btn_atras15, self.btn_play, self.btn_adelante15, self.btn_stop, self.btn_siguiente):
            fila.addWidget(w)
        fila.addStretch(1)
        for w in (self.btn_subs, self.btn_mute, self.volumen, self.lbl_volumen, self.btn_cola, self.btn_mas,
                  self.btn_completa):
            fila.addWidget(w)
        self.btn_subs.setObjectName("botonCC")       # «CC»: los subtítulos, a mano (también están en el menú «⋯»)
        self.volumen.setFixedWidth(90)

        # Barra de sincronización, visible con un archivo de subtítulos cargado.
        # En palabras («1,5 s antes») en vez de un retraso con signo, que confunde.
        self.lbl_sub = QLabel()
        self.lbl_sincronia = QLabel(alignment=Qt.AlignCenter, minimumWidth=120)
        self.lbl_sincronia.setToolTip("Cómo salen los subtítulos respecto del archivo original")
        self.barra_subs = QWidget()
        self.barra_subs.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        fila_subs = QHBoxLayout(self.barra_subs)
        fila_subs.setContentsMargins(4, 2, 4, 0)
        fila_subs.setSpacing(4)
        fila_subs.addWidget(self.lbl_sub, 1)
        fila_subs.addWidget(QLabel("Sincronía:"))
        botones = [("◀◀", -500, "Mostrar los subtítulos 0,5 s antes"),
                   ("◀", -100, "Mostrar los subtítulos 0,1 s antes (G)"), (None, 0, ""),
                   ("▶", 100, "Mostrar los subtítulos 0,1 s después (H)"),
                   ("▶▶", 500, "Mostrar los subtítulos 0,5 s después")]
        botones_sinc = []
        for texto, ms, ayuda in botones:
            if texto is None:
                fila_subs.addWidget(self.lbl_sincronia)
                continue
            boton = QPushButton(texto, objectName="chico", toolTip=ayuda)
            boton.clicked.connect(lambda _=False, d=ms: self.ajustar_retraso(d))
            fila_subs.addWidget(boton)
            botones_sinc.append(boton)
        # El número exacto, escrito a mano (Enter para aplicar) o con las flechas / la rueda, de 100 en 100
        self.campo_ms = QSpinBox(minimum=-600_000, maximum=600_000, singleStep=100, suffix=" ms",
                                 keyboardTracking=False, minimumWidth=96)
        self.campo_ms.setToolTip("Retraso en milisegundos: negativo, los subtítulos salen antes; positivo, después.\n"
                                 "Escribí el número que quieras y apretá Enter, o usá las flechas.")
        self.campo_ms.valueChanged.connect(self._campo_ms_cambio)
        fila_subs.insertWidget(fila_subs.indexOf(self.lbl_sincronia) + 1, self.campo_ms)
        self._sincronizando = False
        self.progreso_sincronia = -1  # -1: no se está sincronizando; 0..100: avance del análisis
        self.lbl_cargando = QLabel(objectName="pista")
        self.lbl_cargando.hide()
        self._giro = 0
        self._reloj_giro = QTimer(self, interval=130, timeout=self._girar)
        self.avance_sincronia.connect(self._avance_sincronia)
        fila_subs.insertWidget(fila_subs.indexOf(self.lbl_sub) + 1, self.lbl_cargando, 1)
        btn_auto = QPushButton("🪄 Auto", objectName="chico", toolTip=(
            "Sincroniza solo: compara cuándo se habla en el audio con cuándo hay diálogos en el subtítulo.\n"
            "Tarda un rato según el largo de la película (hace falta ffmpeg)."))
        btn_auto.clicked.connect(lambda: self.sincronizar_automatico())
        btn_sinc_ahora = QPushButton("🎯 Ahora", objectName="chico", toolTip=(
            "Tocalo justo cuando alguien empieza a hablar:\n"
            "el subtítulo más cercano se acomoda a ese momento"))
        btn_sinc_ahora.clicked.connect(self.sincronizar_ahora)
        btn_cero = QPushButton("↺", objectName="chico", toolTip="Sin ajuste (como viene el archivo)")
        btn_cero.clicked.connect(lambda: self.fijar_retraso(0))
        self.btn_auto = btn_auto
        fila_subs.addWidget(btn_auto)
        fila_subs.addWidget(btn_sinc_ahora)
        fila_subs.addWidget(btn_cero)
        botones_sinc += [btn_auto, btn_sinc_ahora, btn_cero]

        # Aviso de siguiente capítulo, sobre el video
        self.panel_sig = QFrame(self.pantalla, objectName="panelSiguiente")
        self.lbl_sig_cuenta = QLabel(objectName="titulo")
        self.lbl_sig_nombre = QLabel()
        btn_ahora = QPushButton("▶ Reproducir ahora")
        btn_cancelar = QPushButton("Cancelar")
        btn_ahora.clicked.connect(self.siguiente_ahora)
        btn_cancelar.clicked.connect(self.cancelar_siguiente)
        capa_sig = QVBoxLayout(self.panel_sig)
        capa_sig.setContentsMargins(16, 12, 16, 12)
        capa_sig.addWidget(self.lbl_sig_cuenta)
        capa_sig.addWidget(self.lbl_sig_nombre)
        fila_sig = QHBoxLayout()
        fila_sig.addWidget(btn_ahora)
        fila_sig.addWidget(btn_cancelar)
        capa_sig.addLayout(fila_sig)
        self.panel_sig.hide()
        self.pantalla.panel = self.panel_sig

        # «⏭ Saltar intro»: abajo a la izquierda mientras pasa la intro de un capítulo (la detecta intro.py)
        self.intro: tuple[int, int] | None = None    # (inicio, fin) en ms, del video abierto
        self.al_abrir_video = None                    # función (ruta) que pide la intro; la asigna la ventana
        self.btn_intro = QPushButton("⏭  Saltar intro", self.pantalla, objectName="saltarIntro")
        self.btn_intro.setCursor(Qt.PointingHandCursor)
        self.btn_intro.setToolTip("Ir al final de la introducción (tecla I)")
        self.btn_intro.setStyleSheet(
            "QPushButton#saltarIntro { background: rgba(10, 16, 28, 210); color: #ffffff; font-size: 12pt; "
            "font-weight: 600; padding: 10px 22px; border: 2px solid rgba(255, 255, 255, 170); border-radius: 8px; } "
            "QPushButton#saltarIntro:hover { background: rgba(255, 255, 255, 235); color: #0b1220; }")
        self.btn_intro.clicked.connect(self.saltar_intro)
        self.btn_intro.hide()
        self.pantalla.boton_intro = self.btn_intro

        for b in (self.btn_play, self.btn_stop, self.btn_siguiente, self.btn_atras15,
                  self.btn_adelante15, self.btn_mute, self.btn_subs, self.btn_cola,
                  self.btn_completa, *botones_sinc, self.barra, self.volumen, btn_ahora, btn_cancelar):
            b.setFocusPolicy(Qt.NoFocus)

        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        capa.addWidget(self.pila, 1)
        capa.addWidget(self.controles)
        capa.addWidget(self.barra_subs)

        # En pantalla completa los controles se ocultan tras unos segundos sin mover el mouse
        self._timer_ocultar = QTimer(self, singleShot=True, interval=2500)
        self._timer_ocultar.timeout.connect(self._ocultar_controles)

        self.btn_play.clicked.connect(self.alternar_play)
        self.btn_stop.clicked.connect(self.reproductor.stop)
        self.btn_siguiente.clicked.connect(self.siguiente_capitulo)
        self.btn_atras15.clicked.connect(lambda: self.adelantar(-15000))
        self.btn_adelante15.clicked.connect(lambda: self.adelantar(15000))
        self.btn_completa.clicked.connect(self.pedir_pantalla_completa)
        self.pantalla.doble_clic.connect(self.pedir_pantalla_completa)
        self.pantalla.clic.connect(self.alternar_play)
        self.imagen.doble_clic.connect(self.pedir_pantalla_completa)
        self.pantalla.mouse_movido.connect(self._actividad)
        self.btn_mute.clicked.connect(self.alternar_mute)
        self.volumen.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        self.volumen.valueChanged.connect(self._volumen_cambiado)
        self.barra.sliderMoved.connect(self.reproductor.setPosition)
        self.sink.videoFrameChanged.connect(self._nuevo_frame)
        self.sink.subtitleTextChanged.connect(self._texto_pista_interna)
        self.reproductor.positionChanged.connect(self._posicion)
        self.reproductor.durationChanged.connect(self._duracion)
        self.reproductor.playbackStateChanged.connect(self._estado)
        self.reproductor.mediaStatusChanged.connect(self._estado_medio)
        self.reproductor.errorOccurred.connect(lambda _e, msg: self.lbl_tiempo.setText(f"Error: {msg}"))
        self._actualizar_controles()
        self._actualizar_cola()

    # --- Mostrar archivos ---------------------------------------------------

    def agregar_control(self, widget: QWidget):
        """Suma una opción a los controles: va dentro del menú «⋯» (el botón queda escondido y el menú lo usa)."""
        widget.setFocusPolicy(Qt.NoFocus)
        widget.setParent(self.controles)
        widget.hide()
        self._extras.append(widget)

    # Los controles que se pueden esconder desde el menú de desarrollador (nombre: botón)
    def controles_editables(self) -> dict:
        return {"atras15": self.btn_atras15, "play": self.btn_play, "adelante15": self.btn_adelante15, "stop": self.btn_stop,
                "siguiente": self.btn_siguiente, "mute": self.btn_mute, "volumen": self.volumen, "porcentaje": self.lbl_volumen,
                "subs": self.btn_subs, "mas": self.btn_mas, "completa": self.btn_completa}

    def esconder_controles(self, nombres):
        for nombre, w in self.controles_editables().items():
            w.setVisible(nombre not in nombres)

    def _armar_menu_mas(self):
        m = self.menu_mas
        m.clear()
        self.menu_subs.setTitle("💬 Subtítulos")
        m.addMenu(self.menu_subs)
        if self.cola:
            self.menu_cola.setTitle(f"☰ Cola ({len(self.cola)})")
            m.addMenu(self.menu_cola)
        m.addSeparator()
        for w in self._extras:
            if isinstance(w, QCheckBox):
                accion = m.addAction(w.text())
                accion.setCheckable(True)
                accion.setChecked(w.isChecked())
                accion.toggled.connect(w.setChecked)
            else:
                texto = w.text() if hasattr(w, "text") else ""
                if w.toolTip() and len(texto) <= 2:
                    texto = f"{texto}  {w.toolTip()}".strip()
                accion = m.addAction(texto or w.toolTip())
                accion.triggered.connect(w.click)
        m.addSeparator()
        m.addAction("⛶ Pantalla completa\tF", self.pedir_pantalla_completa)

    def mostrar(self, ruta: str | None, tipo: str | None, config_sub: tuple | None = None,
                posicion_ms: int = 0, aviso_vacio: str = "Elegí un archivo de la lista",
                modo: str = REPRODUCIR):
        """config_sub: (ruta del subtítulo o None, retraso ms) guardado para este video,
        o None si nunca se configuró (entonces se buscan subtítulos junto al video).
        posicion_ms: punto desde el que arranca el video.
        modo: REPRODUCIR, VISTA_PREVIA o SI_ES_LARGO."""
        self.guardar_progreso()
        self._reiniciar_siguiente()
        self.reproductor.stop()
        self.reproductor.setSource(QUrl())
        self.pantalla.limpiar()
        self._descartar_subtitulos()
        self.ruta_video = None
        self._es_video = False
        self._tamano_avisado = False
        self._modo = modo
        self._vista_previa = modo != REPRODUCIR
        self.pantalla.portada = False
        self._inicio_ms = posicion_ms
        self._ultimo_guardado = posicion_ms
        self._posicion_pendiente = 0 if self._vista_previa else posicion_ms
        if ruta is None:
            self.vacio.setText(aviso_vacio)
            self.pila.setCurrentWidget(self.vacio)
        elif not Path(ruta).exists():
            self.vacio.setText("El archivo ya no está en esa ubicación")
            self.pila.setCurrentWidget(self.vacio)
        elif tipo == "imagen":
            self.imagen.mostrar(ruta)
            self.pila.setCurrentWidget(self.imagen)
        else:
            self.ruta_video = ruta
            self._es_video = True
            self.intro = None
            self.btn_intro.hide()
            if self.al_abrir_video and not self._vista_previa:
                self.al_abrir_video(ruta)
            self.pila.setCurrentWidget(self.pantalla)
            if config_sub is None:
                if auto := buscar_junto_a(ruta):
                    self.cargar_subtitulos(auto, 0, guardar=False)
            elif config_sub[0]:
                self.cargar_subtitulos(config_sub[0], config_sub[1], guardar=False)
            self.reproductor.setSource(QUrl.fromLocalFile(ruta))
            if self._vista_previa:
                # En pausa: al cargar se salta a un punto de muestra y se dibuja ese cuadro, sin sonido
                self.pantalla.portada = True
                self.reproductor.pause()
            else:
                self.reproductor.play()
                self.pantalla.setFocus()
        self._actualizar_controles()

    def empezar(self):
        """Sale de la vista previa y reproduce desde el principio (o la posición pedida)."""
        self._vista_previa = False
        self.pantalla.portada = False
        self.pantalla.update()
        if self.reproductor.mediaStatus() in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferingMedia,
                                              QMediaPlayer.BufferedMedia):
            self.reproductor.setPosition(self._inicio_ms)
            self._avisar_retomado(self._inicio_ms)
        else:
            self._posicion_pendiente = self._inicio_ms
        self.reproductor.play()
        self.pantalla.setFocus()

    def _avisar_retomado(self, ms: int):
        if ms:
            self.pantalla.mostrar_osd(f"Sigue desde {formato_tiempo(ms)} · Inicio = desde el principio")

    def guardar_progreso(self):
        """Avisa hasta dónde se vio el video actual (en vista previa todavía no se vio nada)."""
        if self._es_video and self.ruta_video and not self._vista_previa:
            pos, dur = self.reproductor.position(), self.reproductor.duration()
            if pos > 0 and dur > 0:
                self._ultimo_guardado = pos
                self.progreso.emit(self.ruta_video, pos, dur)

    def posicion_actual(self) -> int:
        """Posición para retomar el video (en vista previa, todavía no empezó)."""
        return self._inicio_ms if self._vista_previa else self.reproductor.position()

    @property
    def es_video(self) -> bool:
        return self._es_video

    @property
    def en_vista_previa(self) -> bool:
        return self._vista_previa

    def ir_a(self, ms: int):
        """Salta a ese punto; desde la vista previa, empieza a reproducir ahí."""
        if not self._es_video:
            return
        ms = max(0, min(ms, self.reproductor.duration()))
        if self._vista_previa:
            self._inicio_ms = ms
            self.empezar()
        else:
            self.reproductor.setPosition(ms)

    def alternar_play(self):
        if not self._es_video:
            return
        if self._vista_previa:
            self.empezar()
        elif self.reproductor.playbackState() == QMediaPlayer.PlayingState:
            self.reproductor.pause()
            self.pantalla.mostrar_osd("⏸ Pausa")
        else:
            self.reproductor.play()
            self.pantalla.mostrar_osd("▶ Reproduciendo")

    def adelantar(self, ms: int):
        if self._es_video:
            destino = self.reproductor.position() + ms
            self.reproductor.setPosition(max(0, min(destino, self.reproductor.duration())))

    # --- Pantalla completa ----------------------------------------------------

    def set_modo_completo(self, activo: bool):
        self._modo_completo = activo
        if activo:
            self._actividad()
        else:
            self._timer_ocultar.stop()
            self._mostrar_cursor()
            self._actualizar_controles()

    def _mostrar_cursor(self):
        self.pantalla.unsetCursor()
        self.unsetCursor()

    def _actividad(self):
        if self._modo_completo:
            self._mostrar_cursor()
            self._actualizar_controles()
            self._quieto_desde = time.monotonic()
            self._timer_ocultar.start()

    def _ocultar_controles(self):
        if not self._modo_completo:
            return
        # Con el cursor de verdad: underMouse() queda «pegado» en True después de usar un menú o una lista
        # desplegable (Qt no avisa que el mouse salió), y los controles no se ocultaban más
        pos = QCursor.pos()
        if pos != getattr(self, "_ultima_pos", None):
            self._ultima_pos = pos
            self._quieto_desde = time.monotonic()
        quieto = time.monotonic() - getattr(self, "_quieto_desde", 0)

        def encima(w):
            return w.isVisible() and w.rect().contains(w.mapFromGlobal(pos))
        desplegado = (QApplication.activePopupWidget() is not None
                      or self.menu_subs.isVisible() or self.menu_cola.isVisible())
        # Con el mouse encima de los controles se quedan, pero si el mouse quedó quieto ahí un rato
        # (por ejemplo después de tocar ▶) se esconden igual
        encima_activo = (encima(self.controles) or encima(self.barra_subs)) and quieto < 4
        if desplegado or encima_activo or self.reproductor.playbackState() != QMediaPlayer.PlayingState:
            self._timer_ocultar.start()
            return
        QToolTip.hideText()
        self.controles.hide()
        self.barra_subs.hide()
        self.pantalla.setCursor(Qt.BlankCursor)
        self.setCursor(Qt.BlankCursor)

    def _actualizar_controles(self):
        self.controles.setVisible(self._es_video)
        self.barra_subs.setVisible(self._es_video and self.subs is not None)

    # --- Subtítulos -----------------------------------------------------------

    def cargar_subtitulos(self, ruta_sub: str, retraso_ms: int = 0, guardar: bool = True) -> bool:
        if not self.ruta_video:
            return False
        try:
            subs = Subtitulos(ruta_sub)
        except OSError as e:
            if guardar:
                QMessageBox.warning(self, "Subtítulos", f"No se pudo leer el archivo:\n{e}")
            return False
        self.reproductor.setActiveSubtitleTrack(-1)
        self.subs, self.ruta_sub = subs, ruta_sub
        self._fin_dialogo = max((b for _a, b, t in subs.cues if not PUBLICIDAD_SUB.search(t)), default=None)
        self.lbl_sub.setText(f"Subtítulos: {Path(ruta_sub).name}")
        self.lbl_sub.setToolTip(ruta_sub)
        self._poner_retraso(retraso_ms)
        self._actualizar_controles()
        self._actualizar_subtitulo()
        if guardar:
            self._guardar_subtitulos()
            self.pantalla.mostrar_osd(f"Subtítulos: {Path(ruta_sub).name}")
        return True

    def quitar_subtitulos(self):
        self._descartar_subtitulos()
        self.reproductor.setActiveSubtitleTrack(-1)
        self._actualizar_controles()
        if self.ruta_video:
            self._guardar_subtitulos()
            self.pantalla.mostrar_osd("Subtítulos desactivados")

    def ajustar_retraso(self, delta_ms: int):
        """Negativo: los subtítulos salen antes; positivo: después."""
        if self.subs is not None:
            self.fijar_retraso(self.retraso_ms + delta_ms)
        elif self._es_video:
            self.pantalla.mostrar_osd("No hay un archivo de subtítulos cargado")

    def fijar_retraso(self, ms: int):
        if self.subs is None:
            return
        self._poner_retraso(max(-600_000, min(600_000, int(ms))))
        self._actualizar_subtitulo()
        self._guardar_subtitulos()
        self.pantalla.mostrar_osd(f"Subtítulos: {texto_sincronia(self.retraso_ms)}")

    def sincronizar_ahora(self):
        """Se toca cuando alguien empieza a hablar: el subtítulo que empieza más cerca de este
        momento (con el ajuste actual) pasa a empezar justo ahora."""
        if self.subs is None or not self.subs.cues:
            self.pantalla.mostrar_osd("No hay un archivo de subtítulos cargado")
            return
        ahora = self.reproductor.position()
        inicio = min((c[0] for c in self.subs.cues), key=lambda a: abs(a + self.retraso_ms - ahora))
        self.fijar_retraso(ahora - inicio)

    def _descartar_subtitulos(self):
        self.subs = self.ruta_sub = None
        self._fin_dialogo = None
        self._poner_retraso(0)
        self.pantalla.set_texto("")

    def _poner_retraso(self, ms: int):
        self.retraso_ms = ms
        self.lbl_sincronia.setText(texto_sincronia(ms))
        if self.campo_ms.value() != ms:
            self.campo_ms.blockSignals(True)  # no volver a aplicar lo que se acaba de aplicar
            self.campo_ms.setValue(ms)
            self.campo_ms.blockSignals(False)

    # --- Indicador de «sincronizando…» (símbolo que gira + porcentaje) ---------------------------------

    def _empezar_carga(self):
        self.progreso_sincronia = 0
        self.btn_auto.setEnabled(False)
        self.lbl_sub.hide()
        self.lbl_cargando.show()
        self._reloj_giro.start()
        self._girar()

    def _terminar_carga(self):
        self.progreso_sincronia = -1
        self._reloj_giro.stop()
        self.lbl_cargando.hide()
        self.lbl_sub.show()
        self.btn_auto.setEnabled(True)

    def _avance_sincronia(self, porcentaje: int):
        if self._sincronizando:
            self.progreso_sincronia = porcentaje

    def _girar(self):
        self._giro = (self._giro + 1) % 4
        self.lbl_cargando.setText(f"{'◐◓◑◒'[self._giro]} Analizando… {max(0, self.progreso_sincronia)} %")

    def _campo_ms_cambio(self, ms: int):
        if self.subs is None:
            self.pantalla.mostrar_osd("No hay un archivo de subtítulos cargado")
            self.campo_ms.blockSignals(True)
            self.campo_ms.setValue(0)
            self.campo_ms.blockSignals(False)
            return
        self.fijar_retraso(ms)

    def sincronizar_automatico(self, preguntar: bool = True):
        """Calcula el retraso comparando el audio del video con los diálogos del subtítulo (en segundo plano).
        Devuelve un texto de aviso, o lanza ErrorSincronia si no se puede empezar."""
        if self.subs is None or not self.subs.cues or not self.ruta_video:
            self.pantalla.mostrar_osd("No hay un archivo de subtítulos cargado")
            raise sincronia.ErrorSincronia("Hace falta un archivo de subtítulos cargado")
        if self._sincronizando:
            raise sincronia.ErrorSincronia("Ya se está sincronizando")
        from .remoto import ffmpeg
        exe = ffmpeg()
        if not exe:
            if preguntar and QMessageBox.question(
                    self, "Falta ffmpeg",
                    "Para sincronizar solo hace falta ffmpeg (gratis). ¿Lo instalo ahora con winget?\n\n"
                    "Se abre una ventana negra para seguir el avance; al terminar, volvé a tocar «🪄 Auto».",
            ) == QMessageBox.Yes:
                sincronia.instalar_ffmpeg()
            raise sincronia.ErrorSincronia("Hace falta ffmpeg en la PC para sincronizar solo")
        ruta, subs = self.ruta_video, self.subs
        duracion_s = max(1, self.reproductor.duration() / 1000)
        self._sincronizando = True
        self._empezar_carga()
        self.pantalla.mostrar_osd("Analizando el audio… puede tardar un rato")

        def listo(resultado):
            self._sincronizando = False
            self._terminar_carga()
            retraso = resultado.retraso_ms
            if self.ruta_video == ruta and self.subs is subs:  # si cambió de video mientras tanto, no se toca
                self.fijar_retraso(retraso)
                aviso = f"  ·  {resultado.avisos[0]}" if resultado.avisos else ""
                self.pantalla.mostrar_osd(f"✓ Subtítulos sincronizados: {texto_sincronia(retraso)}{aviso}")

        def fallo(mensaje):
            self._sincronizando = False
            self._terminar_carga()
            titulo, _, detalle = str(mensaje).partition("\n")
            if detalle:           # un aviso importante (el subtítulo es de otra película): grande y por más tiempo
                self.pantalla.mostrar_aviso(titulo, detalle, segundos=14)
            else:
                self.pantalla.mostrar_aviso("No se pudo sincronizar", titulo, segundos=10)

        def avance(segundos: float):  # desde el hilo de fondo: la señal lo pasa al de la interfaz
            self.avance_sincronia.emit(min(99, int(segundos * 100 / duracion_s)))

        en_segundo_plano(lambda: sincronia.sincronizar_detallado(exe, ruta, subs.cues, avance), listo, fallo)
        return "Analizando el audio… el ajuste se aplica solo al terminar"

    def _guardar_subtitulos(self):
        self.subtitulos_cambiados.emit(self.ruta_video, self.ruta_sub, self.retraso_ms)

    def _actualizar_subtitulo(self):
        if self.subs is not None:
            self.pantalla.set_texto(self.subs.texto_en(self.reproductor.position() - self.retraso_ms))

    def _texto_pista_interna(self, texto: str):
        if self.subs is None and self.reproductor.activeSubtitleTrack() >= 0:
            self.pantalla.set_texto(texto)

    def _elegir_archivo_subs(self):
        inicio = str(Path(self.ruta_video).parent) if self.ruta_video else ""
        ruta, _ = QFileDialog.getOpenFileName(self, "Cargar subtítulos", inicio, "Subtítulos (*.srt *.vtt)")
        if ruta:
            self.cargar_subtitulos(ruta)

    def usar_pista_interna(self, indice: int):
        self._descartar_subtitulos()
        self._actualizar_controles()
        self.reproductor.setActiveSubtitleTrack(indice)

    def _nombre_pista(self, datos: QMediaMetaData, indice: int) -> str:
        partes = []
        idioma = datos.value(QMediaMetaData.Language)
        if isinstance(idioma, QLocale.Language) and idioma != QLocale.AnyLanguage:
            partes.append(QLocale.languageToString(idioma))
        if titulo := datos.stringValue(QMediaMetaData.Title):
            partes.append(titulo)
        return f"Pista {indice + 1}" + (f": {' – '.join(partes)}" if partes else "")

    def archivos_subtitulos(self) -> list[tuple[str, str]]:
        """(ruta, descripción) de los subtítulos que se pueden elegir para el video actual."""
        junto = subtitulos_junto_a(self.ruta_video) if self.ruta_video else []
        if self.ruta_sub and self.ruta_sub not in junto:
            junto.append(self.ruta_sub)
        return [(ruta, descripcion(ruta, self.ruta_video)) for ruta in junto]

    def pistas_subtitulos(self) -> list[tuple[str, bool]]:
        """(nombre, activa) de las pistas de subtítulos que trae el video."""
        activa = self.reproductor.activeSubtitleTrack()
        return [(self._nombre_pista(datos, i), i == activa and self.subs is None)
                for i, datos in enumerate(self.reproductor.subtitleTracks())]

    def _armar_menu_subs(self):
        m = self.menu_subs
        m.clear()
        m.addAction("Cargar archivo de subtítulos…", self._elegir_archivo_subs).setEnabled(self._es_video)
        m.addAction("🌐 Buscar en internet (OpenSubtitles)",
                    lambda: self.buscar_subtitulos_online.emit(self.ruta_video)).setEnabled(self._es_video)
        m.addAction("🌐 Buscar en subdivx…",
                    lambda: self.buscar_subtitulos_subdivx.emit(self.ruta_video)).setEnabled(self._es_video)
        archivos = self.archivos_subtitulos()
        if archivos:
            m.addSection("Archivos de subtítulos")
        for ruta, texto in archivos:
            m.addAction(self._fila_subtitulo(m, ruta, texto))
        pistas = self.pistas_subtitulos()
        if pistas:
            m.addSection("Pistas incluidas en el video")
        for i, (nombre, activa) in enumerate(pistas):
            accion = m.addAction(nombre, lambda i=i: self.usar_pista_interna(i))
            accion.setCheckable(True)
            accion.setChecked(activa)
        m.addSeparator()
        m.addAction("Desactivar subtítulos", self.quitar_subtitulos).setEnabled(
            self.subs is not None or self.reproductor.activeSubtitleTrack() >= 0)
        tamanos = m.addMenu("Tamaño del texto")
        for nombre, escala in TAMANOS_SUB:
            accion = tamanos.addAction(nombre, lambda e=escala: self.cambiar_tamano_sub(e))
            accion.setCheckable(True)
            accion.setChecked(self.pantalla.escala_sub == escala)

    def _fila_subtitulo(self, menu: QMenu, ruta, texto: str):
        """Una opción del menú de subtítulos: el nombre (lo elige) y, al final, una papelerita roja (lo borra)."""
        from PySide6.QtWidgets import QWidgetAction
        accion = QWidgetAction(menu)
        fila = QWidget(objectName="filaSubtitulo")
        capa = QHBoxLayout(fila)
        capa.setContentsMargins(4, 1, 4, 1)
        capa.setSpacing(6)
        elegido = ruta == self.ruta_sub
        nombre = QPushButton(("✓  " if elegido else "     ") + texto, objectName="subtituloNombre", flat=True)
        nombre.setStyleSheet("QPushButton#subtituloNombre { text-align: left; padding: 5px 8px; border: none; background: transparent; }"
                             "QPushButton#subtituloNombre:hover { background: rgba(127, 127, 127, 60); border-radius: 4px; }")
        nombre.setCursor(Qt.PointingHandCursor)
        nombre.clicked.connect(lambda: (menu.close(), self.cargar_subtitulos(ruta)))
        papelera = QPushButton("🗑", objectName="subtituloBorrar", toolTip="Borrar este archivo de subtítulos (va a la Papelera)")
        papelera.setFixedSize(30, 26)
        papelera.setCursor(Qt.PointingHandCursor)
        papelera.setStyleSheet("QPushButton#subtituloBorrar { color: #ff5252; background: rgba(229, 57, 53, 40); border: 1px solid "
                               "rgba(229, 57, 53, 120); border-radius: 5px; font-size: 12pt; padding: 0; }"
                               "QPushButton#subtituloBorrar:hover { background: #e53935; color: white; }")
        papelera.clicked.connect(lambda: (menu.close(), self._borrar_subtitulo(ruta)))
        capa.addWidget(nombre, 1)
        capa.addWidget(papelera)
        accion.setDefaultWidget(fila)
        return accion

    def _borrar_subtitulo(self, ruta):
        from pathlib import Path
        from .dominio_publico import a_la_papelera
        ruta = Path(ruta)
        if QMessageBox.question(self, "Borrar subtítulos", f"¿Mandar «{ruta.name}» a la Papelera?") != QMessageBox.Yes:
            return
        if ruta == (Path(self.ruta_sub) if self.ruta_sub else None):
            self.quitar_subtitulos()
        if a_la_papelera(ruta):
            self.pantalla.mostrar_osd(f"🗑 {ruta.name} fue a la Papelera")
        else:
            self.pantalla.mostrar_osd("No se pudo borrar el archivo")

    def cambiar_tamano_sub(self, escala: float):
        self.pantalla.escala_sub = escala
        self.pantalla.update()

    # --- Reproducción ---------------------------------------------------------

    def _nuevo_frame(self, frame):
        self._actualizar_subtitulo()
        self.pantalla.set_frame(frame)
        if not self._tamano_avisado and self._es_video and frame.isValid():
            self._tamano_avisado = True
            self.tamano_video.emit(frame.size())

    def _salida_audio_cambiada(self):
        self.audio.setDevice(QMediaDevices.defaultAudioOutput())

    def _volumen_cambiado(self, valor: int):
        """El nivel, al lado de la barra y grande sobre el video mientras se mueve."""
        self.lbl_volumen.setText(f"{valor} %")
        self.volumen.setToolTip(f"Volumen: {valor} %")
        if self._es_video:
            self.pantalla.mostrar_osd(f"🔊 {valor} %")

    def alternar_mute(self):
        self.audio.setMuted(not self.audio.isMuted())
        icono = QStyle.SP_MediaVolumeMuted if self.audio.isMuted() else QStyle.SP_MediaVolume
        self.btn_mute.setIcon(self.style().standardIcon(icono))

    def _posicion(self, pos: int):
        if not self.barra.isSliderDown():
            self.barra.setValue(pos)
        self.lbl_tiempo.setText(f"{formato_tiempo(pos)} / {formato_tiempo(self.reproductor.duration())}")
        self._actualizar_subtitulo()
        self._revisar_siguiente(pos)
        self._revisar_intro(pos)
        if abs(pos - self._ultimo_guardado) >= 10_000:
            self.guardar_progreso()

    def poner_intro(self, ruta: str, intro: tuple[int, int] | None):
        """La intro detectada para un video (si sigue siendo el que está abierto)."""
        if ruta == self.ruta_video:
            self.intro = intro if intro and intro[1] > intro[0] else None
            self._revisar_intro(self.reproductor.position())

    def en_intro(self, pos: int | None = None) -> bool:
        pos = self.reproductor.position() if pos is None else pos
        return bool(self.intro and self._es_video and self.intro[0] - 500 <= pos < self.intro[1] - 1500)

    def _revisar_intro(self, pos: int):
        mostrar = self.en_intro(pos) and not self._vista_previa
        if mostrar != self.btn_intro.isVisible():
            self.btn_intro.setVisible(mostrar)
            if mostrar:
                self.pantalla.colocar_panel()
                self.btn_intro.raise_()

    def saltar_intro(self):
        if self.intro and self._es_video:
            self.reproductor.setPosition(self.intro[1])
            self.btn_intro.hide()
            self.pantalla.mostrar_osd("⏭ Intro salteada")

    def _estado_medio(self, estado):
        if self._vista_previa:
            self._preparar_vista_previa()
        # La posición inicial solo se puede aplicar cuando el video terminó de cargar
        elif self._posicion_pendiente and estado in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
            self.reproductor.setPosition(self._posicion_pendiente)
            self._avisar_retomado(self._posicion_pendiente)
            self._posicion_pendiente = 0
        elif estado == QMediaPlayer.EndOfMedia:
            if self.ruta_video and (dur := self.reproductor.duration()) > 0:
                self.progreso.emit(self.ruta_video, dur, dur)
            self._fin_del_video()

    # --- Siguiente capítulo ---------------------------------------------------

    def _buscar_siguiente(self) -> str | None:
        if self.cola:
            return self.cola[0]
        if self.buscar_siguiente and self.ruta_video:
            return self.buscar_siguiente(self.ruta_video)
        return None

    def pasar_a(self, ruta: str):
        if ruta in self.cola:
            self.cola.remove(ruta)
            self._actualizar_cola()
        self.reproducir_siguiente.emit(ruta)

    def siguiente_capitulo(self):
        if not self._es_video:
            return
        if siguiente := self._buscar_siguiente():
            self.pasar_a(siguiente)
        else:
            self.pantalla.mostrar_osd("No hay videos en la cola ni un capítulo siguiente")

    # --- Cola -------------------------------------------------------------------

    def encolar(self, rutas: list[str]) -> int:
        """Suma videos a la cola. Si no se está viendo nada, arranca el primero ya."""
        nuevas = [r for r in dict.fromkeys(rutas) if r != self.ruta_video and r not in self.cola]
        self.cola.extend(nuevas)
        # Lo agregado cambia lo que sigue, aunque se hubiera cancelado el aviso
        self._siguiente_cancelado = False
        self._ruta_siguiente = None
        self._actualizar_cola()
        if self.cola and (not self._es_video or self.reproductor.mediaStatus() == QMediaPlayer.EndOfMedia):
            self.pasar_a(self.cola[0])
        return len(nuevas)

    def quitar_de_cola(self, ruta: str):
        if ruta in self.cola:
            self.cola.remove(ruta)
            self._ruta_siguiente = None
            self._actualizar_cola()

    def _actualizar_cola(self):
        self.btn_cola.setText(f"☰ Cola ({len(self.cola)})")
        self.btn_cola.setVisible(bool(self.cola))

    def _armar_menu_cola(self):
        m = self.menu_cola
        m.clear()
        m.addSection("A continuación")
        for i, ruta in enumerate(self.cola, 1):
            sub = m.addMenu(f"{i}. {Path(ruta).stem}")
            sub.addAction("▶ Reproducir ahora", lambda r=ruta: self.pasar_a(r))
            sub.addAction("Quitar de la cola", lambda r=ruta: self.quitar_de_cola(r))
        m.addSeparator()
        m.addAction("Vaciar la cola", self.vaciar_cola)

    def vaciar_cola(self):
        self.cola.clear()
        self._ruta_siguiente = None
        self._actualizar_cola()

    def _revisar_siguiente(self, pos: int):
        """Muestra el aviso en los últimos segundos; la cuenta sigue al video,
        así que se frena con la pausa y desaparece si se retrocede."""
        dur = self.reproductor.duration()
        if (not self._es_video or dur <= 0 or self._vista_previa or self._siguiente_cancelado
                or self.apagar_al_terminar):
            self.panel_sig.hide()
            return
        restante = dur - pos
        if restante > self.AVISO_SIGUIENTE_MS and not self._en_creditos(pos, dur):
            self.panel_sig.hide()
            return
        if self._ruta_siguiente is None:
            self._ruta_siguiente = self._buscar_siguiente()
            if self._ruta_siguiente is None:
                self._siguiente_cancelado = True  # no hay siguiente: no volver a buscar
                return
            self.lbl_sig_nombre.setText(Path(self._ruta_siguiente).stem)
        que = "Siguiente de la cola" if self._ruta_siguiente in self.cola else "Siguiente capítulo"
        # Durante los créditos queda a mano; la cuenta regresiva, solo en los últimos segundos
        if restante > self.AVISO_SIGUIENTE_MS:
            self.lbl_sig_cuenta.setText(que)
        else:
            self.lbl_sig_cuenta.setText(f"{que} en {max(1, math.ceil(restante / 1000))} s")
        if not self.panel_sig.isVisible():
            self.panel_sig.show()
        self.pantalla.colocar_panel()

    def _en_creditos(self, pos: int, dur: int) -> bool:
        """Ya terminó el último diálogo de los subtítulos: lo que queda son los créditos.
        Solo si eso pasa en el último tercio, para no confundir un final sin diálogos."""
        if self._fin_dialogo is None:
            return False
        fin = self._fin_dialogo + self.retraso_ms
        return dur * 2 // 3 <= fin <= dur - self.CREDITOS_MINIMO_MS and pos >= fin

    def _fin_del_video(self):
        if self.apagar_al_terminar:
            self.pedir_apagado.emit()
        elif not self._siguiente_cancelado:
            self.siguiente_ahora()

    def siguiente_ahora(self):
        if ruta := self._ruta_siguiente or self._buscar_siguiente():
            self.pasar_a(ruta)

    def cancelar_siguiente(self):
        self._siguiente_cancelado = True
        self.panel_sig.hide()

    def _reiniciar_siguiente(self):
        self._siguiente_cancelado = False
        self._ruta_siguiente = None
        self.panel_sig.hide()

    def _preparar_vista_previa(self):
        """Una vez cargado y con la duración conocida (en algunos .mkv llega después),
        arranca si es largo o salta al cuadro de muestra."""
        dur = self.reproductor.duration()
        # En BufferingMedia todavía puede no estar listo: un play() ahí se pierde con algunos .mkv
        cargado = self.reproductor.mediaStatus() in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia)
        if not cargado or dur <= 0 or self.reproductor.position() > 0:
            return
        if self._modo == SI_ES_LARGO and dur > DURACION_LARGA_MS:
            # Fuera de la señal del reproductor: un play() dentro de ella se ignora
            QTimer.singleShot(0, self.empezar)
        else:
            # Cuadro de muestra: al 10 % del video, como mucho a los 5 minutos
            self.reproductor.setPosition(self._inicio_ms or min(dur // 10, 300_000))

    def _duracion(self, dur: int):
        self.barra.setRange(0, dur)
        if self._vista_previa:
            self._preparar_vista_previa()

    def _estado(self, estado):
        icono = QStyle.SP_MediaPause if estado == QMediaPlayer.PlayingState else QStyle.SP_MediaPlay
        self.btn_play.setIcon(self.style().standardIcon(icono))
        if estado == QMediaPlayer.PausedState:
            self.guardar_progreso()
        if self._modo_completo:
            self._actividad()
