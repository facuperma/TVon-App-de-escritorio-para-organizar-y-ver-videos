"""Las banderas del fondo de BiriBiri: se dibujan con QPainter (3:2, sin descargar nada) y quedan como PNG en la carpeta de
caché; la escena (vista3d) las pone flameando detrás del muñequito."""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

ANCHO, ALTO = 900, 600
VERSION = 1


def _rect(p, x, y, w, h, color):
    p.fillRect(QRectF(x, y, w, h), QColor(color))


def _franjas_h(p, colores, pesos=None):
    pesos = pesos or [1] * len(colores)
    total, y = sum(pesos), 0.0
    for c, w in zip(colores, pesos):
        h = ALTO * w / total
        _rect(p, 0, y, ANCHO, h + 1, c)
        y += h


def _franjas_v(p, colores, pesos=None):
    pesos = pesos or [1] * len(colores)
    total, x = sum(pesos), 0.0
    for c, w in zip(colores, pesos):
        a = ANCHO * w / total
        _rect(p, x, 0, a + 1, ALTO, c)
        x += a


def _poligono(p, puntos, color):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in puntos]))


def _circulo(p, cx, cy, r, color, borde=None, grosor=0):
    p.setBrush(QColor(color))
    if borde:
        p.setPen(QPen(QColor(borde), grosor))
    else:
        p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(cx, cy), r, r)


def _estrella(p, cx, cy, r, color, puntas=5, giro=-90.0):
    pts = []
    for i in range(puntas * 2):
        rad = r if i % 2 == 0 else r * (0.382 if puntas == 5 else 0.5)
        a = math.radians(giro + i * 180.0 / puntas)
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    _poligono(p, pts, color)


def _sol(p, cx, cy, r, color="#f6b40e", borde="#85340a", rayos=16):
    """El Sol de Mayo / Sol de la Bandera: rayos rectos y círculo con borde."""
    for i in range(rayos):
        a = 2 * math.pi * i / rayos
        a1, a2 = a - math.pi / rayos * 0.55, a + math.pi / rayos * 0.55
        punta = r * 1.75 if i % 2 == 0 else r * 1.5
        _poligono(p, [(cx + r * 0.9 * math.cos(a1), cy + r * 0.9 * math.sin(a1)),
                      (cx + punta * math.cos(a), cy + punta * math.sin(a)),
                      (cx + r * 0.9 * math.cos(a2), cy + r * 0.9 * math.sin(a2))], color)
    _circulo(p, cx, cy, r, color, borde, max(2.0, r * 0.07))
    p.setPen(QPen(QColor(borde), max(2.0, r * 0.06), Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(cx - r * 0.5, cy - r * 0.1, r, r * 0.6), 200 * 16, 140 * 16)       # la sonrisa
    p.drawPoint(QPointF(cx - r * 0.3, cy - r * 0.22))
    p.drawPoint(QPointF(cx + r * 0.3, cy - r * 0.22))


def _hoja(p, cx, cy, r, color):
    """Hoja de arce (aproximada)."""
    pts = [(0, -1), (0.2, -0.62), (0.5, -0.74), (0.42, -0.3), (0.82, -0.42), (0.7, -0.1), (0.98, 0.02), (0.58, 0.28),
           (0.64, 0.5), (0.1, 0.42), (0.08, 0.98), (-0.08, 0.98), (-0.1, 0.42), (-0.64, 0.5), (-0.58, 0.28),
           (-0.98, 0.02), (-0.7, -0.1), (-0.82, -0.42), (-0.42, -0.3), (-0.5, -0.74), (-0.2, -0.62)]
    _poligono(p, [(cx + x * r, cy + y * r) for x, y in pts], color)


def _ar(p):
    _franjas_h(p, ["#74acdf", "#ffffff", "#74acdf"])
    _sol(p, ANCHO / 2, ALTO / 2, 52)


def _uy(p):
    _franjas_h(p, ["#ffffff", "#0038a8"] * 4 + ["#ffffff"])
    _rect(p, 0, 0, ALTO * 4 / 9, ALTO * 4 / 9, "#ffffff")
    _sol(p, ALTO * 2 / 9, ALTO * 2 / 9, 38, rayos=16)


def _cl(p):
    _franjas_h(p, ["#ffffff", "#d52b1e"])
    _rect(p, 0, 0, ALTO / 2, ALTO / 2, "#0039a6")
    _estrella(p, ALTO / 4, ALTO / 4, 70, "#ffffff")


def _py(p):
    _franjas_h(p, ["#d52b1e", "#ffffff", "#0038a8"])
    _circulo(p, ANCHO / 2, ALTO / 2, 62, "#ffffff", "#2d6a30", 6)
    _estrella(p, ANCHO / 2, ALTO / 2, 40, "#f6c900")


def _bo(p):
    _franjas_h(p, ["#d52b1e", "#f9e300", "#007934"])


def _pe(p):
    _franjas_v(p, ["#d91023", "#ffffff", "#d91023"])
    _circulo(p, ANCHO / 2, ALTO / 2, 46, "#c9a227", "#6d4c1b", 4)


def _ec(p):
    _franjas_h(p, ["#ffdd00", "#034ea2", "#ed1c24"], [2, 1, 1])
    _circulo(p, ANCHO / 2, ALTO / 2, 52, "#7da7d9", "#6d4c1b", 5)


def _co(p):
    _franjas_h(p, ["#fcd116", "#003893", "#ce1126"], [2, 1, 1])


def _ve(p):
    _franjas_h(p, ["#ffcc00", "#00247d", "#cf142b"])
    for i in range(8):      # arco de 8 estrellas sobre la franja azul
        ang = math.radians(215 + i * (110 / 7))
        _estrella(p, ANCHO / 2 + 165 * math.cos(ang), 420 + 165 * math.sin(ang), 17, "#ffffff")


def _br(p):
    p.fillRect(QRectF(0, 0, ANCHO, ALTO), QColor("#009c3b"))
    _poligono(p, [(ANCHO / 2, 40), (ANCHO - 60, ALTO / 2), (ANCHO / 2, ALTO - 40), (60, ALTO / 2)], "#ffdf00")
    _circulo(p, ANCHO / 2, ALTO / 2, 125, "#002776")
    p.setPen(QPen(QColor("#ffffff"), 18))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(ANCHO / 2 - 150, ALTO / 2 - 20, 300, 130), 20 * 16, 140 * 16)


def _mx(p):
    _franjas_v(p, ["#006847", "#ffffff", "#ce1126"])
    _circulo(p, ANCHO / 2, ALTO / 2, 70, "#8b5a2b")
    _circulo(p, ANCHO / 2, ALTO / 2 + 10, 48, "#2e7d32")
    p.setPen(QPen(QColor("#2e7d32"), 8))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(ANCHO / 2 - 90, ALTO / 2 - 20, 180, 130), 200 * 16, 140 * 16)


def _cu(p):
    _franjas_h(p, ["#002a8f", "#ffffff"] * 2 + ["#002a8f"])
    _poligono(p, [(0, 0), (ALTO * 0.87, ALTO / 2), (0, ALTO)], "#cf142b")
    _estrella(p, ALTO * 0.29, ALTO / 2, 62, "#ffffff")


def _es(p):
    _franjas_h(p, ["#aa151b", "#f1bf00", "#aa151b"], [1, 2, 1])
    _rect(p, 190, 235, 60, 130, "#ad1519")
    _circulo(p, 220, 300, 38, "#c8a84b", "#7c5a1a", 4)


def _pt(p):
    _franjas_v(p, ["#006600", "#ff0000"], [2, 3])
    _circulo(p, ANCHO * 0.4, ALTO / 2, 78, "#ffcc00", "#ffffff", 5)
    _circulo(p, ANCHO * 0.4, ALTO / 2, 48, "#ffffff", "#ff0000", 6)


def _fr(p):
    _franjas_v(p, ["#0055a4", "#ffffff", "#ef4135"])


def _it(p):
    _franjas_v(p, ["#009246", "#ffffff", "#ce2b37"])


def _de(p):
    _franjas_h(p, ["#000000", "#dd0000", "#ffce00"])


def _ru(p):
    _franjas_h(p, ["#ffffff", "#0039a6", "#d52b1e"])


def _gb(p):
    p.fillRect(QRectF(0, 0, ANCHO, ALTO), QColor("#012169"))
    for color, grosor in (("#ffffff", 120), ("#c8102e", 40)):
        p.setPen(QPen(QColor(color), grosor, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(0, 0), QPointF(ANCHO, ALTO))
        p.drawLine(QPointF(ANCHO, 0), QPointF(0, ALTO))
    p.setPen(Qt.NoPen)
    _rect(p, 0, ALTO / 2 - 100, ANCHO, 200, "#ffffff")
    _rect(p, ANCHO / 2 - 100, 0, 200, ALTO, "#ffffff")
    _rect(p, 0, ALTO / 2 - 60, ANCHO, 120, "#c8102e")
    _rect(p, ANCHO / 2 - 60, 0, 120, ALTO, "#c8102e")


def _us(p):
    _franjas_h(p, ["#b22234", "#ffffff"] * 6 + ["#b22234"])
    ancho, alto = ANCHO * 0.4, ALTO * 7 / 13
    _rect(p, 0, 0, ancho, alto, "#3c3b6e")
    for fila in range(9):
        n = 6 if fila % 2 == 0 else 5
        for i in range(n):
            x = ancho * (0.07 + (0.86 / 5) * i + (0 if n == 6 else 0.86 / 10))
            _estrella(p, x, alto * (0.07 + 0.86 * fila / 8), 11, "#ffffff")


def _ca(p):
    _franjas_v(p, ["#d80621", "#ffffff", "#d80621"], [1, 2, 1])
    _hoja(p, ANCHO / 2, ALTO / 2, 130, "#d80621")


def _il(p):
    _franjas_h(p, ["#ffffff"])
    _rect(p, 0, ALTO * 0.09, ANCHO, ALTO * 0.12, "#0038b8")
    _rect(p, 0, ALTO * 0.79, ANCHO, ALTO * 0.12, "#0038b8")
    p.setPen(QPen(QColor("#0038b8"), 11))
    p.setBrush(Qt.NoBrush)
    r = 88
    for giro in (0, 180):
        a = [(ANCHO / 2 + r * math.cos(math.radians(-90 + giro + k * 120)), ALTO / 2 + r * math.sin(math.radians(-90 + giro + k * 120)))
             for k in range(3)]
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in a]))


def _cn(p):
    p.fillRect(QRectF(0, 0, ANCHO, ALTO), QColor("#de2910"))
    _estrella(p, 150, 140, 80, "#ffde00")
    for cx, cy in ((300, 60), (350, 130), (350, 210), (300, 275)):
        _estrella(p, cx, cy, 26, "#ffde00")


def _jp(p):
    p.fillRect(QRectF(0, 0, ANCHO, ALTO), QColor("#ffffff"))
    _circulo(p, ANCHO / 2, ALTO / 2, 180, "#bc002d")


DIBUJOS = {"ar": _ar, "uy": _uy, "cl": _cl, "py": _py, "bo": _bo, "pe": _pe, "ec": _ec, "co": _co, "ve": _ve, "br": _br,
           "mx": _mx, "cu": _cu, "es": _es, "pt": _pt, "fr": _fr, "it": _it, "de": _de, "gb": _gb, "ru": _ru, "us": _us,
           "ca": _ca, "il": _il, "cn": _cn, "jp": _jp}


def ruta(codigo: str, carpeta: Path) -> Path | None:
    """El PNG de la bandera (lo dibuja la primera vez); None si no hay bandera con ese código."""
    dibujo = DIBUJOS.get(codigo)
    if dibujo is None:
        return None
    destino = Path(carpeta) / "banderas" / f"{codigo}_{VERSION}.png"
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen = QImage(ANCHO, ALTO, QImage.Format_RGB32)
    imagen.fill(QColor("#ffffff"))
    p = QPainter(imagen)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    dibujo(p)
    p.end()
    imagen.save(str(destino), "PNG")
    return destino
