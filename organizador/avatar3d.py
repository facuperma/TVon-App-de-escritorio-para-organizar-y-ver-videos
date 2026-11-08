"""El muñequito 3D: el avatar del usuario, armado con piezas simples (esferas, cajas, cilindros) y dibujado píxel por píxel
(rayos contra cada pieza con numpy, sin OpenGL: anda en cualquier PC). La misma descripción (un dict chico) se usa en el foro de la revista,
que lo arma igual con three.js."""
from __future__ import annotations

import base64
import json
import math
import re

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

NOMBRE = "Protagonista"   # cómo se llama el avatar en la app («Armá tu Protagonista»)

# Cada opción: clave -> {valor: texto}. El primer valor es el predeterminado.
OPCIONES = {
    "peinado": {"corto": "Corto", "flequillo": "Flequillo", "largo": "Largo", "colita": "Colita", "trenzas": "Trenzas",
                "rulos": "Rulos", "afro": "Afro", "cresta": "Cresta", "rodete": "Rodete", "pelado": "Pelado"},
    "boca": {"sonrisa": "Sonrisa", "seria": "Seria", "sorpresa": "¡Sorpresa!", "lengua": "Sacando la lengua"},
    "barba": {"ninguna": "Sin barba", "bigote": "Bigote", "candado": "Candado", "barba": "Barba"},
    "cuerpo": {"normal": "Normal", "flaco": "Flaco", "robusto": "Robusto"},
    "ropa": {"remera": "Remera", "buzo": "Buzo con capucha", "campera": "Campera", "vestido": "Vestido"},
    "estampa": {"lisa": "Lisa", "rayas": "Rayas", "logo": "Logo en el pecho"},
    "cabeza": {"ninguno": "Nada", "gorra": "Gorra", "gorro": "Gorro con pompón", "sombrero": "Sombrero",
               "galera": "Galera de cine", "corona": "Corona"},
    "lentes": {"ninguno": "Nada", "anteojos": "Anteojos", "lentes3d": "Lentes 3D de cine", "sol": "Lentes de sol",
               "antifaz": "Antifaz"},
    "extra": {"ninguno": "Nada", "pochoclos": "Balde de pochoclos", "gaseosa": "Gaseosa", "claqueta": "Claqueta",
              "auriculares": "Auriculares", "bufanda": "Bufanda", "capa": "Capa de superhéroe"},
}
COLORES = ("piel", "pelo", "ojos", "remera", "estampa_color", "pantalon", "zapatillas", "accesorio_color")
PREDETERMINADO = {
    "piel": "#e8b896", "pelo": "#3b2a1e", "ojos": "#2b1d14",
    "remera": "#2f7fd1", "estampa_color": "#f2f2f2", "pantalon": "#2b3a55", "zapatillas": "#f2f2f2",
    "accesorio_color": "#d4513d",
    **{clave: next(iter(valores)) for clave, valores in OPCIONES.items()},
}
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


def armar(spec: dict):
    """Las piezas del muñequito según su descripción. Pies en y=0, la cabeza arriba (≈ 3,3 de alto).
    Devuelve un Modelo: las piezas y la foto de la cara (si hay), que va hundida en la cabeza."""
    s = normalizar(spec)
    m = _Escena()
    piel, pelo, ca = s["piel"], s["pelo"], s["accesorio_color"]
    foto = pixmap_de_foto(s.get("foto", ""))
    # Contextura: radio del torso (abajo, arriba), profundidad y separación de brazos y piernas
    r0, r1, ez, bx, px = {"flaco": (0.36, 0.33, 0.7, 0.48, 0.19), "robusto": (0.54, 0.47, 0.8, 0.66, 0.25)}.get(
        s["cuerpo"], (0.44, 0.4, 0.72, 0.56, 0.22))

    def frente(y):  # z del pecho a esa altura
        return (r0 + (r1 - r0) * (y - 1.0) / 0.95) * ez

    ropa, remera = s["ropa"], s["remera"]
    # Piernas y zapatillas
    for x in (-px, px):
        _caja(m, (x, 0.09, 0.06), (0.27, 0.18, 0.44), s["zapatillas"])
        _cilindro(m, (x, 0.16, 0), 0.14, 0.92, piel if ropa == "vestido" else s["pantalon"], lados=8)
    # Torso: liso o a rayas; el vestido es un cono desde las rodillas
    franjas = [remera, s["estampa_color"]] * 3 if s["estampa"] == "rayas" else [remera]
    if ropa == "vestido":
        _tronco(m, 0.55, 1.95, 0.66, r1, franjas[:-1] if len(franjas) > 1 else franjas, ez)
    else:
        _tronco(m, 1.0, 1.95, r0, r1, franjas, ez)
    if s["estampa"] == "logo":
        _caja(m, (0, 1.58, frente(1.58) + 0.01), (0.34, 0.26, 0.03), s["estampa_color"])
        _caja(m, (0, 1.58, frente(1.58) + 0.03), (0.22, 0.05, 0.02), remera)
    if ropa == "campera":
        # Abierta: se ve la remera de abajo (color de la estampa) en una franja del frente, y el cuello
        _caja(m, (0, 1.47, frente(1.47) + 0.005), (0.2, 0.9, 0.03), s["estampa_color"])
        for x in (-0.15, 0.15):
            _caja(m, (x, 1.9, frente(1.9) - 0.03), (0.2, 0.1, 0.12), remera)
    elif ropa == "buzo":
        _esfera(m, (0, 2.0, -0.3), 0.36, remera, escala=(1.1, 0.75, 0.7), lat=6, lon=10)  # capucha
        _caja(m, (0, 1.22, frente(1.22) + 0.01), (0.46, 0.2, 0.03), remera)              # bolsillo
        for x in (-0.09, 0.09):
            _caja(m, (x, 1.74, frente(1.74) + 0.02), (0.025, 0.24, 0.02), s["estampa_color"])  # cordones
    # Brazos: manga corta con remera y vestido; larga con buzo y campera
    larga = ropa in ("buzo", "campera")
    for x in (-bx, bx):
        if larga:
            _cilindro(m, (x, 1.22, 0), 0.12, 0.66, remera, lados=8)
        else:
            _cilindro(m, (x, 1.22, 0), 0.1, 0.4, piel, lados=8)
            _cilindro(m, (x, 1.6, 0), 0.125, 0.28, remera, lados=8)
        _esfera(m, (x, 1.14, 0), 0.13, piel, lat=6, lon=8)
    _cilindro(m, (0, 1.9, 0), 0.13, 0.2, piel, lados=8)
    # Cabeza (grande, estilo muñequito)
    _esfera(m, (0, 2.58, 0), 0.64, piel, lat=10, lon=14, marca="cabeza")
    if foto is None:
        for x in (-0.22, 0.22):
            _esfera(m, (x, 2.62, 0.55), 0.085, s["ojos"], escala=(1, 1.25, 0.55), lat=6, lon=8)
            _esfera(m, (x + 0.03, 2.66, 0.6), 0.025, "#ffffff", lat=4, lon=6)
        boca = s["boca"]
        if boca in ("sonrisa", "lengua"):
            for dx, y in ((-0.11, 2.385), (-0.04, 2.355), (0.04, 2.355), (0.11, 2.385)):
                _caja(m, (dx, y, 0.6), (0.085, 0.04, 0.05), "#7a3b2e")
            if boca == "lengua":
                _esfera(m, (0.02, 2.31, 0.6), 0.06, "#e8707a", escala=(1, 0.8, 0.5), lat=4, lon=6)
        elif boca == "sorpresa":
            _esfera(m, (0, 2.36, 0.59), 0.07, "#5a2a20", escala=(1, 1.25, 0.45), lat=5, lon=8)
        else:
            _caja(m, (0, 2.36, 0.6), (0.2, 0.045, 0.05), "#7a3b2e")
    # Desde acá, lo que va sobre la cara (encima de la foto): barba, pelo de arriba, sombreros, lentes
    m.encima = True
    # Barba (del color del pelo)
    b = s["barba"]
    if b in ("bigote", "candado"):
        _caja(m, (0, 2.43, 0.6), (0.32, 0.07, 0.07), pelo)
    if b == "candado":
        _caja(m, (0, 2.2, 0.5), (0.2, 0.14, 0.14), pelo)
    elif b == "barba":
        _esfera(m, (0, 2.3, 0.2), 0.5, pelo, escala=(1.06, 0.62, 0.86), lat=7, lon=12)
    # Pelo. Con algo en la cabeza, lo que sobresale arriba (cresta, rodete, afro) no se ve
    p, sombrero = s["peinado"], s["cabeza"]
    tapado = sombrero != "ninguno"
    if p in ("corto", "flequillo", "largo", "rodete", "cresta", "colita", "trenzas") or (tapado and p != "pelado"):
        _esfera(m, (0, 2.62, -0.03), 0.68, pelo, hasta=0.42, lat=10, lon=14)
        if p != "largo":
            # La nuca: el pelo baja por atrás y por los costados (si no, de espaldas parecía un casquito)
            nuca = _Elipsoide((0, 2.6, -0.04), (0.67, 0.67, 0.67), pelo, desde_y=2.18)
            nuca.planos.append((np.array([0.0, 0.0, 1.0]), -0.06))
            m.piezas.append(nuca)
    if p == "flequillo":
        _esfera(m, (0.08, 2.98, 0.4), 0.42, pelo, escala=(1.15, 0.34, 0.55), lat=6, lon=10)
    m.encima = p not in ("largo", "colita", "trenzas", "rodete", "rulos", "afro")  # lo de atrás y los costados, no
    if p == "largo":
        # Pelo largo atrás: una pieza redondeada (con una caja, la cabeza se veía a través desde atrás)
        _esfera(m, (0, 2.3, -0.2), 0.7, pelo, escala=(1.0, 1.3, 0.75), lat=9, lon=14)
        for x in (-0.58, 0.58):
            _esfera(m, (x, 2.3, 0.05), 0.2, pelo, escala=(0.6, 2.6, 1.2), lat=6, lon=8)
    elif p == "colita":
        _esfera(m, (0, 2.78, -0.68), 0.16, pelo, lat=5, lon=8)
        _esfera(m, (0, 2.42, -0.8), 0.15, pelo, escala=(1, 1.9, 1), lat=6, lon=8)
    elif p == "trenzas":
        for x in (-0.56, 0.56):
            for i in range(5):
                _esfera(m, (x * (1 - i * 0.04), 2.32 - i * 0.17, -0.02), 0.11 - i * 0.008, pelo, lat=4, lon=6)
            _esfera(m, (x * 0.84, 1.55, -0.02), 0.05, ca, lat=4, lon=6)  # gomita
    elif p == "rodete" and not tapado:
        _esfera(m, (0, 3.22, -0.32), 0.24, pelo, lat=6, lon=8)
    elif p == "cresta" and not tapado:
        for i, z in enumerate((0.36, 0.1, -0.16, -0.42)):
            _caja(m, (0, 3.3 - abs(i - 1.5) * 0.06, z), (0.14, 0.32, 0.24), pelo)
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
    m.encima = True
    # Cabeza: gorra, gorro, sombrero, galera, corona
    if sombrero == "gorra":
        _esfera(m, (0, 2.68, -0.02), 0.7, ca, hasta=0.4, lat=10, lon=14)
        _caja(m, (0, 2.96, 0.62), (0.8, 0.05, 0.5), ca)
    elif sombrero == "gorro":
        _esfera(m, (0, 2.7, -0.02), 0.71, ca, hasta=0.45, lat=10, lon=14)
        _cilindro(m, (0, 2.84, -0.02), 0.71, 0.12, s["estampa_color"], lados=14)
        _esfera(m, (0, 3.42, -0.02), 0.14, s["estampa_color"], lat=5, lon=8)
    elif sombrero == "sombrero":
        _cilindro(m, (0, 2.96, 0), 1.0, 0.04, ca, lados=16)
        _cilindro(m, (0, 2.99, 0), 0.6, 0.36, ca, lados=14, radio_arriba=0.54)
        _cilindro(m, (0, 3.0, 0), 0.605, 0.08, "#1d1d1f", lados=14)
    elif sombrero == "galera":
        _cilindro(m, (0, 2.96, 0), 0.82, 0.04, "#1d1d1f", lados=16)
        _cilindro(m, (0, 2.99, 0), 0.58, 0.66, "#1d1d1f", lados=14, radio_arriba=0.6)
        _cilindro(m, (0, 3.0, 0), 0.585, 0.11, ca, lados=14)
    elif sombrero == "corona":
        _cilindro(m, (0, 3.0, 0), 0.5, 0.2, "#e0b23a", lados=12, radio_arriba=0.56)
        for j in range(6):
            ph = 2 * math.pi * j / 6
            _esfera(m, (0.55 * math.cos(ph), 3.24, 0.55 * math.sin(ph)), 0.065, "#e0b23a", lat=4, lon=6)
        _esfera(m, (0, 3.1, 0.52), 0.06, ca, lat=4, lon=6)
    # Lentes
    lentes = s["lentes"]
    if lentes in ("anteojos", "lentes3d", "sol"):
        marco = {"anteojos": "#151515", "lentes3d": "#f4f4f4", "sol": ca}[lentes]
        for x, vidrio in ((-0.22, "#d43a3a"), (0.22, "#2ec5d6")):
            _caja(m, (x, 2.62, 0.66), (0.3, 0.24, 0.03), marco)
            if lentes == "lentes3d":
                _caja(m, (x, 2.62, 0.685), (0.24, 0.18, 0.02), vidrio)
            elif lentes == "sol":
                _caja(m, (x, 2.61, 0.685), (0.26, 0.19, 0.02), "#141414")
        _caja(m, (0, 2.66, 0.66), (0.16, 0.04, 0.03), marco)
    elif lentes == "antifaz":
        _caja(m, (0, 2.64, 0.64), (0.9, 0.26, 0.05), ca)
        for x in (-0.22, 0.22):
            _caja(m, (x, 2.64, 0.67), (0.2, 0.12, 0.02), "#141414")
    m.encima = False
    # Extra
    e = s["extra"]
    if e == "auriculares":
        pasos = 9
        alto = 0.9 if p in ("rulos", "afro") else 0.76
        m.encima = True  # la vincha pasa por arriba de la cabeza; los parlantes de los costados, no
        for i in range(pasos):
            ang = math.pi * i / (pasos - 1)
            _caja(m, (math.cos(ang) * 0.74, 2.6 + math.sin(ang) * alto, 0), (0.13, 0.13, 0.16), "#1d1d1f")
        m.encima = False
        for x in (-0.7, 0.7):
            _cilindro(m, (x - 0.08 if x < 0 else x - 0.1, 2.5, 0), 0.2, 0.18, ca, lados=10)
    elif e == "pochoclos":
        _cilindro(m, (bx + 0.16, 1.0, 0.22), 0.16, 0.34, "#f4f4f4", lados=10, radio_arriba=0.2,
                  colores_lados=["#d43a3a", "#f4f4f4"])
        for dx, dz in ((0, 0), (0.09, 0.05), (-0.08, 0.06), (0.05, -0.08), (-0.06, -0.06)):
            _esfera(m, (bx + 0.16 + dx, 1.38, 0.22 + dz), 0.075, "#f6e7b0", lat=4, lon=6)
    elif e == "gaseosa":
        _cilindro(m, (bx + 0.12, 1.0, 0.22), 0.12, 0.38, ca, lados=10, radio_arriba=0.15,
                  colores_lados=[ca, "#f4f4f4"])
        _cilindro(m, (bx + 0.12, 1.38, 0.22), 0.155, 0.04, "#f4f4f4", lados=10)
        _caja(m, (bx + 0.15, 1.52, 0.22), (0.03, 0.26, 0.03), "#f4f4f4")
    elif e == "claqueta":
        cx = bx + 0.14
        _caja(m, (cx, 1.25, 0.24), (0.06, 0.34, 0.46), "#1d1d1f")
        _caja(m, (cx, 1.47, 0.24), (0.07, 0.08, 0.48), "#f4f4f4")
        for z in (0.06, 0.24, 0.42):
            _caja(m, (cx, 1.47, z), (0.075, 0.085, 0.07), "#1d1d1f")
    elif e == "bufanda":
        _cilindro(m, (0, 1.86, 0), 0.3, 0.16, ca, lados=12, escala_z=0.85)
        _caja(m, (0.14, 1.55, frente(1.55) + 0.05), (0.16, 0.42, 0.06), ca)
    elif e == "capa":
        _caja(m, (0, 1.32, -r1 * ez - 0.06), (r1 * 2.4, 1.25, 0.04), ca)
        _cilindro(m, (0, 1.9, 0), r1 * 0.95, 0.07, ca, lados=12, escala_z=ez)
    techo = {"galera": 3.68, "gorro": 3.58, "sombrero": 3.38, "corona": 3.33}.get(sombrero, 3.32)
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
        brillo = np.clip(nv @ _MEDIO.astype(np.float32), 0, 1) ** 28
        borde = np.clip(1 - nv[:, 2], 0, 1) ** 3
        foto = plano[lleno]
        luz = np.where(foto, 0.72 + 0.32 * difusa, 0.38 + 0.62 * difusa + 0.14 * relleno)
        extra = (0.22 * brillo + 0.10 * borde) * np.where(foto, 0.3, 1.0)
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


class Munequito(QWidget):
    """El muñequito girando despacio. Con arrastrable=True se lo gira con el mouse (en el editor).

    Cada ángulo se dibuja una sola vez y se guarda (el saltito es solo correr la imagen): la primera vez rápido y,
    con el programa tranquilo, se lo vuelve a dibujar con bordes suaves."""
    tocado = Signal()
    PASO = 0.05          # radianes entre cuadros guardados
    MAXIMO = 90          # cuadros guardados (los más viejos se tiran)

    def __init__(self, spec: dict | None = None, encuadre: str = "cuerpo", arrastrable: bool = False, parent=None):
        super().__init__(parent)
        self.encuadre = encuadre
        self.arrastrable = arrastrable
        self._geo = armar(spec or PREDETERMINADO)
        self._cuadros: dict[int, tuple[QImage, bool]] = {}
        self._t = 0.0
        self._giro_mano = 0.0
        self._clave = 0
        self._arrastre: float | None = None
        self._reloj = QTimer(self, interval=60)
        self._reloj.timeout.connect(self._avanzar)
        self._pulir = QTimer(self, interval=120)
        self._pulir.timeout.connect(self._pulir_uno)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) if encuadre == "busto" else None
        self.setCursor(Qt.OpenHandCursor if arrastrable else Qt.PointingHandCursor)

    def poner(self, spec: dict):
        self._geo = armar(spec)
        self._cuadros.clear()
        self.update()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._cuadros.clear()

    def showEvent(self, evento):
        super().showEvent(evento)
        self._reloj.start()
        self._pulir.start()

    def hideEvent(self, evento):
        super().hideEvent(evento)
        self._reloj.stop()
        self._pulir.stop()

    def _avanzar(self):
        self._t += 0.06
        self.update()

    def _area(self) -> QRectF:
        m = 2 if self.height() > 40 else 0
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _cuadro(self, clave: int, fino: bool) -> QImage:
        dpr = self.devicePixelRatioF()
        r = self._area()
        ancho, alto = max(1, round(r.width() * dpr)), max(1, round(r.height() * dpr))
        chico = ancho * alto < 60000
        muestras = (3 if ancho * alto < 9000 else 2) if (fino or chico) else 1
        img = renderizar(self._geo, ancho, alto, clave * self.PASO, encuadre=self.encuadre, muestras=muestras)
        img.setDevicePixelRatio(dpr)
        if len(self._cuadros) >= self.MAXIMO:
            self._cuadros.pop(next(iter(self._cuadros)))
        self._cuadros[clave] = (img, fino or chico)
        return img

    def _pulir_uno(self):
        """Vuelve a dibujar con bordes suaves el cuadro provisorio más cercano al ángulo de ahora."""
        if self._arrastre is not None:
            return
        pendientes = [c for c, (_img, fino) in self._cuadros.items() if not fino]
        if pendientes:
            self._cuadro(min(pendientes, key=lambda c: abs(c - self._clave)), True)

    def paintEvent(self, _evento):
        giro = math.sin(self._t * 0.7) * 0.55 + self._giro_mano
        salto = abs(math.sin(self._t * 2.2)) * 0.04
        self._clave = round(giro / self.PASO)
        guardado = self._cuadros.get(self._clave)
        img = guardado[0] if guardado else self._cuadro(self._clave, False)
        r = self._area()
        escala, _ = _encuadre(self._geo, r.width(), r.height(), self.encuadre)
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
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
