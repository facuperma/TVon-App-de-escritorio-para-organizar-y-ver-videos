"""Vida propia de BiriBiri y su mascota en la videoteca: una pequeña «IA» local, sin internet ni modelos, hecha de rutinas.

Cada uno decide cada tanto qué hacer: pasear hasta un lugar libre (caminando, mirando hacia donde va y sin atravesar
muebles), ir a sentarse solo en un sillón o en la silla, quedarse quieto un rato, o (BiriBiri) llamar a la mascota para
hacerle mimos; la mascota además lo sigue, se le sube a la falda cuando está sentado, o se sienta a su lado. Mientras
arrastrás algo, acomodás muebles o editás a BiriBiri, esperan."""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QObject, QTimer

from . import casa as modelo
from . import poses

CELDA, SUB = modelo.CELDA, modelo.SUB
VELOCIDAD = {"bb": 0.34, "mascota": 0.46}        # metros por segundo (BiriBiri mide 0,62 en la habitación)
CAMINAR_BB = {"ampBx": 24, "ampP": 28, "ritmo": 9, "reposo": 0, "ampS": 0.006}
LIMITES = (-1.55, 1.55, -0.95, 1.05)             # x mínimo, x máximo, z mínimo, z máximo por donde se camina


def _a_celda(x: float, z: float) -> tuple[float, float]:
    return x / CELDA + modelo.COLUMNAS / 2 - 0.5, z / CELDA + modelo.FILAS / 2 - 0.5


class Vida(QObject):
    def __init__(self, escena, casa: modelo.Casa, con_mascota=lambda: True):
        super().__init__()
        self.e = escena
        self.casa = casa
        self.con_mascota = con_mascota
        self.azar = random.Random()
        ahora = time.monotonic()
        self.estado = {q: {"modo": "quieto", "hasta": ahora + self.azar.uniform(2, 5), "destino": None, "luego": None}
                       for q in ("bb", "mascota")}
        self.jugando_hasta = 0.0
        self._ultimo = ahora
        self.reloj = QTimer(self, interval=40, timeout=self._tic)
        self.reloj.start()
        escena.vida = self

    # --- Lo que agregan a la pose de la escena ------------------------------------------------------------
    def extra_bb(self) -> dict:
        if self.jugando_hasta > time.monotonic():
            return poses.interaccion("acariciar", "perro")[0]
        if self.estado["bb"]["modo"] == "camina":
            return dict(CAMINAR_BB)
        return {}

    def extra_pet(self) -> dict:
        if self.jugando_hasta > time.monotonic():
            pet = poses.interaccion("acariciar", "perro")[1]
            return {k: v for k, v in pet.items() if k not in ("petPos", "petZ", "petRotY", "petEsc", "comida", "texto")}
        if self.estado["mascota"]["modo"] == "camina":
            return {"petSalto": 0.014, "petRitmo": 11, "petCola": 30}
        return {}

    @property
    def activa(self) -> bool:
        return bool(self.casa.datos.get("vida", True))

    def poner_activa(self, si: bool):
        self.casa.datos["vida"] = bool(si)
        self.casa.guardar()
        if not si:
            for q in self.estado:
                self._quieto(q, 3, 6)
            self.jugando_hasta = 0
            self.e.refrescar()

    def soltar_control(self, quien: str):
        """Lo agarraste con el mouse: se queda donde lo dejes un rato."""
        self._quieto(quien, 8, 14)
        self.jugando_hasta = 0

    # --- El reloj ----------------------------------------------------------------------------------------
    def _tic(self):
        ahora = time.monotonic()
        dt = min(0.1, ahora - self._ultimo)
        self._ultimo = ahora
        if not self.activa or self.e.ocupado or not self.e.v.isVisible():
            return
        if self.jugando_hasta and ahora >= self.jugando_hasta:
            self.jugando_hasta = 0
            self._quieto("bb", 3, 6)
            self._quieto("mascota", 2, 5)
            self.e.refrescar()
        for quien in ("bb", "mascota"):
            if quien == "mascota" and not self.con_mascota():
                continue
            st = self.estado[quien]
            if st["modo"] == "camina":
                self._caminar(quien, dt)
            elif st["modo"] != "juega" and ahora >= st["hasta"]:
                self._decidir(quien)

    def _pos(self, quien: str) -> tuple[float, float]:
        d = self.casa.datos[quien]
        return modelo.celda_a_mundo(d["cx"], d["cz"])

    def _poner(self, quien: str, x: float, z: float, rot: float | None = None):
        cx, cz = _a_celda(x, z)
        d = self.casa.datos[quien]
        d["cx"], d["cz"] = cx, cz
        if rot is not None:
            d["rot"] = int(rot)
        if quien == "bb":
            self.e.v.pose(bbX=x, bbZ=z, bbRot=float(d["rot"]))
        else:
            self.e.v._casa_pet.update(petPos=x, petZ=z, petRotY=float(d["rot"]))
            self.e.v.pose(petPos=x, petZ=z, petRotY=float(d["rot"]))

    def _caminar(self, quien: str, dt: float):
        st = self.estado[quien]
        x, z = self._pos(quien)
        tx, tz = st["destino"]
        dx, dz = tx - x, tz - z
        dist = math.hypot(dx, dz)
        paso = VELOCIDAD[quien] * dt
        if dist <= paso:
            self._poner(quien, tx, tz, math.degrees(math.atan2(dx, dz)) if dist > 1e-3 else None)
            luego = st["luego"]
            self._quieto(quien, 2, 5)
            self.casa.guardar()
            if luego:
                luego()
            self.e.refrescar()
            return
        self._poner(quien, x + dx / dist * paso, z + dz / dist * paso, math.degrees(math.atan2(dx, dz)))

    def _quieto(self, quien: str, desde: float, hasta: float):
        self.estado[quien] = {"modo": "quieto", "hasta": time.monotonic() + self.azar.uniform(desde, hasta), "destino": None,
                              "luego": None}

    def _ir(self, quien: str, x: float, z: float, luego=None) -> bool:
        if not self._camino_libre(self._pos(quien), (x, z)):
            return False
        self.estado[quien] = {"modo": "camina", "hasta": 0, "destino": (x, z), "luego": luego}
        self.e.refrescar()          # que se ponga a caminar (brazos y piernas)
        return True

    # --- Dónde se puede pisar ---------------------------------------------------------------------------
    def _libre(self, x: float, z: float, ocupadas: set) -> bool:
        if not (LIMITES[0] <= x <= LIMITES[1] and LIMITES[2] <= z <= LIMITES[3]):
            return False
        sx = int((x / CELDA + modelo.COLUMNAS / 2) * SUB)
        sz = int((z / CELDA + modelo.FILAS / 2) * SUB)
        return (sx, sz) not in ocupadas

    def _camino_libre(self, desde, hasta) -> bool:
        ocupadas = self.casa.ocupadas()
        (x0, z0), (x1, z1) = desde, hasta
        dist = math.hypot(x1 - x0, z1 - z0)
        pasos = max(1, int(dist / 0.07))
        return all(self._libre(x0 + (x1 - x0) * k / pasos, z0 + (z1 - z0) * k / pasos, ocupadas) for k in range(1, pasos + 1))

    def _lugar_al_azar(self) -> tuple[float, float] | None:
        ocupadas = self.casa.ocupadas()
        for _ in range(20):
            x, z = self.azar.uniform(*LIMITES[:2]), self.azar.uniform(*LIMITES[2:])
            if self._libre(x, z, ocupadas) and self._camino_libre(self._pos("bb"), (x, z)):
                return x, z
        return None

    def _asientos_libres(self) -> list[tuple[int, int]]:
        tomados = {tuple(v) for v in (self.casa.datos["sentado"]["bb"], self.casa.datos["sentado"]["mascota"]) if v}
        libres = []
        for i, m in enumerate(self.casa.datos["muebles"]):
            for plaza in range(len(modelo.PLAZAS.get(m["id"], []))):
                if (i, plaza) not in tomados:
                    libres.append((i, plaza))
        return libres

    # --- Qué hace cada uno ------------------------------------------------------------------------------
    def _decidir(self, quien: str):
        sentado = self.casa.datos["sentado"]
        if sentado[quien] or (quien == "mascota" and sentado["falda"]):
            self._levantarse(quien)
            return
        opciones = ["pasear", "pasear", "pasear", "sentarse", "quieto"]
        if quien == "bb" and self.con_mascota() and not sentado["mascota"] and not sentado["falda"]:
            opciones += ["mimos", "mimos"]
        if quien == "mascota":
            opciones += ["seguir", "seguir", "seguir"]
            if sentado["bb"]:
                opciones += ["falda", "falda"]
        eleccion = self.azar.choice(opciones)
        if eleccion == "sentarse" and self._ir_a_sentarse(quien):
            return
        if eleccion == "mimos" and self._mimos():
            return
        if eleccion == "seguir" and self._seguir():
            return
        if eleccion == "falda" and not sentado["falda"]:
            sentado["falda"] = True
            sentado["mascota"] = None
            self.casa.guardar()
            self._quieto(quien, 10, 18)
            self.e.refrescar()
            return
        if eleccion in ("pasear", "sentarse", "mimos", "seguir"):
            lugar = self._lugar_al_azar()
            if lugar and self._ir(quien, *lugar):
                return
        self._quieto(quien, 3, 7)

    def _ir_a_sentarse(self, quien: str) -> bool:
        libres = self._asientos_libres()
        self.azar.shuffle(libres)
        for i, plaza in libres:
            x, z, _rot = self.e.frente_del_asiento(i, plaza)
            if not self._libre(x, z, self.casa.ocupadas()):
                continue

            def sentarse(i=i, plaza=plaza):
                if (i, plaza) in self._asientos_libres() and self.casa.sentar(quien, i, plaza):
                    self._quieto(quien, 12, 25)
            if self._ir(quien, x, z, sentarse):
                return True
        return False

    def _levantarse(self, quien: str):
        sentado = self.casa.datos["sentado"]
        lugar = sentado[quien]
        if lugar:
            x, z, rot = self.e.frente_del_asiento(*lugar)
        else:                       # la mascota se baja de la falda: al lado de BiriBiri
            x, z = self._pos("bb")
            x, rot = x + 0.25, 0.0
        if quien == "bb":
            sentado["falda"] = False
        self.casa.parar(quien)
        cx, cz = _a_celda(x, z)
        self.casa.datos[quien].update(cx=cx, cz=cz, rot=int(rot))
        self.casa.guardar()
        self._quieto(quien, 2, 5)
        self.e.refrescar()

    def _seguir(self) -> bool:
        bx, bz = self._pos("bb")
        ang = self.azar.uniform(0, 2 * math.pi)
        x, z = bx + 0.3 * math.cos(ang), bz + 0.3 * math.sin(ang)
        return self._libre(x, z, self.casa.ocupadas()) and self._ir("mascota", x, z)

    def _mimos(self) -> bool:
        """La mascota viene al lado derecho de BiriBiri y él le hace mimos un rato (con corazones)."""
        bx, bz = self._pos("bb")
        rot = self.casa.datos["bb"]["rot"]
        th = math.radians(rot)
        lx, lz = 0.25, 0.06
        x, z = bx + lx * math.cos(th) + lz * math.sin(th), bz - lx * math.sin(th) + lz * math.cos(th)
        if not self._libre(x, z, self.casa.ocupadas()):
            return False

        def jugar():
            self.casa.datos["mascota"]["rot"] = int(rot - 28)
            self.jugando_hasta = time.monotonic() + self.azar.uniform(4, 7)
            self.estado["bb"]["modo"] = self.estado["mascota"]["modo"] = "juega"
        self._quieto("bb", 30, 30)              # espera a la mascota
        return self._ir("mascota", x, z, jugar)
