"""El Protagonista hecho con formas suaves (organizador/modelado.py) y dibujado con Qt Quick 3D.

Mide ~1 de alto, estilo muñequito cabezón. Se arma en 5 partes que se animan por separado (cabeza, torso, brazos y
piernas), cada una un .glb en la carpeta de caché; las opciones son las mismas de avatar3d (OPCIONES)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from . import avatar3d
from .modelado import cortar, curva, elipsoide, esfera, capsula, caja_redonda, guardar_glb, malla, restar, unir

VERSION = 13 # subir si cambia la forma: así se rearman los que están en caché
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


# --- Cuerpo -----------------------------------------------------------------------------------------------

def _medidas(s: dict):
    return {"flaco": (0.117, 0.105, 0.74), "robusto": (0.136, 0.122, 0.8)}.get(s["cuerpo"], (0.125, 0.112, 0.76))


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
        # La cara se curva hacia adentro como un cuenco (más hondo en el medio, nada en el borde): la foto va
        # pegada a esa curva y encima queda un vidrio al ras de la cara
        d = d + _hondo_foto(p)
    return d


RADIO_FOTO, RADIO_FOTO_X, HONDO_FOTO = 0.122, 0.138, 0.04   # alto, ancho (apenas más ancho que alto) y hondura


def _hondo_foto(p):
    """Un cuadro circular hundido en la cara: borde que baja suave y el fondo parejo (ahí va la foto)."""
    r = np.sqrt(p[..., 0] ** 2 / RADIO_FOTO_X ** 2 + (p[..., 1] - 0.8) ** 2 / RADIO_FOTO ** 2)
    u = np.clip((1 - r) / 0.28, 0, 1)
    # Un reborde apenas levantado alrededor, como el párpado del ojo
    reborde = 0.0065 * np.exp(-(((r - 1.12) / 0.11) ** 2))
    return (HONDO_FOTO * (u * u * (3 - 2 * u)) - reborde) * (p[..., 2] > 0.04)


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
        espalda = elipsoide(p, (0, 0.72, -0.07), (0.21, 0.24, 0.14))
        d = unir(d, cortar(espalda, plano(p, (0, 0, 1), 0.02), 0.03), 0.04)
        for lado in (-1, 1):
            cortina = elipsoide(p, (lado * 0.175, 0.72, 0.0), (0.06, 0.2, 0.13))
            cortina = cortar(cortina, plano(p, (0, -1, 0), -0.5), 0.04)
            d = unir(d, cortina, 0.06)
            for z in (0.07, -0.02):
                d = unir(d, curva(p, [(lado * 0.17, 0.86, z), (lado * 0.21, 0.7, z), (lado * 0.17, 0.5, z - 0.02)],
                                  0.055, 0.025), 0.04)
        for x in (-0.12, -0.05, 0.03, 0.1):
            d = unir(d, curva(p, [(x * 0.3, 1.0, 0.02), (x, 0.98, 0.14), (x * 1.6, 0.88, 0.18)], 0.05, 0.016), 0.03)
    elif est == "colita":
        d = unir(d, curva(p, [(0, 0.9, -0.2), (0, 0.98, -0.33), (0, 0.78, -0.36), (0, 0.6, -0.27)], 0.065, 0.014), 0.035)
    elif est == "trenzas":
        for lado in (-1, 1):
            for i in range(7):
                y = 0.78 - i * 0.042
                x = lado * (0.175 - i * 0.004) + (0.008 if i % 2 else -0.008) * lado
                d = unir(d, esfera(p, (x, y, -0.03), 0.034 - i * 0.002), 0.012)
            d = unir(d, curva(p, [(lado * 0.15, 0.48, -0.03), (lado * 0.15, 0.43, -0.03)], 0.02, 0.006), 0.01)
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


def _ropa_torso(p, s):
    """La ropa de arriba (sin mangas)."""
    ropa = s["ropa"]
    if ropa == "vestido":
        cono = capsula(p * np.array([1, 1, 1 / 0.85], np.float32), (0, 0.585, 0), (0, 0.2, 0), 0.105, 0.2) * 0.85
        return cortar(unir(_torso(p, s, 0.012), cono, 0.04), -plano(p, (0, 1, 0), 0.2), 0.01)
    t = _torso(p, s, 0.012 if ropa in ("remera", "boca") else 0.022)
    if ropa == "campera":
        abertura = cortar(np.abs(p[..., 0]) - 0.035, plano(p, (0, 0, -1), -0.02), 0.0)
        t = restar(t, abertura, 0.008)
    cuello = capsula(p, (0, 0.59, 0), (0, 0.64, 0), 0.06)
    t = restar(t, cuello, 0.01)
    if ropa == "buzo":
        capucha = elipsoide(p, (0, 0.64, -0.1), (0.13, 0.08, 0.08))
        t = unir(t, capucha, 0.04)
    return t


HOMBRO_A_MUNECA = 0.585 - 0.42


def _corte_brazo(p, lado, hasta_y):
    """Lo del brazo que está por encima de hasta_y (perpendicular al brazo, con un poco de inclinación)."""
    eje = np.array([lado * (0.2 - HOMBRO[0]), 0.42 - 0.585, 0.02], np.float32)
    eje /= np.linalg.norm(eje)
    punto = np.array([HOMBRO[0] * lado, 0.585, 0], np.float32) + eje * ((0.585 - hasta_y) / -eje[1])
    return plano(p - punto, eje, 0.0)


def _manga(p, s, lado):
    larga = s["ropa"] in ("buzo", "campera")
    gruesa = capsula(p, (lado * HOMBRO[0], 0.585, 0), (lado * 0.2, 0.42, 0.02), 0.05, 0.044)
    return cortar(gruesa, _corte_brazo(p, lado, 0.425 if larga else 0.505), 0.006)


def _puno(p, lado, y0, y1, grosor):
    gruesa = capsula(p, (lado * HOMBRO[0], 0.585, 0), (lado * 0.2, 0.42, 0.02), 0.038 + grosor, 0.033 + grosor)
    return cortar(cortar(gruesa, _corte_brazo(p, lado, y0), 0.004), -_corte_brazo(p, lado, y1), 0.004)


def _brazo(p, lado):
    return unir(capsula(p, (lado * HOMBRO[0], 0.585, 0), (lado * 0.2, 0.42, 0.02), 0.038, 0.033),
                elipsoide(p, (lado * 0.205, 0.39, 0.025), (0.042, 0.048, 0.04)), 0.025)


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
    caja_cabeza = ((-0.32, 0.5, -0.4), (0.32, 1.25, 0.32))

    # Cabeza
    partes["cabeza"].append(("piel", lambda p: unir(unir(_cabeza_sdf(p, con_foto),
                                                         elipsoide(p, (-0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015),
                                                    elipsoide(p, (0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015)
                             if con_foto else unir(unir(unir(_cabeza_sdf(p), elipsoide(p, (0, 0.79, 0.178), (0.026, 0.021, 0.02)), 0.02),
                                                        elipsoide(p, (-0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015),
                                                   elipsoide(p, (0.195, 0.8, 0.0), (0.03, 0.048, 0.036)), 0.015),
                             ((-0.25, 0.6, -0.22), (0.25, 1.05, 0.25)), m_piel))
    if not con_foto:
        ojos = lambda p: unir(elipsoide(p, (-0.068, 0.83, 0.16), (0.03, 0.04, 0.018)),  # noqa: E731
                              elipsoide(p, (0.068, 0.83, 0.16), (0.03, 0.04, 0.018)))
        partes["cabeza"].append(("ojos", ojos, ((-0.12, 0.77, 0.12), (0.12, 0.89, 0.2)),
                                 {"color": _c(s["ojos"]), "rugosidad": 0.15}))
        brillos = lambda p: unir(esfera(p, (-0.058, 0.846, 0.174), 0.009), esfera(p, (0.078, 0.846, 0.174), 0.009))  # noqa: E731
        partes["cabeza"].append(("brillo", brillos, ((-0.08, 0.83, 0.16), (0.1, 0.86, 0.19)),
                                 {"color": (1, 1, 1), "rugosidad": 0.1}))
        cejas = lambda p: unir(curva(p, [(-0.1, 0.875, 0.152), (-0.07, 0.888, 0.163), (-0.04, 0.88, 0.168)], 0.009, 0.006),  # noqa: E731
                               curva(p, [(0.1, 0.875, 0.152), (0.07, 0.888, 0.163), (0.04, 0.88, 0.168)], 0.009, 0.006))
        partes["cabeza"].append(("cejas", cejas, ((-0.12, 0.86, 0.13), (0.12, 0.9, 0.19)), m_tela(_oscuro(pelo, 0.85), 0.6)))
        boca = s["boca"]
        if boca in ("sonrisa", "lengua"):
            forma = lambda p: curva(p, [(-0.042, 0.742, 0.168), (0, 0.712, 0.181), (0.042, 0.742, 0.168)], 0.0085, 0.0085)  # noqa: E731
        elif boca == "sorpresa":
            forma = lambda p: elipsoide(p, (0, 0.725, 0.172), (0.022, 0.028, 0.014))  # noqa: E731
        else:
            forma = lambda p: curva(p, [(-0.032, 0.728, 0.172), (0, 0.726, 0.178), (0.032, 0.728, 0.172)], 0.007, 0.007)  # noqa: E731
        partes["cabeza"].append(("boca", forma, ((-0.06, 0.69, 0.14), (0.06, 0.76, 0.2)), m_tela("#6b2a24", 0.5)))
        if boca == "lengua":
            partes["cabeza"].append(("lengua", lambda p: elipsoide(p, (0.005, 0.712, 0.178), (0.02, 0.016, 0.012)),
                                     ((-0.03, 0.69, 0.16), (0.03, 0.73, 0.2)), m_tela("#e8707a", 0.4)))
        rubor = lambda p: unir(elipsoide(p, (-0.115, 0.77, 0.135), (0.032, 0.018, 0.012)),  # noqa: E731
                               elipsoide(p, (0.115, 0.77, 0.135), (0.032, 0.018, 0.012)))
        partes["cabeza"].append(("rubor", rubor, ((-0.16, 0.74, 0.11), (0.16, 0.8, 0.16)),
                                 {"color": _c(_mezclar(piel, "#ff8a8a", 0.35)), "rugosidad": 0.7}))
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
    _lentes(partes["cabeza"], s, ca)
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
    _extras_torso(partes["torso"], s, ca, detalle)

    # Brazos (con mano) y mangas
    for nombre, lado in (("brazo_i", -1), ("brazo_d", 1)):
        caja = ((lado * 0.13 - 0.17, 0.3, -0.12), (lado * 0.13 + 0.17, 0.68, 0.16))
        caja = (tuple(min(a, b) for a, b in zip(*caja)), tuple(max(a, b) for a, b in zip(*caja)))
        partes[nombre].append(("brazo", lambda p, lado=lado: _brazo(p, lado), caja, m_piel))
        partes[nombre].append(("manga", lambda p, lado=lado: _manga(p, s, lado), caja, m_tela(remera)))
        if s["ropa"] in ("buzo", "campera"):
            partes[nombre].append(("puño", lambda p, lado=lado: _puno(p, lado, 0.425, 0.452, 0.019),
                                   caja, m_tela(_oscuro(remera, 0.82))))
        elif boca_jrs:
            partes[nombre].append(("puño", lambda p, lado=lado: _puno(p, lado, 0.505, 0.53, 0.02),
                                   caja, m_tela(avatar3d.BOCA_ORO)))
    _extras_mano(partes["brazo_d"], s, ca)

    # Piernas, cadera y zapatillas
    caja_piernas = ((-0.2, -0.01, -0.12), (0.2, 0.5, 0.16))
    pantalon = s["pantalon"]
    if s["ropa"] == "vestido":
        partes["piernas"].append(("piernas", lambda p: _piernas(p, s), caja_piernas, m_piel))
    else:
        partes["piernas"].append(("pantalon", lambda p: _piernas(p, s), caja_piernas, m_tela(pantalon)))
    zapa = s["zapatillas"]
    partes["piernas"].append(("zapatillas", lambda p: unir(_zapatillas(p, -0.07), _zapatillas(p, 0.07)), caja_piernas,
                              m_tela(zapa, 0.6)))
    suela = "#d9dce1" if avatar3d._rgb(zapa)[0] > 0.8 else "#f2f2f2"
    partes["piernas"].append(("suela", lambda p: unir(_suela(p, -0.07), _suela(p, 0.07)), caja_piernas, m_tela(suela, 0.7)))
    return partes


def _pelo_funcion(s):
    # Con algo en la cabeza (gorra, gorro, sombrero, galera, corona) no se le pone pelo: así nada atraviesa el accesorio
    if s["peinado"] == "pelado" or s["cabeza"] != "ninguno":
        return None
    return lambda p: _pelo(p, s)


def _sombreros(lista, s, ca, detalle):
    c = s["cabeza"]
    caja = ((-0.3, 0.85, -0.3), (0.3, 1.32, 0.42))
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


def _lentes(lista, s, ca):
    l = s["lentes"]
    caja = ((-0.22, 0.75, -0.05), (0.22, 0.92, 0.25))
    if l in ("anteojos", "lentes3d", "sol"):
        marco = {"anteojos": "#151515", "lentes3d": "#f4f4f4", "sol": ca}[l]

        def armazon(p):
            d = unir(toro_z(p, (-0.07, 0.83, 0.19), 0.048, 0.007), toro_z(p, (0.07, 0.83, 0.19), 0.048, 0.007))
            d = unir(d, capsula(p, (-0.025, 0.835, 0.193), (0.025, 0.835, 0.193), 0.006))
            for lado in (-1, 1):
                d = unir(d, capsula(p, (lado * 0.118, 0.835, 0.185), (lado * 0.19, 0.84, 0.04), 0.005))
            return d
        lista.append(("marco", armazon, caja, {"color": _c(marco), "rugosidad": 0.3}))
        for lado, color in ((-1, "#d43a3a"), (1, "#2ec5d6")):
            tono = color if l == "lentes3d" else ("#111111" if l == "sol" else "#cfe9f5")
            lista.append((f"vidrio{lado}", lambda p, lado=lado: elipsoide(p, (lado * 0.07, 0.83, 0.19), (0.046, 0.046, 0.004)),
                          caja, {"color": _c(tono), "rugosidad": 0.05, "metal": 0.2 if l != "sol" else 0.0}))
    elif l == "antifaz":
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
    "cabeza": ("peinado", "cabeza", "lentes", "boca", "barba", "extra"),
    "torso": ("ropa", "estampa", "cuerpo", "extra"),
    "brazo_i": ("ropa", "cuerpo"),
    "brazo_d": ("ropa", "cuerpo", "extra"),
    "piernas": ("ropa", "cuerpo"),
}


def clave(spec: dict) -> str:
    s = avatar3d.normalizar(spec)
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
                fino = nombre in ("brillo", "boca", "ojos", "cejas", "lengua")
                geo = malla(funcion, caja[0], caja[1], paso * 0.6 if fino else paso)
            nuevas[f"{nombre}__v"], nuevas[f"{nombre}__n"], nuevas[f"{nombre}__t"] = geo
            mallas.append((nombre, geo, material))
        if set(nuevas) != set(guardadas):
            np.savez_compressed(archivo_forma, **nuevas)
        guardar_glb(destino / f"{nombre_parte}.glb", mallas)
    (destino / "listo").write_text("1")
    return destino
