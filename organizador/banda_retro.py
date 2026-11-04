"""La banda de arriba de los temas retro: una pantallita con el título que corre y una animación por tema
(estrellas, ecualizador, nubes, aurora, lluvia de letras, grilla de neón…). Todo dibujado a mano con QPainter."""
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from .temas import Tema

ALTO = 36
FPS = 30


def _color(texto: str, alfa: int | None = None) -> QColor:
    c = QColor(texto)
    if alfa is not None:
        c.setAlpha(alfa)
    return c


class BandaRetro(QWidget):
    def __init__(self, estado, parent=None):
        """estado(): devuelve (título o "", reproduciendo, posición ms, duración ms)."""
        super().__init__(parent, objectName="bandaRetro")
        self.estado = estado
        self.setFixedHeight(ALTO)
        self.setMinimumWidth(400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.tema: Tema | None = None
        self.animada = True
        self.t = 0.0
        self._azar = random.Random(7)
        self._particulas: list[list[float]] = []
        self._barras: list[float] = []
        self._picos: list[float] = []
        self._columnas: list[list[float]] = []
        self._desplazamiento = 0.0
        self._reloj = QTimer(self, interval=1000 // FPS, timeout=self._tic)

    def aplicar(self, tema: Tema, animada: bool):
        self.tema = tema
        self.animada = animada
        self._particulas.clear()
        self._columnas.clear()
        self._barras = [0.0] * 40
        self._picos = [0.0] * 40
        self._reloj.setInterval(1000 // FPS)
        if animada and tema.animacion != "ninguna":
            self._reloj.start()
        else:
            self._reloj.stop()
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if self.animada and self.tema and self.tema.animacion != "ninguna":
            self._reloj.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._reloj.stop()

    def _tic(self):
        # Con la ventana minimizada o tapada no se gasta nada
        if not self.isVisible() or self.window().isMinimized():
            return
        self.t += 1 / FPS
        self._desplazamiento += 1.4
        self.update()

    # --- Dibujo ---------------------------------------------------------------------------

    def paintEvent(self, _e):
        t = self.tema
        if t is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), _color(t.lcd_fondo))
        titulo, sonando, pos, dur = self.estado()
        dibujar = getattr(self, "_" + t.animacion, None)
        if dibujar:
            p.save()
            dibujar(p, t, sonando)
            p.restore()
        self._pantallita(p, t, titulo, sonando, pos, dur)
        # Borde de abajo, como el filo de un panel
        p.setPen(QPen(_color(t.borde), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.end()

    def _pantallita(self, p: QPainter, t: Tema, titulo: str, sonando: bool, pos: int, dur: int):
        """La pantallita LCD con el título que corre y el tiempo (a la izquierda)."""
        ancho = min(420, max(220, self.width() // 3))
        caja = QRectF(8, 5, ancho, self.height() - 10)
        p.setPen(QPen(_color(t.lcd_texto, 120), 1))
        p.setBrush(_color(t.lcd_fondo, 215))
        p.drawRoundedRect(caja, min(t.radio, 6), min(t.radio, 6))
        fuente = QFont(t.lcd_letra, 10)
        fuente.setBold(True)
        p.setFont(fuente)
        m = QFontMetrics(fuente)
        tiempo = f"{pos // 60000}:{pos // 1000 % 60:02}" if dur else ""
        texto = (("▶ " if sonando else "❚❚ ") + titulo) if titulo else "TorrentVision · Torrent para todos"
        ancho_tiempo = m.horizontalAdvance(tiempo) + 12 if tiempo else 0
        zona = caja.adjusted(8, 0, -8 - ancho_tiempo, 0)
        p.setClipRect(zona)
        p.setPen(_color(t.lcd_texto))
        largo = m.horizontalAdvance(texto)
        base = zona.center().y() + m.ascent() / 2 - 1
        if largo <= zona.width():
            p.drawText(QPointF(zona.left(), base), texto)
        else:
            # Marquesina: el título corre de derecha a izquierda y vuelve a entrar
            ciclo = largo + 60
            x = zona.left() - (self._desplazamiento % ciclo)
            p.drawText(QPointF(x, base), texto)
            p.drawText(QPointF(x + ciclo, base), texto)
        p.setClipping(False)
        if tiempo:
            p.setPen(_color(t.lcd_texto))
            p.drawText(QPointF(caja.right() - ancho_tiempo, base), tiempo)

    def _zona(self) -> QRectF:
        """Donde va la animación: todo el ancho (la pantallita se dibuja encima)."""
        return QRectF(self.rect())

    # --- Animaciones ------------------------------------------------------------------------

    def _estrellas(self, p: QPainter, t: Tema, _sonando: bool):
        """Estrellas en tres capas que pasan a distinta velocidad (paralaje)."""
        w, h = self.width(), self.height()
        if not self._particulas:
            self._particulas = [[self._azar.uniform(0, w), self._azar.uniform(0, h), self._azar.choice((0.3, 0.7, 1.4)),
                                 self._azar.uniform(0, 6.28)] for _ in range(max(60, w // 12))]
        degradado = QLinearGradient(0, 0, 0, h)
        degradado.setColorAt(0, _color("#0b1f4a"))
        degradado.setColorAt(1, _color("#020611"))
        p.fillRect(self.rect(), degradado)
        p.setPen(Qt.NoPen)
        for s in self._particulas:
            s[0] -= s[2]
            if s[0] < 0:
                s[0], s[1] = w, self._azar.uniform(0, h)
            brillo = int(140 + 115 * (0.5 + 0.5 * math.sin(self.t * 3 + s[3])) * (s[2] / 1.4))
            p.setBrush(QColor(200, 230, 255, min(255, brillo)))
            r = 0.6 + s[2] * 0.6
            p.drawEllipse(QPointF(s[0], s[1]), r, r)
        # Una estrella fugaz de vez en cuando
        fase = (self.t % 7) / 7
        if fase < 0.12:
            x = w * (1 - fase / 0.12)
            p.setPen(QPen(QColor(143, 216, 255, 200), 1.5))
            p.drawLine(QPointF(x, 4 + fase * 60), QPointF(x + 40, fase * 60))

    def _warp(self, p: QPainter, t: Tema, _sonando: bool):
        """El protector de pantalla de estrellas: salen del centro hacia afuera."""
        w, h = self.width(), self.height()
        cx, cy = w * 0.62, h / 2
        if not self._particulas:
            self._particulas = [[self._azar.uniform(-1, 1), self._azar.uniform(-1, 1), self._azar.uniform(0.05, 1)]
                                for _ in range(160)]
        p.fillRect(self.rect(), Qt.black)
        for s in self._particulas:
            s[2] -= 0.012
            if s[2] <= 0.02:
                s[0], s[1], s[2] = self._azar.uniform(-1, 1), self._azar.uniform(-1, 1), 1.0
            x = cx + s[0] / s[2] * w * 0.12
            y = cy + s[1] / s[2] * h * 0.9
            if not (0 <= x <= w and 0 <= y <= h):
                s[2] = 0
                continue
            g = int(255 * min(1, (1 - s[2]) * 1.4))
            p.setPen(QPen(QColor(g, g, g), 1 + (1 - s[2]) * 1.6))
            p.drawPoint(QPointF(x, y))

    def _ecualizador(self, p: QPainter, t: Tema, sonando: bool):
        """Barras de ecualizador en bloques verde-amarillo-rojo, con el pico que cae despacio."""
        w, h = self.width(), self.height()
        n = len(self._barras)
        x0 = w * 0.38
        ancho = (w - x0 - 10) / n
        for i in range(n):
            if sonando:
                # Graves más altos, agudos más nerviosos: parece música aunque es una simulación
                objetivo = abs(math.sin(self.t * (1.3 + i * 0.17) + i)) * (1 - i / (n * 1.6)) * self._azar.uniform(0.55, 1)
            else:
                objetivo = 0.04
            self._barras[i] += (objetivo - self._barras[i]) * 0.35
            self._picos[i] = max(self._picos[i] - 0.012, self._barras[i])
            bloques = int(self._barras[i] * 9)
            for b in range(bloques):
                color = "#00e000" if b < 5 else ("#e0e000" if b < 7 else "#ff3b1f")
                y = h - 5 - (b + 1) * 3.2
                p.fillRect(QRectF(x0 + i * ancho, y, ancho - 2, 2.4), _color(color))
            yp = h - 5 - int(self._picos[i] * 9 + 1) * 3.2
            p.fillRect(QRectF(x0 + i * ancho, yp, ancho - 2, 1.4), _color("#c8c8d8"))

    def _nubes(self, p: QPainter, t: Tema, _sonando: bool):
        """Cielo celeste, nubes que pasan y la loma verde."""
        w, h = self.width(), self.height()
        cielo = QLinearGradient(0, 0, 0, h)
        cielo.setColorAt(0, _color("#3a8ce8"))
        cielo.setColorAt(1, _color("#9fd0ff"))
        p.fillRect(self.rect(), cielo)
        if not self._particulas:
            self._particulas = [[self._azar.uniform(0, w), self._azar.uniform(2, h * 0.55), self._azar.uniform(18, 46),
                                 self._azar.uniform(0.15, 0.4)] for _ in range(max(6, w // 160))]
        p.setPen(Qt.NoPen)
        for c in self._particulas:
            c[0] += c[3]
            if c[0] - c[2] * 2 > w:
                c[0] = -c[2] * 2
            p.setBrush(QColor(255, 255, 255, 215))
            for dx, dy, r in ((0, 0, 1), (c[2] * 0.7, 2, 0.8), (-c[2] * 0.6, 3, 0.7)):
                p.drawEllipse(QPointF(c[0] + dx, c[1] + dy + 6), c[2] * 0.5 * r, c[2] * 0.22 * r)
        loma = QPainterPath(QPointF(w * 0.35, h))
        loma.cubicTo(QPointF(w * 0.55, h * 0.35), QPointF(w * 0.8, h * 0.2), QPointF(w, h * 0.45))
        loma.lineTo(w, h)
        loma.closeSubpath()
        verde = QLinearGradient(0, h * 0.3, 0, h)
        verde.setColorAt(0, _color("#6fcf3a"))
        verde.setColorAt(1, _color("#2c8a13"))
        p.setBrush(verde)
        p.drawPath(loma)

    def _gotas(self, p: QPainter, t: Tema, _sonando: bool):
        """Gotas de gel azul que «respiran» (crecen y se achican)."""
        w, h = self.width(), self.height()
        fondo = QLinearGradient(0, 0, 0, h)
        fondo.setColorAt(0, _color("#f4f6fa"))
        fondo.setColorAt(1, _color("#d3d8e2"))
        p.fillRect(self.rect(), fondo)
        # Rayitas finas horizontales, como el fondo a rayas de la época
        p.setPen(QPen(QColor(255, 255, 255, 140), 1))
        for y in range(0, h, 2):
            p.drawLine(0, y, w, y)
        p.setPen(Qt.NoPen)
        n = max(5, w // 130)
        for i in range(n):
            x = w * 0.36 + (w * 0.64) * (i + 0.5) / n
            r = 9 + 4 * math.sin(self.t * 1.6 + i * 1.3)
            g = QRadialGradient(QPointF(x - r * 0.3, h / 2 - r * 0.4), r * 1.4)
            g.setColorAt(0, _color("#e8f4ff"))
            g.setColorAt(0.35, _color("#5aa8ff"))
            g.setColorAt(1, _color("#0b4fbf"))
            p.setBrush(g)
            p.drawEllipse(QPointF(x, h / 2), r, r)
            p.setBrush(QColor(255, 255, 255, 170))
            p.drawEllipse(QPointF(x - r * 0.25, h / 2 - r * 0.5), r * 0.45, r * 0.22)

    def _aurora(self, p: QPainter, t: Tema, sonando: bool):
        """Ondas de luz azul que ondulan (más vivas mientras se reproduce)."""
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), Qt.black)
        fuerza = 1.0 if sonando else 0.45
        for k, (color, fase, alto) in enumerate((("#3fa9f5", 0.0, 0.32), ("#7a5cff", 1.7, 0.24), ("#39e6d0", 3.1, 0.18))):
            camino = QPainterPath()
            for x in range(0, w + 8, 8):
                y = h / 2 + math.sin(x / 70 + self.t * (1.1 + k * 0.4) + fase) * h * alto * fuerza \
                    + math.sin(x / 23 + self.t * 2.3) * 2
                camino.lineTo(x, y) if x else camino.moveTo(0, y)
            for grosor, alfa in ((7, 40), (3, 110), (1.2, 255)):
                p.setPen(QPen(_color(color, alfa), grosor, Qt.SolidLine, Qt.RoundCap))
                p.drawPath(camino)

    def _brillo(self, p: QPainter, t: Tema, sonando: bool):
        """Aluminio cepillado con un brillo que pasa, y puntitos de sonido en la pantallita."""
        w, h = self.width(), self.height()
        metal = QLinearGradient(0, 0, 0, h)
        metal.setColorAt(0, _color("#f2f2f2"))
        metal.setColorAt(0.5, _color("#c4c4c4"))
        metal.setColorAt(1, _color("#dadada"))
        p.fillRect(self.rect(), metal)
        rnd = random.Random(3)
        for y in range(h):
            p.setPen(QPen(QColor(255, 255, 255, rnd.randint(10, 60)) if y % 2 else QColor(0, 0, 0, rnd.randint(5, 25)), 1))
            p.drawLine(0, y, w, y)
        x = (self.t * 160) % (w + 300) - 150
        g = QLinearGradient(x - 80, 0, x + 80, 0)
        g.setColorAt(0, QColor(255, 255, 255, 0))
        g.setColorAt(0.5, QColor(255, 255, 255, 150))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(x - 80, 0, 160, h), g)
        # Onda de sonido chiquita a la derecha
        p.setPen(QPen(_color("#5d7fa8"), 2, Qt.SolidLine, Qt.RoundCap))
        for i in range(24):
            amp = (abs(math.sin(self.t * 4 + i * 0.6)) * 10 + 2) if sonando else 2
            xx = w - 20 - i * 7
            p.drawLine(QPointF(xx, h / 2 - amp / 2), QPointF(xx, h / 2 + amp / 2))

    def _flechas(self, p: QPainter, t: Tema, sonando: bool):
        """Flechitas verdes que bajan y azules que suben, como las transferencias de antes."""
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), _color("#0f2f18"))
        p.setPen(Qt.NoPen)
        x0 = w * 0.38
        n = int((w - x0) // 26)
        for i in range(n):
            baja = i % 3 != 2
            vel = 18 + (i * 7) % 11
            y = (self.t * vel + i * 13) % (h + 16) - 8
            if not baja:
                y = h - y
            x = x0 + i * 26 + 8
            flecha = QPainterPath()
            if baja:
                flecha.moveTo(x, y + 6)
                flecha.lineTo(x - 5, y)
                flecha.lineTo(x + 5, y)
            else:
                flecha.moveTo(x, y - 6)
                flecha.lineTo(x - 5, y)
                flecha.lineTo(x + 5, y)
            flecha.closeSubpath()
            p.setBrush(_color("#7dff6e" if baja else "#6ec8ff", 230))
            p.drawPath(flecha)
            p.fillRect(QRectF(x - 1.5, y - (8 if baja else -2), 3, 6), _color("#7dff6e" if baja else "#6ec8ff", 160))

    def _lluvia(self, p: QPainter, t: Tema, _sonando: bool):
        """Lluvia de letras verdes y líneas de barrido de monitor de tubo."""
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), _color("#000000"))
        fuente = QFont("Lucida Console", 8)
        p.setFont(fuente)
        paso = 10
        n = w // paso
        if len(self._columnas) != n:
            self._columnas = [[self._azar.uniform(-h, h), self._azar.uniform(0.6, 1.8)] for _ in range(n)]
        letras = "アイウエオカキクケコ01ﾊﾋﾌﾍﾎ<>/*+=TVON"
        for i, c in enumerate(self._columnas):
            c[0] += c[1]
            if c[0] - 60 > h:
                c[0], c[1] = self._azar.uniform(-40, 0), self._azar.uniform(0.6, 1.8)
            for k in range(6):
                y = c[0] - k * 10
                if 0 <= y <= h + 10:
                    alfa = 255 if k == 0 else max(0, 200 - k * 38)
                    p.setPen(QColor(180, 255, 200, alfa) if k == 0 else QColor(57, 255, 106, alfa))
                    p.drawText(QPointF(i * paso, y), letras[(i * 7 + int(c[0] / 10) + k) % len(letras)])
        # Líneas de barrido y un parpadeo muy leve
        for y in range(0, h, 3):
            p.fillRect(0, y, w, 1, QColor(0, 0, 0, 120))
        if int(self.t * 30) % 97 == 0:
            p.fillRect(self.rect(), QColor(57, 255, 106, 18))

    def _grilla(self, p: QPainter, t: Tema, _sonando: bool):
        """La grilla infinita hacia un sol de atardecer a rayas."""
        w, h = self.width(), self.height()
        cielo = QLinearGradient(0, 0, 0, h)
        cielo.setColorAt(0, _color("#1a0640"))
        cielo.setColorAt(1, _color("#5a0c6e"))
        p.fillRect(self.rect(), cielo)
        cx, horizonte = w * 0.68, h * 0.55
        sol = QLinearGradient(0, horizonte - 26, 0, horizonte)
        sol.setColorAt(0, _color("#ffd23f"))
        sol.setColorAt(1, _color("#ff2fd6"))
        p.setPen(Qt.NoPen)
        p.setBrush(sol)
        p.setClipRect(QRectF(0, 0, w, horizonte))
        p.drawEllipse(QPointF(cx, horizonte), 30, 30)
        for i in range(4):
            p.fillRect(QRectF(cx - 32, horizonte - 4 - i * 6, 64, 1.5 + i * 0.4), _color("#1a0640"))
        p.setClipping(False)
        p.fillRect(QRectF(0, horizonte, w, h - horizonte), _color("#0a0218"))
        p.setPen(QPen(_color("#22e4ff", 200), 1))
        for i in range(-14, 15):
            p.drawLine(QPointF(cx + i * 6, horizonte), QPointF(cx + i * 90, h))
        fase = (self.t * 0.8) % 1
        for k in range(6):
            z = (k + fase) / 6
            y = horizonte + (h - horizonte) * z * z
            p.setPen(QPen(_color("#ff2fd6", int(80 + 175 * z)), 1))
            p.drawLine(QPointF(0, y), QPointF(w, y))

    def _burbujas(self, p: QPainter, t: Tema, _sonando: bool):
        """Burbujas de vidrio que suben con un vaivén."""
        w, h = self.width(), self.height()
        cielo = QLinearGradient(0, 0, w, h)
        cielo.setColorAt(0, _color("#bfe8fb"))
        cielo.setColorAt(0.6, _color("#7fcff2"))
        cielo.setColorAt(1, _color("#55c2a8"))
        p.fillRect(self.rect(), cielo)
        if not self._particulas:
            self._particulas = [[self._azar.uniform(w * 0.35, w), self._azar.uniform(0, h + 20),
                                 self._azar.uniform(3, 11), self._azar.uniform(0.2, 0.6), self._azar.uniform(0, 6.28)]
                                for _ in range(max(14, w // 50))]
        for b in self._particulas:
            b[1] -= b[3]
            if b[1] + b[2] < 0:
                b[0], b[1] = self._azar.uniform(w * 0.35, w), h + b[2]
            x = b[0] + math.sin(self.t * 1.5 + b[4]) * 4
            g = QRadialGradient(QPointF(x - b[2] * 0.3, b[1] - b[2] * 0.3), b[2] * 1.2)
            g.setColorAt(0, QColor(255, 255, 255, 230))
            g.setColorAt(0.5, QColor(255, 255, 255, 60))
            g.setColorAt(1, QColor(255, 255, 255, 25))
            p.setPen(QPen(QColor(255, 255, 255, 180), 1))
            p.setBrush(g)
            p.drawEllipse(QPointF(x, b[1]), b[2], b[2])
