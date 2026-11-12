"""El muñequito 3D: el avatar del usuario, armado con piezas simples (esferas, cajas, cilindros) y dibujado píxel por píxel
(rayos contra cada pieza con numpy, sin OpenGL: anda en cualquier PC). La misma descripción (un dict chico) se usa en el foro de la revista,
que lo arma igual con three.js."""
from __future__ import annotations

import base64
import json
import math
import re
import threading

import numpy as np

from . import mascotas, poses
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

NOMBRE = "BiriBiri"   # cómo se llama el avatar en la app («Armá tu BiriBiri»)

# Cada opción: clave -> {valor: texto}. El primer valor es el predeterminado (salvo el género: ver más abajo).
OPCIONES = {
    "genero": {"hombre": "Hombre", "mujer": "Mujer", "nobinario": "No binario"},
    "peinado": {"corto": "Corto", "flequillo": "Flequillo", "largo": "Largo", "colita": "Colita", "trenzas": "Trenzas",
                "rulos": "Rulos", "afro": "Afro", "cresta": "Cresta", "rodete": "Rodete", "pelado": "Pelado"},
    "mirada": {"normal": "Normales", "grandes": "Grandes y asombrados", "feliz": "Felices (^ ^)", "guino": "Guiño",
               "enojados": "Enojados", "tristes": "Tristes", "entrecerrados": "Entrecerrados",
               "dormidos": "Cerrados (durmiendo)", "enamorado": "Enamorado (corazones)"},
    "cejas": {"normales": "Normales", "finas": "Finitas", "arqueadas": "Finitas y arqueadas", "pobladas": "Pobladas",
              "peludas": "Peludas", "unidas": "Unidas", "enojadas": "Enojadas", "tristes": "Tristes",
              "levantada": "Una levantada", "ninguna": "Sin cejas"},
    "boca": {"sonrisa": "Sonrisa", "dientes": "Sonrisa con dientes", "risa": "Carcajada", "abierta": "Boca abierta",
             "sorpresa": "¡Sorpresa!", "seria": "Seria", "triste": "Triste", "picara": "Sonrisa pícara",
             "lengua": "Sacando la lengua"},
    "barba": {"ninguna": "Sin barba", "bigote": "Bigote", "bigote_fino": "Bigote fino", "manubrio": "Bigote manubrio",
              "perilla": "Perilla", "candado": "Candado", "chivita": "Chivita", "barba_corta": "Barba corta",
              "barba": "Barba completa", "barba_larga": "Barba larga"},
    "cuerpo": {"normal": "Normal", "flaco": "Flaco", "robusto": "Robusto"},
    "ropa": {"remera": "Remera", "boca": "Camiseta de Boca", "buzo": "Buzo con capucha", "campera": "Campera",
             "camisa": "Camisa", "traje": "Traje con corbata", "musculosa": "Musculosa",
             "sweater": "Sweater de cuello alto", "peto": "Peto de jardinero",
             "vestido": "Vestido", "vestido_largo": "Vestido largo", "pollera": "Remera y pollera",
             "blusa": "Blusa con moño"},
    "estampa": {"lisa": "Lisa", "rayas": "Rayas", "logo": "Logo en el pecho"},
    "cabeza": {"ninguno": "Nada", "gorra": "Gorra", "gorro": "Gorro con pompón", "sombrero": "Sombrero",
               "paja": "Sombrero de paja", "galera": "Galera de cine", "corona": "Corona", "kipa": "Kipá"},
    "lentes": {"ninguno": "Nada", "anteojos": "Anteojos redondos", "cuadrados": "Anteojos cuadrados",
               "aviador": "Aviador", "gatuno": "Gatunos", "corazones": "Corazones", "sol": "Lentes de sol",
               "lentes3d": "Lentes 3D", "antifaz": "Antifaz"},
    "extra": {"ninguno": "Nada", "pochoclos": "Balde de pochoclos", "gaseosa": "Gaseosa", "claqueta": "Claqueta",
              "auriculares": "Auriculares", "bufanda": "Bufanda", "capa": "Capa de superhéroe"},
    "bandera": {"ninguna": "Sin bandera", "ar": "Argentina", "uy": "Uruguay", "cl": "Chile", "py": "Paraguay",
                "bo": "Bolivia", "pe": "Perú", "ec": "Ecuador", "co": "Colombia", "ve": "Venezuela", "br": "Brasil",
                "mx": "México", "cu": "Cuba", "es": "España", "pt": "Portugal", "fr": "Francia", "it": "Italia",
                "de": "Alemania", "gb": "Reino Unido", "ru": "Rusia", "us": "Estados Unidos", "ca": "Canadá",
                "ps": "Palestina", "cn": "China", "jp": "Japón"},
    "pose": poses.etiquetas(),      # cómo está parado el muñequito (se arma aparte: no cambia el modelo)
    "lugar": poses.LUGARES,         # en qué otro lugar del reproductor aparece
    "mascota": mascotas.ETIQUETAS,                  # el perro o gato que está parado a su lado
    "interaccion": poses.ETIQUETAS_INTERACCION,     # qué hacen juntos (mimos, comida…)
}
# Qué prendas se ofrecen según el género (las que no figuran son para cualquiera; «no binario» ve todas)
ROPA_GENERO = {"traje": "hombre", "vestido": "mujer", "vestido_largo": "mujer", "pollera": "mujer", "blusa": "mujer"}
COLORES = ("piel", "pelo", "ojos", "remera", "estampa_color", "pantalon", "zapatillas", "accesorio_color", "lentes_color",
           "mascota_color", "mascota_color2")
# Valores numéricos (mínimo, máximo, de partida): cómo se acomoda la bandera de fondo
NUMEROS = {"bandera_x": (-100, 100, 0), "bandera_y": (-100, 100, 0), "bandera_tam": (40, 220, 100),
           "bandera_giro": (-60, 60, 16), "bandera_costado": (-80, 80, -32)}
PREDETERMINADO = {
    "piel": "#e8b896", "pelo": "#3b2a1e", "ojos": "#2b1d14",
    "remera": "#2f7fd1", "estampa_color": "#f2f2f2", "pantalon": "#2b3a55", "zapatillas": "#f2f2f2",
    "accesorio_color": "#d4513d", "lentes_color": "#151515", "mascota_color": "#e0b060", "mascota_color2": "#c99a4a",
    **{clave: next(iter(valores)) for clave, valores in OPCIONES.items()},
}
PREDETERMINADO.update({k: v[2] for k, v in NUMEROS.items()})
PREDETERMINADO["genero"] = "nobinario"   # los que ya tenían su muñequito siguen igual (cuerpo neutro)
# Compatibilidad: antes había un solo «accesorio»
_ACCESORIO_VIEJO = {"gorra": ("cabeza", "gorra"), "anteojos": ("lentes", "anteojos"), "lentes3d": ("lentes", "lentes3d"),
                    "auriculares": ("extra", "auriculares"), "pochoclos": ("extra", "pochoclos")}
FOTO_MAXIMO = 24_000  # caracteres del data URL (una foto chica de la cara, ~ 17 KB)
_HEX = re.compile(r"#[0-9a-fA-F]{6}")
_FOTO = re.compile(r"data:image/jpeg;base64,[A-Za-z0-9+/=]+")


def normalizar(spec) -> dict:
    """Solo claves y valores conocidos (lo que viene del servidor o de la configuración puede estar mal)."""
    if isinstance(spec, str):
        try:
            spec = json.loads(spec)
        except ValueError:
            spec = {}
    if not isinstance(spec, dict):
        spec = {}
    limpio = dict(PREDETERMINADO)
    viejo = _ACCESORIO_VIEJO.get(spec.get("accesorio"))
    if viejo:
        limpio[viejo[0]] = viejo[1]
    for clave in COLORES:
        valor = spec.get(clave)
        if isinstance(valor, str) and _HEX.fullmatch(valor):
            limpio[clave] = valor.lower()
    for clave, valores in OPCIONES.items():
        if spec.get(clave) in valores:
            limpio[clave] = spec[clave]
    for clave, (minimo, maximo, _por_defecto) in NUMEROS.items():
        valor = spec.get(clave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            limpio[clave] = int(max(minimo, min(maximo, round(valor))))
    foto = spec.get("foto")
    if isinstance(foto, str) and len(foto) <= FOTO_MAXIMO and _FOTO.fullmatch(foto):
        limpio["foto"] = foto
    return limpio


_fotos: dict[str, QPixmap] = {}


def pixmap_de_foto(foto: str) -> QPixmap | None:
    """La foto de la cara (data URL) como imagen, con caché (se dibuja muchas veces por segundo)."""
    if not foto:
        return None
    if foto not in _fotos:
        pix = QPixmap()
        try:
            pix.loadFromData(base64.b64decode(foto.split(",", 1)[1], validate=True), "JPG")
        except (ValueError, IndexError):
            pix = QPixmap()
        if len(_fotos) > 64:
            _fotos.clear()
        _fotos[foto] = pix
    pix = _fotos[foto]
    return None if pix.isNull() else pix


# --- Geometría: piezas exactas (no triángulos) ------------------------------------------------------------
# Cada pieza es un sólido convexo: una cuádrica (elipsoide o cilindro/cono con sección elíptica) recortada por
# planos, o una caja (solo planos). Al dibujar, cada píxel le pregunta a cada pieza dónde la toca su rayo y se queda
# con la más cercana: así no hay errores de orden entre piezas que se cruzan, y las superficies salen redondas.

def _rgb(hexa: str) -> tuple[float, float, float]:
    return int(hexa[1:3], 16) / 255, int(hexa[3:5], 16) / 255, int(hexa[5:7], 16) / 255


_ARRIBA, _ABAJO = np.array([0.0, 1.0, 0.0]), np.array([0.0, -1.0, 0.0])


class _Pieza:
    tipo = ""

    def __init__(self, color, planos=(), centro=(0, 0, 0), radio=1.0, franjas=None, marca=""):
        self.color = np.array(_rgb(color), np.float32)
        self.planos = [(np.asarray(n, float), float(k)) for n, k in planos]  # sólido = {x : n·x <= k}
        self.centro = np.asarray(centro, float)
        self.radio = float(radio)           # esfera que la contiene (para saber qué píxeles mirar)
        self.franjas = franjas              # (cantidad de lados, colores): el costado pintado por gajos
        self.marca = marca

    def _cuadrica(self, O, D):
        return None

    def tocar(self, O, D):
        """Para cada rayo (origen O, dirección D común): distancia de entrada, normal y si entró por la cuádrica."""
        n = len(O)
        t_in = np.full(n, -np.inf)
        t_out = np.full(n, np.inf)
        fuente = np.full(n, -1)
        normal_cuad = None
        q = self._cuadrica(O, D)
        if q is not None:
            t0, t1, ok, normal_cuad = q
            t_in = np.where(ok, t0, np.inf)
            t_out = np.where(ok, t1, -np.inf)
        for i, (nv, k) in enumerate(self.planos):
            no = O @ nv - k
            nd = float(D @ nv)
            if abs(nd) < 1e-9:
                t_out = np.where(no <= 0, t_out, -np.inf)
                continue
            tt = -no / nd
            if nd < 0:
                cambia = tt > t_in
                t_in = np.where(cambia, tt, t_in)
                fuente = np.where(cambia, i, fuente)
            else:
                t_out = np.minimum(t_out, tt)
        toca = np.isfinite(t_in) & (t_in < t_out)
        normal = np.zeros((n, 3))
        if normal_cuad is not None:
            usa = toca & (fuente == -1)
            if usa.any():
                normal[usa] = normal_cuad(O[usa] + t_in[usa, None] * D)
        for i, (nv, _k) in enumerate(self.planos):
            normal[toca & (fuente == i)] = nv
        return np.where(toca, t_in, np.inf), normal, toca & (fuente == -1)

    def color_en(self, P, de_costado):
        return np.broadcast_to(self.color, (len(P), 3))


class _Elipsoide(_Pieza):
    def __init__(self, centro, semiejes, color, desde_y=None, **kw):
        c = np.asarray(centro, float)
        s = np.asarray(semiejes, float)
        planos = [(_ABAJO, -desde_y)] if desde_y is not None else []  # casquete: solo y >= desde_y
        super().__init__(color, planos, c, float(s.max()), **kw)
        self.s = s

    def _cuadrica(self, O, D):
        p = (O - self.centro) / self.s
        d = D / self.s
        a = float(d @ d)
        b = 2 * (p @ d)
        c = np.einsum("ij,ij->i", p, p) - 1
        disc = b * b - 4 * a * c
        ok = disc > 0
        raiz = np.sqrt(np.where(ok, disc, 0))
        s2 = self.s ** 2
        return (-b - raiz) / (2 * a), (-b + raiz) / (2 * a), ok, lambda P: (P - self.centro) / s2


class _Cilindro(_Pieza):
    """Vertical, de y0 a y0+alto, radio r abajo y r2 arriba (cono truncado), sección elíptica (z escalada)."""

    def __init__(self, base, r, alto, color, r2=None, ez=1.0, **kw):
        b = np.asarray(base, float)
        r2 = r if r2 is None else r2
        planos = [(_ABAJO, -b[1]), (_ARRIBA, b[1] + alto)]
        mitad = b + (0, alto / 2, 0)
        super().__init__(color, planos, mitad, math.hypot(max(r, r2), alto / 2), **kw)
        self.b, self.r, self.k, self.ez = b, r, (r2 - r) / alto, ez

    def _cuadrica(self, O, D):
        ox, oz = O[:, 0] - self.b[0], O[:, 2] - self.b[2]
        uy = O[:, 1] - self.b[1]
        dx, dy, dz = D
        e2, k = self.ez ** 2, self.k
        R = self.r + k * uy
        a = dx * dx + dz * dz / e2 - k * k * dy * dy
        bb = 2 * (ox * dx + oz * dz / e2) - 2 * k * R * dy
        c = ox * ox + oz * oz / e2 - R * R
        disc = bb * bb - 4 * a * c
        ok = (disc > 0) & (a > 1e-9)
        raiz = np.sqrt(np.where(ok, disc, 0))

        def normal(P):
            y = P[:, 1] - self.b[1]
            return np.stack([P[:, 0] - self.b[0], -k * (self.r + k * y), (P[:, 2] - self.b[2]) / e2], axis=1)

        return (-bb - raiz) / (2 * a), (-bb + raiz) / (2 * a), ok, normal

    def color_en(self, P, de_costado):
        if not self.franjas:
            return super().color_en(P, de_costado)
        lados, colores = self.franjas
        ang = np.arctan2((P[:, 2] - self.b[2]) / self.ez, P[:, 0] - self.b[0])
        i = (np.floor(ang / (2 * math.pi) * lados).astype(int)) % len(colores)
        tabla = np.array([_rgb(c) for c in colores], np.float32)
        return np.where(de_costado[:, None], tabla[i], self.color)


class _Caja(_Pieza):
    def __init__(self, centro, tam, color, **kw):
        c = np.asarray(centro, float)
        m = np.asarray(tam, float) / 2
        planos = []
        for eje in range(3):
            n = np.zeros(3)
            n[eje] = 1
            planos += [(n, c[eje] + m[eje]), (-n, -(c[eje] - m[eje]))]
        super().__init__(color, planos, c, float(np.linalg.norm(m)), **kw)


class _Escena:
    """Las piezas del muñequito (se llama igual que antes para no cambiar cómo se arma)."""

    def __init__(self):
        self.piezas: list[_Pieza] = []
        self.encima = False  # ya no hace falta (hay profundidad por píxel); se deja para no tocar armar()


class Modelo:
    def __init__(self, piezas: list[_Pieza], foto: QPixmap | None, techo: float = 3.42):
        self.piezas = piezas
        self.techo = techo  # hasta dónde llega arriba (pelo, sombreros): para que no se corte
        self.foto = foto
        self.foto_px = _a_numpy(foto.toImage()) if foto is not None else None


def _esfera(m: _Escena, centro, radio, color, escala=(1, 1, 1), lat=8, lon=12, hasta=1.0, marca=""):
    """hasta < 1: solo la parte de arriba (un casquete: el pelo, la gorra)."""
    s = np.asarray(escala, float) * radio
    desde = None
    if hasta < 1.0:
        filas = max(1, round(lat * hasta))
        desde = centro[1] + math.cos(math.pi * filas / lat) * s[1]
    m.piezas.append(_Elipsoide(centro, s, color, desde_y=desde, marca=marca))


def _caja(m: _Escena, centro, tam, color):
    m.piezas.append(_Caja(centro, tam, color))


def _cilindro(m: _Escena, base, radio, alto, color, lados=10, escala_z=1.0, radio_arriba=None, colores_lados=None):
    m.piezas.append(_Cilindro(base, radio, alto, color, r2=radio_arriba, ez=escala_z,
                              franjas=(lados, colores_lados) if colores_lados else None))


def _tronco(m: _Escena, y0, y1, r0, r1, colores, escala_z, lados=12):
    """El torso (o el vestido) en franjas horizontales: un color por franja (rayas) o uno solo."""
    n = len(colores)
    for i, color in enumerate(colores):
        a, b = y0 + (y1 - y0) * i / n, y0 + (y1 - y0) * (i + 1) / n
        ra, rb = r0 + (r1 - r0) * i / n, r0 + (r1 - r0) * (i + 1) / n
        _cilindro(m, (0, a, 0), ra, b - a, color, lados=lados, escala_z=escala_z, radio_arriba=rb)


def _elip(m: _Escena, centro, semiejes, color, planos=(), desde_y=None):
    """Elipsoide (con planos que lo recortan: el sólido queda donde n·x <= k)."""
    pieza = _Elipsoide(centro, semiejes, color, desde_y=desde_y)
    for n, k in planos:
        pieza.planos.append((np.asarray(n, float), float(k)))
    m.piezas.append(pieza)


def _oscurecer(hexa: str, f: float) -> str:
    r, g, b = _rgb(hexa)
    return "#%02x%02x%02x" % tuple(int(max(0, min(1, c * f)) * 255) for c in (r, g, b))


BOCA_AZUL, BOCA_ORO = "#0b3a86", "#f3c300"


def armar(spec: dict):
    """Las piezas del muñequito según su descripción. Pies en y=0, la cabeza arriba (≈ 3,3 de alto).
    Devuelve un Modelo: las piezas y la foto de la cara (si hay), que va hundida en la cabeza."""
    s = normalizar(spec)
    m = _Escena()
    piel, pelo, ca, detalle = s["piel"], s["pelo"], s["accesorio_color"], s["estampa_color"]
    foto = pixmap_de_foto(s.get("foto", ""))
    ropa = s["ropa"]
    boca_jrs = ropa == "boca"
    remera = BOCA_AZUL if boca_jrs else s["remera"]
    # Contextura: radio del torso (abajo, arriba), profundidad y separación de brazos y piernas
    r0, r1, ez, bx, px = {"flaco": (0.36, 0.33, 0.7, 0.48, 0.19), "robusto": (0.54, 0.47, 0.8, 0.66, 0.25)}.get(
        s["cuerpo"], (0.44, 0.4, 0.72, 0.56, 0.22))

    def frente(y):  # z del pecho a esa altura
        return (r0 + (r1 - r0) * (y - 1.0) / 0.95) * ez

    # --- Piernas, cadera y zapatillas (redondeadas, con suela)
    suela = "#cfd3d8" if _rgb(s["zapatillas"])[0] > 0.8 else "#f2f2f2"
    for x in (-px, px):
        _elip(m, (x, 0.13, 0.08), (0.15, 0.11, 0.25), s["zapatillas"], desde_y=0.05)
        _caja(m, (x, 0.035, 0.08), (0.29, 0.07, 0.5), suela)
        _cilindro(m, (x, 0.16, 0), 0.14, 0.92, piel if ropa == "vestido" else s["pantalon"], lados=8)
        if ropa != "vestido":
            _cilindro(m, (x, 0.16, 0), 0.155, 0.06, _oscurecer(s["pantalon"], 0.85))  # ruedo
    if ropa != "vestido":
        _elip(m, (0, 1.04, 0), (r0 * 0.98, 0.16, r0 * ez * 0.98), s["pantalon"])  # cadera
        _cilindro(m, (0, 0.98, 0), r0 * 1.0, 0.07, _oscurecer(s["pantalon"], 0.7), escala_z=ez)  # cinturón
    # --- Torso
    if boca_jrs:
        franjas = [BOCA_AZUL, BOCA_ORO, BOCA_AZUL]
    elif s["estampa"] == "rayas":
        franjas = [remera, detalle] * 3
    else:
        franjas = [remera]
    if ropa == "vestido":
        _tronco(m, 0.55, 1.95, 0.66, r1, franjas[:-1] if len(franjas) > 1 else franjas, ez)
        _cilindro(m, (0, 1.3, 0), 0.0 + (0.66 + (r1 - 0.66) * 0.536) * 1.01, 0.07, detalle, escala_z=ez)  # cinta
    else:
        _tronco(m, 1.0, 1.95, r0, r1, franjas, ez)
    # Hombros redondos y cuello de la remera
    for x in (-1, 1):
        _elip(m, (x * (bx - 0.05), 1.84, 0), (0.15, 0.12, 0.14), remera)
    _cilindro(m, (0, 1.93, 0), 0.17, 0.05, BOCA_ORO if boca_jrs else _oscurecer(remera, 0.82), escala_z=0.9)
    if s["estampa"] == "logo" and not boca_jrs:
        _elip(m, (0, 1.6, frente(1.6) - 0.01), (0.16, 0.12, 0.04), detalle)
        _elip(m, (0, 1.6, frente(1.6) + 0.015), (0.09, 0.03, 0.02), remera)
    if boca_jrs:
        _caja(m, (0.17, 1.74, frente(1.74) + 0.005), (0.09, 0.1, 0.02), BOCA_ORO)  # escudito (sin marca)
    if ropa == "campera":
        # Abierta: se ve la remera de abajo; cierre y solapas
        _caja(m, (0, 1.47, frente(1.47) + 0.005), (0.2, 0.9, 0.03), detalle)
        for x in (-0.11, 0.11):
            _caja(m, (x, 1.47, frente(1.47) + 0.02), (0.025, 0.9, 0.02), "#c9ccd1")
            _caja(m, (x * 1.5, 1.88, frente(1.88) - 0.02), (0.17, 0.12, 0.1), _oscurecer(remera, 0.85))
    elif ropa == "buzo":
        _elip(m, (0, 2.02, -0.3), (0.42, 0.3, 0.26), remera)                       # capucha
        _elip(m, (0, 2.02, -0.24), (0.3, 0.2, 0.2), _oscurecer(remera, 0.7))       # adentro de la capucha
        _elip(m, (0, 1.24, frente(1.24) - 0.03), (0.25, 0.12, 0.05), _oscurecer(remera, 0.9))  # bolsillo
        for x in (-0.09, 0.09):
            _cilindro(m, (x, 1.58, frente(1.7) + 0.02), 0.014, 0.3, detalle, lados=6)  # cordones
            _elip(m, (x, 1.57, frente(1.6) + 0.02), (0.025, 0.035, 0.025), detalle)
    # --- Brazos: manga corta (remera, vestido, Boca) o larga (buzo, campera), con puño
    larga = ropa in ("buzo", "campera")
    for x in (-bx, bx):
        if larga:
            _cilindro(m, (x, 1.24, 0), 0.115, 0.64, remera, lados=10, radio_arriba=0.125)
            _cilindro(m, (x, 1.2, 0), 0.12, 0.07, _oscurecer(remera, 0.8), lados=10)
        else:
            _cilindro(m, (x, 1.22, 0), 0.095, 0.42, piel, lados=10, radio_arriba=0.105)
            _cilindro(m, (x, 1.6, 0), 0.13, 0.26, remera, lados=10, radio_arriba=0.14)
            if boca_jrs:
                _cilindro(m, (x, 1.6, 0), 0.135, 0.045, BOCA_ORO, lados=10)
        _elip(m, (x, 1.12, 0.01), (0.12, 0.14, 0.12), piel)                       # mano
    _cilindro(m, (0, 1.9, 0), 0.13, 0.2, piel, lados=10)
    # --- Cabeza: orejas, nariz, cejas, ojos con brillo, boca
    _esfera(m, (0, 2.58, 0), 0.64, piel, lat=10, lon=14, marca="cabeza")
    for x in (-0.62, 0.62):
        _elip(m, (x, 2.54, 0.02), (0.08, 0.14, 0.1), piel)
    if foto is None:
        _elip(m, (0, 2.5, 0.63), (0.065, 0.06, 0.05), _oscurecer(piel, 0.96))   # nariz
        for x in (-0.22, 0.22):
            _elip(m, (x, 2.62, 0.55), (0.085, 0.106, 0.047), s["ojos"])
            _elip(m, (x + 0.03, 2.66, 0.59), (0.026, 0.026, 0.012), "#ffffff")
            _elip(m, (x, 2.78, 0.57), (0.1, 0.022, 0.03), _oscurecer(pelo, 0.9))  # ceja
        boca = s["boca"]
        labio = "#7a3b2e"
        if boca in ("sonrisa", "lengua"):
            _elip(m, (0, 2.39, 0.585), (0.13, 0.06, 0.03), labio, planos=[((0, 1, 0), 2.39)])
            if boca == "lengua":
                _elip(m, (0.02, 2.33, 0.6), (0.055, 0.045, 0.03), "#e8707a")
        elif boca == "sorpresa":
            _elip(m, (0, 2.36, 0.59), (0.07, 0.088, 0.032), "#5a2a20")
        else:
            _elip(m, (0, 2.37, 0.6), (0.1, 0.018, 0.025), labio)
    # --- Barba (del color del pelo)
    b = s["barba"]
    if b in ("bigote", "candado"):
        for x in (-0.085, 0.085):
            _elip(m, (x, 2.435, 0.6), (0.11, 0.04, 0.05), pelo)
    if b == "candado":
        _elip(m, (0, 2.22, 0.5), (0.1, 0.08, 0.08), pelo)
    elif b == "barba":
        _esfera(m, (0, 2.3, 0.2), 0.5, pelo, escala=(1.06, 0.62, 0.86), lat=7, lon=12)
    # --- Pelo. Con algo en la cabeza, lo que sobresale arriba (cresta, rodete, afro) no se ve
    p, sombrero = s["peinado"], s["cabeza"]
    tapado = sombrero != "ninguno"
    if p in ("corto", "flequillo", "largo", "rodete", "cresta", "colita", "trenzas") or (tapado and p != "pelado"):
        _esfera(m, (0, 2.62, -0.03), 0.68, pelo, hasta=0.42, lat=10, lon=14)
        if p != "largo":
            # La nuca: el pelo baja por atrás y por los costados (si no, de espaldas parecía un casquito)
            _elip(m, (0, 2.6, -0.04), (0.67, 0.67, 0.67), pelo, planos=[((0, 0, 1), -0.06)], desde_y=2.18)
            for x in (-0.57, 0.57):
                _elip(m, (x, 2.68, 0.22), (0.05, 0.1, 0.07), pelo)  # patillas (adelante de la oreja)
    if p == "flequillo":
        for x, y in ((-0.24, 2.9), (0.02, 2.93), (0.27, 2.88)):
            _elip(m, (x, y, 0.47), (0.22, 0.11, 0.16), pelo)
    elif p == "largo":
        _elip(m, (0, 2.3, -0.2), (0.7, 0.92, 0.53), pelo)
        for x in (-0.6, 0.6):
            _elip(m, (x, 2.42, 0.04), (0.12, 0.42, 0.22), pelo)
            _elip(m, (x * 0.97, 2.02, 0.0), (0.1, 0.2, 0.19), pelo)
    elif p == "colita":
        _elip(m, (0, 2.8, -0.66), (0.08, 0.08, 0.06), ca)                    # gomita
        _elip(m, (0, 2.62, -0.78), (0.15, 0.24, 0.15), pelo)
        _elip(m, (0, 2.3, -0.8), (0.11, 0.2, 0.11), pelo)
    elif p == "trenzas":
        for x in (-0.56, 0.56):
            for i in range(6):
                _elip(m, (x * (1 - i * 0.035), 2.36 - i * 0.14, -0.02), (0.1 - i * 0.006,) * 3, pelo)
            _elip(m, (x * 0.8, 1.52, -0.02), (0.05, 0.04, 0.05), ca)       # gomita
            _elip(m, (x * 0.8, 1.42, -0.02), (0.06, 0.08, 0.06), pelo)    # puntita
    elif p == "rodete" and not tapado:
        _elip(m, (0, 3.24, -0.3), (0.25, 0.22, 0.25), pelo)
        _cilindro(m, (0, 3.0, -0.27), 0.16, 0.06, ca, lados=12)
    elif p == "cresta" and not tapado:
        for i, z in enumerate((0.38, 0.14, -0.1, -0.34, -0.56)):
            alto = 0.26 - abs(i - 1.5) * 0.04
            _elip(m, (0, 3.2 - abs(i - 1.5) * 0.05 - (0.08 if i == 4 else 0), z), (0.08, alto, 0.13), pelo)
    elif p in ("rulos", "afro"):
        grande = p == "afro"
        radio, bola = (0.74, 0.3) if grande else (0.62, 0.24)
        anillos = ((0.0, 1), (0.5, 7), (0.95, 10), (1.35, 11)) if grande else ((0.0, 1), (0.55, 6), (1.0, 9))
        for th, n in anillos:
            for j in range(n):
                ph = 2 * math.pi * j / n + th
                x, y, z = math.sin(th) * math.cos(ph), math.cos(th), math.sin(th) * math.sin(ph)
                if (z > 0.5 and y < 0.75) or (tapado and y > 0.45):
                    continue  # que no le tape la cara (ni atraviese el sombrero)
                _esfera(m, (x * radio, 2.62 + y * (radio - 0.02), z * radio - 0.05), bola, pelo, lat=5, lon=7)
    # --- Cabeza: gorra, gorro, sombrero, galera, corona
    if sombrero == "gorra":
        _esfera(m, (0, 2.68, -0.02), 0.7, ca, hasta=0.4, lat=10, lon=14)
        _elip(m, (0, 2.93, 0.52), (0.47, 0.05, 0.5), _oscurecer(ca, 0.85), planos=[((0, 0, -1), -0.4)])  # visera
        _elip(m, (0, 3.33, -0.02), (0.06, 0.04, 0.06), _oscurecer(ca, 0.8))   # botón
    elif sombrero == "gorro":
        _esfera(m, (0, 2.7, -0.02), 0.71, ca, hasta=0.45, lat=10, lon=14)
        _cilindro(m, (0, 2.82, -0.02), 0.725, 0.14, detalle, lados=14)
        _elip(m, (0, 3.43, -0.02), (0.15, 0.15, 0.15), detalle)
    elif sombrero == "sombrero":
        _elip(m, (0, 2.98, 0), (1.0, 0.04, 0.95), ca)
        _cilindro(m, (0, 2.99, 0), 0.6, 0.36, ca, lados=14, radio_arriba=0.52)
        _elip(m, (0, 3.35, 0), (0.52, 0.07, 0.52), ca)
        _cilindro(m, (0, 3.0, 0), 0.605, 0.08, "#1d1d1f", lados=14)
    elif sombrero == "galera":
        _elip(m, (0, 2.98, 0), (0.84, 0.035, 0.8), "#1d1d1f")
        _cilindro(m, (0, 2.99, 0), 0.58, 0.66, "#1d1d1f", lados=14, radio_arriba=0.6)
        _cilindro(m, (0, 3.0, 0), 0.59, 0.11, ca, lados=14)
    elif sombrero == "corona":
        oro = "#e0b23a"
        _cilindro(m, (0, 3.0, 0), 0.5, 0.2, oro, lados=14, radio_arriba=0.56)
        for j in range(8):
            ph = 2 * math.pi * j / 8
            _elip(m, (0.55 * math.cos(ph), 3.25, 0.55 * math.sin(ph)), (0.06, 0.08, 0.06), oro)
        for j, gema in enumerate((ca, "#2f7fd1", "#2e9f6b")):
            ph = math.pi / 2 + (j - 1) * 0.55
            _elip(m, (0.535 * math.cos(ph), 3.1, 0.535 * math.sin(ph)), (0.05, 0.05, 0.03), gema)
    # --- Lentes: marcos redondeados con vidrio adentro
    lentes = s["lentes"]
    if lentes in ("anteojos", "lentes3d", "sol"):
        marco = {"anteojos": "#151515", "lentes3d": "#f4f4f4", "sol": ca}[lentes]
        for x, vidrio in ((-0.22, "#d43a3a"), (0.22, "#2ec5d6")):
            _elip(m, (x, 2.62, 0.655), (0.155, 0.125, 0.025), marco)
            tono = vidrio if lentes == "lentes3d" else ("#141414" if lentes == "sol" else "#bfe3f0")
            _elip(m, (x, 2.62, 0.672), (0.125, 0.097, 0.015), tono)
            _elip(m, (x - 0.04, 2.66, 0.684), (0.035, 0.02, 0.006), "#ffffff")   # reflejo
        _caja(m, (0, 2.65, 0.66), (0.14, 0.035, 0.03), marco)
        for x in (-0.38, 0.38):
            _caja(m, (x, 2.64, 0.45), (0.03, 0.035, 0.42), marco)               # patillas
    elif lentes == "antifaz":
        _elip(m, (0, 2.64, 0.6), (0.5, 0.15, 0.08), ca)
        for x in (-0.22, 0.22):
            _elip(m, (x, 2.64, 0.665), (0.1, 0.06, 0.02), "#141414")
    # --- Extra
    e = s["extra"]
    if e == "auriculares":
        alto = 0.9 if p in ("rulos", "afro") else 0.76
        for i in range(29):
            ang = math.pi * i / 28
            _elip(m, (math.cos(ang) * 0.72, 2.6 + math.sin(ang) * alto, 0), (0.075, 0.075, 0.09), "#1d1d1f")
        for x in (-0.7, 0.7):
            _elip(m, (x, 2.52, 0), (0.1, 0.2, 0.19), ca)
            _elip(m, (x * 0.93, 2.52, 0), (0.06, 0.16, 0.15), "#1d1d1f")
    elif e == "pochoclos":
        cx = bx + 0.16
        _cilindro(m, (cx, 1.0, 0.22), 0.16, 0.34, "#f4f4f4", lados=12, radio_arriba=0.21,
                  colores_lados=["#d43a3a", "#f4f4f4"])
        for dx, dy, dz in ((0, 0.06, 0), (0.1, 0.02, 0.05), (-0.09, 0.03, 0.07), (0.06, 0.02, -0.1), (-0.07, 0.01, -0.08),
                           (0.03, 0.12, 0.04), (-0.04, 0.1, -0.03), (0.12, 0.0, -0.03), (-0.12, 0.0, 0.0)):
            _elip(m, (cx + dx, 1.38 + dy, 0.22 + dz), (0.075, 0.065, 0.075), "#f6e7b0")
    elif e == "gaseosa":
        cx = bx + 0.12
        _cilindro(m, (cx, 1.0, 0.22), 0.12, 0.38, ca, lados=12, radio_arriba=0.15, colores_lados=[ca, "#f4f4f4"])
        _elip(m, (cx, 1.38, 0.22), (0.155, 0.07, 0.155), "#f4f4f4", desde_y=1.38)   # tapa
        _cilindro(m, (cx + 0.04, 1.4, 0.22), 0.022, 0.3, "#f4f4f4", lados=6)        # sorbete
        _cilindro(m, (cx + 0.04, 1.6, 0.22), 0.024, 0.06, ca, lados=6)
    elif e == "claqueta":
        cx = bx + 0.14
        _caja(m, (cx, 1.24, 0.24), (0.05, 0.34, 0.48), "#1d1d1f")
        for i, z in enumerate((0.04, 0.14, 0.24, 0.34, 0.44)):
            _caja(m, (cx, 1.46, z), (0.06, 0.08, 0.1), "#f4f4f4" if i % 2 else "#1d1d1f")
        for z in (0.12, 0.36):
            _caja(m, (cx + 0.03, 1.22, z), (0.01, 0.025, 0.18), "#f4f4f4")          # rayitas de tiza
    elif e == "bufanda":
        _cilindro(m, (0, 1.84, 0), 0.31, 0.17, ca, lados=14, escala_z=0.85, colores_lados=[ca, detalle])
        for i in range(3):
            _caja(m, (0.14, 1.66 - i * 0.14, frente(1.6) + 0.06), (0.17, 0.14, 0.06), ca if i % 2 == 0 else detalle)
        for dx in (-0.05, 0, 0.05):
            _caja(m, (0.14 + dx, 1.33, frente(1.6) + 0.06), (0.02, 0.08, 0.02), ca)  # flecos
    elif e == "capa":
        _caja(m, (0, 1.3, -r1 * ez - 0.06), (r1 * 2.5, 1.3, 0.035), ca)
        _cilindro(m, (0, 1.88, 0), r1 * 0.98, 0.09, ca, lados=14, escala_z=ez)
        for x in (-0.14, 0.14):
            _elip(m, (x, 1.86, frente(1.86) + 0.02), (0.05, 0.05, 0.03), "#e0b23a")  # broches
    techo = {"galera": 3.68, "gorro": 3.6, "sombrero": 3.45, "corona": 3.36}.get(sombrero, 3.32)
    if not tapado:
        techo = max(techo, {"afro": 3.66, "cresta": 3.48, "rodete": 3.48, "rulos": 3.48}.get(p, 3.32))
    return Modelo(m.piezas, foto, techo)


# --- Dibujo ------------------------------------------------------------------------------------------------

_LUZ = np.array([-0.45, 0.6, 0.75]) / np.linalg.norm([-0.45, 0.6, 0.75])
_RELLENO = np.array([0.6, 0.1, 0.8]) / np.linalg.norm([0.6, 0.1, 0.8])
_MEDIO = (_LUZ + np.array([0.0, 0.0, 1.0])) / np.linalg.norm(_LUZ + np.array([0.0, 0.0, 1.0]))
# La foto de la cara va hundida en la cabeza: un disco plano un poco adentro, con su borde y su sombra
_CARA_Y, _CARA_R, _CARA_Z = -0.03, 0.42, 0.45


def _a_numpy(imagen: QImage) -> np.ndarray:
    img = imagen.convertToFormat(QImage.Format_RGB888)
    alto, ancho, linea = img.height(), img.width(), img.bytesPerLine()
    datos = np.frombuffer(img.constBits(), np.uint8, count=linea * alto).reshape(alto, linea)
    return datos[:, :ancho * 3].reshape(alto, ancho, 3).astype(np.float32) / 255


def _rotacion(giro: float, inclinacion: float) -> np.ndarray:
    cg, sg = math.cos(giro), math.sin(giro)
    ci, si = math.cos(inclinacion), math.sin(inclinacion)
    rot = np.array([[cg, 0, sg], [0, 1, 0], [-sg, 0, cg]])
    return np.array([[1, 0, 0], [0, ci, -si], [0, si, ci]]) @ rot


def _encuadre(modelo: Modelo, W: float, H: float, encuadre: str) -> tuple[float, float]:
    """Píxeles por unidad y fila de pantalla donde está y = 0: el cuerpo entero o del pecho para arriba,
    centrado y sin cortar lo que tenga en la cabeza."""
    techo = modelo.techo
    y0, y1 = (1.45, max(3.45, techo + 0.05)) if encuadre == "busto" else (-0.1, max(3.5, techo + 0.06))
    escala = min(H / (y1 - y0), W / 2.1)
    return escala, H - (H - (y1 - y0) * escala) / 2 + y0 * escala


def renderizar(modelo: Modelo, ancho: int, alto: int, giro: float = 0.0, inclinacion: float = 0.08,
               encuadre: str = "cuerpo", salto: float = 0.0, muestras: int = 2) -> QImage:
    """El muñequito en una imagen con transparencia. Proyección ortográfica, un rayo por subpíxel (muestras² por
    píxel, para que los bordes salgan suaves), profundidad por píxel, luz con brillo y contorno."""
    W, H = max(1, ancho * muestras), max(1, alto * muestras)
    rot = _rotacion(giro, inclinacion)
    inv = rot.T
    escala, cy = _encuadre(modelo, W, H, encuadre)
    ax, ay, az = inv[:, 0], inv[:, 1], inv[:, 2]  # ejes de la vista, en coordenadas del muñequito
    D = -az
    LEJOS = 20.0
    N = H * W
    prof = np.full(N, np.inf)
    norm = np.zeros((N, 3), np.float32)
    col = np.zeros((N, 3), np.float32)
    plano = np.zeros(N, bool)                    # la foto: se ilumina distinto
    for pieza in modelo.piezas:
        cv = rot @ pieza.centro
        c0 = int(max(0, math.floor((cv[0] - pieza.radio) * escala + W / 2)))
        c1 = int(min(W, math.ceil((cv[0] + pieza.radio) * escala + W / 2) + 1))
        f0 = int(max(0, math.floor(cy - (cv[1] + salto + pieza.radio) * escala)))
        f1 = int(min(H, math.ceil(cy - (cv[1] + salto - pieza.radio) * escala) + 1))
        if c0 >= c1 or f0 >= f1:
            continue
        filas, cols = np.arange(f0, f1), np.arange(c0, c1)
        X = ((cols + 0.5) - W / 2) / escala
        Y = (cy - (filas + 0.5)) / escala - salto
        O = (Y[:, None, None] * ay + X[None, :, None] * ax + LEJOS * az).reshape(-1, 3)
        t, n, costado = pieza.tocar(O, D)
        es_foto = None
        if pieza.marca == "cabeza" and modelo.foto_px is not None:
            t, n, es_foto, color_foto = _hundir_cara(pieza, modelo.foto_px, O, D, t, n)
        lugar = (filas[:, None] * W + cols[None, :]).reshape(-1)
        gana = t < prof[lugar]
        if not gana.any():
            continue
        donde = lugar[gana]
        P = O[gana] + t[gana, None] * D
        colores = np.array(pieza.color_en(P, costado[gana]), np.float32)
        if es_foto is not None:
            tipo = es_foto[gana]
            colores[tipo == 1] = color_foto[gana][tipo == 1]
            colores[tipo == 2] *= 0.62     # la pared del hueco
            plano[donde] = tipo == 1
        else:
            plano[donde] = False
        prof[donde] = t[gana]
        norm[donde] = n[gana]
        col[donde] = colores

    lleno = np.isfinite(prof)
    rgb = np.zeros((N, 3), np.float32)
    if lleno.any():
        # Luz (en la vista), solo donde hay algo: ambiente + principal + relleno + brillo + borde iluminado
        nv = norm[lleno] @ rot.T.astype(np.float32)
        nv /= np.maximum(np.linalg.norm(nv, axis=1, keepdims=True), 1e-6)
        difusa = np.clip(nv @ _LUZ.astype(np.float32), 0, 1)
        relleno = np.clip(nv @ _RELLENO.astype(np.float32), 0, 1)
        brillo = np.clip(nv @ _MEDIO.astype(np.float32), 0, 1) ** 40
        borde = np.clip(1 - nv[:, 2], 0, 1) ** 3
        foto = plano[lleno]
        luz = np.where(foto, 0.72 + 0.32 * difusa, 0.38 + 0.62 * difusa + 0.14 * relleno)
        extra = (0.12 * brillo + 0.10 * borde) * np.where(foto, 0.3, 1.0)
        rgb[lleno] = col[lleno] * luz[:, None] + extra[:, None]
    # Contorno: donde la profundidad salta (entre piezas o contra el fondo) se oscurece un poco
    p = np.where(lleno, prof, 1e3).reshape(H, W)
    salto_prof = np.zeros((H, W))
    np.maximum(salto_prof[:, 1:], np.abs(p[:, 1:] - p[:, :-1]), out=salto_prof[:, 1:])
    np.maximum(salto_prof[1:, :], np.abs(p[1:, :] - p[:-1, :]), out=salto_prof[1:, :])
    contorno = ((salto_prof > 0.12).reshape(-1)) & lleno
    rgb[contorno] *= 0.55
    np.clip(rgb, 0, 1, out=rgb)
    alfa = lleno.astype(np.float32)
    # Promedio de las muestras de cada píxel (antialias), en color premultiplicado
    pre = np.empty((N, 4), np.float32)
    pre[:, :3] = rgb[:, ::-1] * alfa[:, None]   # BGR (así lo guarda QImage en memoria)
    pre[:, 3] = alfa
    pre = pre.reshape(alto, muestras, ancho, muestras, 4).mean(axis=(1, 3))
    bgra = np.ascontiguousarray((pre * 255 + 0.5).astype(np.uint8))
    imagen = QImage(bgra.data, ancho, alto, ancho * 4, QImage.Format_ARGB32_Premultiplied)
    return imagen.copy()


def _hundir_cara(pieza: _Elipsoide, foto: np.ndarray, O, D, t, n):
    """La cara con foto: donde el rayo toca la cabeza adentro del círculo de la cara, en vez de la esfera se ve un
    disco plano más adentro (la foto) o, si se mira de costado, la pared del hueco."""
    c = pieza.centro
    tipo = np.zeros(len(O), np.int8)
    color = np.zeros((len(O), 3), np.float32)
    toca = np.isfinite(t)
    if not toca.any() or D[2] >= -1e-6:
        return t, n, tipo, color
    P = O + np.where(toca, t, 0)[:, None] * D - c
    adentro = toca & (P[:, 0] ** 2 + (P[:, 1] - _CARA_Y) ** 2 < _CARA_R ** 2) & (P[:, 2] > _CARA_Z)
    if not adentro.any():
        return t, n, tipo, color
    tp = (c[2] + _CARA_Z - O[:, 2]) / D[2]
    Q = O + tp[:, None] * D - c
    r = np.sqrt(Q[:, 0] ** 2 + (Q[:, 1] - _CARA_Y) ** 2)
    disco = adentro & (r < _CARA_R)
    pared = adentro & ~disco
    t = np.where(disco, tp, t)
    n = n.copy()
    n[disco] = (0.0, 0.0, 1.0)
    n[pared] = np.stack([-Q[pared, 0], -(Q[pared, 1] - _CARA_Y), np.full(pared.sum(), 0.25)], axis=1)
    tipo[disco], tipo[pared] = 1, 2
    if disco.any():
        alto, ancho = foto.shape[:2]
        u = np.clip(((Q[disco, 0] / _CARA_R + 1) / 2 * ancho).astype(int), 0, ancho - 1)
        v = np.clip(((1 - (Q[disco, 1] - _CARA_Y) / _CARA_R) / 2 * alto).astype(int), 0, alto - 1)
        tono = foto[v, u]
        # Sombra del borde: más fuerte del lado de la luz (arriba a la izquierda), como un hueco de verdad
        dx, dy = Q[disco, 0] + 0.07, (Q[disco, 1] - _CARA_Y) - 0.07
        hasta_borde = np.clip((_CARA_R - np.sqrt(dx * dx + dy * dy)) / 0.13, 0, 1)
        cerca = np.clip((_CARA_R - r[disco]) / 0.05, 0, 1)
        color[disco] = tono * (0.45 + 0.55 * hasta_borde ** 0.8)[:, None] * (0.6 + 0.4 * cerca)[:, None]
    return t, n, tipo, color


def dibujar(painter: QPainter, rect: QRectF, geometria: Modelo, giro: float = 0.0, inclinacion: float = 0.08,
            encuadre: str = "cuerpo", salto: float = 0.0, muestras: int | None = None):
    """Lo dibuja en el painter, a la resolución real de la pantalla."""
    dpr = painter.device().devicePixelRatioF() if painter.device() else 1.0
    ancho, alto = max(1, round(rect.width() * dpr)), max(1, round(rect.height() * dpr))
    if muestras is None:
        muestras = 3 if ancho * alto < 9000 else 2   # los chiquitos con más muestras: el borde se nota más
    img = renderizar(geometria, ancho, alto, giro, inclinacion, encuadre, salto, muestras)
    img.setDevicePixelRatio(dpr)
    painter.drawImage(rect.topLeft(), img)


def imagen(spec: dict, alto: int = 96, encuadre: str = "cuerpo", giro: float = -0.45) -> QPixmap:
    """El muñequito quieto, para las listas (amigos)."""
    ancho = alto if encuadre == "busto" else int(alto * 0.62)
    pix = QPixmap(ancho * 2, alto * 2)
    pix.setDevicePixelRatio(2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    dibujar(p, QRectF(0, 0, ancho, alto), armar(spec), giro=giro, encuadre=encuadre)
    p.end()
    return pix


class _Dibujante:
    """Dibuja los cuadros de un muñequito en un hilo aparte (numpy suelta el GIL en las cuentas pesadas), así la
    ventana nunca espera. Siempre elige el cuadro pendiente más cercano al ángulo que se está mostrando."""

    def __init__(self, avisar):
        self._avisar = avisar           # se llama desde el hilo: tiene que ser una señal (llega encolada)
        self._cond = threading.Condition()
        self._pendientes: set[int] = set()
        self._trabajo = None            # (generación, modelo, ancho, alto, dpr, encuadre, paso, muestras)
        self._cerca = 0
        self._vivo = True
        threading.Thread(target=self._bucle, daemon=True, name="munequito").start()

    def pedir(self, trabajo, claves, cerca):
        with self._cond:
            if trabajo != self._trabajo:
                self._trabajo = trabajo
                self._pendientes = set()
            self._pendientes.update(claves)
            self._cerca = cerca
            self._cond.notify()

    def ya_esta(self, clave):
        with self._cond:
            self._pendientes.discard(clave)

    def parar(self):
        with self._cond:
            self._vivo = False
            self._cond.notify()

    def _bucle(self):
        while True:
            with self._cond:
                while self._vivo and not self._pendientes:
                    self._cond.wait()
                if not self._vivo:
                    return
                clave = min(self._pendientes, key=lambda c: abs(c - self._cerca))
                self._pendientes.discard(clave)
                trabajo = self._trabajo
            gen, modelo, ancho, alto, dpr, encuadre, paso, muestras = trabajo
            try:
                img = renderizar(modelo, ancho, alto, clave * paso, encuadre=encuadre, muestras=muestras)
                img.setDevicePixelRatio(dpr)
                self._avisar(gen, clave, img)
            except RuntimeError:
                return  # el widget ya no existe


class Munequito(QWidget):
    """El muñequito girando despacio. Con arrastrable=True se lo gira con el mouse (en el editor).

    Cada ángulo se dibuja una sola vez, en otro hilo, y se guarda (el saltito es solo correr la imagen); mientras
    tanto se muestra el cuadro listo más cercano."""
    tocado = Signal()
    _listo = Signal(int, int, QImage)
    PASO = 0.03          # radianes entre cuadros guardados
    MAXIMO = 140         # cuadros guardados (los más lejanos se tiran)

    def __init__(self, spec: dict | None = None, encuadre: str = "cuerpo", arrastrable: bool = False, parent=None):
        super().__init__(parent)
        self.encuadre = encuadre
        self.arrastrable = arrastrable
        self._geo = armar(spec or PREDETERMINADO)
        self._gen = 0
        self._cuadros: dict[int, QImage] = {}
        self._t = 0.0
        self._giro_mano = 0.0
        self._clave = 0
        self._arrastre: float | None = None
        self._listo.connect(self._recibir)
        self._dibujante = _Dibujante(self._listo.emit)
        self.destroyed.connect(self._dibujante.parar)
        self._reloj = QTimer(self, interval=33)
        self._reloj.timeout.connect(self._avanzar)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) if encuadre == "busto" else None
        self.setCursor(Qt.OpenHandCursor if arrastrable else Qt.PointingHandCursor)

    def _invalidar(self):
        self._gen += 1
        self._cuadros.clear()
        self._pedir()
        self.update()

    def poner(self, spec: dict):
        self._geo = armar(spec)
        self._invalidar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._invalidar()

    def showEvent(self, evento):
        super().showEvent(evento)
        self._reloj.start()
        self._pedir()

    def hideEvent(self, evento):
        super().hideEvent(evento)
        self._reloj.stop()

    def _area(self) -> QRectF:
        m = 2 if self.height() > 40 else 0
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _trabajo(self):
        dpr = self.devicePixelRatioF()
        r = self._area()
        ancho, alto = max(1, round(r.width() * dpr)), max(1, round(r.height() * dpr))
        muestras = 3 if ancho * alto < 9000 else 2
        return (self._gen, self._geo, ancho, alto, dpr, self.encuadre, self.PASO, muestras)

    def _pedir(self):
        """Todos los ángulos del vaivén (y el de ahora, si se lo está girando con el mouse)."""
        centro = round(self._giro_mano / self.PASO)
        ancho = int(0.58 / self.PASO) + 1
        claves = {c for c in range(centro - ancho, centro + ancho + 1) if c not in self._cuadros}
        claves.add(self._clave) if self._clave not in self._cuadros else None
        if claves:
            self._dibujante.pedir(self._trabajo(), claves, self._clave)

    def _recibir(self, gen: int, clave: int, img: QImage):
        if gen != self._gen:
            return
        if len(self._cuadros) >= self.MAXIMO:
            self._cuadros.pop(max(self._cuadros, key=lambda c: abs(c - self._clave)))
        self._cuadros[clave] = img
        self.update()

    def _avanzar(self):
        self._t += 0.033
        self.update()

    def paintEvent(self, _evento):
        giro = math.sin(self._t * 0.7) * 0.55 + self._giro_mano
        salto = abs(math.sin(self._t * 2.2)) * 0.04
        clave = round(giro / self.PASO)
        if clave != self._clave:
            self._clave = clave
            if clave not in self._cuadros:
                self._pedir()
        img = self._cuadros.get(clave)
        if img is None and self._cuadros:
            img = self._cuadros[min(self._cuadros, key=lambda c: abs(c - clave))]
        if img is None:
            return  # el primer cuadro llega en un ratito
        r = self._area()
        escala, _ = _encuadre(self._geo, r.width(), r.height(), self.encuadre)
        p = QPainter(self)
        p.drawImage(r.topLeft() - QPointF(0, salto * escala), img)
        p.end()

    def mousePressEvent(self, e):
        if self.arrastrable and e.button() == Qt.LeftButton:
            self._arrastre = e.position().x()
            self.setCursor(Qt.ClosedHandCursor)
        elif e.button() == Qt.LeftButton:
            self.tocado.emit()

    def mouseMoveEvent(self, e):
        if self._arrastre is not None:
            x = e.position().x()
            self._giro_mano += (x - self._arrastre) / 60
            self._arrastre = x
            self.update()

    def mouseReleaseEvent(self, _e):
        if self._arrastre is not None:
            self._arrastre = None
            self.setCursor(Qt.OpenHandCursor)
            self._pedir()
