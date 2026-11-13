"""Vida propia de BiriBiri y su mascota en la videoteca: una pequeña «IA» local, sin internet ni modelos, hecha de rutinas.

Cada uno decide cada tanto qué hacer y lo arma como una lista de pasos (ir a un lugar, darse vuelta, esperar haciendo
algo, hacer algo). BiriBiri pasea, se sienta solo en un sillón o en la silla, mira la tele (en un sillón que le apunte o
sentado en el piso adelante, con la tele prendida), se acuesta a dormir en la cama (z z z, y antes apaga la lámpara),
prende y apaga las lámparas, le llena el plato a la mascota, le tira la pelota para que se la traiga y la llama para
hacerle mimos. La mascota pasea, lo sigue, se le sube a la falda, come de su plato, juega sola con la pelota (la empuja y
la persigue) y se duerme a los pies de la cama si él está durmiendo. Caminan esquivando los muebles, girando de a poco
hacia donde van, y al sentarse, acostarse o levantarse pasan suave de una pose a la otra. Mientras arrastrás algo,
acomodás muebles o editás a BiriBiri, esperan."""
from __future__ import annotations

import heapq
import math
import random
import time
from collections import deque

from PySide6.QtCore import QObject, QTimer

from . import casa as modelo
from . import poses

CELDA = modelo.CELDA
SUB = 2                                          # la grilla con la que buscan el camino: medias celdas (0,15)
MARGEN = 0.12                                    # cuánto lugar dejan alrededor de los muebles (en celdas)
VELOCIDAD = {"bb": 0.34, "mascota": 0.46}        # metros por segundo (BiriBiri mide 0,62 en la habitación)
CORRIENDO = {"bb": 0.55, "mascota": 0.95}
GIRO = 360.0                                     # grados por segundo al darse vuelta
LIMITES = (-1.55, 1.55, -0.95, 1.05)             # x mínimo, x máximo, z mínimo, z máximo por donde se camina
ESC = 0.62                                       # la escala de los dos en la habitación (ver vista3d.ESC_CASA)

NEUTRO = {k: v for k, v in poses.BASE.items() if k != "esc"}
# Caminar: brazos al revés que las piernas, un rebote en cada paso, la cadera que gira y el cuerpo apenas para adelante
CAMINAR_BB = {**NEUTRO, "ampBx": -26, "ampP": 30, "ritmo": 10, "reposo": 0, "ampS": 0.013, "vaiven": 0, "giroPaso": 7, "rX": 5,
              "aiZ": -6, "adZ": 6, "cabX": -3}
CORRER_BB = {**CAMINAR_BB, "ampBx": -42, "ampP": 40, "ritmo": 13, "ampS": 0.022, "rX": 9}
CAMINAR_PET = {"petSalto": 0.014, "petRitmo": 11, "petCola": 30}
CORRER_PET = {"petSalto": 0.045, "petRitmo": 17, "petCola": 48, "petCabX": -8}
ACOSTADO = {**NEUTRO, "rX": -90, "pY": 0.33, "reposo": 0.15, "vaiven": 0, "aiZ": -8, "adZ": 8, "aiX": 4, "adX": 4, "sombra": False,
            "cabZ": -10}
EN_EL_PISO = {**NEUTRO, **poses.POSES["sentado"][1], "pY": poses.POSES["sentado"][1]["pY"] * ESC, "vaiven": 0.4}
LLENAR = {**NEUTRO, "reposo": 0, "rX": 12, "adX": -55, "adZ": 24, "aiZ": -8, "cabX": 16, "ondaD": 6, "ritmo": 8}
LEVANTAR = {**NEUTRO, "reposo": 0, "rX": 16, "adX": -48, "adZ": 18, "cabX": 18}
APUNTAR = {**NEUTRO, "reposo": 0, "adX": -78, "adZ": 22, "cabY": 6}
TIRAR = {**NEUTRO, "reposo": 0, "adX": -160, "adZ": 12, "aiZ": -20, "rX": -4}
DORMIR_PET = {"petCabX": 34, "petCola": 5, "petRitmo": 2, "petSalto": 0}
COMER = {"petCabX": 40, "petCola": 34, "petRitmo": 13, "texto": "¡Ñam!"}
LADRAR = {"petCabX": -14, "petCola": 50, "petRitmo": 16, "petSalto": 0.03}
RADIO_PELOTA = 0.035


def _a_celda(x: float, z: float) -> tuple[float, float]:
    return x / CELDA + modelo.COLUMNAS / 2 - 0.5, z / CELDA + modelo.FILAS / 2 - 0.5


def _rumbo(dx: float, dz: float) -> float:
    return math.degrees(math.atan2(dx, dz))


def _dif(a: float, b: float) -> float:
    """Cuánto hay que girar para pasar de a a b (entre -180 y 180)."""
    return (b - a + 540) % 360 - 180


class Vida(QObject):
    def __init__(self, escena, casa: modelo.Casa, con_mascota=lambda: True):
        super().__init__()
        self.e = escena
        self.casa = casa
        self.con_mascota = con_mascota
        self.azar = random.Random()
        ahora = time.monotonic()
        self.cola = {q: deque() for q in ("bb", "mascota")}
        self.paso: dict = {"bb": None, "mascota": None}
        self.pose_extra: dict = {"bb": {}, "mascota": {}}
        self.libre_desde = {"bb": ahora + self.azar.uniform(2, 5), "mascota": ahora + self.azar.uniform(2, 5)}
        # Estados que duran (los muestra la escena): BiriBiri acostado o sentado en el piso, la mascota en la cama
        self.lugar: dict = {"bb": None, "mascota": None}      # {"x", "z", "rot", "y", "pose", "tipo", "i"}
        self.tele: int | None = None                         # la tele prendida (número de mueble)
        self.plato_lleno = True
        self.pelota_en: str | None = None                    # «bb» o «mascota»: la tiene en la mano / en la boca
        self.vuelo: dict | None = None                       # la pelota en el aire o rodando
        self.pelota_y = 0.0
        self.pelota_rumbo = 0.0
        self.pelota_giro = 0.0
        self.marcas: set[str] = set()                         # señales entre los dos («llegó», «la soltó»…)
        self._ultimo = ahora
        self.reloj = QTimer(self, interval=40, timeout=self._tic)
        self.reloj.start()
        escena.vida = self

    # --- Lo que muestra la escena -----------------------------------------------------------------------------
    def extra_bb(self) -> dict:
        p = self.paso["bb"]
        if p and p["t"] == "ir" and p.get("andando"):
            return dict(CORRER_BB if p.get("rapido") else CAMINAR_BB)
        return dict(self.pose_extra["bb"])

    def extra_pet(self) -> dict:
        p = self.paso["mascota"]
        if p and p["t"] == "ir" and p.get("andando"):
            return dict(CORRER_PET if p.get("rapido") else CAMINAR_PET)
        return dict(self.pose_extra["mascota"])

    def lugar_bb(self) -> dict | None:
        return self.lugar["bb"]

    def lugar_pet(self) -> dict | None:
        return self.lugar["mascota"]

    def zzz(self) -> tuple[float, float, float] | None:
        lugar = self.lugar["bb"]
        if lugar and lugar.get("tipo") == "cama":
            return lugar["zzz"]
        return None

    def tele_prendida(self, i: int) -> bool:
        return self.tele == i

    def pelota(self) -> tuple[float, float, float, float, float]:
        p = self.casa.datos["pelota"]
        return p["x"], self.pelota_y, p["z"], self.pelota_rumbo, self.pelota_giro

    @property
    def activa(self) -> bool:
        return bool(self.casa.datos.get("vida", True))

    def poner_activa(self, si: bool):
        self.casa.datos["vida"] = bool(si)
        self.casa.guardar()
        if not si:
            self.cortar()
            self.e.refrescar(suave=True)

    def soltar_control(self, quien: str | None = None):
        """Agarraste a alguno (o algo) con el mouse: dejan lo que estaban haciendo y se quedan quietos un rato."""
        self.cortar()
        for q in ("bb", "mascota"):
            self.libre_desde[q] = time.monotonic() + self.azar.uniform(8, 14)

    def mirame(self, quien: str):
        """Le hiciste clic: deja lo que hacía (si estaba caminando), se da vuelta hacia vos y te saluda."""
        if not self._parado(quien):
            self.pose_extra[quien] = {"cabX": -6, "cabY": 0} if quien == "bb" else {"petCabX": -14, "petCola": 50, "petRitmo": 16}
            self.e.refrescar(suave=True)
            QTimer.singleShot(2500, lambda: (self.pose_extra.__setitem__(quien, {}), self.e.refrescar(suave=True)))
            return
        if quien == "bb":
            pose = {**NEUTRO, "reposo": 0.4, "adZ": 120, "ondaD": 20, "ritmo": 7, "cabZ": -5}
        else:
            pose = LADRAR
        self._plan(quien, [self._mirar(0), self._esperar(2.5, pose)])
        self.libre_desde[quien] = time.monotonic() + 6

    def ordenar(self, quien: str, que: str) -> bool:
        """Lo que elegiste en su menú: deja lo que estaba haciendo y lo hace (devuelve False si no se puede)."""
        if que == "saludar":
            self.mirame(quien)
            return True
        self.cortar()
        for q in ("bb", "mascota"):
            if not self._parado(q) and (q == quien or que in ("mimos", "tirar_pelota", "falda")):
                self._levantarse(q)
        if que == "falda":
            s = self.casa.datos["sentado"]
            if not s["bb"]:      # primero se sienta él y, cuando ya está sentado, la mascota se le sube
                return self._r_sentarse("bb", al_sentarse=lambda: QTimer.singleShot(400, lambda: self._r_falda("mascota"))) is not False
        if que == "a_los_pies" and not (self.lugar["bb"] and self.lugar["bb"].get("tipo") == "cama"):
            return False
        hecho = getattr(self, "_r_" + que)(quien) is not False
        otro = "mascota" if quien == "bb" else "bb"
        if not self._ocupado(otro):
            self.libre_desde[otro] = time.monotonic() + self.azar.uniform(4, 8)
        return hecho

    def cortar(self):
        """Termina todo lo que están haciendo (se levantan de la cama o del piso, la tele se apaga, sueltan la pelota)."""
        for q in ("bb", "mascota"):
            self.cola[q].clear()
            self.paso[q] = None
            self.pose_extra[q] = {}
            self._salir_del_lugar(q)
        self.tele = None
        self.marcas.clear()
        if self.vuelo:
            self._mover_pelota(self.vuelo["x1"], self.vuelo["z1"])
        self.vuelo = None
        self.pelota_en = None
        self.pelota_y = 0.0

    # --- El reloj ---------------------------------------------------------------------------------------------
    def _tic(self):
        ahora = time.monotonic()
        dt = min(0.1, ahora - self._ultimo)
        self._ultimo = ahora
        if not self.activa or self.e.ocupado or not self.e.v.isVisible():
            return
        self._pelota_tic(ahora, dt)
        for quien in ("bb", "mascota"):
            if quien == "mascota" and not self.con_mascota():
                continue
            if self.paso[quien] is None:
                if self.cola[quien]:
                    self._empezar(quien, self.cola[quien].popleft())
                elif ahora >= self.libre_desde[quien]:
                    self._decidir(quien)
                continue
            self._seguir_paso(quien, ahora, dt)

    def _empezar(self, quien: str, paso: dict):
        paso["desde"] = time.monotonic()
        self.paso[quien] = paso
        t = paso["t"]
        if t == "ir":
            destino = paso["a"]() if callable(paso.get("a")) else paso.get("a")
            ruta = self._ruta(self._pos(quien), destino) if destino is not None else None
            if not ruta:
                return self._abortar(quien)
            paso["ruta"] = ruta
        elif t == "esperar":
            self.pose_extra[quien] = dict(paso.get("pose") or {})
            self.e.refrescar(suave=paso.get("suave", True))
        elif t == "hacer":
            self.paso[quien] = None
            if paso["fn"]() is False:
                return self._abortar(quien)
        elif t == "mirar":
            objetivo = paso["a"]() if callable(paso["a"]) else paso["a"]
            if isinstance(objetivo, tuple):
                x, z = self._pos(quien)
                objetivo = _rumbo(objetivo[0] - x, objetivo[1] - z)
            paso["rot"] = objetivo

    def _terminar_paso(self, quien: str):
        p = self.paso[quien]
        self.paso[quien] = None
        cambio = False
        if p and p["t"] == "esperar" and p.get("pose") and not p.get("seguir_pose"):
            self.pose_extra[quien] = {}
            cambio = True
        if p and p["t"] == "ir" and p.get("andando") and not (self.cola[quien] and self.cola[quien][0]["t"] == "ir"):
            cambio = True
        if not self.cola[quien]:
            self.libre_desde[quien] = time.monotonic() + self.azar.uniform(2, 5)
        if cambio:
            self.e.refrescar()

    def _abortar(self, quien: str):
        """El plan no se puede seguir (se cruzó algo): se queda quieto un rato."""
        self.paso[quien] = None
        self.cola[quien].clear()
        self.pose_extra[quien] = {}
        self.libre_desde[quien] = time.monotonic() + self.azar.uniform(1.5, 4)
        self.e.refrescar()

    def _seguir_paso(self, quien: str, ahora: float, dt: float):
        p = self.paso[quien]
        t = p["t"]
        if t == "ir":
            self._caminar(quien, p, dt)
        elif t == "mirar":
            d = self.casa.datos[quien]
            falta = _dif(d["rot"], p["rot"])
            if abs(falta) <= GIRO * dt:
                self._poner(quien, *self._pos(quien), p["rot"])
                self._terminar_paso(quien)
            else:
                self._poner(quien, *self._pos(quien), d["rot"] + math.copysign(GIRO * dt, falta))
        elif t == "esperar":
            hasta = p.get("hasta")
            listo = hasta() if callable(hasta) else False
            if listo or ahora - p["desde"] >= p["seg"]:
                self._terminar_paso(quien)

    # --- Moverse ----------------------------------------------------------------------------------------------
    def _pos(self, quien: str) -> tuple[float, float]:
        d = self.casa.datos[quien]
        return modelo.celda_a_mundo(d["cx"], d["cz"])

    def _poner(self, quien: str, x: float, z: float, rot: float | None = None):
        cx, cz = _a_celda(x, z)
        d = self.casa.datos[quien]
        d["cx"], d["cz"] = cx, cz
        if rot is not None:
            d["rot"] = int(round(rot)) % 360
        if quien == "bb":
            self.e.v.pose(bbX=x, bbZ=z, bbRot=float(d["rot"]))
        else:
            self.e.v._casa_pet.update(petPos=x, petZ=z, petRotY=float(d["rot"]))
            self.e.v.pose(petPos=x, petZ=z, petRotY=float(d["rot"]))
        if self.pelota_en == quien:
            self._pelota_a_la_boca()

    def _caminar(self, quien: str, p: dict, dt: float):
        x, z = self._pos(quien)
        tx, tz = p["ruta"][0]
        dx, dz = tx - x, tz - z
        dist = math.hypot(dx, dz)
        if dist < 1e-3:
            p["ruta"].pop(0)
            if not p["ruta"]:
                self._terminar_paso(quien)
            return
        d = self.casa.datos[quien]
        rumbo = _rumbo(dx, dz)
        falta = _dif(d["rot"], rumbo)
        giro = max(-GIRO * dt, min(GIRO * dt, falta))
        if abs(falta) > 70:                 # primero se da vuelta (en el lugar) y después camina
            self._poner(quien, x, z, d["rot"] + giro)
            return
        if not p.get("andando"):
            p["andando"] = True
            self.e.sin_suave()              # caminando, la posición va directo (sin la transición de sentarse)
            self.e.refrescar()              # que se ponga a caminar (brazos y piernas)
        paso = (CORRIENDO if p.get("rapido") else VELOCIDAD)[quien] * dt
        if dist <= paso:
            self._poner(quien, tx, tz, d["rot"] + giro)
            p["ruta"].pop(0)
            if not p["ruta"]:
                self.casa.guardar()
                self._terminar_paso(quien)
            return
        self._poner(quien, x + dx / dist * paso, z + dz / dist * paso, d["rot"] + giro)

    def _ir(self, quien: str, a, rapido: bool = False) -> dict:
        return {"t": "ir", "a": a, "rapido": rapido}

    @staticmethod
    def _esperar(seg: float, pose: dict | None = None, hasta=None, suave: bool = True, seguir_pose: bool = False) -> dict:
        return {"t": "esperar", "seg": seg, "pose": pose, "hasta": hasta, "suave": suave, "seguir_pose": seguir_pose}

    @staticmethod
    def _hacer(fn) -> dict:
        return {"t": "hacer", "fn": fn}

    @staticmethod
    def _mirar(a) -> dict:
        return {"t": "mirar", "a": a}

    def _plan(self, quien: str, pasos: list):
        self.cola[quien].clear()
        self.cola[quien].extend(pasos)
        self.paso[quien] = None

    def _ocupado(self, quien: str) -> bool:
        return self.paso[quien] is not None or bool(self.cola[quien])

    # --- Dónde se puede pisar ---------------------------------------------------------------------------------
    def _libre(self, x: float, z: float, ocupadas: set) -> bool:
        if not (LIMITES[0] <= x <= LIMITES[1] and LIMITES[2] <= z <= LIMITES[3]):
            return False
        return not modelo.Casa.pisado(x / CELDA + modelo.COLUMNAS / 2, z / CELDA + modelo.FILAS / 2, ocupadas, MARGEN)

    def _derecho(self, desde, hasta, ocupadas: set, salida: float = 0.12) -> bool:
        """¿Se llega caminando derecho? (el primer tramo puede salir de al lado de un mueble)"""
        (x0, z0), (x1, z1) = desde, hasta
        dist = math.hypot(x1 - x0, z1 - z0)
        pasos = max(1, int(dist / 0.05))
        return all(self._libre(x0 + (x1 - x0) * k / pasos, z0 + (z1 - z0) * k / pasos, ocupadas)
                   for k in range(1, pasos + 1) if k * dist / pasos > salida or k == pasos)

    def _camino_libre(self, desde, hasta, quien: str | None = None) -> bool:
        return self._ruta(desde, hasta) is not None

    def _ruta(self, desde, hasta) -> list[tuple[float, float]] | None:
        """Cómo llegar esquivando los muebles: A* sobre las medias celdas (en diagonal también) y después se estira el
        camino (de cada punto, al más lejano que se vea derecho). Devuelve los puntos a pisar, o None si no se llega."""
        ocupadas = self.casa.ocupadas()
        if not self._libre(*hasta, ocupadas):
            return None
        if self._derecho(desde, hasta, ocupadas):
            return [tuple(hasta)]
        celda = lambda x, z: (int((x / CELDA + modelo.COLUMNAS / 2) * SUB), int((z / CELDA + modelo.FILAS / 2) * SUB))   # noqa: E731
        centro = lambda c: (((c[0] + 0.5) / SUB - modelo.COLUMNAS / 2) * CELDA, ((c[1] + 0.5) / SUB - modelo.FILAS / 2) * CELDA)  # noqa: E731
        libre = lambda c: self._libre(*centro(c), ocupadas)      # noqa: E731
        inicio, fin = celda(*desde), celda(*hasta)
        abiertos = [(0.0, 0.0, inicio)]
        costo = {inicio: 0.0}
        vino = {}
        while abiertos:
            _f, g, c = heapq.heappop(abiertos)
            if c == fin:
                break
            if g > costo.get(c, 1e9):
                continue
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if not dx and not dz:
                        continue
                    n = (c[0] + dx, c[1] + dz)
                    if not libre(n) or (dx and dz and not (libre((c[0] + dx, c[1])) and libre((c[0], c[1] + dz)))):
                        continue
                    ng = g + (1.414 if dx and dz else 1.0)
                    if ng < costo.get(n, 1e9):
                        costo[n] = ng
                        vino[n] = c
                        heapq.heappush(abiertos, (ng + math.hypot(fin[0] - n[0], fin[1] - n[1]), ng, n))
        else:
            return None
        if fin not in vino and fin != inicio:
            return None
        celdas = [fin]
        while celdas[-1] != inicio:
            celdas.append(vino[celdas[-1]])
        puntos = [tuple(desde)] + [centro(c) for c in reversed(celdas[:-1])][:-1] + [tuple(hasta)]
        # estirar: de cada punto, saltar al más lejano que se vea derecho
        ruta, i = [], 0
        while i < len(puntos) - 1:
            j = len(puntos) - 1
            while j > i + 1 and not self._derecho(puntos[i], puntos[j], ocupadas, 0.12 if i == 0 else 0.0):
                j -= 1
            ruta.append(puntos[j])
            i = j
        return ruta

    def _lugar_al_azar(self, desde, cerca: float | None = None) -> tuple[float, float] | None:
        ocupadas = self.casa.ocupadas()
        for _ in range(24):
            if cerca:
                ang = self.azar.uniform(0, 2 * math.pi)
                r = self.azar.uniform(cerca * 0.6, cerca)
                x, z = desde[0] + r * math.cos(ang), desde[1] + r * math.sin(ang)
            else:
                x, z = self.azar.uniform(*LIMITES[:2]), self.azar.uniform(*LIMITES[2:])
            if self._libre(x, z, ocupadas) and self._camino_libre(desde, (x, z)):
                return x, z
        return None

    def _al_lado_de(self, x0: float, z0: float, distancia: float, desde) -> tuple[float, float] | None:
        """Un lugar libre a esa distancia de (x0, z0), del lado más cerca de desde."""
        ocupadas = self.casa.ocupadas()
        base = math.atan2(desde[0] - x0, desde[1] - z0)
        for k in (0, 1, -1, 2, -2, 3, -3, 4):
            ang = base + k * math.pi / 4
            x, z = x0 + distancia * math.sin(ang), z0 + distancia * math.cos(ang)
            if self._libre(x, z, ocupadas) and self._ruta(desde, (x, z)) is not None:
                return x, z
        return None

    def _local(self, i: int, lx: float, lz: float) -> tuple[float, float]:
        m = self.casa.datos["muebles"][i]
        x0, z0 = self.e.centro_mueble(m)
        th = math.radians(m["rot"])
        return x0 + lx * math.cos(th) + lz * math.sin(th), z0 - lx * math.sin(th) + lz * math.cos(th)

    def _muebles(self, tipo: str) -> list[int]:
        return [i for i, m in enumerate(self.casa.datos["muebles"]) if m["id"] == tipo]

    def _asientos_libres(self) -> list[tuple[int, int]]:
        tomados = {tuple(v) for v in (self.casa.datos["sentado"]["bb"], self.casa.datos["sentado"]["mascota"]) if v}
        libres = []
        for i, m in enumerate(self.casa.datos["muebles"]):
            for plaza in range(len(modelo.PLAZAS.get(m["id"], []))):
                if (i, plaza) not in tomados:
                    libres.append((i, plaza))
        return libres

    # --- Estados que duran --------------------------------------------------------------------------------------
    def _parado(self, quien: str) -> bool:
        s = self.casa.datos["sentado"]
        return not (s[quien] or self.lugar[quien] or (quien == "mascota" and s["falda"]))

    def _salir_del_lugar(self, quien: str):
        lugar = self.lugar[quien]
        if lugar:
            self.lugar[quien] = None
            sx, sz = lugar.get("salida", (lugar["x"], lugar["z"]))
            self.casa.datos[quien].update(dict(zip(("cx", "cz"), _a_celda(sx, sz))), rot=int(lugar.get("rot_salida", lugar["rot"])) % 360)
        if quien == "bb" and self.lugar["mascota"] and self.lugar["mascota"].get("tipo") == "cama":
            pass      # la mascota sigue durmiendo un rato: se despierta sola

    def _levantarse(self, quien: str):
        sentado = self.casa.datos["sentado"]
        if self.lugar[quien]:
            self._salir_del_lugar(quien)
        else:
            lugar = sentado[quien]
            if lugar and lugar[0] < len(self.casa.datos["muebles"]):
                x, z, rot = self.e.frente_del_asiento(*lugar)
            else:                       # la mascota se baja de la falda: al lado de BiriBiri
                x, z = self._pos("bb")
                x, rot = x + 0.25, 0.0
            if quien == "bb":
                sentado["falda"] = False
            self.casa.parar(quien)
            cx, cz = _a_celda(x, z)
            self.casa.datos[quien].update(cx=cx, cz=cz, rot=int(rot) % 360)
        if quien == "bb":
            self.tele = None
            if sentado["falda"]:
                sentado["falda"] = False
        self.casa.guardar()
        self.libre_desde[quien] = time.monotonic() + self.azar.uniform(2, 5)
        self.e.refrescar(suave=True)

    # --- Qué hace cada uno -------------------------------------------------------------------------------------
    def _decidir(self, quien: str):
        if not self._parado(quien):
            if quien == "mascota" and self.lugar["mascota"] and self.lugar["bb"] and self.azar.random() < 0.7:
                self.libre_desde[quien] = time.monotonic() + self.azar.uniform(6, 12)     # sigue durmiendo con él
                return
            self._levantarse(quien)
            return
        opciones = self._opciones_bb() if quien == "bb" else self._opciones_pet()
        nombres = [n for n, peso in opciones for _ in range(peso)]
        self.azar.shuffle(nombres)
        probadas = set()
        for nombre in nombres:
            if nombre in probadas:
                continue
            probadas.add(nombre)
            if getattr(self, "_r_" + nombre)(quien) is not False:
                return
        self.libre_desde[quien] = time.monotonic() + self.azar.uniform(3, 7)

    def _mascota_libre(self) -> bool:
        return self.con_mascota() and self._parado("mascota") and not self._ocupado("mascota")

    def _opciones_bb(self) -> list[tuple[str, int]]:
        o = [("pasear", 4), ("quieto", 1), ("sentarse", 2)]
        if self._muebles("tele"):
            o.append(("tele", 3))
        if self._muebles("cama"):
            o.append(("dormir", 2))
        if self._muebles("lampara"):
            o.append(("lampara", 1))
        if self._mascota_libre():
            o += [("mimos", 2), ("tirar_pelota", 2)]
            o.append(("llenar_plato", 1 if self.plato_lleno else 4))
        return o

    def _opciones_pet(self) -> list[tuple[str, int]]:
        s = self.casa.datos["sentado"]
        o = [("pasear", 3), ("seguir", 3), ("quieto", 1), ("sentarse", 1), ("jugar_pelota", 2)]
        if self.plato_lleno:
            o.append(("comer", 3))
        if s["bb"] and not s["falda"]:
            o.append(("falda", 3))
        if self.lugar["bb"] and self.lugar["bb"].get("tipo") == "cama":
            o.append(("a_los_pies", 5))
        return o

    # Rutinas: arman el plan (o devuelven False si no se puede)
    def _r_quieto(self, quien):
        self.libre_desde[quien] = time.monotonic() + self.azar.uniform(3, 7)

    def _r_pasear(self, quien):
        lugar = self._lugar_al_azar(self._pos(quien))
        if not lugar:
            return False
        self._plan(quien, [self._ir(quien, lugar)])

    def _r_seguir(self, quien):
        bx, bz = self._pos("bb")
        lugar = self._al_lado_de(bx, bz, 0.3, self._pos("mascota"))
        if not lugar or not self._camino_libre(self._pos("mascota"), lugar):
            return False
        self._plan("mascota", [self._ir("mascota", lugar), self._mirar((bx, bz)), self._esperar(1.5, LADRAR if self.azar.random() < 0.3 else None)])

    def _r_sentarse(self, quien, solo_estos: list | None = None, al_sentarse=None, segundos=(12, 25)):
        libres = solo_estos if solo_estos is not None else self._asientos_libres()
        self.azar.shuffle(libres)
        for i, plaza in libres:
            x, z, _rot = self.e.frente_del_asiento(i, plaza)
            if not self._libre(x, z, self.casa.ocupadas()) or not self._camino_libre(self._pos(quien), (x, z)):
                continue

            def sentarse(i=i, plaza=plaza):
                if (i, plaza) not in self._asientos_libres() or not self.casa.sentar(quien, i, plaza):
                    return False
                if al_sentarse:
                    al_sentarse()
                self.libre_desde[quien] = time.monotonic() + self.azar.uniform(*segundos)
                self.e.refrescar(suave=True)
            self._plan(quien, [self._ir(quien, (x, z)), self._mirar(_rot), self._hacer(sentarse)])
            return True
        return False

    def _r_falda(self, quien):
        s = self.casa.datos["sentado"]
        lugar = s["bb"]
        if not lugar:
            return False
        # se para adelante del asiento (lo primero libre, un poco más lejos si el mueble es hondo)
        for distancia in (0.32, 0.4, 0.5):
            x, z, rot = self.e.frente_del_asiento(*lugar, distancia=distancia)
            if self._libre(x, z, self.casa.ocupadas()) and self._camino_libre(self._pos("mascota"), (x, z)):
                break
        else:
            return False

        def subirse():
            if not s["bb"]:
                return False
            s["falda"] = True
            s["mascota"] = None
            self.casa.guardar()
            self.libre_desde["mascota"] = time.monotonic() + self.azar.uniform(10, 18)
            self.e.refrescar(suave=True)
        self._plan("mascota", [self._ir("mascota", (x, z)), self._mirar(rot + 180), self._esperar(0.6, LADRAR), self._hacer(subirse)])

    # --- La tele -------------------------------------------------------------------------------------------------
    def _r_tele(self, quien):
        teles = self._muebles("tele")
        self.azar.shuffle(teles)
        for i in teles:
            m = self.casa.datos["muebles"][i]
            tx, tz = self.e.centro_mueble(m)
            th = math.radians(m["rot"])
            frente = (math.sin(th), math.cos(th))
            # un sillón libre que le apunte a la tele
            buenos = []
            for j, plaza in self._asientos_libres():
                sx, _y, sz, srot = self.e._asiento([j, plaza])
                vx, vz = tx - sx, tz - sz
                dist = math.hypot(vx, vz)
                if not 0.45 < dist < 2.8:
                    continue
                sr = math.radians(srot)
                if (math.sin(sr) * vx + math.cos(sr) * vz) / dist > 0.72 and -(frente[0] * vx + frente[1] * vz) / dist > 0.45:
                    buenos.append((j, plaza))

            def prender(i=i):
                self.tele = i
            if buenos and self._r_sentarse("bb", buenos, al_sentarse=prender, segundos=(22, 40)):
                return True
            # si no, sentado en el piso adelante de la tele
            px, pz = tx + frente[0] * 0.72, tz + frente[1] * 0.72
            if not self._libre(px, pz, self.casa.ocupadas()) or not self._camino_libre(self._pos("bb"), (px, pz)):
                continue
            rot = (m["rot"] + 180) % 360

            def sentarse_en_el_piso(px=px, pz=pz, rot=rot, i=i):
                self.lugar["bb"] = {"tipo": "piso", "x": px, "z": pz, "rot": rot, "pose": EN_EL_PISO, "salida": (px, pz)}
                self.tele = i
                self.libre_desde["bb"] = time.monotonic() + self.azar.uniform(20, 35)
                self.e.refrescar(suave=True)
            self._plan("bb", [self._ir("bb", (px, pz)), self._mirar(rot), self._hacer(sentarse_en_el_piso)])
            return True
        return False

    # --- La cama -------------------------------------------------------------------------------------------------
    def _r_dormir(self, quien):
        camas = self._muebles("cama")
        self.azar.shuffle(camas)
        for i in camas:
            for lado in self.azar.sample((1, -1), 2):
                sx, sz = self._local(i, lado * 0.62, 0.05)
                if not self._libre(sx, sz, self.casa.ocupadas()) or not self._camino_libre(self._pos("bb"), (sx, sz)):
                    continue
                m = self.casa.datos["muebles"][i]
                pies = self._local(i, 0.0, 0.1)
                cabeza = self._local(i, 0.0, -0.42)
                hacia_la_cama = _rumbo(pies[0] - sx, pies[1] - sz)

                def acostarse(i=i, sx=sx, sz=sz, pies=pies, cabeza=cabeza, rot=m["rot"], hacia=hacia_la_cama):
                    if i >= len(self.casa.datos["muebles"]) or self.casa.datos["muebles"][i]["id"] != "cama":
                        return False
                    self.lugar["bb"] = {"tipo": "cama", "i": i, "x": pies[0], "z": pies[1], "rot": rot, "pose": ACOSTADO,
                                        "salida": (sx, sz), "rot_salida": (hacia + 180) % 360, "zzz": (cabeza[0], 0.5, cabeza[1])}
                    self.libre_desde["bb"] = time.monotonic() + self.azar.uniform(25, 45)
                    self.e.refrescar(suave=True)
                pasos = []
                lamparas = [j for j in self._muebles("lampara") if self.casa.datos["muebles"][j].get("on", True)]
                if lamparas and self.azar.random() < 0.75:      # antes de dormir apaga la luz
                    pasos += self._pasos_lampara(lamparas[0], prender=False)
                pasos += [self._ir("bb", (sx, sz)), self._mirar(hacia_la_cama), self._esperar(0.5), self._hacer(acostarse)]
                self._plan("bb", pasos)
                return True
        return False

    def _r_a_los_pies(self, quien):
        lugar = self.lugar["bb"]
        if not lugar or lugar.get("tipo") != "cama":
            return False
        i = lugar["i"]
        for lado in (1, -1):
            sx, sz = self._local(i, lado * 0.62, 0.45)
            if not self._libre(sx, sz, self.casa.ocupadas()) or not self._camino_libre(self._pos("mascota"), (sx, sz)):
                continue
            px, pz = self._local(i, 0.12 * lado, 0.5)
            rot = (self.casa.datos["muebles"][i]["rot"] + 90 * lado + 180) % 360

            def subirse(px=px, pz=pz, rot=rot, sx=sx, sz=sz):
                if not self.lugar["bb"]:
                    return False
                self.lugar["mascota"] = {"tipo": "cama", "x": px, "z": pz, "rot": rot, "y": 0.27, "pose": DORMIR_PET, "salida": (sx, sz)}
                self.libre_desde["mascota"] = time.monotonic() + self.azar.uniform(15, 30)
                self.e.refrescar(suave=True)
            self._plan("mascota", [self._ir("mascota", (sx, sz)), self._mirar((px, pz)), self._esperar(0.4, LADRAR), self._hacer(subirse)])
            return True
        return False

    # --- Las lámparas ----------------------------------------------------------------------------------------------
    def _pasos_lampara(self, i: int, prender: bool | None = None) -> list:
        x0, z0 = self.e.centro_mueble(self.casa.datos["muebles"][i])
        lugar = self._al_lado_de(x0, z0, 0.27, self._pos("bb"))
        if not lugar:
            return []

        def cambiar():
            if i < len(self.casa.datos["muebles"]) and self.casa.datos["muebles"][i]["id"] == "lampara":
                self.casa.lampara(i, prender)
                self.e.refrescar()
        return [self._ir("bb", lugar), self._mirar((x0, z0)), self._esperar(0.45, APUNTAR), self._hacer(cambiar),
                self._esperar(0.5, APUNTAR, seguir_pose=False)]

    def _r_lampara(self, quien):
        lamparas = self._muebles("lampara")
        if not lamparas:
            return False
        pasos = self._pasos_lampara(self.azar.choice(lamparas))
        if not pasos or not self._camino_libre(self._pos("bb"), pasos[0]["a"]):
            return False
        self._plan("bb", pasos)

    # --- El plato -------------------------------------------------------------------------------------------------
    def _r_llenar_plato(self, quien):
        p = self.casa.datos["plato"]
        lugar = self._al_lado_de(p["x"], p["z"], 0.2, self._pos("bb"))
        if not lugar or not self._camino_libre(self._pos("bb"), lugar):
            return False

        def llenar():
            self.plato_lleno = True
            self.e.refrescar()
            if self._mascota_libre():           # la mascota viene corriendo a comer
                self._r_comer("mascota", rapido=True)
        self._plan("bb", [self._ir("bb", lugar), self._mirar((p["x"], p["z"])), self._esperar(1.8, LLENAR), self._hacer(llenar),
                          self._esperar(0.6)])

    def _r_comer(self, quien, rapido=False):
        p = self.casa.datos["plato"]
        lugar = self._al_lado_de(p["x"], p["z"], 0.15, self._pos("mascota"))
        if not lugar or not self._camino_libre(self._pos("mascota"), lugar):
            return False

        def terminar():
            self.plato_lleno = False
            self.e.refrescar()
        self._plan("mascota", [self._ir("mascota", lugar, rapido), self._mirar((p["x"], p["z"])),
                               self._esperar(self.azar.uniform(3.5, 5.5), COMER), self._hacer(terminar), self._esperar(0.8, LADRAR)])

    # --- La pelota -------------------------------------------------------------------------------------------------
    def _mover_pelota(self, x: float, z: float):
        self.casa.datos["pelota"] = {"x": round(x, 3), "z": round(z, 3)}

    def _pelota_a_la_boca(self):
        quien = self.pelota_en
        x, z = self._pos(quien)
        th = math.radians(self.casa.datos[quien]["rot"])
        if quien == "mascota":
            self._mover_pelota(x + 0.17 * math.sin(th), z + 0.17 * math.cos(th))
            self.pelota_y = 0.1
        else:                               # en la mano derecha de BiriBiri
            self._mover_pelota(x + 0.11 * math.cos(th) + 0.06 * math.sin(th), z - 0.11 * math.sin(th) + 0.06 * math.cos(th))
            self.pelota_y = 0.16
        self._pelota_en_escena()

    def _pelota_en_escena(self):
        x, y, z, rumbo, giro = self.pelota()
        self.e.v.pose(pelotaX=x, pelotaY=y, pelotaZ=z, pelotaRumbo=rumbo, pelotaGiro=giro)

    def _lanzar(self, x1: float, z1: float, alto: float, rodar: bool):
        p = self.casa.datos["pelota"]
        dist = math.hypot(x1 - p["x"], z1 - p["z"])
        self.pelota_en = None
        self.pelota_rumbo = _rumbo(x1 - p["x"], z1 - p["z"])
        self.vuelo = {"x0": p["x"], "z0": p["z"], "y0": self.pelota_y, "x1": x1, "z1": z1, "alto": alto, "rodar": rodar,
                      "desde": time.monotonic(), "dur": max(0.35, dist / (1.7 if alto else 1.1)), "dist": dist}

    def _pelota_tic(self, ahora: float, dt: float):
        v = self.vuelo
        if not v:
            return
        s = min(1.0, (ahora - v["desde"]) / v["dur"])
        k = s if v["alto"] else 1 - (1 - s) ** 2          # en el aire va parejo; rodando, frena
        x = v["x0"] + (v["x1"] - v["x0"]) * k
        z = v["z0"] + (v["z1"] - v["z0"]) * k
        anterior = self.casa.datos["pelota"]
        avance = math.hypot(x - anterior["x"], z - anterior["z"])
        self._mover_pelota(x, z)
        self.pelota_y = (v["y0"] * (1 - s) + 4 * v["alto"] * s * (1 - s)) if v["alto"] else 0.0
        self.pelota_giro = (self.pelota_giro + math.degrees(avance / RADIO_PELOTA)) % 360
        self._pelota_en_escena()
        if s >= 1:
            self.vuelo = None
            self.pelota_y = 0.0
            if v["rodar"]:                    # cae y rueda un poquito más
                th = math.radians(self.pelota_rumbo)
                x2, z2 = v["x1"] + 0.18 * math.sin(th), v["z1"] + 0.18 * math.cos(th)
                if self._libre(x2, z2, self.casa.ocupadas()):
                    self._lanzar(x2, z2, 0.0, False)
                    return
            self._pelota_en_escena()
            self.marcas.add("cayó")
            self.casa.guardar()

    def _destino_pelota(self, desde, lejos=(0.7, 1.3)) -> tuple[float, float] | None:
        ocupadas = self.casa.ocupadas()
        for _ in range(30):
            ang = self.azar.uniform(0, 2 * math.pi)
            r = self.azar.uniform(*lejos)
            x, z = desde[0] + r * math.sin(ang), desde[1] + r * math.cos(ang)
            if (self._libre(x, z, ocupadas) and self._libre(x + 0.25 * math.sin(ang), z + 0.25 * math.cos(ang), ocupadas)
                    and self._camino_libre(desde, (x, z))):
                return x, z
        return None

    def _r_jugar_pelota(self, quien, vueltas: int | None = None):
        """La mascota sola: va hasta la pelota, la empuja con el hocico y la persigue (unas cuantas veces)."""
        vueltas = vueltas or self.azar.randint(2, 4)
        if self.pelota_en or self.vuelo:
            return False
        p = self.casa.datos["pelota"]
        destino = self._destino_pelota((p["x"], p["z"]))
        if not destino:
            return False
        th = math.atan2(destino[0] - p["x"], destino[1] - p["z"])
        atras = (p["x"] - 0.13 * math.sin(th), p["z"] - 0.13 * math.cos(th))
        if not self._libre(*atras, self.casa.ocupadas()) or not self._camino_libre(self._pos("mascota"), atras):
            return False

        def empujar(destino=destino):
            self.marcas.discard("cayó")
            self._lanzar(destino[0], destino[1], 0.0, False)

        def otra():
            if vueltas > 1:
                self._r_jugar_pelota("mascota", vueltas - 1)
        self._plan("mascota", [self._ir("mascota", atras, rapido=True), self._mirar((p["x"], p["z"])), self._esperar(0.3, LADRAR),
                               self._hacer(empujar), self._esperar(0.25),
                               self._ir("mascota", lambda: self._al_lado_de(self.casa.datos["pelota"]["x"], self.casa.datos["pelota"]["z"],
                                                                           0.14, self._pos("mascota")), rapido=True),
                               self._mirar(lambda: (self.casa.datos["pelota"]["x"], self.casa.datos["pelota"]["z"])),
                               self._esperar(0.6, LADRAR), self._hacer(otra)])

    def _r_tirar_pelota(self, quien, vueltas: int | None = None):
        """BiriBiri le tira la pelota y la mascota se la trae (dos o tres veces)."""
        if self.pelota_en or self.vuelo or not self._mascota_libre():
            return False
        vueltas = vueltas or self.azar.randint(2, 3)
        p = self.casa.datos["pelota"]
        bb = self._pos("bb")
        pasos = []
        if math.hypot(p["x"] - bb[0], p["z"] - bb[1]) > 0.2:           # primero la va a buscar
            lugar = self._al_lado_de(p["x"], p["z"], 0.14, bb)
            if not lugar or not self._camino_libre(bb, lugar):
                return False
            bb = lugar

            def agarrar():
                self.pelota_en = "bb"
                self._pelota_a_la_boca()
            pasos += [self._ir("bb", lugar), self._mirar((p["x"], p["z"])), self._esperar(0.6, LEVANTAR), self._hacer(agarrar)]
        else:
            pasos.append(self._hacer(lambda: (setattr(self, "pelota_en", "bb"), self._pelota_a_la_boca())))
        destino = self._destino_pelota(bb, (0.8, 1.4))
        if not destino:
            return False
        self.marcas -= {"cayó", "trajo"}

        def tirar():
            self.marcas.discard("cayó")
            self._lanzar(destino[0], destino[1], 0.32, True)
        pasos += [self._mirar(destino), self._esperar(0.45, TIRAR), self._hacer(tirar), self._esperar(0.4, APUNTAR),
                  self._esperar(12, hasta=lambda: "trajo" in self.marcas),
                  self._mirar(lambda: self._pos("mascota")), self._esperar(1.0)]
        if vueltas > 1:
            pasos.append(self._hacer(lambda: self._r_tirar_pelota("bb", vueltas - 1) is not False or None))
        self._plan("bb", pasos)

        # la mascota: espera mirando, corre cuando cae, la agarra y se la lleva
        def agarrarla():
            self.pelota_en = "mascota"
            self._pelota_a_la_boca()

        def soltarla():
            self.pelota_en = None
            self.pelota_y = 0.0
            self._pelota_en_escena()
            self.casa.guardar()
            self.marcas.add("trajo")
        pelota = lambda: (self.casa.datos["pelota"]["x"], self.casa.datos["pelota"]["z"])      # noqa: E731
        cerca_bb = self._al_lado_de(bb[0], bb[1], 0.3, destino)
        if not cerca_bb:
            self._plan("bb", [])
            return False
        self._plan("mascota", [
            self._ir("mascota", lambda: self._al_lado_de(bb[0], bb[1], 0.35, self._pos("mascota"))),
            self._mirar(bb), self._esperar(14, LADRAR, hasta=lambda: "cayó" in self.marcas),
            self._ir("mascota", lambda: self._al_lado_de(*pelota(), 0.15, self._pos("mascota")), rapido=True),
            self._mirar(pelota), self._esperar(0.35, {"petCabX": 30}), self._hacer(agarrarla),
            self._ir("mascota", lambda: self._al_lado_de(bb[0], bb[1], 0.3, self._pos("mascota")), rapido=True),
            self._mirar(lambda: self._pos("bb")), self._esperar(0.3, {"petCabX": 26}), self._hacer(soltarla),
            self._esperar(0.4, LADRAR)])

    # --- Mimos -----------------------------------------------------------------------------------------------------
    def _r_mimos(self, quien):
        """La mascota viene al lado derecho de BiriBiri y él le hace mimos un rato (con corazones)."""
        bx, bz = self._pos("bb")
        rot = self.casa.datos["bb"]["rot"]
        th = math.radians(rot)
        lx, lz = 0.25, 0.06
        x, z = bx + lx * math.cos(th) + lz * math.sin(th), bz - lx * math.sin(th) + lz * math.cos(th)
        if not self._libre(x, z, self.casa.ocupadas()) or not self._camino_libre(self._pos("mascota"), (x, z)):
            return False
        bb_mimos, pet_mimos = poses.interaccion("acariciar", "perro")
        pet_mimos = {k: v for k, v in pet_mimos.items() if k not in ("petPos", "petZ", "petRotY", "petEsc", "comida", "texto")}
        segundos = self.azar.uniform(4, 7)
        self.marcas.discard("al lado")
        self._plan("bb", [self._esperar(10, hasta=lambda: "al lado" in self.marcas, suave=False),
                          self._esperar(segundos, {**NEUTRO, **bb_mimos})])
        self._plan("mascota", [self._ir("mascota", (x, z)), self._mirar(rot - 28), self._hacer(lambda: self.marcas.add("al lado")),
                               self._esperar(segundos, pet_mimos)])
