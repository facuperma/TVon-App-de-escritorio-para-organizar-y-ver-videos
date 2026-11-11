"""El Protagonista hecho con formas suaves (organizador/modelado.py) y dibujado con Qt Quick 3D.

Mide ~1 de alto, estilo muñequito cabezón. Se arma en 5 partes que se animan por separado (cabeza, torso, brazos y
piernas), cada una un .glb en la carpeta de caché; las opciones son las mismas de avatar3d (OPCIONES)."""
from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from math import comb
from pathlib import Path

import numpy as np

from . import avatar3d
from .modelado import cortar, curva, elipsoide, esfera, capsula, caja_redonda, guardar_glb, malla, restar, unir

VERSION = 17 # subir si cambia la forma: así se rearman los que están en caché
PASO = 0.0045

# Puntos de articulación (para animar): hombros, cuello, cadera
HOMBRO = 0.155, 0.585, 0.0
CUELLO = 0.0, 0.64, 0.0
CABEZA = (0.0, 0.83, 0.0)


def _c(hexa: str) -> tuple[float, float, float]:
    r, g, b = avatar3d._rgb(hexa)
    # glTF usa color lineal
    return tuple(round(x ** 2.2, 4) for x in (r, g, b))


def _mezclar(a: str, b: str, t: float) -> str:
    ra, rb = avatar3d._rgb(a), avatar3d._rgb(b)
    return "#%02x%02x%02x" % tuple(int((x + (y - x) * t) * 255) for x, y in zip(ra, rb))


def _oscuro(a: str, f: float) -> str:
    return avatar3d._oscurecer(a, f)


def cilindro(p, c, r, h, redondeo=0.004):
    """Cilindro vertical con base en c, radio r, alto h, bordes redondeados."""
    q = p - np.asarray(c, np.float32)
    d = np.stack([np.linalg.norm(q[..., [0, 2]], axis=-1) - (r - redondeo), np.abs(q[..., 1] - h / 2) - (h / 2 - redondeo)], -1)
    return np.minimum(np.maximum(d[..., 0], d[..., 1]), 0.0) + np.linalg.norm(np.maximum(d, 0.0), axis=-1) - redondeo


def toro_z(p, c, radio, grosor):
    """Aro mirando hacia adelante (eje z): los marcos de los anteojos."""
    q = p - np.asarray(c, np.float32)
    return np.sqrt((np.linalg.norm(q[..., :2], axis=-1) - radio) ** 2 + q[..., 2] ** 2) - grosor


def toro_y(p, c, radio, grosor, escala_z=1.0):
    """Aro horizontal (eje y): bufanda, borde del gorro."""
    q = p - np.asarray(c, np.float32)
    q = q * np.array([1, 1, 1 / escala_z], np.float32)
    return np.sqrt((np.linalg.norm(q[..., [0, 2]], axis=-1) - radio) ** 2 + q[..., 1] ** 2) - grosor


def plano(p, normal, d):
    """Semiespacio: negativo donde normal·p < d."""
    return p @ np.asarray(normal, np.float32) - d


# --- Cosas que van pegadas a la cara (ojos, cejas, bocas) y formas planas --------------------------------------

@lru_cache(maxsize=None)
def _zc(x: float, y: float) -> float:
    """Hasta dónde llega la cara (sin foto) hacia adelante en (x, y): así lo que se pega ahí sigue su curva."""
    zs = np.linspace(0.30, 0.0, 1201, dtype=np.float32)
    pts = np.stack([np.full_like(zs, x), np.full_like(zs, y), zs], 1)
    return float(zs[int(np.argmax(_cabeza_sdf(pts) <= 0))])


def _tubo_cara(p, ctrl, r0, r1, dz=0.003, n=9):
    """Un trazo (ceja, sonrisa, ojo cerrado) que sigue la curva de la cara: Bézier en (x, y) con el z de la cara."""
    t = np.linspace(0, 1, n)
    k = len(ctrl) - 1
    xy = sum(comb(k, i) * ((1 - t) ** (k - i) * t ** i)[:, None] * np.asarray(ctrl[i], float) for i in range(k + 1))
    pts = [(float(x), float(y), _zc(round(float(x), 3), round(float(y), 3)) + dz) for x, y in xy]
    d = None
    for i in range(n - 1):
        c = capsula(p, pts[i], pts[i + 1], r0 + (r1 - r0) * i / (n - 1), r0 + (r1 - r0) * (i + 1) / (n - 1))
        d = c if d is None else np.minimum(d, c)
    return d


def _calco(forma, alto=0.005):
    """Una forma plana (de x, y) pegada a la cara como una calcomanía de `alto` de espesor: siempre sobre la superficie."""
    def f(p):
        capa = cortar(forma(p), _cabeza_sdf(p) - alto)
        capa = cortar(capa, -(_cabeza_sdf(p) + 0.012))
        return cortar(capa, plano(p, (0, 0, -1), -0.05))
    return f


def _elipse2d(p, cx, cy, a, b):
    return (np.hypot((p[..., 0] - cx) / a, (p[..., 1] - cy) / b) - 1.0) * min(a, b)


def _caja2d(x, y, mx, my, r):
    """Rectángulo redondeado en 2D: medio ancho, medio alto, radio de las esquinas."""
    qx, qy = np.abs(x) - (mx - r), np.abs(y) - (my - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def _corazon2d(x, y, e):
    """Corazón (punta abajo) de tamaño e, centrado más o menos en (0, 0)."""
    x = np.abs(x) / e
    y = y / e + 0.55
    arriba = np.hypot(x - 0.25, y - 0.75) - math.sqrt(2) / 4
    q = np.maximum(x + y, 0) * 0.5
    abajo = np.sqrt(np.minimum(x ** 2 + (y - 1) ** 2, (x - q) ** 2 + (y - q) ** 2)) * np.sign(x - y)
    return np.where(y + x > 1.0, arriba, abajo) * e


# --- Cuerpo -----------------------------------------------------------------------------------------------

# Cuánto cambia el cuerpo según el género: (cadera, pecho). Mujer: más cadera y menos pecho; hombre: al revés
GENERO_CUERPO = {"hombre": (0.98, 1.07), "mujer": (1.08, 0.93), "nobinario": (1.0, 1.0)}


def _medidas(s: dict):
    r0, r1, ez = {"flaco": (0.117, 0.105, 0.74), "robusto": (0.136, 0.122, 0.8)}.get(s["cuerpo"], (0.125, 0.112, 0.76))
    cadera, pecho = GENERO_CUERPO.get(s.get("genero"), (1.0, 1.0))
    return r0 * cadera, r1 * pecho, ez


# Escala de todo el muñeco según la contextura (ancho, alto, profundidad)
ESCALA = {"flaco": (0.88, 1.03, 0.88), "robusto": (1.17, 0.97, 1.14), "normal": (1.0, 1.0, 1.0)}


def _torso(p, s, extra=0.0):
    r0, r1, ez = _medidas(s)
    q = p * np.array([1, 1, 1 / ez], np.float32)
    t = capsula(q, (0, 0.475, 0), (0, 0.585, 0), r0 + extra, r1 + extra) * ez
    hombros = capsula(p, (-HOMBRO[0] + 0.02, 0.585, 0), (HOMBRO[0] - 0.02, 0.585, 0), 0.05 + extra)
    t = unir(t, hombros, 0.05)
    # Ruedo: más ancho que la cadera del pantalón y cortado derecho abajo
    ruedo = capsula(q, (0, 0.445, 0), (0, 0.5, 0), r0 + 0.018 + extra, r0 + 0.006 + extra) * ez
    t = unir(t, ruedo, 0.03)
    return cortar(t, -plano(p, (0, 1, 0), 0.418), 0.006)


def _cabeza_sdf(p, con_foto=False):
    cabeza = elipsoide(p, CABEZA, (0.2, 0.19, 0.18))
    cachetes = elipsoide(p, (0, 0.77, 0.03), (0.155, 0.11, 0.14))
    d = unir(cabeza, cachetes, 0.06)
    if con_foto:
        # La cara sale hacia adelante en el centro (como una lente): la foto va pegada a esa curva
        d = d + _hondo_foto(p)
    return d


RADIO_FOTO, RADIO_FOTO_X, ELEVA_FOTO = 0.122, 0.138, 0.034   # alto, ancho (apenas más ancho que alto) y cuánto sale
SALIDA_FOTO = ELEVA_FOTO + 0.004   # lo que hay que adelantar lo que va sobre la cara (lentes) cuando hay foto


def _hondo_foto(p):
    """La cara se abulta hacia adelante en el centro del cuadro de la foto, como una lente: parejo en el borde y lo más
    alto en el medio (ahí va la foto). Alrededor, un reborde finito."""
    r2 = (p[..., 0] / RADIO_FOTO_X) ** 2 + ((p[..., 1] - 0.8) / RADIO_FOTO) ** 2
    domo = ELEVA_FOTO * np.clip(1 - r2, 0, 1) ** 1.15
    reborde = 0.0024 * np.exp(-(((np.sqrt(r2) - 1.05) / 0.07) ** 2))
    return -(domo + reborde) * (p[..., 2] > 0.04)


def _linea_pelo(p):
    """Donde empieza el pelo: más alto adelante (la frente) y bajo en la nuca."""
    a = math.radians(38)
    return -(p[..., 1] * math.cos(a) - p[..., 2] * math.sin(a) - 0.655)


def _casco(p, margen=0.018):
    casco = elipsoide(p, (0, 0.835, -0.012), (0.2 + margen, 0.19 + margen, 0.18 + margen))
    # Surcos que bajan desde la coronilla: se ve como pelo peinado y no como un casco
    angulo = np.arctan2(p[..., 0], p[..., 2] + 0.02)
    casco = casco + 0.0045 * np.sin(angulo * 30.0) * np.clip((p[..., 1] - 0.7) * 6, 0, 1)
    return cortar(casco, _linea_pelo(p), 0.015)


def _pelo(p, s):
    est = s["peinado"]
    tapado = s["cabeza"] != "ninguno"
    if est == "pelado":
        return None
    d = _casco(p)
    if est == "corto":
        for x in (-0.09, -0.03, 0.03, 0.09):
            d = unir(d, curva(p, [(x * 0.6, 1.0, -0.02), (x, 1.03, 0.08), (x * 1.15, 0.95, 0.17)], 0.04, 0.012), 0.02)
    elif est == "flequillo":
        # Una capa que baja sobre la frente con el borde ondulado (mechones) y se funde con el resto del pelo
        capa = elipsoide(p, (0, 0.835, -0.005), (0.222, 0.212, 0.205))
        borde = 0.858 + 0.022 * np.abs(np.sin(p[..., 0] * 30.0)) + 0.35 * p[..., 0] ** 2
        capa = cortar(capa, borde - p[..., 1], 0.012)
        capa = cortar(capa, plano(p, (0, 0, -1), -0.02), 0.03)
        d = unir(d, capa, 0.03)
    elif est == "largo":
        # Cae por detrás de la cabeza y por los costados, AFUERA de los hombros y los brazos (la cabeza está agrandada y el
        # cuerpo achicado: más cerca, el pelo atravesaba el cuerpo al girar la cabeza), con las puntas redondeadas
        espalda = elipsoide(p, (0, 0.73, -0.12), (0.2, 0.22, 0.09))
        d = unir(d, cortar(espalda, plano(p, (0, 0, 1), -0.02), 0.03), 0.04)
        for lado in (-1, 1):
            # Un mechón a cada lado, pegado a la cabeza y apenas por afuera de los brazos, que termina en punta
            d = unir(d, curva(p, [(lado * 0.19, 0.9, 0.02), (lado * 0.215, 0.76, -0.02), (lado * 0.2, 0.6, -0.05)],
                              0.052, 0.018), 0.04)
        for x in (-0.12, -0.05, 0.03, 0.1):
            d = unir(d, curva(p, [(x * 0.3, 1.0, 0.02), (x, 0.98, 0.14), (x * 1.6, 0.88, 0.18)], 0.05, 0.016), 0.03)
    elif est == "colita":
        d = unir(d, curva(p, [(0, 0.9, -0.2), (0, 0.98, -0.33), (0, 0.78, -0.36), (0, 0.6, -0.27)], 0.065, 0.014), 0.035)
    elif est == "trenzas":
        # Colgando por afuera de los hombros (si no, se meten en los brazos), una cuenta tras otra y un moñito al final
        for lado in (-1, 1):
            for i in range(7):
                y = 0.8 - i * 0.04
                x = lado * (0.215 - i * 0.002) + (0.007 if i % 2 else -0.007) * lado
                d = unir(d, esfera(p, (x, y, -0.03), 0.034 - i * 0.002), 0.012)
            d = unir(d, curva(p, [(lado * 0.211, 0.535, -0.03), (lado * 0.211, 0.5, -0.03)], 0.02, 0.006), 0.01)
    elif est == "rulos":
        d = _rulos(p, d, 0.205, 0.045, 70)
    elif est == "afro":
        base = elipsoide(p, (0, 0.87, -0.03), (0.24, 0.23, 0.225))
        base = restar(base, elipsoide(p, (0, 0.77, 0.2), (0.17, 0.15, 0.14)), 0.03)
        d = unir(d, cortar(base, _linea_pelo(p) - 0.02, 0.04), 0.03)
        d = _rulos(p, d, 0.255, 0.05, 150, centro=(0, 0.87, -0.03), limite=-0.035)
    elif est == "cresta":
        d = _casco(p, 0.006)
        for i, z in enumerate((0.15, 0.08, 0.0, -0.08, -0.15)):
            alto = 0.13 - abs(i - 1.5) * 0.015
            d = unir(d, curva(p, [(0, 0.98, z), (0, 1.0 + alto * 0.7, z - 0.03), (0, 1.0 + alto, z - 0.08)],
                                0.035, 0.004), 0.02)
    elif est == "rodete":
        d = unir(d, elipsoide(p, (0, 1.0, -0.11), (0.08, 0.075, 0.08)), 0.03)
    if tapado and est in ("cresta", "rodete", "afro"):
        d = cortar(d, plano(p, (0, 1, 0), 0.96), 0.01)
    return d


def _rulos(p, d, radio, bola, cuantos, centro=(0, 0.84, -0.015), limite=0.02):
    """Rulos: bolitas repartidas parejo (espiral de Fibonacci) por la parte del casco que tiene pelo."""
    c = np.asarray(centro, np.float32)
    dorado = math.pi * (3 - math.sqrt(5))
    for i in range(cuantos):
        y = 1 - 2 * (i + 0.5) / cuantos
        r = math.sqrt(1 - y * y)
        ang = dorado * i
        punto = c + radio * np.array([r * math.cos(ang), y, r * math.sin(ang)], np.float32)
        if float(_linea_pelo(punto[None])[0]) > limite:
            continue
        d = unir(d, esfera(p, punto, bola), 0.018)
    return d


# Cuánto sobresale la tela del cuerpo según la prenda (el saco y el sweater son más gruesos que una remera)
ESPESOR = {"remera": 0.012, "boca": 0.012, "camisa": 0.012, "musculosa": 0.012, "blusa": 0.012, "pollera": 0.012,
           "peto": 0.012, "vestido": 0.012, "vestido_largo": 0.012, "traje": 0.03, "sweater": 0.026}
FALDA_PIEL = ("vestido", "vestido_largo", "pollera")     # con estas, las piernas se ven (son de piel)
MANGA_LARGA = ("buzo", "campera", "sweater", "traje")


def _cono(p, y_abajo, r_abajo, ez=0.85):
    """La pollera del vestido: un cono desde el pecho (de ancho r_abajo abajo) con la misma profundidad que el torso."""
    q = p * np.array([1, 1, 1 / ez], np.float32)
    return capsula(q, (0, 0.585, 0), (0, y_abajo, 0), 0.105, r_abajo) * ez


@lru_cache(maxsize=None)
def _z_frente(cuerpo: str, genero: str, y: float, extra: float) -> float:
    """Hasta dónde llega el frente del torso (con tela de espesor `extra`) a la altura y: ahí se pegan botones y corbata."""
    s = {"cuerpo": cuerpo, "genero": genero}
    zs = np.linspace(0.3, 0.0, 1201, dtype=np.float32)
    pts = np.stack([np.zeros_like(zs), np.full_like(zs, y), zs], 1)
    return float(zs[int(np.argmax(_torso(pts, s, extra) <= 0))])


def _zf(s, y, extra):
    return _z_frente(s["cuerpo"], s.get("genero", "nobinario"), round(y, 3), extra)


def _ropa_torso(p, s):
    """La ropa de arriba (sin mangas)."""
    ropa = s["ropa"]
    ext = ESPESOR.get(ropa, 0.022)
    if ropa == "vestido":
        return cortar(unir(_torso(p, s, ext), _cono(p, 0.2, 0.2), 0.04), -plano(p, (0, 1, 0), 0.2), 0.01)
    if ropa == "vestido_largo":
        # Largo casi hasta los pies, con vuelo y el borde ondulado
        borde = 0.115 + 0.012 * np.sin(np.arctan2(p[..., 0], p[..., 2]) * 14.0)
        return cortar(unir(_torso(p, s, ext), _cono(p, 0.1, 0.28), 0.05), borde - p[..., 1], 0.01)
    t = _torso(p, s, ext)
    if ropa == "campera":
        abertura = cortar(np.abs(p[..., 0]) - 0.035, plano(p, (0, 0, -1), -0.02), 0.0)
        t = restar(t, abertura, 0.008)
    if ropa == "traje":
        # Saco abierto en V: se ve la camisa y la corbata
        v = cortar(np.abs(p[..., 0]) - 0.05 * np.clip((p[..., 1] - 0.45) / 0.15, 0, 1.2), plano(p, (0, 0, -1), -0.02), 0.0)
        t = restar(t, v, 0.006)
    if ropa == "musculosa":
        # Sin mangas: los hombros quedan al aire (arriba de la cintura solo queda la parte de adelante de las tiras)
        for lado in (-1, 1):
            t = restar(t, elipsoide(p, (lado * 0.16, 0.555, 0.0), (0.07, 0.12, 0.25)), 0.02)
        t = restar(t, elipsoide(p, (0, 0.64, 0.1), (0.075, 0.085, 0.09)), 0.014)
    cuello = capsula(p, (0, 0.59, 0), (0, 0.64, 0), 0.06)
    t = restar(t, cuello, 0.01)
    if ropa == "buzo":
        capucha = elipsoide(p, (0, 0.64, -0.1), (0.13, 0.08, 0.08))
        t = unir(t, capucha, 0.04)
    if ropa == "sweater":
        # Cuello alto: un tubo alrededor del cuello
        tubo = restar(capsula(p, (0, 0.58, 0), (0, 0.69, 0), 0.072), capsula(p, (0, 0.55, 0), (0, 0.75, 0), 0.05), 0.004)
        t = unir(t, tubo, 0.015)
    return t


def _falda(p, s):
    """La pollera (de «remera y pollera»): ancha, plisada y con el borde ondulado, hasta las rodillas."""
    r0 = _medidas(s)[0]
    q = p * np.array([1, 1, 1 / 0.85], np.float32)
    f = capsula(q, (0, 0.5, 0), (0, 0.3, 0), r0 + 0.022, 0.21) * 0.85
    ang = np.arctan2(p[..., 0], p[..., 2])
    f = f + 0.005 * np.sin(ang * 18.0) * np.clip((0.5 - p[..., 1]) * 6, 0, 1)
    f = cortar(f, 0.3 + 0.008 * np.sin(ang * 9.0) - p[..., 1], 0.008)
    return cortar(f, p[..., 1] - 0.5, 0.01)


def _peto(p, s):
    """El peto: la cintura del pantalón (todo alrededor) y el pechero de adelante, entre las tiras."""
    zona = np.minimum(p[..., 1] - 0.5, np.maximum(np.maximum(-p[..., 2], p[..., 1] - 0.57), np.abs(p[..., 0]) - 0.09))
    return cortar(_torso(p, s, 0.034), zona, 0.008)


def _tiras_peto(p, s):
    d = None
    for lado in (-1, 1):
        zf = _zf(s, 0.55, 0.034)
        t = curva(p, [(lado * 0.07, 0.555, zf), (lado * 0.082, 0.64, 0.03), (lado * 0.07, 0.585, -0.1)], 0.016, 0.016)
        d = t if d is None else unir(d, t, 0.0)
    return d


def _botones(p, s, alturas, extra, r=0.007):
    d = None
    for y in alturas:
        b = esfera(p, (0, y, _zf(s, y, extra) + 0.004), r)
        d = b if d is None else unir(d, b, 0.0)
    return d


def _detalles_ropa(lista, s, caja, tela):
    """Lo que lleva cada prenda aparte de la tela principal (cuello, botones, corbata, moño…)."""
    ropa, remera, ca = s["ropa"], s["remera"], s["accesorio_color"]
    blanco = "#f4f4f4"
    if ropa == "camisa":
        cuello = _mezclar(remera, "#ffffff", 0.3)

        def solapas(p):
            d = toro_y(p, (0, 0.618, 0), 0.058, 0.01, 0.9)
            for lado in (-1, 1):
                d = unir(d, capsula(p, (lado * 0.056, 0.634, _zf(s, 0.63, 0.012) - 0.014),
                                    (lado * 0.008, 0.578, _zf(s, 0.585, 0.012) + 0.01), 0.02, 0.012), 0.008)
            return d
        lista.append(("cuello_camisa", solapas, caja, tela(cuello)))
        lista.append(("botones", lambda p: _botones(p, s, (0.565, 0.525, 0.485, 0.445), 0.012), caja, tela(blanco, 0.4)))
    elif ropa == "traje":
        lista.append(("camisa_traje", lambda p: restar(cortar(_torso(p, s, 0.014), 0.43 - p[..., 1], 0.008),
                                                       capsula(p, (0, 0.59, 0), (0, 0.64, 0), 0.06), 0.01), caja, tela(blanco, 0.7)))
        lista.append(("solapas", lambda p: unir(
            capsula(p, (-0.054, 0.598, _zf(s, 0.598, 0.03)), (-0.004, 0.452, _zf(s, 0.452, 0.03)), 0.012, 0.01),
            capsula(p, (0.054, 0.598, _zf(s, 0.598, 0.03)), (0.004, 0.452, _zf(s, 0.452, 0.03)), 0.012, 0.01), 0.0),
            caja, tela(_oscuro(remera, 0.82))))

        def corbata(p):
            zt = lambda y: _zf(s, y, 0.014) + 0.007  # noqa: E731
            nudo = esfera(p, (0, 0.585, zt(0.585)), 0.019)
            cuerpo = capsula(p, (0, 0.575, zt(0.575)), (0, 0.475, zt(0.475)), 0.014, 0.024)
            punta = capsula(p, (0, 0.475, zt(0.475)), (0, 0.438, zt(0.438)), 0.024, 0.004)
            return unir(unir(nudo, cuerpo, 0.012), punta, 0.01)
        lista.append(("corbata", corbata, caja, tela(ca, 0.55)))
        lista.append(("botones", lambda p: _botones(p, s, (0.425,), 0.03, r=0.008), caja, tela("#2b2b2b", 0.4)))
    elif ropa == "pollera":
        lista.append(("pollera", lambda p: _falda(p, s), caja, tela(s["pantalon"], 0.85)))
        lista.append(("cintura", lambda p: cortar(_torso(p, s, 0.03), np.abs(p[..., 1] - 0.485) - 0.02), caja,
                      tela(_oscuro(s["pantalon"], 0.8), 0.8)))
    elif ropa == "peto":
        lista.append(("peto", lambda p: _peto(p, s), caja, tela(s["pantalon"], 0.85)))
        lista.append(("tiras", lambda p: _tiras_peto(p, s), caja, tela(s["pantalon"], 0.85)))
        lista.append(("botones_peto", lambda p: unir(esfera(p, (-0.072, 0.545, _zf(s, 0.545, 0.034) + 0.004), 0.011),
                                                      esfera(p, (0.072, 0.545, _zf(s, 0.545, 0.034) + 0.004), 0.011)),
                      caja, {"color": _c("#e0b23a"), "rugosidad": 0.3, "metal": 0.8}))
    elif ropa == "blusa":
        def mono(p):
            z = _zf(s, 0.6, 0.012) + 0.008
            d = esfera(p, (0, 0.602, z), 0.014)
            for lado in (-1, 1):
                d = unir(d, elipsoide(p, (lado * 0.03, 0.604, z - 0.002), (0.03, 0.02, 0.013)), 0.01)
            return d
        lista.append(("mono", mono, caja, tela(ca, 0.5)))
        lista.append(("botones", lambda p: _botones(p, s, (0.55, 0.51, 0.47), 0.012), caja, tela(blanco, 0.4)))
    elif ropa == "sweater":
        lista.append(("ruedo_sweater", lambda p: cortar(_torso(p, s, 0.034), np.abs(p[..., 1] - 0.43) - 0.02), caja,
                      tela(_oscuro(remera, 0.85), 0.95)))
    elif ropa == "vestido_largo":
        lista.append(("cinto", lambda p: cortar(_ropa_torso(p, s) + (-0.012), np.abs(p[..., 1] - 0.47) - 0.016), caja,
                      tela(s["estampa_color"], 0.6)))


HOMBRO_A_MUNECA = 0.585 - 0.42


def _corte_brazo(p, lado, hasta_y):
    """Lo del brazo que está por encima de hasta_y (perpendicular al brazo, con un poco de inclinación)."""
    eje = np.array([lado * (0.2 - HOMBRO[0]), 0.42 - 0.585, 0.02], np.float32)
    eje /= np.linalg.norm(eje)
    punto = np.array([HOMBRO[0] * lado, 0.585, 0], np.float32) + eje * ((0.585 - hasta_y) / -eje[1])
    return plano(p - punto, eje, 0.0)


def _manga(p, s, lado):
    ropa = s["ropa"]
    larga = ropa in MANGA_LARGA
    r = {"traje": 0.056, "sweater": 0.054, "blusa": 0.062}.get(ropa, 0.05)    # la blusa lleva mangas globo
    gruesa = capsula(p, (lado * HOMBRO[0], 0.585, 0), (lado * 0.2, 0.42, 0.02), r, r - 0.006)
    hasta = 0.425 if larga else (0.535 if ropa == "blusa" else 0.505)
    return cortar(gruesa, _corte_brazo(p, lado, hasta), 0.006)


def _puno(p, lado, y0, y1, grosor):
    gruesa = capsula(p, (lado * HOMBRO[0], 0.585, 0), (lado * 0.2, 0.42, 0.02), 0.038 + grosor, 0.033 + grosor)
    return cortar(cortar(gruesa, _corte_brazo(p, lado, y0), 0.004), -_corte_brazo(p, lado, y1), 0.004)


def _brazo(p, lado):
    mano = unir(capsula(p, (lado * HOMBRO[0], 0.585, 0), (lado * 0.2, 0.42, 0.02), 0.038, 0.033),
                elipsoide(p, (lado * 0.205, 0.39, 0.025), (0.042, 0.048, 0.04)), 0.025)
    return unir(mano, esfera(p, (lado * 0.152, 0.585, 0), 0.046), 0.03)     # el hombro, que se ve sin mangas


def _piernas(p, s):
    d = None
    for x in (-0.07, 0.07):
        pierna = capsula(p, (x, 0.08, 0.0), (x * 1.05, 0.42, 0.0), 0.05, 0.058)
        d = pierna if d is None else unir(d, pierna, 0.0)
    cadera = elipsoide(p, (0, 0.42, 0), (_medidas(s)[0] * 1.02, 0.07, _medidas(s)[0] * _medidas(s)[2]))
    return unir(d, cadera, 0.035)


def _zapatillas(p, x):
    zapa = elipsoide(p, (x, 0.05, 0.035), (0.06, 0.055, 0.1))
    return cortar(zapa, -plano(p, (0, 1, 0), 0.008), 0.01)


def _suela(p, x):
    borde = elipsoide(p, (x, 0.05, 0.035), (0.066, 0.06, 0.107))
    return cortar(borde, plano(p, (0, 1, 0), 0.024), 0.004)


# --- Las partes, con sus materiales ------------------------------------------------------------------------

def _armar(s: dict, foto_jpg: bytes | None) -> dict[str, list]:
    """{parte: [(nombre, función de distancia, caja (min, max), material)]}"""
    piel = s["piel"]
    pelo = s["pelo"]
    boca_jrs = s["ropa"] == "boca"
    remera = avatar3d.BOCA_AZUL if boca_jrs else s["remera"]
    detalle = s["estampa_color"]
    ca = s["accesorio_color"]
    m_piel = {"color": _c(piel), "rugosidad": 0.62}
    m_pelo = {"color": _c(pelo), "rugosidad": 0.55}
    m_tela = lambda col, r=0.82: {"color": _c(col), "rugosidad": r}  # noqa: E731
    con_foto = foto_jpg is not None
    partes: dict[str, list] = {"cabeza": [], "torso": [], "brazo_i": [], "brazo_d": [], "piernas": []}
    caja_cabeza = ((-0.38, 0.44, -0.46), (0.38, 1.3, 0.34))   # ancha: ningún pelo ni sombrero se corta en el borde

    # Cabeza
    partes["cabeza"].append(("piel", lambda p: unir(unir(_cabeza_sdf(p, con_foto),
                                                         elipsoide(p, (-0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015),
                                                    elipsoide(p, (0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015)
                             if con_foto else unir(unir(unir(_cabeza_sdf(p), elipsoide(p, (0, 0.79, 0.178), (0.026, 0.021, 0.02)), 0.02),
                                                        elipsoide(p, (-0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015),
                                                   elipsoide(p, (0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015),
                             ((-0.25, 0.6, -0.22), (0.25, 1.05, 0.25)), m_piel))
    if not con_foto:
        _rasgos(partes["cabeza"], s, m_tela)
    if (pelo_sdf := _pelo_funcion(s)) is not None:
        partes["cabeza"].append(("pelo", pelo_sdf, caja_cabeza, m_pelo))
    b = s["barba"]
    if b != "ninguna":
        def barba(p, b=b):
            bigote = unir(curva(p, [(-0.06, 0.748, 0.162), (-0.03, 0.758, 0.178), (0, 0.752, 0.183)], 0.013, 0.009),
                          curva(p, [(0.06, 0.748, 0.162), (0.03, 0.758, 0.178), (0, 0.752, 0.183)], 0.013, 0.009), 0.01)
            if b == "bigote":
                return bigote
            if b == "candado":
                return unir(bigote, elipsoide(p, (0, 0.685, 0.13), (0.045, 0.035, 0.045)), 0.02)
            mandibula = cortar(elipsoide(p, (0, 0.74, 0.03), (0.175, 0.13, 0.165)), plano(p, (0, 1, 0), 0.79), 0.02)
            mandibula = restar(mandibula, _cabeza_sdf(p) + 0.006, 0.0)
            mandibula = restar(mandibula, elipsoide(p, (0, 0.73, 0.18), (0.045, 0.022, 0.05)), 0.01)
            return unir(mandibula, bigote, 0.015)
        partes["cabeza"].append(("barba", barba, ((-0.22, 0.58, -0.1), (0.22, 0.85, 0.24)), m_pelo))
    _sombreros(partes["cabeza"], s, ca, detalle)
    _lentes(partes["cabeza"], s, ca, con_foto)
    if con_foto:
        partes["cabeza"].append(("foto", "foto", None, {"color": (1, 1, 1), "rugosidad": 0.6, "textura": foto_jpg, "dos_caras": True}))

    # Torso: cuello, ropa, estampa
    partes["torso"].append(("cuello", lambda p: capsula(p, (0, 0.58, 0), (0, 0.7, 0), 0.046),
                             ((-0.07, 0.56, -0.07), (0.07, 0.72, 0.07)), m_piel))
    caja_torso = ((-0.26, 0.15, -0.25), (0.26, 0.7, 0.22))
    if boca_jrs:
        franja = lambda p: np.abs(p[..., 1] - 0.505) - 0.04  # noqa: E731
        partes["torso"].append(("remera", lambda p: cortar(_ropa_torso(p, s), -franja(p)), caja_torso, m_tela(remera)))
        partes["torso"].append(("franja", lambda p: cortar(_ropa_torso(p, s), franja(p)), caja_torso, m_tela(avatar3d.BOCA_ORO)))
        partes["torso"].append(("cuello_ropa", lambda p: toro_y(p, (0, 0.6, 0), 0.058, 0.011, 0.9),
                                ((-0.09, 0.57, -0.09), (0.09, 0.63, 0.09)), m_tela(avatar3d.BOCA_ORO)))
    elif s["estampa"] == "rayas":
        raya = lambda p: np.sin(p[..., 1] * 2 * math.pi / 0.05)  # noqa: E731
        partes["torso"].append(("remera", lambda p: cortar(_ropa_torso(p, s), raya(p) * 0.01), caja_torso, m_tela(remera)))
        partes["torso"].append(("rayas", lambda p: cortar(_ropa_torso(p, s), -raya(p) * 0.01), caja_torso, m_tela(detalle)))
    else:
        partes["torso"].append(("remera", lambda p: _ropa_torso(p, s), caja_torso, m_tela(remera)))
    if s["estampa"] == "logo" and not boca_jrs:
        partes["torso"].append(("logo", lambda p: cortar(_ropa_torso(p, s) - 0.004,
                                                         elipsoide(p, (0, 0.52, 0.12), (0.05, 0.035, 0.08))),
                                caja_torso, m_tela(detalle, 0.5)))
    if s["ropa"] == "campera":
        partes["torso"].append(("remera_abajo", lambda p: cortar(_torso(p, s, 0.016), np.abs(p[..., 0]) - 0.04),
                                caja_torso, m_tela(detalle)))
        partes["torso"].append(("cierre", lambda p: unir(capsula(p, (-0.045, 0.43, 0.12), (-0.045, 0.6, 0.1), 0.006),
                                                           capsula(p, (0.045, 0.43, 0.12), (0.045, 0.6, 0.1), 0.006)),
                                caja_torso, {"color": _c("#c9ccd1"), "rugosidad": 0.3, "metal": 0.6}))
    if s["ropa"] == "buzo":
        partes["torso"].append(("cordones", lambda p: unir(curva(p, [(-0.03, 0.6, 0.11), (-0.035, 0.53, 0.125)], 0.006, 0.006),
                                                             curva(p, [(0.03, 0.6, 0.11), (0.035, 0.53, 0.125)], 0.006, 0.006)),
                                caja_torso, m_tela(detalle, 0.6)))
        partes["torso"].append(("bolsillo", lambda p: cortar(_ropa_torso(p, s) - 0.005,
                                                             caja_redonda(p, (0, 0.46, 0.12), (0.14, 0.06, 0.1), 0.02)),
                                caja_torso, m_tela(_oscuro(remera, 0.88))))
    _detalles_ropa(partes["torso"], s, caja_torso, m_tela)
    _extras_torso(partes["torso"], s, ca, detalle)

    # Brazos (con mano) y mangas
    for nombre, lado in (("brazo_i", -1), ("brazo_d", 1)):
        caja = ((lado * 0.13 - 0.17, 0.3, -0.12), (lado * 0.13 + 0.17, 0.68, 0.16))
        caja = (tuple(min(a, b) for a, b in zip(*caja)), tuple(max(a, b) for a, b in zip(*caja)))
        partes[nombre].append(("brazo", lambda p, lado=lado: _brazo(p, lado), caja, m_piel))
        if s["ropa"] != "musculosa":
            partes[nombre].append(("manga", lambda p, lado=lado: _manga(p, s, lado), caja, m_tela(remera)))
        if s["ropa"] in ("buzo", "campera", "sweater"):
            partes[nombre].append(("puño", lambda p, lado=lado: _puno(p, lado, 0.425, 0.452, 0.019),
                                   caja, m_tela(_oscuro(remera, 0.82))))
        elif boca_jrs:
            partes[nombre].append(("puño", lambda p, lado=lado: _puno(p, lado, 0.505, 0.53, 0.02),
                                   caja, m_tela(avatar3d.BOCA_ORO)))
    _extras_mano(partes["brazo_d"], s, ca)

    # Piernas, cadera y zapatillas
    caja_piernas = ((-0.2, -0.01, -0.12), (0.2, 0.5, 0.16))
    pantalon = s["pantalon"]
    if s["ropa"] in FALDA_PIEL:
        partes["piernas"].append(("piernas", lambda p: _piernas(p, s), caja_piernas, m_piel))
    else:
        partes["piernas"].append(("pantalon", lambda p: _piernas(p, s), caja_piernas, m_tela(pantalon)))
    zapa = s["zapatillas"]
    partes["piernas"].append(("zapatillas", lambda p: unir(_zapatillas(p, -0.07), _zapatillas(p, 0.07)), caja_piernas,
                              m_tela(zapa, 0.6)))
    suela = "#d9dce1" if avatar3d._rgb(zapa)[0] > 0.8 else "#f2f2f2"
    partes["piernas"].append(("suela", lambda p: unir(_suela(p, -0.07), _suela(p, 0.07)), caja_piernas, m_tela(suela, 0.7)))
    return partes


# --- Los rasgos de la cara: ojos, cejas, boca ----------------------------------------------------------------

CAJA_OJOS = ((-0.15, 0.77, 0.10), (0.15, 0.93, 0.22))
CAJA_BOCA = ((-0.08, 0.66, 0.10), (0.08, 0.78, 0.22))


def _bola_ojo(p, cx, cy=0.83, a=0.03, b=0.04):
    return elipsoide(p, (cx, cy, 0.16), (a, b, 0.018))


def _ojo_con_parpado(p, cx, lado, inclinacion, cy=0.83):
    """Un ojo con el párpado cortado en diagonal (enojado, triste) o derecho (entrecerrado): inclinacion 1 = enojado,
    -1 = triste, 0 = párpado a la mitad. Devuelve (ojo, línea del párpado)."""
    interior = -lado
    u = interior * (p[..., 0] - cx)
    k = 0.55 * inclinacion
    corte = (p[..., 1] - (cy + 0.012 - k * u)) / math.sqrt(1 + k * k)
    return cortar(_bola_ojo(p, cx, cy), corte, 0.004)


def _linea_parpado(p, cx, lado, inclinacion, cy=0.83):
    k = 0.55 * inclinacion
    yo = cy + 0.012 + k * 0.032     # punta de afuera
    yi = cy + 0.012 - k * 0.032     # punta de adentro
    return _tubo_cara(p, [(cx + lado * 0.032, yo), (cx - lado * 0.032, yi)], 0.0048, 0.0048, dz=0.004, n=4)


def _pestanas(p, cx, lado, cy=0.83):
    d = None
    for ang, largo in ((0.15, 0.03), (0.6, 0.032), (1.05, 0.028)):
        x0, y0 = cx + lado * 0.027, cy + 0.016
        x1, y1 = x0 + lado * largo * math.cos(ang), y0 + largo * math.sin(ang)
        t = _tubo_cara(p, [(x0, y0), (x1, y1)], 0.0034, 0.0016, dz=0.003, n=3)
        d = t if d is None else np.minimum(d, t)
    return d


def _rasgos(lista, s, tela):
    piel, pelo, mirada = s["piel"], s["pelo"], s["mirada"]
    trazo = tela(_oscuro(s["ojos"], 0.4), 0.5)
    iris = {"color": _c(s["ojos"]), "rugosidad": 0.15}
    blanco = {"color": (1, 1, 1), "rugosidad": 0.1}

    def brillos(*puntos):
        def f(p):
            d = None
            for (c, r) in puntos:
                e = esfera(p, c, r)
                d = e if d is None else unir(d, e)
            return d
        return f

    # --- ojos
    if mirada == "normal":
        lista.append(("ojos", lambda p: unir(_bola_ojo(p, -0.068), _bola_ojo(p, 0.068)), CAJA_OJOS, iris))
        lista.append(("brillo", brillos(((-0.058, 0.846, 0.174), 0.009), ((0.078, 0.846, 0.174), 0.009)), CAJA_OJOS, blanco))
    elif mirada == "grandes":
        esclera = _calco(lambda p: np.minimum(_elipse2d(p, -0.068, 0.83, 0.042, 0.056), _elipse2d(p, 0.068, 0.83, 0.042, 0.056)), 0.004)
        lista.append(("esclera", esclera, CAJA_OJOS, blanco))
        lista.append(("ojos", lambda p: unir(_bola_ojo(p, -0.068, 0.83, 0.027, 0.04), _bola_ojo(p, 0.068, 0.83, 0.027, 0.04)),
                      CAJA_OJOS, iris))
        lista.append(("brillo", brillos(((-0.058, 0.847, 0.176), 0.011), ((0.078, 0.847, 0.176), 0.011)), CAJA_OJOS, blanco))
    elif mirada in ("feliz", "guino", "dormidos"):
        def arco(p, cx, invertido):
            if invertido:
                return _tubo_cara(p, [(cx - 0.031, 0.836), (cx, 0.803), (cx + 0.031, 0.836)], 0.0075, 0.0075, dz=0.004)
            return _tubo_cara(p, [(cx - 0.031, 0.82), (cx, 0.86), (cx + 0.031, 0.82)], 0.0075, 0.0075, dz=0.004)
        if mirada == "guino":
            lista.append(("ojos", lambda p: _bola_ojo(p, -0.068), CAJA_OJOS, iris))
            lista.append(("brillo", brillos(((-0.058, 0.846, 0.174), 0.009)), CAJA_OJOS, blanco))
            lista.append(("trazos", lambda p: arco(p, 0.068, False), CAJA_OJOS, trazo))
        else:
            inv = mirada == "dormidos"
            lista.append(("trazos", lambda p: np.minimum(arco(p, -0.068, inv), arco(p, 0.068, inv)), CAJA_OJOS, trazo))
    elif mirada in ("enojados", "tristes", "entrecerrados"):
        inc = {"enojados": 1.0, "tristes": -1.0, "entrecerrados": 0.0}[mirada]
        lista.append(("ojos", lambda p: unir(_ojo_con_parpado(p, -0.068, -1, inc), _ojo_con_parpado(p, 0.068, 1, inc)),
                      CAJA_OJOS, iris))
        lista.append(("trazos", lambda p: np.minimum(_linea_parpado(p, -0.068, -1, inc), _linea_parpado(p, 0.068, 1, inc)),
                      CAJA_OJOS, trazo))
        lista.append(("brillo", brillos(((-0.060, 0.826, 0.175), 0.007), ((0.076, 0.826, 0.175), 0.007)), CAJA_OJOS, blanco))
    elif mirada == "enamorado":
        lista.append(("corazones", _calco(lambda p: np.minimum(_corazon2d(p[..., 0] + 0.068, p[..., 1] - 0.83, 0.05),
                                                               _corazon2d(p[..., 0] - 0.068, p[..., 1] - 0.83, 0.05)), 0.007),
                      CAJA_OJOS, {"color": _c("#ff3d6e"), "rugosidad": 0.3}))
    if s.get("genero") == "mujer" and mirada in ("normal", "grandes", "tristes", "enojados", "entrecerrados"):
        lista.append(("pestanas", lambda p: np.minimum(_pestanas(p, -0.068, -1), _pestanas(p, 0.068, 1)), CAJA_OJOS, trazo))

    # --- cejas
    if s["cejas"] != "ninguna":
        lista.append(("cejas", lambda p: _cejas(p, s["cejas"]), ((-0.13, 0.84, 0.10), (0.13, 0.95, 0.21)),
                      tela(_oscuro(pelo, 0.85), 0.6)))

    # --- boca
    _boca(lista, s, tela)

    rubor = lambda p: unir(elipsoide(p, (-0.115, 0.77, 0.135), (0.032, 0.018, 0.012)),  # noqa: E731
                           elipsoide(p, (0.115, 0.77, 0.135), (0.032, 0.018, 0.012)))
    lista.append(("rubor", rubor, ((-0.16, 0.74, 0.11), (0.16, 0.8, 0.16)),
                  {"color": _c(_mezclar(piel, "#ff8a8a", 0.35)), "rugosidad": 0.7}))


def _bezier2d(ctrl, t):
    k = len(ctrl) - 1
    return sum(comb(k, i) * ((1 - t) ** (k - i) * t ** i) * np.asarray(ctrl[i], float) for i in range(k + 1))


def _ceja_lado(p, lado, tipo):
    def ruta(pts):
        return [(lado * x, y) for x, y in pts]
    if tipo == "normales":
        return _tubo_cara(p, ruta([(0.1, 0.876), (0.07, 0.892), (0.038, 0.884)]), 0.009, 0.006)
    if tipo == "finas":
        return _tubo_cara(p, ruta([(0.105, 0.874), (0.07, 0.894), (0.034, 0.883)]), 0.0042, 0.0032)
    if tipo == "arqueadas":
        return _tubo_cara(p, ruta([(0.103, 0.862), (0.07, 0.91), (0.034, 0.872)]), 0.0045, 0.0035)
    if tipo == "pobladas":
        return _tubo_cara(p, ruta([(0.106, 0.876), (0.07, 0.894), (0.032, 0.884)]), 0.015, 0.011)
    if tipo == "enojadas":
        return _tubo_cara(p, ruta([(0.106, 0.9), (0.07, 0.888), (0.034, 0.864)]), 0.01, 0.008)
    if tipo == "tristes":
        return _tubo_cara(p, ruta([(0.106, 0.866), (0.07, 0.882), (0.034, 0.9)]), 0.008, 0.008)
    if tipo == "levantada":
        if lado > 0:
            return _tubo_cara(p, ruta([(0.104, 0.89), (0.07, 0.918), (0.034, 0.9)]), 0.009, 0.006)
        return _tubo_cara(p, ruta([(0.1, 0.876), (0.07, 0.892), (0.038, 0.884)]), 0.009, 0.006)
    if tipo == "unidas":
        return _tubo_cara(p, ruta([(0.1, 0.876), (0.07, 0.892), (0.0, 0.888)]), 0.01, 0.009)
    if tipo == "peludas":
        base = [(0.104, 0.872), (0.07, 0.891), (0.034, 0.88)]
        d = _tubo_cara(p, ruta(base), 0.0085, 0.0075)
        for k in range(17):
            t = k / 16
            x0, y0 = _bezier2d(base, t)
            alto = 0.017 + 0.007 * math.sin(k * 2.3)
            x1 = x0 + 0.007 * (1 - 2 * t) + 0.003 * math.sin(k * 3.1)
            hebra = _tubo_cara(p, [(lado * x0, y0 + 0.003), (lado * x1, y0 + alto)], 0.0034, 0.0016, dz=0.003, n=3)
            d = np.minimum(d, hebra)
            if k % 2 == 0:       # y unas pocas para abajo, que despeinan
                abajo = _tubo_cara(p, [(lado * x0, y0 - 0.003), (lado * (x0 + 0.003), y0 - 0.011)], 0.003, 0.0016, dz=0.003, n=3)
                d = np.minimum(d, abajo)
        return d
    return None


def _cejas(p, tipo):
    d = np.minimum(_ceja_lado(p, -1, tipo), _ceja_lado(p, 1, tipo))
    if tipo == "unidas":
        d = np.minimum(d, _tubo_cara(p, [(-0.036, 0.888), (0.0, 0.89), (0.036, 0.888)], 0.0095, 0.0095))
    return d


def _boca(lista, s, tela):
    b = s["boca"]
    labio = tela("#6b2a24", 0.5)
    hueco = tela("#3b1114", 0.5)
    dientes = tela("#f7f4ea", 0.35)
    lengua = tela("#e8707a", 0.4)

    def linea(ctrl, r=0.0085):
        lista.append(("boca", lambda p: _tubo_cara(p, ctrl, r, r, dz=0.003), CAJA_BOCA, labio))

    if b == "sonrisa":
        linea([(-0.042, 0.742), (0.0, 0.70), (0.042, 0.742)])
    elif b == "picara":
        linea([(-0.034, 0.728), (0.004, 0.72), (0.046, 0.748)])
    elif b == "triste":
        linea([(-0.036, 0.716), (0.0, 0.752), (0.036, 0.716)])
    elif b == "seria":
        linea([(-0.032, 0.728), (0.0, 0.726), (0.032, 0.728)], 0.007)
    elif b == "lengua":
        linea([(-0.042, 0.742), (0.0, 0.70), (0.042, 0.742)])
        lista.append(("lengua", _calco(lambda p: _elipse2d(p, 0.004, 0.706, 0.019, 0.024), 0.009), CAJA_BOCA, lengua))
    elif b == "sorpresa":
        lista.append(("boca", _calco(lambda p: _elipse2d(p, 0.0, 0.724, 0.022, 0.029), 0.005), CAJA_BOCA, hueco))
        lista.append(("lengua", _calco(lambda p: np.maximum(_elipse2d(p, 0.0, 0.712, 0.014, 0.01),
                                                            _elipse2d(p, 0.0, 0.724, 0.022, 0.029)), 0.007), CAJA_BOCA, lengua))
    elif b in ("dientes", "risa"):
        grande = b == "risa"
        ancho, alto, corte = (0.054, 0.039, 0.741) if grande else (0.046, 0.031, 0.739)
        cy = 0.722 if grande else 0.725

        def d_boca(p):
            return np.maximum(_elipse2d(p, 0.0, cy, ancho, alto), p[..., 1] - corte)
        lista.append(("boca", _calco(d_boca, 0.005), CAJA_BOCA, hueco))
        lista.append(("lengua", _calco(lambda p: np.maximum(_elipse2d(p, 0.0, cy - 0.016, ancho * 0.55, alto * 0.45), d_boca(p)),
                                       0.0075), CAJA_BOCA, lengua))
        medio = ancho * 0.88
        lista.append(("dientes", _calco(lambda p: np.maximum(_caja2d(p[..., 0], p[..., 1] - (corte - 0.0075), medio, 0.0078, 0.003),
                                                             d_boca(p)), 0.0085), CAJA_BOCA, dientes))
    elif b == "abierta":
        def d_boca(p):
            return _elipse2d(p, 0.0, 0.722, 0.031, 0.038)
        lista.append(("boca", _calco(d_boca, 0.005), CAJA_BOCA, hueco))
        lista.append(("lengua", _calco(lambda p: np.maximum(_elipse2d(p, 0.0, 0.702, 0.021, 0.013), d_boca(p)), 0.0075),
                      CAJA_BOCA, lengua))
        lista.append(("dientes", _calco(lambda p: np.maximum(_caja2d(p[..., 0], p[..., 1] - 0.746, 0.022, 0.0065, 0.003),
                                                             d_boca(p)), 0.0085), CAJA_BOCA, dientes))


def _pelo_funcion(s):
    # Con algo en la cabeza (gorra, gorro, sombrero, galera, corona) no se le pone pelo: así nada atraviesa el accesorio.
    # La kipá es la excepción: es chiquita y va sobre el pelo (los peinados altos se bajan a «corto» para que no la tapen)
    if s["peinado"] == "pelado" or s["cabeza"] not in ("ninguno", "kipa"):
        return None
    if s["cabeza"] == "kipa" and s["peinado"] in ("afro", "rulos", "cresta", "rodete"):
        s = {**s, "peinado": "corto"}
    return lambda p: _pelo(p, s)


def _sombreros(lista, s, ca, detalle):
    c = s["cabeza"]
    caja = ((-0.37, 0.85, -0.37), (0.37, 1.32, 0.42))    # el ala del sombrero llega a 0.31: la caja tiene que pasarla
    if c == "gorra":
        lista.append(("gorra", lambda p: cortar(elipsoide(p, (0, 0.88, -0.01), (0.215, 0.2, 0.2)), -plano(p, (0, 1, 0), 0.9), 0.01),
                      caja, {"color": _c(ca), "rugosidad": 0.8}))
        lista.append(("visera", lambda p: cortar(elipsoide(p, (0, 0.905, 0.15), (0.17, 0.018, 0.17)), -plano(p, (0, 0, 1), 0.12), 0.01),
                      caja, {"color": _c(_oscuro(ca, 0.85)), "rugosidad": 0.8}))
    elif c == "gorro":
        lista.append(("gorro", lambda p: cortar(elipsoide(p, (0, 0.89, -0.01), (0.22, 0.215, 0.205)), -plano(p, (0, 1, 0), 0.92), 0.01),
                      caja, {"color": _c(ca), "rugosidad": 0.95}))
        lista.append(("borde", lambda p: toro_y(p, (0, 0.93, -0.01), 0.205, 0.03, 0.93), caja, {"color": _c(detalle), "rugosidad": 0.95}))
        lista.append(("pompon", lambda p: esfera(p, (0, 1.13, -0.02), 0.05), caja, {"color": _c(detalle), "rugosidad": 1.0}))
    elif c == "sombrero":
        lista.append(("sombrero", lambda p: unir(cilindro(p, (0, 0.95, 0), 0.31, 0.014, 0.006),
                                                 cilindro(p, (0, 0.95, 0), 0.17, 0.13, 0.03), 0.02),
                      caja, {"color": _c(ca), "rugosidad": 0.85}))
        lista.append(("cinta", lambda p: cilindro(p, (0, 0.962, 0), 0.172, 0.03, 0.004), caja, {"color": _c("#1d1d1f"), "rugosidad": 0.6}))
    elif c == "paja":
        def ala(p):
            r = np.hypot(p[..., 0], p[..., 2])
            q = p.copy()
            q[..., 1] = p[..., 1] + 0.12 * np.clip(r - 0.18, 0, 0.2)       # el ala cae un poco hacia afuera
            return cilindro(q, (0, 0.945, 0), 0.3, 0.016, 0.006) - 0.0016 * np.sin(r * 230.0)   # surcos de la paja
        lista.append(("paja", lambda p: unir(ala(p), cortar(elipsoide(p, (0, 0.95, 0), (0.175, 0.14, 0.18)),
                                                            -plano(p, (0, 1, 0), 0.95), 0.01), 0.012),
                      caja, {"color": _c("#e2c275"), "rugosidad": 0.95}))
        lista.append(("cinta", lambda p: toro_y(p, (0, 0.965, 0), 0.176, 0.013, 1.03), caja, {"color": _c(ca), "rugosidad": 0.7}))
    elif c == "kipa":
        def kipa(p):
            n = np.array([0.0, 0.9855, -0.17], np.float32)
            casquete = restar(elipsoide(p, (0, 0.835, -0.012), (0.233, 0.223, 0.213)),
                              elipsoide(p, (0, 0.835, -0.012), (0.224, 0.214, 0.204)))
            return cortar(casquete, 1.0 - p @ n, 0.004)
        lista.append(("kipa", kipa, caja, {"color": _c(ca), "rugosidad": 0.85}))
    elif c == "galera":
        lista.append(("galera", lambda p: unir(cilindro(p, (0, 0.95, 0), 0.26, 0.012, 0.005),
                                               cilindro(p, (0, 0.95, 0), 0.155, 0.24, 0.012), 0.01),
                      caja, {"color": _c("#1d1d1f"), "rugosidad": 0.5}))
        lista.append(("cinta", lambda p: cilindro(p, (0, 0.962, 0), 0.157, 0.04, 0.004), caja, {"color": _c(ca), "rugosidad": 0.5}))
    elif c == "corona":
        def corona(p):
            aro = restar(cilindro(p, (0, 0.95, 0), 0.165, 0.06, 0.006), cilindro(p, (0, 0.94, 0), 0.15, 0.09, 0.0))
            for j in range(7):
                a = 2 * math.pi * j / 7
                x, z = 0.158 * math.cos(a), 0.158 * math.sin(a)
                aro = unir(aro, capsula(p, (x, 1.0, z), (x * 1.02, 1.07, z * 1.02), 0.022, 0.008), 0.008)
            return aro
        lista.append(("corona", corona, caja, {"color": _c("#e0b23a"), "rugosidad": 0.25, "metal": 0.9}))
        lista.append(("gemas", lambda p: unir(esfera(p, (0, 0.98, 0.164), 0.016),
                                              unir(esfera(p, (0.09, 0.98, 0.138), 0.012), esfera(p, (-0.09, 0.98, 0.138), 0.012))),
                      caja, {"color": _c(ca), "rugosidad": 0.1}))


def _forma_lente(tipo):
    """(distancia al borde del vidrio —negativa adentro—, medio ancho, grosor del borde, tinte del vidrio) de cada modelo.
    La distancia es de (u, v): u hacia afuera (la oreja) y v hacia arriba, desde el centro del vidrio."""
    if tipo == "cuadrados":
        return (lambda u, v: _caja2d(u, v, 0.052, 0.037, 0.011)), 0.052, 0.008, "#d8ecf7"
    if tipo == "aviador":
        # Gota: ancha y casi plana arriba, que se afina hacia abajo
        return ((lambda u, v: (np.hypot(u / (0.058 * (1 + 0.24 * np.clip((v - 0.004) / 0.05, -1, 1))), (v + 0.004) / 0.052) - 1.0) * 0.05),
                0.057, 0.005, "#a9843f")
    if tipo == "gatuno":
        return (lambda u, v: _caja2d(u, v - 0.3 * u, 0.056, 0.03, 0.014)), 0.058, 0.008, "#e6d5f0"
    if tipo == "corazones":
        return (lambda u, v: _corazon2d(u, v, 0.085)), 0.051, 0.007, "#ff7aa8"
    if tipo == "sol":
        return ((lambda u, v: _caja2d(u / (1 + 0.2 * np.clip(v / 0.04, -1, 1)), v, 0.055, 0.036, 0.012)),
                0.056, 0.011, "#161616")
    return (lambda u, v: np.hypot(u, v) - 0.048), 0.048, 0.007, "#cfe9f5"       # anteojos redondos


def _lentes(lista, s, ca, con_foto=False):
    tipo = s["lentes"]
    marco_color = s["lentes_color"]
    zl = 0.19 + (SALIDA_FOTO if con_foto else 0.0)      # con la foto, la cara sale hacia adelante: los lentes también
    caja = ((-0.25, 0.73, -0.06), (0.25, 0.94, zl + 0.06))
    if tipo == "lentes3d":
        # Los de cartón de cine: una plancha con dos ventanas (rojo y celeste) y las patas del color del borde
        def hueco(p, lado):
            return _caja2d(p[..., 0] - lado * 0.06, p[..., 1] - 0.83, 0.038, 0.031, 0.008)

        def plancha(p):
            d = caja_redonda(p, (0, 0.83, zl), (0.205, 0.088, 0.008), 0.0035)
            for lado in (-1, 1):
                d = restar(d, hueco(p, lado))
            for lado in (-1, 1):
                d = unir(d, capsula(p, (lado * 0.1, 0.84, zl - 0.004), (lado * 0.19, 0.84, 0.04), 0.0045))
            return d
        lista.append(("marco", plancha, caja, {"color": _c(marco_color), "rugosidad": 0.6}))
        for lado, color in ((-1, "#d43a3a"), (1, "#2ec5d6")):
            lista.append((f"vidrio{lado}", lambda p, lado=lado: np.maximum(hueco(p, lado), np.abs(p[..., 2] - zl) - 0.003),
                          caja, {"color": _c(color), "rugosidad": 0.05, "metal": 0.2}))
    elif tipo in ("anteojos", "cuadrados", "aviador", "gatuno", "corazones", "sol"):
        f, ancho, grosor, tinte = _forma_lente(tipo)

        def borde(p, lado):
            u, v = (p[..., 0] - lado * 0.07) * lado, p[..., 1] - 0.83
            return f(u, v)

        def armazon(p):
            d = None
            for lado in (-1, 1):
                aro = np.sqrt(borde(p, lado) ** 2 + (p[..., 2] - zl) ** 2) - grosor
                d = aro if d is None else unir(d, aro)
            interior = 0.07 - ancho
            d = unir(d, capsula(p, (-interior, 0.835, zl + 0.003), (interior, 0.835, zl + 0.003), 0.006))
            if tipo == "aviador":
                d = unir(d, capsula(p, (-interior, 0.858, zl + 0.003), (interior, 0.858, zl + 0.003), 0.0045))
            for lado in (-1, 1):
                d = unir(d, capsula(p, (lado * (0.07 + ancho), 0.84, zl - 0.005), (lado * 0.19, 0.84, 0.04), 0.005))
            return d
        lista.append(("marco", armazon, caja, {"color": _c(marco_color), "rugosidad": 0.3}))
        vidrio = {"color": _c(tinte), "rugosidad": 0.05, "metal": 0.0 if tipo == "sol" else 0.2}
        for lado in (-1, 1):
            lista.append((f"vidrio{lado}", lambda p, lado=lado: np.maximum(borde(p, lado), np.abs(p[..., 2] - zl) - 0.004),
                          caja, vidrio))
    elif tipo == "antifaz":
        lista.append(("antifaz", lambda p: restar(cortar(_cabeza_sdf(p) - 0.012, np.abs(p[..., 1] - 0.835) - 0.04),
                                                  unir(elipsoide(p, (-0.068, 0.83, 0.17), (0.03, 0.025, 0.05)),
                                                       elipsoide(p, (0.068, 0.83, 0.17), (0.03, 0.025, 0.05))), 0.004),
                      caja, {"color": _c(ca), "rugosidad": 0.5}))


def _extras_torso(lista, s, ca, detalle):
    e = s["extra"]
    caja = ((-0.3, 0.1, -0.35), (0.3, 0.75, 0.3))
    if e == "bufanda":
        lista.append(("bufanda", lambda p: unir(toro_y(p, (0, 0.62, 0.0), 0.075, 0.03, 1.0),
                                                curva(p, [(0.05, 0.6, 0.09), (0.07, 0.52, 0.13), (0.06, 0.44, 0.13)], 0.03, 0.025), 0.02),
                      caja, {"color": _c(ca), "rugosidad": 1.0}))
    elif e == "capa":
        def capa(p):
            hoja = restar(elipsoide(p, (0, 0.42, -0.02), (0.22, 0.32, 0.15)), elipsoide(p, (0, 0.42, 0.0), (0.205, 0.33, 0.14)))
            hoja = cortar(hoja, plano(p, (0, 0, 1), -0.03), 0.01)
            return cortar(hoja, plano(p, (0, 1, 0), 0.62), 0.01)
        lista.append(("capa", capa, caja, {"color": _c(ca), "rugosidad": 0.55}))


def _extras_mano(lista, s, ca):
    e = s["extra"]
    caja = ((0.1, 0.2, -0.1), (0.42, 0.75, 0.25))
    mano = np.array((0.24, 0.36, 0.08), np.float32)
    if e == "pochoclos":
        def balde(p, rojo):
            b = restar(cilindro(p, mano + (0, -0.04, 0), 0.06, 0.13, 0.008), cilindro(p, mano + (0, 0.07, 0), 0.052, 0.1, 0.0))
            raya = np.sin(np.arctan2(p[..., 2] - mano[2], p[..., 0] - mano[0]) * 6)
            return cortar(b, raya * 0.01 if rojo else -raya * 0.01)
        lista.append(("balde_r", lambda p: balde(p, True), caja, {"color": _c("#d43a3a"), "rugosidad": 0.6}))
        lista.append(("balde_b", lambda p: balde(p, False), caja, {"color": _c("#f4f4f4"), "rugosidad": 0.6}))

        def pochoclo(p):
            d = None
            rng = np.random.default_rng(7)
            for _ in range(14):
                c = mano + (rng.uniform(-0.045, 0.045), 0.085 + rng.uniform(0, 0.04), rng.uniform(-0.045, 0.045))
                b = esfera(p, c, 0.022)
                d = b if d is None else unir(d, b, 0.008)
            return d
        lista.append(("pochoclos", pochoclo, caja, {"color": _c("#f6e7b0"), "rugosidad": 0.9}))
    elif e == "gaseosa":
        lista.append(("vaso", lambda p: cilindro(p, mano + (0, -0.04, 0), 0.045, 0.14, 0.008), caja, {"color": _c(ca), "rugosidad": 0.5}))
        lista.append(("tapa", lambda p: cortar(elipsoide(p, mano + (0, 0.1, 0), (0.05, 0.022, 0.05)), -plano(p, (0, 1, 0), mano[1] + 0.1)),
                      caja, {"color": _c("#f4f4f4"), "rugosidad": 0.4}))
        lista.append(("sorbete", lambda p: capsula(p, mano + (0.01, 0.1, 0), mano + (0.02, 0.2, 0), 0.007), caja,
                      {"color": _c("#f4f4f4"), "rugosidad": 0.4}))
    elif e == "claqueta":
        lista.append(("claqueta", lambda p: caja_redonda(p, mano + (0, 0.04, 0.03), (0.02, 0.12, 0.17), 0.005), caja,
                      {"color": _c("#1d1d1f"), "rugosidad": 0.6}))
        lista.append(("claqueta_tapa", lambda p: cortar(caja_redonda(p, mano + (0, 0.115, 0.03), (0.022, 0.03, 0.17), 0.004),
                                                        np.sin((p[..., 2] - p[..., 1]) * 90) * 0.01),
                      caja, {"color": _c("#f4f4f4"), "rugosidad": 0.6}))
    elif e == "auriculares":
        # Van con la cabeza: se agregan en _armar como accesorio de la cabeza (ver más abajo)
        pass


def _auriculares(lista, s, ca):
    if s["extra"] != "auriculares":
        return
    caja = ((-0.3, 0.6, -0.15), (0.3, 1.15, 0.15))
    alto = 0.3 if s["peinado"] in ("afro", "rulos") else 0.235
    lista.append(("vincha", lambda p: cortar(toro_z(p, (0, 0.8, 0), alto, 0.016), -plano(p, (0, 1, 0), 0.78)),
                  caja, {"color": _c("#1d1d1f"), "rugosidad": 0.4}))
    for lado in (-1, 1):
        lista.append((f"parlante{lado}", lambda p, lado=lado: elipsoide(p, (lado * 0.215, 0.8, 0), (0.035, 0.07, 0.065)),
                      caja, {"color": _c(ca), "rugosidad": 0.45}))


# --- La foto en la cara ------------------------------------------------------------------------------------

def _ojo(jpg: bytes) -> bytes:
    """La foto como si fuera el ojo del Protagonista, sin exagerar: un aro oscuro en el borde, el borde apenas más
    oscuro (como el volumen de un ojo) y un brillito de luz arriba a la izquierda (más otro chico). Sin vidrio."""
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QPointF, Qt
        from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QRadialGradient
        imagen = QImage.fromData(jpg)
        if imagen.isNull():
            return jpg
        n = 384
        imagen = imagen.scaled(n, n, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        imagen = imagen.copy((imagen.width() - n) // 2, (imagen.height() - n) // 2, n, n).convertToFormat(QImage.Format_RGB32)
        pintor = QPainter(imagen)
        pintor.setRenderHint(QPainter.Antialiasing)
        # Lo que se ve de la foto es una elipse (la foto no se estira): el dibujo se hace en un círculo y se achata
        pintor.translate(n / 2, n / 2)
        pintor.scale(RADIO_FOTO / RADIO_FOTO_X, 1.0)
        r = n / 2
        sombra = QRadialGradient(QPointF(0, 0), r)
        sombra.setColorAt(0.0, QColor(0, 0, 0, 0))
        sombra.setColorAt(0.6, QColor(0, 0, 0, 0))
        sombra.setColorAt(0.88, QColor(0, 0, 0, 55))
        sombra.setColorAt(1.0, QColor(0, 0, 0, 120))
        pintor.fillRect(-n, -n, 2 * n, 2 * n, QBrush(sombra))
        pintor.setBrush(Qt.NoBrush)
        pintor.setPen(QPen(QColor(25, 15, 10, 110), n * 0.022))
        pintor.drawEllipse(QPointF(0, 0), r * 0.985, r * 0.985)
        for (cx, cy, rad, alfa) in ((-0.34, -0.36, 0.11, 215), (0.30, 0.33, 0.045, 110)):
            brillo = QRadialGradient(QPointF(cx * r, cy * r), rad * r)
            brillo.setColorAt(0.0, QColor(255, 255, 255, alfa))
            brillo.setColorAt(0.55, QColor(255, 255, 255, alfa // 2))
            brillo.setColorAt(1.0, QColor(255, 255, 255, 0))
            pintor.setPen(Qt.NoPen)
            pintor.setBrush(QBrush(brillo))
            pintor.drawEllipse(QPointF(cx * r, cy * r), rad * r, rad * r)
        pintor.end()
        datos = QByteArray()
        buffer = QBuffer(datos)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        imagen.save(buffer, "JPG", 92)
        return bytes(datos)
    except Exception:  # noqa: BLE001 - si algo falla, la foto sin retocar
        return jpg


def _disco_foto(vidrio=False):
    """La foto, pegada a la curva hacia adentro de la cara (vidrio=False), o el vidrio que la tapa al ras de la
    cara (vidrio=True). Cada punto se ubica sobre la superficie buscándola de adelante hacia atrás."""
    anillos, lados = 16, 72
    margen = 0.004 if not vidrio else 0.0
    rx, ry = RADIO_FOTO_X - margen, RADIO_FOTO - margen
    achicar = RADIO_FOTO / RADIO_FOTO_X     # la foto no se estira: a lo ancho se ve solo el centro
    xy, uv = [(0.0, 0.8)], [(0.5, 0.5)]
    for a in range(1, anillos + 1):
        r = a / anillos
        for j in range(lados):
            ang = 2 * math.pi * j / lados
            u, v = r * math.cos(ang), r * math.sin(ang)
            xy.append((u * rx, 0.8 + v * ry))
            uv.append((0.5 + u * achicar / 2, 1 - (v + 1) / 2))
    xy = np.array(xy, np.float32)
    superficie = (lambda q: _cabeza_sdf(q)) if vidrio else (lambda q: _cabeza_sdf(q, True))

    def en(z):
        return np.concatenate([xy, z[:, None]], axis=1).astype(np.float32)

    # Bisección en z: adelante (0.3) está afuera, atrás (0.0) adentro
    lejos, cerca = np.full(len(xy), 0.3, np.float32), np.zeros(len(xy), np.float32)
    for _ in range(32):
        medio = (lejos + cerca) / 2
        afuera = superficie(en(medio)) > 0
        lejos = np.where(afuera, medio, lejos)
        cerca = np.where(afuera, cerca, medio)
    vert = en((lejos + cerca) / 2)
    # Normal = gradiente de la superficie (así la luz muestra la curva)
    h = 0.002
    normal = np.stack([superficie(vert + np.array(e, np.float32) * h) - superficie(vert - np.array(e, np.float32) * h)
                       for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1))], axis=1)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-6)
    vert = vert + normal * (0.0025 if not vidrio else 0.0015)
    tris = [(0, 1 + j, 1 + (j + 1) % lados) for j in range(lados)]
    for a in range(anillos - 1):
        b0, b1 = 1 + a * lados, 1 + (a + 1) * lados
        for j in range(lados):
            j2 = (j + 1) % lados
            tris += [(b0 + j, b1 + j, b1 + j2), (b0 + j, b1 + j2, b0 + j2)]
    return vert.astype(np.float32), normal.astype(np.float32), np.array(tris, np.uint32), np.array(uv, np.float32)


# --- Armar y guardar ------------------------------------------------------------------------------------------

# Qué opciones cambian la FORMA de cada parte (los colores no: cambiar un color no vuelve a modelar nada)
FORMA = {
    "cabeza": ("peinado", "cabeza", "lentes", "boca", "barba", "extra", "mirada", "cejas", "genero"),
    "torso": ("ropa", "estampa", "cuerpo", "extra", "genero"),
    "brazo_i": ("ropa", "cuerpo"),
    "brazo_d": ("ropa", "cuerpo", "extra"),
    "piernas": ("ropa", "cuerpo", "genero"),
}


# Qué tan fina es la grilla de cada pieza chica (1 = la normal): las calcomanías de la cara necesitan mucho más
FINURA = {"brillo": 0.6, "ojos": 0.6, "cejas": 0.6, "trazos": 0.6, "pestanas": 0.6, "boca": 0.5, "lengua": 0.5,
          "dientes": 0.5, "esclera": 0.5, "corazones": 0.5}
# La bandera de fondo no cambia el muñequito (la dibuja la escena aparte): no cuenta para armarlo
SOLO_ESCENA = ("bandera",)


def clave(spec: dict) -> str:
    s = {k: v for k, v in avatar3d.normalizar(spec).items() if k not in SOLO_ESCENA}
    return hashlib.sha1(json.dumps({**s, "v": VERSION}, sort_keys=True).encode()).hexdigest()[:16]


def _clave_forma(s: dict, parte: str) -> str:
    datos = {k: s[k] for k in FORMA[parte]}
    datos["foto"] = bool(s.get("foto")) and parte == "cabeza"
    return hashlib.sha1(json.dumps({**datos, "parte": parte, "v": VERSION}, sort_keys=True).encode()).hexdigest()[:16]


def construir(spec: dict, carpeta: Path, paso: float = PASO) -> Path:
    """Arma las 5 partes como .glb en carpeta/<clave>/ (si ya están, no hace nada) y devuelve esa carpeta.
    Las formas se guardan aparte (carpeta/formas): con otro color, solo se reescriben los .glb (al instante)."""
    s = avatar3d.normalizar(spec)
    carpeta = Path(carpeta)
    destino = carpeta / clave(s)
    if (destino / "listo").exists():
        return destino
    destino.mkdir(parents=True, exist_ok=True)
    formas = carpeta / "formas"
    formas.mkdir(exist_ok=True)
    foto = None
    if s.get("foto"):
        import base64
        foto = _ojo(base64.b64decode(s["foto"].split(",", 1)[1]))
    partes = _armar(s, foto)
    _auriculares(partes["cabeza"], s, s["accesorio_color"])
    for nombre_parte, piezas in partes.items():
        archivo_forma = formas / f"{nombre_parte}_{_clave_forma(s, nombre_parte)}.npz"
        guardadas = {}
        if archivo_forma.exists():
            try:
                with np.load(archivo_forma) as z:
                    guardadas = {k: z[k] for k in z.files}
            except (OSError, ValueError):
                guardadas = {}
        nuevas = {}
        mallas = []
        for nombre, funcion, caja, material in piezas:
            if funcion == "foto":
                mallas.append((nombre, _disco_foto(), material))
                continue
            if f"{nombre}__v" in guardadas:
                geo = (guardadas[f"{nombre}__v"], guardadas[f"{nombre}__n"], guardadas[f"{nombre}__t"])
            else:
                geo = malla(funcion, caja[0], caja[1], paso * FINURA.get(nombre, 1.0))
            nuevas[f"{nombre}__v"], nuevas[f"{nombre}__n"], nuevas[f"{nombre}__t"] = geo
            mallas.append((nombre, geo, material))
        if set(nuevas) != set(guardadas):
            np.savez_compressed(archivo_forma, **nuevas)
        guardar_glb(destino / f"{nombre_parte}.glb", mallas)
    (destino / "listo").write_text("1")
    return destino
