"""La mascota de BiriBiri: perros y gatos de distintas razas y colores, parados a su lado.

Se modela igual que el muñequito (volúmenes que se funden, ver modelado.py) y se parte en tres piezas: el cuerpo, la
cabeza (que se mueve sola: asiente, se inclina, come) y la cola (que mueve). Mira hacia +z, el piso es y = 0 y mide
unos 0,45 de alto (BiriBiri mide 1)."""
from __future__ import annotations

import math

import numpy as np

from .modelado import capsula, cortar, elipsoide, esfera, restar, unir

# Colores de cada raza: pelaje y color secundario (orejas, manchas, antifaz, puntas…). Son los de partida; se cambian
RAZAS: dict[str, dict] = {
    "labrador": {"tipo": "perro", "nombre": "Perro labrador", "c1": "#e0b060", "c2": "#c99a4a"},
    "salchicha": {"tipo": "perro", "nombre": "Perro salchicha", "c1": "#8a4b2a", "c2": "#6d3a1f"},
    "pug": {"tipo": "perro", "nombre": "Perro pug", "c1": "#d9b98a", "c2": "#2b2522"},
    "husky": {"tipo": "perro", "nombre": "Perro husky", "c1": "#7b8794", "c2": "#f4f4f6"},
    "dalmata": {"tipo": "perro", "nombre": "Perro dálmata", "c1": "#f7f5f0", "c2": "#2a2a2e"},
    "caniche": {"tipo": "perro", "nombre": "Perro caniche", "c1": "#f2ece2", "c2": "#e4d6c0"},
    "atigrado": {"tipo": "gato", "nombre": "Gato atigrado", "c1": "#8f7a62", "c2": "#4b3d30"},
    "siames": {"tipo": "gato", "nombre": "Gato siamés", "c1": "#efe3cc", "c2": "#4a392e"},
    "negro": {"tipo": "gato", "nombre": "Gato negro", "c1": "#25252b", "c2": "#3a3a42"},
    "naranja": {"tipo": "gato", "nombre": "Gato naranja", "c1": "#e8883a", "c2": "#f6e6cf"},
    "persa": {"tipo": "gato", "nombre": "Gato persa", "c1": "#f2eee8", "c2": "#e2d6c8"},
    "manchado": {"tipo": "gato", "nombre": "Gato manchado", "c1": "#f6f2ec", "c2": "#e08a3a"},
}
ETIQUETAS = {"ninguna": "Sin mascota", **{k: v["nombre"] for k, v in RAZAS.items()}}

# Colores para elegir (pelaje y secundario)
PALETA_PELAJE = ["#f7f5f0", "#e0b060", "#8a4b2a", "#3b2a1e", "#25252b", "#7b8794", "#e8883a", "#d9b98a", "#efe3cc", "#b0a8a0"]
PALETA_SECUNDARIO = ["#ffffff", "#2a2a2e", "#c99a4a", "#6d3a1f", "#e08a3a", "#4a392e", "#e4d6c0", "#d28a9a"]


def tipo(raza: str) -> str:
    return RAZAS.get(raza, {}).get("tipo", "")


def colores(raza: str) -> tuple[str, str]:
    r = RAZAS[raza]
    return r["c1"], r["c2"]


def _forma(raza: str) -> dict:
    """Medidas de la raza. y = altura, z = largo; todo chiquito y cabezón."""
    perro = tipo(raza) == "perro"
    g = dict(H=0.11, rx=0.105, ry=0.095, L=0.16, hr=0.105, snx=0.048, sny=0.038, snz=0.06, pata=0.027, cola_largo=0.12,
             orejas="caidas")
    if not perro:
        g.update(H=0.095, rx=0.095, ry=0.09, L=0.12, hr=0.124, snx=0.036, sny=0.028, snz=0.04, pata=0.024, cola_largo=0.17,
                 orejas="puntas")
    if raza == "salchicha":
        g.update(H=0.055, rx=0.082, ry=0.075, L=0.27, hr=0.095, snx=0.04, sny=0.034, snz=0.085, pata=0.026, cola_largo=0.14)
    elif raza == "pug":
        g.update(H=0.09, rx=0.11, ry=0.1, L=0.12, hr=0.118, snx=0.04, sny=0.03, snz=0.03, pata=0.028, cola_largo=0.05)
    elif raza == "husky":
        g.update(orejas="puntas", cola_largo=0.16)
    elif raza == "caniche":
        g.update(H=0.12, rx=0.09, ry=0.085, hr=0.095, snx=0.036, sny=0.032, snz=0.07, pata=0.022)
    elif raza == "persa":
        g.update(rx=0.105, ry=0.095, hr=0.13, snx=0.036, sny=0.026, snz=0.02, cola_largo=0.16)
    g["cy"] = g["H"] + g["ry"] * 0.7
    g["cuello"] = (0.0, g["cy"] + g["ry"] * 0.55, g["L"] * 0.62)
    g["cabeza"] = (0.0, g["cuello"][1] + 0.07, g["cuello"][2] + 0.05)
    g["rabo"] = (0.0, g["cy"] + g["ry"] * 0.3, -g["L"] * 0.92)
    return g


def pivotes(raza: str) -> dict:
    """Dónde gira la cabeza (el cuello) y la cola (la base), para la escena."""
    g = _forma(raza)
    return {"cuelloY": g["cuello"][1], "cuelloZ": g["cuello"][2], "colaY": g["rabo"][1], "colaZ": g["rabo"][2]}


def _suma(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _union(fs, k=0.0):
    def f(p):
        d = None
        for g in fs:
            e = g(p)
            d = e if d is None else unir(d, e, k)
        return d
    return f


def _sobre(forma, centro, radio, grosor=0.004):
    """Una mancha: la forma pegada a la superficie de una esfera (como una calcomanía)."""
    return lambda p: np.maximum(forma(p), esfera(p, centro, radio + grosor))


def armar(raza: str, c1: str, c2: str, col, osc) -> dict[str, list]:
    """{"mascota": [...], "mascota_cabeza": [...], "mascota_cola": [...]}: piezas (nombre, función, caja, material).
    col(hex) da el color para glTF y osc(hex, f) lo oscurece."""
    if raza not in RAZAS:
        return {}
    g = _forma(raza)
    perro = tipo(raza) == "perro"
    cy, H, rx, ry, L, hr = g["cy"], g["H"], g["rx"], g["ry"], g["L"], g["hr"]
    hc = g["cabeza"]
    pelaje = {"color": col(c1), "rugosidad": 0.92}
    sec = {"color": col(c2), "rugosidad": 0.92}
    oscuro = {"color": col("#241a1a"), "rugosidad": 0.35}
    nariz = {"color": col("#2a1d1d" if perro else "#e58a99"), "rugosidad": 0.3}
    blanco = {"color": (1.0, 1.0, 1.0), "rugosidad": 0.1}
    ojo = {"color": col("#2b1b12" if perro else "#c9d94a"), "rugosidad": 0.15}
    orejas_sec = raza in ("labrador", "salchicha", "pug", "dalmata", "siames")
    cola_sec = raza == "siames"
    caja_cuerpo = ((-0.24, -0.01, -L - 0.2), (0.24, cy + ry + 0.14, L + 0.2))
    caja_cab = ((-0.24, hc[1] - 0.17, hc[2] - 0.2), (0.24, hc[1] + 0.24, hc[2] + 0.28))
    rabo = g["rabo"]
    sn_cc = (hc[0], hc[1] - hr * 0.3, hc[2] + hr * 0.78)
    caja_cara = ((-0.16, hc[1] - 0.12, hc[2] + 0.02), (0.16, hc[1] + 0.12, hc[2] + hr + 0.12))
    caja_cola = ((-0.14, rabo[1] - 0.1, rabo[2] - g["cola_largo"] - 0.16), (0.14, rabo[1] + g["cola_largo"] + 0.22, rabo[2] + 0.1))

    # ---------------- Cuerpo: tronco, pecho, patas y patitas
    patas_x, pata_z = rx * 0.55, (L * 0.58, -L * 0.62)

    def cuerpo(p):
        d = elipsoide(p, (0, cy, 0), (rx, ry, L))
        d = unir(d, elipsoide(p, (0, cy - ry * 0.25, L * 0.45), (rx * 0.92, ry * 0.9, L * 0.55)), 0.04)
        for sx in (-1, 1):
            for z in pata_z:
                pata = capsula(p, (sx * patas_x, H + 0.02, z), (sx * patas_x, 0.02, z), g["pata"] * 1.05, g["pata"])
                pata = unir(pata, elipsoide(p, (sx * patas_x, 0.016, z + 0.01), (g["pata"] * 1.15, 0.018, g["pata"] * 1.4)), 0.02)
                d = unir(d, pata, 0.03)
        if raza == "caniche":                       # bolitas de pelo en los tobillos y en el pecho
            for sx in (-1, 1):
                for z in pata_z:
                    d = unir(d, esfera(p, (sx * patas_x, 0.045, z), 0.034), 0.02)
            d = unir(d, esfera(p, (0, cy - 0.01, L * 0.7), 0.075), 0.04)
        if raza == "persa":                         # el collar de pelo
            d = unir(d, esfera(p, (0, g["cuello"][1] - 0.02, g["cuello"][2] - 0.02), 0.09), 0.05)
        return d

    piezas_cuerpo = [("m_cuerpo", cuerpo, caja_cuerpo, pelaje)]

    # Dibujos del pelaje: manchas (dálmata, manchado), rayas (atigrado), patitas oscuras (siamés), pechera (naranja)
    forma_c = lambda p: elipsoide(p, (0, cy, 0), (rx + 0.004, ry + 0.004, L + 0.004))  # noqa: E731
    if raza == "dalmata":
        puntos = [(0.09, cy + 0.03, 0.06, 0.026), (-0.09, cy - 0.02, -0.04, 0.03), (0.0, cy + 0.085, -0.05, 0.028),
                  (0.07, cy - 0.04, -0.1, 0.022), (-0.06, cy + 0.06, 0.1, 0.02), (0.1, cy + 0.0, -0.01, 0.016),
                  (-0.1, cy + 0.04, 0.03, 0.016), (0.03, cy + 0.09, 0.08, 0.016)]
        manchas = _union([(lambda p, c=c: np.maximum(esfera(p, c[:3], c[3]), forma_c(p))) for c in puntos])
        piezas_cuerpo.append(("m_manchas", manchas, caja_cuerpo, sec))
    elif raza == "manchado":
        puntos = [(0.085, cy + 0.04, 0.02, 0.06), (-0.07, cy + 0.05, -0.08, 0.05), (0.0, cy + 0.07, 0.12, 0.035)]
        manchas = _union([(lambda p, c=c: np.maximum(esfera(p, c[:3], c[3]), forma_c(p))) for c in puntos])
        piezas_cuerpo.append(("m_manchas", manchas, caja_cuerpo, sec))
    elif raza == "atigrado":
        def rayas(p):
            d = None
            for z in (-0.1, -0.05, 0.0, 0.05, 0.1):
                s = np.maximum(np.maximum(np.abs(p[..., 2] - z) - 0.011, p[..., 1] - (cy + 0.02)), forma_c(p))
                d = s if d is None else np.minimum(d, s)
            return d
        piezas_cuerpo.append(("m_manchas", rayas, caja_cuerpo, sec))
    elif raza == "siames":
        def patitas(p):
            d = None
            for sx in (-1, 1):
                for z in pata_z:
                    s = capsula(p, (sx * patas_x, 0.06, z), (sx * patas_x, 0.0, z), g["pata"] * 1.08)
                    d = s if d is None else np.minimum(d, s)
            return d
        piezas_cuerpo.append(("m_manchas", patitas, caja_cuerpo, sec))
    elif raza == "naranja":
        piezas_cuerpo.append(("m_manchas", lambda p: np.maximum(elipsoide(p, (0, cy - ry * 0.55, L * 0.5), (rx * 0.7, ry * 0.5, L * 0.5)),
                                                                forma_c(p)), caja_cuerpo, sec))

    # ---------------- Cabeza
    sn_c = (hc[0], hc[1] - hr * 0.3, hc[2] + hr * (0.78 if perro else 0.9))

    def cabeza(p):
        d = esfera(p, hc, hr)
        d = unir(d, elipsoide(p, sn_c, (g["snx"], g["sny"], g["snz"])), 0.035)
        d = unir(d, elipsoide(p, (hc[0], hc[1] - hr * 0.25, hc[2] + hr * 0.15), (hr * 0.98, hr * 0.8, hr * 0.9)), 0.03)
        if raza == "caniche":
            d = unir(d, esfera(p, (hc[0], hc[1] + hr * 0.95, hc[2] - 0.01), 0.062), 0.04)    # el copete
        if raza == "persa":
            d = unir(d, esfera(p, (hc[0], hc[1] - 0.02, hc[2] - 0.02), hr * 1.1), 0.04)
        return d

    def _z_cara(x, y):
        """Hasta dónde llega la cara (hocico o cabeza) hacia adelante en (x, y)."""
        zs = sn_c[2] + g["snz"] * math.sqrt(max(0.0, 1 - (x / g["snx"]) ** 2 - ((y - sn_c[1]) / g["sny"]) ** 2))
        zc = hc[2] + math.sqrt(max(0.0, hr * hr - x * x - (y - hc[1]) ** 2))
        return max(zs, zc)

    def _ruta_boca(r_extra=0.0, hondo=0.0):
        y0 = sn_c[1] - 0.004
        trazos = [[(0.0, y0), (0.0, y0 - 0.011)],
                  [(0.0, y0 - 0.011), (-0.011, y0 - 0.022), (-0.024, y0 - 0.013)],
                  [(0.0, y0 - 0.011), (0.011, y0 - 0.022), (0.024, y0 - 0.013)]]
        return trazos, r_extra, hondo

    def surco(p, radio, hondo):
        d = None
        for tr in _ruta_boca()[0]:
            pts = [(x, y, _z_cara(x, y) - hondo) for x, y in ([tr[0]] + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(tr, tr[1:])] + [tr[-1]])]
            for a, b in zip(pts, pts[1:]):
                c = capsula(p, a, b, radio)
                d = c if d is None else np.minimum(d, c)
        return d

    cabeza_base = cabeza
    if not perro:
        cabeza = lambda p: restar(cabeza_base(p), surco(p, 0.0042, 0.0012))      # noqa: E731

    piezas_cab = [("m_cabeza", cabeza, caja_cab, pelaje)]
    if not perro:
        piezas_cab.append(("m_boca", lambda p: surco(p, 0.0027, 0.0035), caja_cara, {"color": col("#6a2f3a"), "rugosidad": 0.5}))
        piezas_cab.append(("m_rubor", lambda p: unir(elipsoide(p, (-hr * 0.78, hc[1] - hr * 0.2, hc[2] + hr * 0.5), (0.026, 0.016, 0.014)),
                                                      elipsoide(p, (hr * 0.78, hc[1] - hr * 0.2, hc[2] + hr * 0.5), (0.026, 0.016, 0.014))),
                           caja_cab, {"color": col("#ee9aa6"), "rugosidad": 0.8}))
    if raza in ("husky", "pug", "siames"):
        # Antifaz / hocico: pegado a la cabeza
        if raza == "husky":
            mascara = lambda p: np.maximum(elipsoide(p, (hc[0], hc[1] - hr * 0.3, hc[2] + hr * 0.5), (hr * 0.9, hr * 0.75, hr * 0.62)),  # noqa: E731
                                           cabeza(p) - (-0.0) - 0.0035)
        elif raza == "pug":
            mascara = lambda p: np.maximum(elipsoide(p, (hc[0], hc[1] - hr * 0.28, hc[2] + hr * 0.62), (hr * 0.78, hr * 0.62, hr * 0.5)),  # noqa: E731
                                           cabeza(p) - 0.0035)
        else:
            mascara = lambda p: np.maximum(elipsoide(p, (hc[0], hc[1] - hr * 0.22, hc[2] + hr * 0.62), (hr * 0.7, hr * 0.62, hr * 0.5)),  # noqa: E731
                                           cabeza(p) - 0.0035)
        piezas_cab.append(("m_mascara", mascara, caja_cab, sec))
    if raza == "atigrado":
        def frente(p):
            d = None
            for dx in (-0.03, 0.0, 0.03):
                s = np.maximum(capsula(p, (hc[0] + dx, hc[1] + hr * 0.62, hc[2] + hr * 0.5), (hc[0] + dx, hc[1] + hr * 0.95, hc[2] + hr * 0.2), 0.007),
                               cabeza(p) - 0.0035)
                d = s if d is None else np.minimum(d, s)
            return d
        piezas_cab.append(("m_manchas", frente, caja_cab, sec))
    if raza == "naranja":
        piezas_cab.append(("m_manchas", lambda p: np.maximum(elipsoide(p, (hc[0], hc[1] - hr * 0.5, hc[2] + hr * 0.7), (0.045, 0.04, 0.05)),
                                                             cabeza(p) - 0.0035), caja_cab, sec))

    # Orejas
    def orejas(p):
        d = None
        for sx in (-1, 1):
            if raza == "caniche":
                o = esfera(p, (hc[0] + sx * hr * 0.98, hc[1] - 0.005, hc[2] - 0.005), 0.05)
                o = unir(o, esfera(p, (hc[0] + sx * hr * 1.0, hc[1] - 0.05, hc[2] - 0.005), 0.044), 0.03)
            elif g["orejas"] == "caidas":
                largo = 0.1 if raza == "salchicha" else (0.04 if raza == "pug" else 0.065)
                o = capsula(p, (hc[0] + sx * hr * 0.78, hc[1] + hr * 0.7, hc[2] - 0.01),
                            (hc[0] + sx * hr * 1.15, hc[1] + hr * 0.7 - largo, hc[2] - 0.01), 0.032, 0.024)
            else:
                alto = 0.085 if raza != "persa" else 0.06
                o = capsula(p, (hc[0] + sx * hr * 0.6, hc[1] + hr * 0.8, hc[2] - 0.005),
                            (hc[0] + sx * hr * 0.8, hc[1] + hr * 0.8 + alto, hc[2] - 0.01), 0.052, 0.016)
            d = o if d is None else np.minimum(d, o)
        return d

    piezas_cab.append(("m_orejas", orejas, caja_cab, sec if orejas_sec else pelaje))
    # Ojos, brillitos, nariz
    sep = hr * (0.45 if perro else 0.5)
    ey, ez = hc[1] + hr * 0.2, hc[2] + hr * 0.84
    re = 0.021 if perro else 0.03
    piezas_cab.append(("m_ojos", lambda p: unir(esfera(p, (-sep, ey, ez), re), esfera(p, (sep, ey, ez), re)), caja_cara,
                       oscuro if perro else ojo))
    if not perro:
        piezas_cab.append(("m_pupilas", lambda p: unir(elipsoide(p, (-sep, ey, ez + re * 0.9), (re * 0.3, re * 0.72, re * 0.14)),
                                                       elipsoide(p, (sep, ey, ez + re * 0.9), (re * 0.3, re * 0.72, re * 0.14))),
                           caja_cara, oscuro))
    rb = 0.0068 if perro else 0.0105
    hx, hy, hz = re * 0.34, re * 0.44, re * 0.82         # el brillito: arriba a la derecha, sobre la superficie del ojo
    piezas_cab.append(("m_brillo", lambda p: unir(esfera(p, (-sep + hx, ey + hy, ez + hz), rb), esfera(p, (sep + hx, ey + hy, ez + hz), rb)),
                       caja_cara, blanco))
    nz = sn_c[2] + g["snz"] * 0.85
    piezas_cab.append(("m_nariz", lambda p: elipsoide(p, (0, sn_c[1] + g["sny"] * 0.55, nz), (0.022 if perro else 0.013, 0.016 if perro else 0.01, 0.017 if perro else 0.01)),
                       caja_cara, nariz))
    if raza in ("labrador", "dalmata", "husky", "caniche"):
        piezas_cab.append(("m_lengua", lambda p: elipsoide(p, (0, sn_c[1] - g["sny"] * 0.85, nz - 0.02), (0.017, 0.007, 0.026)),
                           caja_cara, {"color": col("#e8707a"), "rugosidad": 0.4}))
    if not perro:
        def bigotes(p):
            d = None
            for sx in (-1, 1):
                for dy, dz in ((0.006, 0.014), (-0.004, 0.0), (-0.014, -0.012)):
                    b = capsula(p, (sx * 0.036, sn_c[1] + dy, nz - 0.01), (sx * 0.125, sn_c[1] + dy * 2 + dz, nz - 0.02), 0.0016)
                    d = b if d is None else np.minimum(d, b)
            return d
        piezas_cab.append(("m_bigotes", bigotes, caja_cara, {"color": col("#f4f1ea"), "rugosidad": 0.4}))

    # ---------------- Cola
    def cola(p):
        n = g["cola_largo"]
        if raza == "pug":                           # enrulada
            return unir(esfera(p, (0, rabo[1] + 0.025, rabo[2] - 0.012), 0.032), esfera(p, (0.014, rabo[1] + 0.05, rabo[2] - 0.02), 0.022), 0.02)
        if raza == "caniche":
            return unir(capsula(p, rabo, (0, rabo[1] + 0.05, rabo[2] - 0.05), 0.014, 0.012),
                        esfera(p, (0, rabo[1] + 0.085, rabo[2] - 0.06), 0.04), 0.03)
        if raza == "husky":                         # enrulada hacia arriba, peluda
            return unir(capsula(p, rabo, (0, rabo[1] + 0.05, rabo[2] - 0.08), 0.026, 0.034),
                        capsula(p, (0, rabo[1] + 0.05, rabo[2] - 0.08), (0, rabo[1] + 0.15, rabo[2] - 0.05), 0.034, 0.03), 0.02)
        if not perro:                               # larga y curva hacia arriba
            ancho = 0.034 if raza == "persa" else 0.018
            pts = [rabo, (0, rabo[1] + 0.02, rabo[2] - n * 0.4), (0, rabo[1] + n * 0.45, rabo[2] - n * 0.65), (0, rabo[1] + n * 0.95, rabo[2] - n * 0.55)]
            d = None
            for i in range(len(pts) - 1):
                c = capsula(p, pts[i], pts[i + 1], ancho, ancho * (0.9 if i < 2 else 0.8))
                d = c if d is None else unir(d, c, 0.015)
            return d
        return capsula(p, rabo, (0, rabo[1] + n * 0.55, rabo[2] - n * 0.9), 0.022, 0.013)

    piezas_cola = [("m_cola", cola, caja_cola, sec if cola_sec else pelaje)]
    if raza == "atigrado":
        def anillos(p):
            d = None
            for t in (0.5, 0.75):
                z = rabo[2] - g["cola_largo"] * (0.65 * t + 0.1)
                s = np.maximum(np.abs(p[..., 2] - z) - 0.006, cola(p) - 0.0035)
                d = s if d is None else np.minimum(d, s)
            return d
        piezas_cola.append(("m_manchas", anillos, caja_cola, sec))
    return {"mascota": piezas_cuerpo, "mascota_cabeza": piezas_cab, "mascota_cola": piezas_cola}
