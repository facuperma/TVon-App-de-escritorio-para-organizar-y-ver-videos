"""Los muebles de la casa de BiriBiri (modelados con volúmenes, como el muñequito y la mascota) y las texturas del piso y las
paredes. Cada mueble se arma una sola vez por color y queda en la carpeta de caché; la escena los carga como .glb.

El origen de cada mueble es el centro de su lugar en el piso (y = 0) y el frente mira hacia +z."""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np

from . import avatar3d, casa
from .modelado import capsula, caja_redonda, elipsoide, esfera, guardar_glb, malla, restar, unir

VERSION = 1
PASO = 0.011


def _c(hexa: str) -> tuple[float, float, float]:
    r, g, b = avatar3d._rgb(hexa)
    return tuple(round(x ** 2.2, 4) for x in (r, g, b))      # glTF usa color lineal


def _mezcla(a: str, b: str, t: float) -> str:
    ra, rb = avatar3d._rgb(a), avatar3d._rgb(b)
    return "#%02x%02x%02x" % tuple(int((x + (y - x) * t) * 255) for x, y in zip(ra, rb))


def _cil(p, c, r, h):
    """Cilindro vertical: c es el centro de la base."""
    q = p - np.asarray(c, np.float32)
    d = np.stack([np.linalg.norm(q[..., [0, 2]], axis=-1) - r, np.abs(q[..., 1] - h / 2) - h / 2], -1)
    return np.minimum(np.maximum(d[..., 0], d[..., 1]), 0.0) + np.linalg.norm(np.maximum(d, 0.0), axis=-1)


def _caja(c, med, r=0.02):
    return lambda p: caja_redonda(p, c, med, r)


def _union(fs, k=0.0):
    def f(p):
        d = None
        for g in fs:
            e = g(p)
            d = e if d is None else unir(d, e, k)
        return d
    return f


def _mat(color, rug=0.75, metal=0.0):
    return {"color": _c(color), "rugosidad": rug, "metal": metal}


# --- Cada mueble: lista de piezas (nombre, función, material) ------------------------------------------------

def _sillon(color):
    claro = _mezcla(color, "#ffffff", 0.14)
    cuerpo = _union([_caja((0, 0.1, 0), (0.9, 0.14, 0.6), 0.03), _caja((0, 0.34, -0.2), (0.86, 0.4, 0.14), 0.05),
                     _caja((-0.4, 0.25, 0.02), (0.12, 0.28, 0.56), 0.045), _caja((0.4, 0.25, 0.02), (0.12, 0.28, 0.56), 0.045)], 0.015)
    almohadones = _union([_caja((-0.19, 0.22, 0.05), (0.36, 0.1, 0.44), 0.035), _caja((0.19, 0.22, 0.05), (0.36, 0.1, 0.44), 0.035),
                          _caja((-0.19, 0.38, -0.12), (0.34, 0.26, 0.08), 0.035), _caja((0.19, 0.38, -0.12), (0.34, 0.26, 0.08), 0.035)])
    patas = _union([lambda p, x=x, z=z: _cil(p, (x, 0, z), 0.025, 0.04) for x in (-0.4, 0.4) for z in (-0.24, 0.24)])
    return [("sillon", cuerpo, _mat(color, 0.9)), ("almohadones", almohadones, _mat(claro, 0.9)), ("patas", patas, _mat("#2a2420", 0.5))]


def _silla_gamer(color):
    negro = "#26262b"
    base = _union([lambda p, a=a: capsula(p, (0, 0.09, 0), (math.cos(a) * 0.22, 0.05, math.sin(a) * 0.22), 0.016) for a in
                   [i * 2 * math.pi / 5 for i in range(5)]] + [lambda p: _cil(p, (0, 0.08, 0), 0.026, 0.14)])
    ruedas = _union([lambda p, a=a: esfera(p, (math.cos(a) * 0.23, 0.028, math.sin(a) * 0.23), 0.028) for a in
                     [i * 2 * math.pi / 5 for i in range(5)]])
    asiento = _union([_caja((0, 0.24, 0.01), (0.44, 0.08, 0.44), 0.035), _caja((0.24, 0.36, 0.0), (0.04, 0.03, 0.3), 0.012),
                      _caja((-0.24, 0.36, 0.0), (0.04, 0.03, 0.3), 0.012), _caja((0.24, 0.3, 0.0), (0.03, 0.12, 0.04), 0.01),
                      _caja((-0.24, 0.3, 0.0), (0.03, 0.12, 0.04), 0.01)], 0.01)
    respaldo = _union([_caja((0, 0.52, -0.2), (0.42, 0.56, 0.09), 0.045), _caja((0, 0.86, -0.21), (0.24, 0.13, 0.08), 0.035)], 0.02)
    centro = _caja((0, 0.52, -0.15), (0.2, 0.46, 0.05), 0.025)
    return [("base", base, _mat(negro, 0.4, 0.4)), ("ruedas", ruedas, _mat("#111114", 0.6)), ("asiento", asiento, _mat(negro, 0.6)),
            ("respaldo", respaldo, _mat(color, 0.55)), ("centro", centro, _mat(negro, 0.6))]


def _mesa(color):
    tapa = _caja((0, 0.2, 0), (0.58, 0.045, 0.58), 0.018)
    patas = _union([lambda p, x=x, z=z: _cil(p, (x, 0, z), 0.024, 0.2) for x in (-0.24, 0.24) for z in (-0.24, 0.24)])
    return [("tapa", tapa, _mat(color, 0.5)), ("patas", patas, _mat(_mezcla(color, "#000000", 0.35), 0.5))]


def _lampara(color):
    base = _cil
    pie = _union([lambda p: _cil(p, (0, 0, 0), 0.09, 0.02), lambda p: capsula(p, (0, 0.02, 0), (0, 0.66, 0), 0.011)], 0.01)
    pantalla = lambda p: capsula(p, (0, 0.6, 0), (0, 0.82, 0), 0.115, 0.07)      # noqa: E731
    return [("pie", pie, _mat("#3a3a40", 0.4, 0.5)), ("pantalla", pantalla, _mat(color, 0.9))]


def _tele(color):
    mueble = _union([_caja((0, 0.1, 0), (0.88, 0.2, 0.29), 0.02)])
    patita = _caja((0, 0.23, 0), (0.12, 0.05, 0.07), 0.01)
    marco = _caja((0, 0.5, 0), (0.78, 0.44, 0.04), 0.012)
    pantalla = _caja((0, 0.5, 0.022), (0.72, 0.38, 0.012), 0.004)
    return [("mueble", mueble, _mat(color, 0.6)), ("patita", patita, _mat("#1d1d22", 0.5)), ("marco", marco, _mat("#18181c", 0.35, 0.3)),
            ("pantalla", pantalla, _mat("#3f78b8", 0.1))]


def _planta(color):
    maceta = lambda p: capsula(p, (0, 0.06, 0), (0, 0.17, 0), 0.075, 0.1)      # noqa: E731
    tierra = lambda p: _cil(p, (0, 0.16, 0), 0.085, 0.015)      # noqa: E731
    hojas = _union([lambda p, a=a: capsula(p, (0, 0.18, 0), (math.cos(a) * 0.1, 0.36 + 0.04 * (i % 3), math.sin(a) * 0.1), 0.02, 0.008)
                    for i, a in enumerate([k * 2 * math.pi / 7 for k in range(7)])] +
                   [lambda p: capsula(p, (0, 0.18, 0), (0, 0.46, 0), 0.02, 0.008)], 0.012)
    palas = _union([lambda p, a=a: elipsoide(p, (math.cos(a) * 0.115, 0.38 + 0.04 * (i % 3), math.sin(a) * 0.115), (0.045, 0.05, 0.02))
                    for i, a in enumerate([k * 2 * math.pi / 7 for k in range(7)])])
    return [("maceta", maceta, _mat(color, 0.7)), ("tierra", tierra, _mat("#3b2a1e", 1.0)), ("tallos", hojas, _mat("#3e8a45", 0.8)),
            ("hojas", palas, _mat("#4fa656", 0.7))]


def _alfombra(color):
    disco = lambda p: _cil(p, (0, 0, 0), 0.43, 0.012)      # noqa: E731
    centro = lambda p: _cil(p, (0, 0, 0), 0.27, 0.016)      # noqa: E731
    return [("alfombra", disco, _mat(color, 1.0)), ("centro", centro, _mat(_mezcla(color, "#ffffff", 0.35), 1.0))]


def _estante(color):
    marco = _union([_caja((-0.28, 0.45, 0), (0.04, 0.9, 0.28), 0.01), _caja((0.28, 0.45, 0), (0.04, 0.9, 0.28), 0.01),
                    _caja((0, 0.45, -0.12), (0.6, 0.9, 0.03), 0.008)] +
                   [_caja((0, y, 0), (0.6, 0.03, 0.28), 0.008) for y in (0.015, 0.3, 0.58, 0.89)])
    colores = ["#c0504d", "#4f81bd", "#e0a21a", "#3e8a45", "#8a5cd1"]
    libros = {c: [] for c in colores}
    azar = random.Random(7)
    for y0 in (0.315, 0.595):
        x = -0.24
        while x < 0.22:
            ancho = azar.choice((0.03, 0.04, 0.05))
            alto = azar.choice((0.17, 0.2, 0.22))
            c = azar.choice(colores)
            libros[c].append(_caja((x + ancho / 2, y0 + alto / 2, 0.01), (ancho, alto, 0.19), 0.005))
            x += ancho + 0.004
    piezas = [("marco", marco, _mat(color, 0.6))]
    for c, lista in libros.items():
        if lista:
            piezas.append((f"libros_{c[1:]}", _union(lista), _mat(c, 0.8)))
    return piezas


def _cama(color):
    madera = "#6b4f3a"
    if color == "boca":             # sábanas azul y oro, con la franja amarilla (el escudo lo pone la escena)
        marco = _union([_caja((0, 0.1, 0), (0.9, 0.14, 1.5), 0.03), _caja((0, 0.38, -0.74), (0.92, 0.46, 0.05), 0.02),
                        _caja((0, 0.2, 0.74), (0.92, 0.26, 0.04), 0.02)])
        colchon = _caja((0, 0.2, 0.0), (0.82, 0.12, 1.4), 0.045)
        manta = _caja((0, 0.235, 0.24), (0.86, 0.08, 0.92), 0.038)
        franja = _caja((0, 0.236, 0.1), (0.872, 0.084, 0.2), 0.036)
        almohada = lambda p: elipsoide(p, (0, 0.285, -0.55), (0.24, 0.045, 0.14))      # noqa: E731
        return [("marco", marco, _mat(madera, 0.6)), ("colchon", colchon, _mat("#f2f0ea", 0.95)), ("manta", manta, _mat("#123d8f", 0.9)),
                ("franja", franja, _mat("#f6c100", 0.85)), ("almohada", almohada, _mat("#f6c100", 0.95))]
    marco = _union([_caja((0, 0.1, 0), (0.9, 0.14, 1.5), 0.03), _caja((0, 0.38, -0.74), (0.92, 0.46, 0.05), 0.02),
                    _caja((0, 0.2, 0.74), (0.92, 0.26, 0.04), 0.02)])
    colchon = _caja((0, 0.2, 0.0), (0.82, 0.12, 1.4), 0.045)
    manta = _caja((0, 0.235, 0.24), (0.86, 0.08, 0.92), 0.038)
    almohada = lambda p: elipsoide(p, (0, 0.285, -0.55), (0.24, 0.045, 0.14))      # noqa: E731
    return [("marco", marco, _mat(madera, 0.6)), ("colchon", colchon, _mat("#f2f0ea", 0.95)), ("manta", manta, _mat(color, 0.95)),
            ("almohada", almohada, _mat("#ffffff", 0.95))]


def _heladera(color):
    cuerpo = _caja((0, 0.5, 0), (0.54, 1.0, 0.52), 0.045)
    division = _caja((0, 0.74, 0.262), (0.52, 0.014, 0.012), 0.004)
    manijas = _union([_caja((0.2, 0.86, 0.275), (0.026, 0.2, 0.03), 0.01), _caja((0.2, 0.52, 0.275), (0.026, 0.3, 0.03), 0.01)])
    return [("cuerpo", cuerpo, _mat(color, 0.35, 0.2)), ("division", division, _mat("#2a2a30", 0.5)), ("manijas", manijas, _mat("#8f939b", 0.3, 0.6))]


CONSTRUCTORES = {"sillon": _sillon, "silla_gamer": _silla_gamer, "mesa": _mesa, "lampara": _lampara, "tele": _tele,
                 "planta": _planta, "alfombra": _alfombra, "estante": _estante, "cama": _cama, "heladera": _heladera}


def archivo(item: str, color: str, carpeta) -> Path:
    return Path(carpeta) / f"{item}_{color.lstrip('#')}_v{VERSION}.glb"


def construir(item: str, color: str, carpeta, paso: float = PASO) -> Path:
    """Arma el mueble (si no estaba) y devuelve su .glb. Va en otro hilo: lleva uno o dos segundos."""
    destino = archivo(item, color, carpeta)
    if destino.exists():
        return destino
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    w, d = casa.CATALOGO[item]["celdas"]
    mx, mz = w * casa.CELDA / 2 + 0.06, d * casa.CELDA / 2 + 0.06
    caja = ((-mx, -0.01, -mz), (mx, 1.1, mz))
    mallas = []
    for nombre, funcion, material in CONSTRUCTORES[item](color):
        mallas.append((nombre, malla(funcion, caja[0], caja[1], paso), material))
    temporal = destino.with_suffix(".tmp")
    guardar_glb(temporal, mallas)
    temporal.replace(destino)
    return destino


# --- Texturas del piso y las paredes --------------------------------------------------------------------------

def textura(clave: str, dibujo: str, c1: str, c2: str, carpeta) -> Path:
    """Un cuadrito de 256 px que se repite (PNG en la carpeta de caché)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    destino = Path(carpeta) / f"tex_{clave}_{c1.lstrip('#')}_{c2.lstrip('#')}_v{VERSION}.png"
    if destino.exists():
        return destino
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    im = QImage(256, 256, QImage.Format_RGB32)
    im.fill(QColor(c1))
    p = QPainter(im)
    p.setRenderHint(QPainter.Antialiasing)
    azar = random.Random(clave)
    if dibujo == "tablas":
        for fila in range(8):
            y = fila * 32
            sombra = QColor(c1).darker(100 + azar.randint(0, 14))
            p.fillRect(QRectF(0, y, 256, 32), sombra)
            p.setPen(QPen(QColor(c2), 2))
            p.drawLine(0, y, 256, y)
            x = azar.randint(20, 230)
            p.drawLine(x, y, x, y + 32)
    elif dibujo == "damero":
        for i in range(4):
            for j in range(4):
                if (i + j) % 2:
                    p.fillRect(QRectF(i * 64, j * 64, 64, 64), QColor(c2))
    elif dibujo == "rayas":
        for i in range(0, 256, 64):
            p.fillRect(QRectF(i, 0, 32, 256), QColor(c2))
    elif dibujo == "ladrillos":
        p.fillRect(QRectF(0, 0, 256, 256), QColor("#d8cfc4"))
        for fila in range(8):
            desplazo = 32 if fila % 2 else 0
            for i in range(-1, 5):
                p.fillRect(QRectF(i * 64 + desplazo + 2, fila * 32 + 2, 60, 28),
                           QColor(c1).darker(100 + azar.randint(0, 22)))
    elif dibujo == "marmol":
        p.setPen(QPen(QColor(c2), 1.5))
        for _ in range(7):
            x, y = azar.randint(0, 256), azar.randint(0, 256)
            for _paso in range(5):
                nx, ny = x + azar.randint(-60, 60), y + azar.randint(-60, 60)
                p.drawLine(x, y, nx, ny)
                x, y = nx, ny
    p.end()
    im.save(str(destino))
    return destino


# --- Adornos de pared y la grilla para acomodar ---------------------------------------------------------------

def textura_grilla(carpeta) -> Path:
    """Un cuadrito transparente con el borde marcado: repetido sobre el piso es la grilla de medias celdas."""
    from PySide6.QtGui import QColor, QImage, QPainter

    destino = Path(carpeta) / f"grilla_v{VERSION}.png"
    if destino.exists():
        return destino
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    im = QImage(64, 64, QImage.Format_ARGB32)
    im.fill(QColor(0, 0, 0, 0))
    p = QPainter(im)
    p.fillRect(0, 0, 64, 2, QColor(255, 255, 255, 120))
    p.fillRect(0, 0, 2, 64, QColor(255, 255, 255, 120))
    p.end()
    im.save(str(destino))
    return destino


def textura_escudo_boca(carpeta) -> Path:
    """El escudo (dibujado acá, simplificado) para las sábanas de Boca: óvalo azul con borde y franja de oro, «CABJ» y
    estrellitas arriba."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen

    destino = Path(carpeta) / f"escudo_boca_v{VERSION}.png"
    if destino.exists():
        return destino
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    W, H = 256, 300
    im = QImage(W, H, QImage.Format_ARGB32)
    im.fill(QColor(0, 0, 0, 0))
    p = QPainter(im)
    p.setRenderHint(QPainter.Antialiasing)
    oro, azul = QColor("#f6c100"), QColor("#123d8f")
    # estrellas arriba
    def estrella(cx, cy, r):
        camino = QPainterPath()
        for k in range(10):
            ang = -math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.45
            punto = QPointF(cx + rr * math.cos(ang), cy + rr * math.sin(ang))
            camino.moveTo(punto) if k == 0 else camino.lineTo(punto)
        camino.closeSubpath()
        p.fillPath(camino, oro)
    for k in range(5):
        estrella(W / 2 + (k - 2) * 30, 26 + abs(k - 2) * 5, 11)
    # el óvalo
    ovalo = QRectF(28, 50, W - 56, H - 62)
    p.setPen(QPen(oro, 12))
    p.setBrush(azul)
    p.drawEllipse(ovalo)
    # la franja de oro, recortada al óvalo
    recorte = QPainterPath()
    recorte.addEllipse(ovalo.adjusted(6, 6, -6, -6))
    p.setClipPath(recorte)
    p.setPen(Qt.NoPen)
    p.fillRect(QRectF(0, ovalo.center().y() - 34, W, 68), oro)
    p.setClipping(False)
    fuente = QFont("Arial Black", 34)
    fuente.setBold(True)
    p.setFont(fuente)
    p.setPen(azul)
    p.drawText(QRectF(0, ovalo.center().y() - 34, W, 68), Qt.AlignCenter, "CABJ")
    p.end()
    im.save(str(destino))
    return destino


def textura_adorno(item: str, carpeta) -> Path:
    """El dibujo de un adorno de pared (PNG con transparencia donde no hay nada)."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

    destino = Path(carpeta) / f"adorno_{item}_v{VERSION}.png"
    if destino.exists():
        return destino
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    w, h = casa.ADORNOS[item]["tam"]
    W, H = int(512 * w / max(w, h)), int(512 * h / max(w, h))
    im = QImage(W, H, QImage.Format_ARGB32)
    im.fill(QColor(0, 0, 0, 0))
    p = QPainter(im)
    p.setRenderHint(QPainter.Antialiasing)
    azar = random.Random(item)
    if item == "ventana":
        cielo = QLinearGradient(0, 0, 0, H)
        cielo.setColorAt(0, QColor("#5aa8e6"))
        cielo.setColorAt(1, QColor("#cfe9fb"))
        p.fillRect(QRectF(0, 0, W, H), cielo)
        p.setBrush(QColor("#ffe27a"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(W * 0.66, H * 0.28), W * 0.07, W * 0.07)
        p.setBrush(QColor(255, 255, 255, 230))
        for cx, cy in ((0.32, 0.3), (0.52, 0.48)):
            for dx in (-0.05, 0.0, 0.05):
                p.drawEllipse(QPointF(W * (cx + dx), H * cy), W * 0.06, H * 0.05)
        p.setBrush(QColor("#6aa84f"))
        p.drawRect(QRectF(0, H * 0.82, W, H * 0.18))
        p.setPen(QPen(QColor("#f4f1ea"), W * 0.035))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(W * 0.0175, H * 0.0175, W * 0.965, H * 0.965))
        p.drawLine(QPointF(W / 2, 0), QPointF(W / 2, H))
        p.drawLine(QPointF(0, H / 2), QPointF(W, H / 2))
        p.setPen(Qt.NoPen)
        for lado in (0, 1):                              # cortinas
            cortina = QLinearGradient(0, 0, W * 0.16, 0)
            cortina.setColorAt(0, QColor("#c0504d"))
            cortina.setColorAt(1, QColor("#e07a6f"))
            p.setBrush(cortina)
            p.drawRect(QRectF(0 if lado == 0 else W * 0.84, 0, W * 0.16, H))
    elif item == "cuadro_paisaje":
        cielo = QLinearGradient(0, 0, 0, H)
        cielo.setColorAt(0, QColor("#f7b267"))
        cielo.setColorAt(1, QColor("#f4845f"))
        p.fillRect(QRectF(0, 0, W, H), cielo)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#fff1b8"))
        p.drawEllipse(QPointF(W * 0.5, H * 0.55), W * 0.12, W * 0.12)
        for color, pico, alto in (("#6d597a", 0.3, 0.45), ("#355070", 0.7, 0.55)):
            camino = QPainterPath(QPointF(0, H))
            camino.lineTo(W * pico, H * (1 - alto))
            camino.lineTo(W, H)
            p.setBrush(QColor(color))
            p.drawPath(camino)
        p.setBrush(QColor("#5fa8d3"))
        p.drawRect(QRectF(0, H * 0.85, W, H * 0.15))
    elif item == "cuadro_abstracto":
        p.fillRect(QRectF(0, 0, W, H), QColor("#f4efe6"))
        p.setPen(Qt.NoPen)
        for color in ("#e63946", "#457b9d", "#f1c453", "#2a9d8f", "#1d3557"):
            p.setBrush(QColor(color))
            if azar.random() < 0.5:
                r = W * azar.uniform(0.1, 0.25)
                p.drawEllipse(QPointF(azar.uniform(0.2, 0.8) * W, azar.uniform(0.2, 0.8) * H), r, r)
            else:
                p.drawRect(QRectF(azar.uniform(0, 0.6) * W, azar.uniform(0, 0.6) * H, W * azar.uniform(0.2, 0.4), H * azar.uniform(0.15, 0.35)))
    elif item == "poster":
        fondo = QLinearGradient(0, 0, 0, H)
        fondo.setColorAt(0, QColor("#1b1035"))
        fondo.setColorAt(1, QColor("#5b1f4f"))
        p.fillRect(QRectF(0, 0, W, H), fondo)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffcf5c"))
        p.drawEllipse(QPointF(W / 2, H * 0.4), W * 0.28, W * 0.28)
        p.setBrush(QColor("#1b1035"))
        for k in range(5):
            a = math.radians(k * 72)
            p.drawEllipse(QPointF(W / 2 + W * 0.16 * math.cos(a), H * 0.4 + W * 0.16 * math.sin(a)), W * 0.06, W * 0.06)
        p.setPen(QColor("#ffffff"))
        letra = QFont("Inter")
        letra.setPixelSize(int(W * 0.17))
        letra.setBold(True)
        p.setFont(letra)
        p.drawText(QRectF(0, H * 0.68, W, H * 0.16), Qt.AlignCenter, "CINE")
        chica = QFont("Inter")
        chica.setPixelSize(int(W * 0.065))
        p.setFont(chica)
        p.drawText(QRectF(0, H * 0.84, W, H * 0.1), Qt.AlignCenter, "TorrentVision presenta")
    elif item == "reloj":
        p.setBrush(QColor("#3b2a1e"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(0, 0, W, H))
        p.setBrush(QColor("#fbf7ef"))
        p.drawEllipse(QRectF(W * 0.07, H * 0.07, W * 0.86, H * 0.86))
        p.setPen(QPen(QColor("#3b2a1e"), W * 0.02))
        for k in range(12):
            a = math.radians(k * 30)
            p.drawLine(QPointF(W / 2 + W * 0.36 * math.sin(a), H / 2 - H * 0.36 * math.cos(a)),
                       QPointF(W / 2 + W * 0.4 * math.sin(a), H / 2 - H * 0.4 * math.cos(a)))
        p.setPen(QPen(QColor("#1d1d1f"), W * 0.035, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(W / 2, H / 2), QPointF(W / 2 - W * 0.17, H / 2 - H * 0.1))
        p.drawLine(QPointF(W / 2, H / 2), QPointF(W / 2 + W * 0.2, H / 2 - H * 0.22))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#c0504d"))
        p.drawEllipse(QPointF(W / 2, H / 2), W * 0.03, W * 0.03)
    elif item == "espejo":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#c9a227"))
        p.drawEllipse(QRectF(0, 0, W, H))
        vidrio = QRadialGradient(QPointF(W * 0.4, H * 0.35), W * 0.6)
        vidrio.setColorAt(0, QColor("#f2f6f8"))
        vidrio.setColorAt(1, QColor("#9fb0bc"))
        p.setBrush(QBrush(vidrio))
        p.drawEllipse(QRectF(W * 0.08, H * 0.06, W * 0.84, H * 0.88))
        p.setBrush(QColor(255, 255, 255, 140))
        reflejo = QPainterPath()
        reflejo.moveTo(W * 0.3, H * 0.2)
        reflejo.lineTo(W * 0.42, H * 0.2)
        reflejo.lineTo(W * 0.25, H * 0.6)
        reflejo.lineTo(W * 0.18, H * 0.6)
        p.drawPath(reflejo)
    elif item == "guirnalda":
        p.setPen(QPen(QColor("#2b2b2b"), H * 0.04))
        puntos = [QPointF(W * k / 40, H * (0.15 + 0.25 * math.sin(k / 40 * math.pi * 3) ** 2)) for k in range(41)]
        for a, b in zip(puntos, puntos[1:]):
            p.drawLine(a, b)
        p.setPen(Qt.NoPen)
        for k, punto in enumerate(puntos[2::4]):
            color = ("#ff5d5d", "#ffd23f", "#4ecdc4", "#a06cd5", "#7bd389")[k % 5]
            centro = punto + QPointF(0, H * 0.2)
            brillo = QRadialGradient(centro, H * 0.24)
            brillo.setColorAt(0, QColor(color))
            brillo.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(brillo))
            p.drawEllipse(centro, H * 0.24, H * 0.24)
            p.setBrush(QColor(color))
            p.drawEllipse(centro, H * 0.1, H * 0.13)
    p.end()
    im.save(str(destino))
    return destino
