"""La casa de BiriBiri: una habitación con piso y paredes que se cambian, muebles que se acomodan en una grilla, y las
monedas con las que se compra todo (se ganan viendo películas y series).

Este módulo es solo el modelo (sin pantalla): el catálogo, el estado que se guarda y las cuentas de las monedas. La
habitación se dibuja en vista3d.py y los muebles se arman en muebles.py. El catálogo son datos: agregar un mueble o un
piso no es programar nada más que su forma."""
from __future__ import annotations

import json
import math

# --- La habitación -------------------------------------------------------------------------------------------
CELDA = 0.3                    # lado de una celda de la grilla (BiriBiri mide 1)
COLUMNAS, FILAS = 12, 8        # 12 celdas de ancho (x) y 8 de fondo (z): 3,6 × 2,4
ANCHO, FONDO = COLUMNAS * CELDA, FILAS * CELDA
ALTO_PARED = 1.7
SUB = 2                        # la grilla para acomodar es de medias celdas (0,15): más lugares donde poner las cosas

# Monedas que da lo que ves (distinto de los puntos de rango, que cuentan la cuenta y los amigos)
RECOMPENSA = {"pelicula": 50, "episodio": 10}
MONEDAS_INICIALES = 150

# Pisos y paredes: nombre, precio, color de base, dibujo y segundo color del dibujo
PISOS = {
    "madera": ("Madera clara", 0, "#c8a070", "tablas", "#b48a5c"),
    "madera_oscura": ("Madera oscura", 60, "#6e4a32", "tablas", "#5a3b27"),
    "baldosas": ("Baldosas", 80, "#e8e4dc", "damero", "#9aa3ad"),
    "alfombrado": ("Alfombrado gris", 50, "#8e939b", "liso", "#8e939b"),
    "marmol": ("Mármol", 150, "#ece8e2", "marmol", "#b9b3aa"),
    "cesped": ("Césped", 70, "#6aa84f", "liso", "#5b9444"),
    "celeste": ("Piso celeste", 40, "#8fc1e3", "damero", "#7ab0d6"),
}
PAREDES = {
    "blanca": ("Blanca", 0, "#f1ece4", "liso", "#f1ece4"),
    "celeste": ("Celeste", 30, "#a9cde8", "liso", "#a9cde8"),
    "rosa": ("Rosa", 30, "#f0b8c8", "liso", "#f0b8c8"),
    "verde": ("Verde menta", 30, "#b5dfc0", "liso", "#b5dfc0"),
    "amarilla": ("Amarilla", 30, "#f3dc86", "liso", "#f3dc86"),
    "gris": ("Gris", 30, "#b9bcc2", "liso", "#b9bcc2"),
    "azul_noche": ("Azul noche", 40, "#34496e", "liso", "#34496e"),
    "rayas": ("Rayas celestes", 60, "#eef3f8", "rayas", "#a9cde8"),
    "ladrillo": ("Ladrillo", 90, "#b5654a", "ladrillos", "#8d4a36"),
}

# Muebles: nombre, categoría, precio, celdas que ocupa (ancho, fondo), colores para elegir (el primero es el de siempre)
CATALOGO: dict[str, dict] = {
    "sillon": {"nombre": "Sillón de 2 lugares", "categoria": "Sillas y sillones", "precio": 120, "celdas": (3, 2),
               "colores": ["#c0504d", "#4f81bd", "#7a8b99", "#6b4f3a", "#4a4a52", "#d9a441"]},
    "silla_gamer": {"nombre": "Silla gamer", "categoria": "Sillas y sillones", "precio": 150, "celdas": (2, 2),
                    "colores": ["#d4332f", "#2f7fd1", "#2e9f6b", "#8a5cd1", "#e0a21a", "#3b3b42"]},
    "mesa": {"nombre": "Mesa ratona", "categoria": "Mesas", "precio": 60, "celdas": (2, 2),
             "colores": ["#8a5a36", "#d8c3a0", "#2f2f35", "#e8e8ec", "#6aa84f"]},
    "lampara": {"nombre": "Lámpara de pie", "categoria": "Luces", "precio": 40, "celdas": (1, 1),
                "colores": ["#f4d98a", "#f1a6b8", "#9bd0f0", "#f5f5f0"]},
    "tele": {"nombre": "Tele con mueble", "categoria": "Electrodomésticos", "precio": 200, "celdas": (3, 1),
             "colores": ["#3b2f2a", "#d8c3a0", "#e8e8ec", "#2f2f35"]},
    "planta": {"nombre": "Planta en maceta", "categoria": "Decoración", "precio": 25, "celdas": (1, 1),
               "colores": ["#c06a4a", "#e8e8ec", "#4f81bd", "#d9a441"]},
    "alfombra": {"nombre": "Alfombra redonda", "categoria": "Decoración", "precio": 50, "celdas": (3, 3),
                 "colores": ["#c0504d", "#4f81bd", "#e8e1d0", "#6aa84f", "#8a5cd1"]},
    "estante": {"nombre": "Biblioteca", "categoria": "Muebles", "precio": 90, "celdas": (2, 1),
                "colores": ["#8a5a36", "#e8e8ec", "#2f2f35", "#d8c3a0"]},
    "cama": {"nombre": "Cama", "categoria": "Muebles", "precio": 140, "celdas": (3, 5),
             "colores": ["#4f81bd", "#c0504d", "#7a8b99", "#6aa84f", "#f1a6b8"]},
    "heladera": {"nombre": "Heladera", "categoria": "Electrodomésticos", "precio": 180, "celdas": (2, 2),
                 "colores": ["#e8e8ec", "#3b3b42", "#c0504d", "#9bd0f0"]},
}
# Dónde se sienta uno: lugares (x, alto del asiento, z) en el sistema del mueble, que mira hacia +z
PLAZAS = {"sillon": [(-0.19, 0.28, 0.05), (0.19, 0.28, 0.05)], "silla_gamer": [(0.0, 0.31, 0.02)]}
# Adornos de la pared del fondo: nombre, precio y tamaño (ancho, alto). Se cuelgan donde quieras
ADORNOS: dict[str, dict] = {
    "ventana": {"nombre": "Ventana con cortinas", "precio": 80, "tam": (0.78, 0.66)},
    "cuadro_paisaje": {"nombre": "Cuadro: paisaje", "precio": 45, "tam": (0.52, 0.38)},
    "cuadro_abstracto": {"nombre": "Cuadro: abstracto", "precio": 45, "tam": (0.4, 0.5)},
    "poster": {"nombre": "Póster de cine", "precio": 30, "tam": (0.36, 0.52)},
    "reloj": {"nombre": "Reloj de pared", "precio": 35, "tam": (0.3, 0.3)},
    "espejo": {"nombre": "Espejo", "precio": 60, "tam": (0.32, 0.5)},
    "guirnalda": {"nombre": "Guirnalda de luces", "precio": 40, "tam": (0.95, 0.2)},
}
CATEGORIAS = ["Sillas y sillones", "Mesas", "Muebles", "Electrodomésticos", "Luces", "Decoración", "Pared"]


def precio(item: str) -> int:
    return (CATALOGO.get(item) or ADORNOS.get(item) or {"precio": 0})["precio"]


def nombre(item: str) -> str:
    return (CATALOGO.get(item) or ADORNOS.get(item) or {"nombre": item})["nombre"]


def celdas_girado(item: str, rot: int) -> tuple[float, float]:
    """Ancho y fondo en celdas con el mueble girado (de a 45°). En diagonal ocupa un cuadrado que lo contiene."""
    w, d = CATALOGO[item]["celdas"]
    if rot % 90:
        lado = math.ceil((w + d) * 0.7071 * SUB) / SUB
        return lado, lado
    return (d, w) if rot % 180 else (w, d)


def _medio(v: float) -> float:
    return round(float(v) * SUB) / SUB


def celda_a_mundo(cx: float, cz: float) -> tuple[float, float]:
    """Centro (x, z) de una celda de la grilla; el origen está en el medio de la habitación."""
    return (cx - COLUMNAS / 2 + 0.5) * CELDA, (cz - FILAS / 2 + 0.5) * CELDA


def mundo_a_celda(x: float, z: float) -> tuple[int, int]:
    return int((x / CELDA) + COLUMNAS / 2), int((z / CELDA) + FILAS / 2)


def estado_inicial() -> dict:
    return {"piso": "madera", "pared": "blanca", "muebles": [], "inventario": {}, "pisos": ["madera"], "paredes": ["blanca"],
            "monedas": MONEDAS_INICIALES, "cobradas": [], "bb": {"cx": 4.5, "cz": 5.0, "rot": 0},
            "mascota": {"cx": 7.0, "cz": 5.0, "rot": -20},
            "sentado": {"bb": None, "mascota": None, "falda": False}, "adornos": [], "bandera": {"x": 0.0, "y": 1.05},
            "vida": True}


class Casa:
    """El estado de la casa de esta PC (se guarda en la configuración); todo lo que cambia llama a guardar()."""

    def __init__(self, bib):
        self.bib = bib
        self.datos = estado_inicial()
        try:
            guardado = json.loads(bib.config("casa") or "{}")
        except ValueError:
            guardado = {}
        self.datos.update({k: v for k, v in guardado.items() if k in self.datos})
        self._limpiar()

    # --- Guardado ------------------------------------------------------------------------------------------
    def _limpiar(self):
        """Lo que viene guardado o de un amigo puede estar mal: solo cosas del catálogo y dentro de la habitación."""
        d = self.datos
        d["piso"] = d["piso"] if d.get("piso") in PISOS else "madera"
        d["pared"] = d["pared"] if d.get("pared") in PAREDES else "blanca"
        d["pisos"] = sorted({p for p in d.get("pisos", []) if p in PISOS} | {"madera", d["piso"]})
        d["paredes"] = sorted({p for p in d.get("paredes", []) if p in PAREDES} | {"blanca", d["pared"]})
        d["inventario"] = {k: int(v) for k, v in d.get("inventario", {}).items() if (k in CATALOGO or k in ADORNOS) and int(v) > 0}
        d["adornos"] = [{"id": a["id"], "x": max(-1.7, min(1.7, float(a.get("x", 0)))), "y": max(0.2, min(1.55, float(a.get("y", 1))))}
                        for a in d.get("adornos", []) if isinstance(a, dict) and a.get("id") in ADORNOS]
        b = d.get("bandera") if isinstance(d.get("bandera"), dict) else {}
        d["bandera"] = {"x": max(-1.5, min(1.5, float(b.get("x", 0.0)))), "y": max(0.4, min(1.4, float(b.get("y", 1.05))))}
        d["vida"] = bool(d.get("vida", True))
        d["monedas"] = max(0, int(d.get("monedas", 0)))
        limpios = []
        for m in d.get("muebles", []):
            if isinstance(m, dict) and m.get("id") in CATALOGO:
                rot = int(m.get("rot", 0)) % 360 // 45 * 45
                w, p = celdas_girado(m["id"], rot)
                cx = max(0.0, min(COLUMNAS - w, _medio(m.get("cx", 0))))
                cz = max(0.0, min(FILAS - p, _medio(m.get("cz", 0))))
                color = m.get("color") if m.get("color") in CATALOGO[m["id"]]["colores"] else CATALOGO[m["id"]]["colores"][0]
                limpios.append({"id": m["id"], "cx": cx, "cz": cz, "rot": rot, "color": color})
        d["muebles"] = limpios
        s = d.get("sentado") if isinstance(d.get("sentado"), dict) else {}
        d["sentado"] = {"bb": None, "mascota": None, "falda": bool(s.get("falda"))}
        for quien in ("bb", "mascota"):
            lugar = s.get(quien)
            if isinstance(lugar, (list, tuple)) and len(lugar) == 2 and 0 <= int(lugar[0]) < len(limpios):
                plazas = PLAZAS.get(limpios[int(lugar[0])]["id"], [])
                if 0 <= int(lugar[1]) < len(plazas):
                    d["sentado"][quien] = [int(lugar[0]), int(lugar[1])]
        for quien in ("bb", "mascota"):
            v = d.get(quien) or {}
            d[quien] = {"cx": max(0.0, min(COLUMNAS - 1.0, float(v.get("cx", 4.5)))), "cz": max(0.0, min(FILAS - 1.0, float(v.get("cz", 5.0)))),
                        "rot": int(v.get("rot", 0))}

    @classmethod
    def ajena(cls, datos: dict) -> "Casa":
        """La casa de un amigo: se arma con sus datos (revisados) y no se guarda en ningún lado."""
        nueva = cls.__new__(cls)
        nueva.bib = None
        nueva.datos = estado_inicial()
        nueva.datos.update({k: v for k, v in (datos or {}).items() if k in nueva.datos and k not in ("monedas", "cobradas", "inventario")})
        nueva._limpiar()
        return nueva

    def publica(self) -> dict:
        """Lo que ven los amigos (sin monedas, inventario ni lo cobrado)."""
        return {k: self.datos[k] for k in ("piso", "pared", "muebles", "adornos", "bandera", "bb", "mascota", "sentado")}

    def guardar(self):
        if self.bib is None:
            return
        self.bib.guardar_config("casa", json.dumps(self.datos))

    # --- Monedas -------------------------------------------------------------------------------------------
    @property
    def monedas(self) -> int:
        return self.datos["monedas"]

    def cobrar(self, vistas: list[dict]) -> int:
        """Suma las monedas de lo que se vio y todavía no se cobró (cada película o capítulo, una sola vez). Devuelve lo ganado."""
        ya = set(self.datos["cobradas"])
        ganado = 0
        for v in vistas:
            h = v.get("huella")
            if h and h not in ya:
                ya.add(h)
                ganado += RECOMPENSA.get(v.get("tipo"), 0)
        if ganado or len(ya) != len(self.datos["cobradas"]):
            self.datos["cobradas"] = sorted(ya)
            self.datos["monedas"] += ganado
            self.guardar()
        return ganado

    # --- Comprar -------------------------------------------------------------------------------------------
    def comprar_mueble(self, item: str) -> bool:
        if (item not in CATALOGO and item not in ADORNOS) or self.monedas < precio(item):
            return False
        costo = precio(item)
        self.datos["monedas"] -= costo
        self.datos["inventario"][item] = self.datos["inventario"].get(item, 0) + 1
        self.guardar()
        return True

    def comprar_piso(self, piso: str) -> bool:
        return self._comprar_acabado("pisos", PISOS, piso)

    def comprar_pared(self, pared: str) -> bool:
        return self._comprar_acabado("paredes", PAREDES, pared)

    def _comprar_acabado(self, lista: str, tabla: dict, clave: str) -> bool:
        if clave not in tabla:
            return False
        if clave in self.datos[lista]:
            return True
        if self.monedas < tabla[clave][1]:
            return False
        self.datos["monedas"] -= tabla[clave][1]
        self.datos[lista].append(clave)
        self.guardar()
        return True

    def poner_piso(self, piso: str) -> bool:
        if piso in self.datos["pisos"]:
            self.datos["piso"] = piso
            self.guardar()
            return True
        return False

    def poner_pared(self, pared: str) -> bool:
        if pared in self.datos["paredes"]:
            self.datos["pared"] = pared
            self.guardar()
            return True
        return False

    # --- Acomodar muebles ----------------------------------------------------------------------------------
    @staticmethod
    def _subceldas(item: str, cx: float, cz: float, rot: int) -> set[tuple[int, int]]:
        w, p = celdas_girado(item, rot)
        x0, z0 = round(cx * SUB), round(cz * SUB)
        return {(x0 + a, z0 + b) for a in range(round(w * SUB)) for b in range(round(p * SUB))}

    def ocupadas(self, sin: int | None = None) -> set[tuple[int, int]]:
        """Medias celdas con algo encima. Las alfombras no ocupan: se puede pisar y poner cosas arriba."""
        celdas = set()
        for i, m in enumerate(self.datos["muebles"]):
            if i == sin or m["id"] == "alfombra":
                continue
            celdas |= self._subceldas(m["id"], m["cx"], m["cz"], m["rot"])
        return celdas

    def cabe(self, item: str, cx: float, cz: float, rot: int, sin: int | None = None) -> bool:
        w, p = celdas_girado(item, rot)
        if cx < 0 or cz < 0 or cx + w > COLUMNAS + 1e-6 or cz + p > FILAS + 1e-6:
            return False
        if item == "alfombra":
            return True
        return not (self._subceldas(item, cx, cz, rot) & self.ocupadas(sin))

    def poner_mueble(self, item: str, cx: int, cz: int, rot: int = 0, color: str | None = None) -> int | None:
        """Saca uno del inventario y lo pone. Devuelve su número, o None si no entra o no tenés."""
        cx, cz = _medio(cx), _medio(cz)
        if item not in CATALOGO or self.datos["inventario"].get(item, 0) < 1 or not self.cabe(item, cx, cz, rot):
            return None
        self.datos["inventario"][item] -= 1
        if self.datos["inventario"][item] <= 0:
            del self.datos["inventario"][item]
        elegido = color if color in CATALOGO[item]["colores"] else CATALOGO[item]["colores"][0]
        self.datos["muebles"].append({"id": item, "cx": cx, "cz": cz, "rot": rot % 360 // 45 * 45, "color": elegido})
        self.guardar()
        return len(self.datos["muebles"]) - 1

    def mover_mueble(self, i: int, cx: int, cz: int) -> bool:
        m = self.datos["muebles"][i]
        cx, cz = _medio(cx), _medio(cz)
        if not self.cabe(m["id"], cx, cz, m["rot"], sin=i):
            return False
        m["cx"], m["cz"] = cx, cz
        self.guardar()
        return True

    def girar_mueble(self, i: int) -> bool:
        m = self.datos["muebles"][i]
        rot = (m["rot"] + 45) % 360
        w, p = celdas_girado(m["id"], rot)
        cx, cz = max(0.0, min(m["cx"], COLUMNAS - w)), max(0.0, min(m["cz"], FILAS - p))   # si al girar se pasa del borde, se corre
        if not self.cabe(m["id"], cx, cz, rot, sin=i):
            return False
        m.update(rot=rot, cx=cx, cz=cz)
        self.guardar()
        return True

    def pintar_mueble(self, i: int, color: str) -> bool:
        m = self.datos["muebles"][i]
        if color not in CATALOGO[m["id"]]["colores"]:
            return False
        m["color"] = color
        self.guardar()
        return True

    def guardar_mueble(self, i: int):
        """Lo vuelve al inventario."""
        m = self.datos["muebles"].pop(i)
        self.datos["inventario"][m["id"]] = self.datos["inventario"].get(m["id"], 0) + 1
        for quien in ("bb", "mascota"):             # quien estaba sentado ahí se levanta; los demás muebles cambian de número
            lugar = self.datos["sentado"][quien]
            if lugar and lugar[0] == i:
                self.datos["sentado"][quien] = None
            elif lugar and lugar[0] > i:
                lugar[0] -= 1
        self.guardar()

    # --- Adornos de la pared --------------------------------------------------------------------------------
    def poner_adorno(self, item: str) -> int | None:
        """Lo cuelga en un lugar libre de la pared del fondo (después se arrastra a donde quieras)."""
        if item not in ADORNOS or self.datos["inventario"].get(item, 0) < 1:
            return None
        self.datos["inventario"][item] -= 1
        if self.datos["inventario"][item] <= 0:
            del self.datos["inventario"][item]
        usados = [a["x"] for a in self.datos["adornos"]]
        x = min((-0.9 + 0.3 * k for k in range(7)), key=lambda c: -min([abs(c - u) for u in usados] or [9]))   # lejos de las puertas
        self.datos["adornos"].append({"id": item, "x": round(x, 2), "y": 1.05})
        self.guardar()
        return len(self.datos["adornos"]) - 1

    def mover_adorno(self, i: int, x: float, y: float, guardar: bool = True):
        a = self.datos["adornos"][i]
        w, h = ADORNOS[a["id"]]["tam"]
        a["x"] = max(-ANCHO / 2 + w / 2 + 0.03, min(ANCHO / 2 - w / 2 - 0.03, x))
        a["y"] = max(h / 2 + 0.05, min(ALTO_PARED - h / 2 - 0.05, y))
        if guardar:
            self.guardar()

    def guardar_adorno(self, i: int):
        a = self.datos["adornos"].pop(i)
        self.datos["inventario"][a["id"]] = self.datos["inventario"].get(a["id"], 0) + 1
        self.guardar()

    def mover_bandera(self, x: float, y: float, guardar: bool = True):
        self.datos["bandera"] = {"x": max(-1.5, min(1.5, x)), "y": max(0.4, min(1.4, y))}
        if guardar:
            self.guardar()

    # --- Sentarse --------------------------------------------------------------------------------------------
    def plazas(self, i: int) -> int:
        return len(PLAZAS.get(self.datos["muebles"][i]["id"], []))

    def sentar(self, quien: str, i: int, plaza: int = 0) -> bool:
        """quien: «bb» o «mascota». Si el lugar lo tiene el otro, se corre al que queda libre."""
        if not 0 <= i < len(self.datos["muebles"]) or plaza >= self.plazas(i):
            return False
        otro = self.datos["sentado"]["mascota" if quien == "bb" else "bb"]
        if otro and otro[0] == i and otro[1] == plaza:
            libres = [p for p in range(self.plazas(i)) if p != plaza]
            if not libres:
                return False
            plaza = libres[0]
        self.datos["sentado"][quien] = [i, plaza]
        self.guardar()
        return True

    def parar(self, quien: str | None = None):
        for q in (("bb", "mascota") if quien is None else (quien,)):
            self.datos["sentado"][q] = None
        if quien in (None, "bb"):
            self.datos["sentado"]["falda"] = False
        self.guardar()

    def mover_personaje(self, quien: str, cx: float, cz: float):
        self.datos["sentado"][quien] = None
        self.datos[quien]["cx"] = max(0.0, min(COLUMNAS - 1.0, cx))
        self.datos[quien]["cz"] = max(0.0, min(FILAS - 1.0, cz))
        self.guardar()
