"""La habitación en pantalla: conecta el modelo (casa.py) con la escena 3D (vista3d.py). Se encarga de armar los muebles en
segundo plano, de mostrar el piso y las paredes, y de lo que se hace con el mouse: arrastrar muebles, a BiriBiri y a su
mascota, y poner un mueble nuevo del inventario."""
from __future__ import annotations

import math

from PySide6.QtCore import QObject, QUrl, Signal

from . import casa as modelo
from . import muebles, vista3d
from .tareas import en_segundo_plano

CELDA = modelo.CELDA
HIP = 0.42 * 0.74 * 0.62       # altura de la cadera de BiriBiri en la habitación (cuerpo × escala de casa)
# Alto de la caja invisible con la que se agarra cada mueble
ALTOS = {"sillon": 0.55, "silla_gamer": 1.0, "mesa": 0.25, "lampara": 0.85, "tele": 0.78, "planta": 0.5, "alfombra": 0.03,
         "estante": 0.95, "cama": 0.55, "heladera": 1.0}


def _url(ruta) -> str:
    return QUrl.fromLocalFile(str(ruta)).toString()


class EscenaCasa(QObject):
    cambio = Signal()       # cambió algo que los paneles tienen que mostrar (selección, inventario, monedas…)

    def __init__(self, vista, casa: modelo.Casa):
        super().__init__()
        self.v = vista
        self.casa = casa
        self.carpeta = vista3d.CARPETA / "casa"
        self.seleccion: int | None = None
        self.colocando: dict | None = None      # {"item", "color", "rot"}: un mueble del inventario que se está por poner
        self._arrastre: dict | None = None
        self._construyendo: set[tuple[str, str]] = set()
        self._temporal: dict[int, tuple[int, int]] = {}      # el mueble que se está arrastrando, en su lugar de ahora
        vista.casa_evento.connect(self._evento)
        self.refrescar()

    # --- Lo que se ve --------------------------------------------------------------------------------------
    def _acabado(self, tabla: dict, clave: str, prefijo: str) -> tuple[str, str]:
        _nombre, _precio, c1, dibujo, c2 = tabla[clave]
        if dibujo == "liso":
            return "", c1
        return _url(muebles.textura(f"{prefijo}_{clave}", dibujo, c1, c2, self.carpeta)), c1

    def _construir(self, item: str, color: str):
        clave = (item, color)
        if clave in self._construyendo:
            return
        self._construyendo.add(clave)
        en_segundo_plano(lambda: str(muebles.construir(item, color, self.carpeta)), lambda _r: self.refrescar(), lambda _e: None)

    def _lista_muebles(self) -> list[dict]:
        lista = []
        for i, m in enumerate(self.casa.datos["muebles"]):
            cx, cz = self._temporal.get(i, (m["cx"], m["cz"]))
            w, p = modelo.celdas_girado(m["id"], m["rot"])
            ancho, fondo = modelo.CATALOGO[m["id"]]["celdas"]
            glb = muebles.archivo(m["id"], m["color"], self.carpeta)
            if not glb.exists():
                self._construir(m["id"], m["color"])
            lista.append({"src": _url(glb) if glb.exists() else "", "x": (cx + w / 2 - modelo.COLUMNAS / 2) * CELDA,
                          "z": (cz + p / 2 - modelo.FILAS / 2) * CELDA, "rot": m["rot"], "i": i, "w": ancho * CELDA,
                          "d": fondo * CELDA, "h": ALTOS.get(m["id"], 0.6)})
        return lista

    def refrescar(self):
        d = self.casa.datos
        pt, pc = self._acabado(modelo.PISOS, d["piso"], "piso")
        at, ac = self._acabado(modelo.PAREDES, d["pared"], "pared")
        bx, bz = modelo.celda_a_mundo(d["bb"]["cx"], d["bb"]["cz"])
        mx, mz = modelo.celda_a_mundo(d["mascota"]["cx"], d["mascota"]["cz"])
        brot = float(d["bb"]["rot"])
        self.v._casa_pet = {"petPos": mx, "petZ": mz, "petRotY": float(d["mascota"]["rot"]), "petY": 0.0}
        self.v._casa_bb = {}
        s = d["sentado"]
        asiento_bb = self._asiento(s["bb"])
        if asiento_bb:                  # BiriBiri sentado: con las piernas para adelante y las manos sobre las piernas
            bx, y, bz, brot = asiento_bb
            self.v._casa_bb = {"liX": -90, "ldX": -90, "aiX": -42, "aiZ": -9, "adX": -42, "adZ": 9, "reposo": 0.3,
                               "pY": y + 0.02 - HIP, "sombra": False}
        asiento_pet = self._asiento(s["mascota"])
        if s["falda"] and asiento_bb:   # la mascota en la falda
            adelante = 0.1
            th = math.radians(brot)
            self.v._casa_pet = {"petPos": bx + adelante * math.sin(th), "petZ": bz + adelante * math.cos(th), "petRotY": brot,
                                "petY": asiento_bb[1] + 0.05}
        elif asiento_pet:               # la mascota sentada en su lugar (se hunde un poco en el almohadón)
            self.v._casa_pet = {"petPos": asiento_pet[0], "petZ": asiento_pet[2], "petRotY": asiento_pet[3], "petY": asiento_pet[1] - 0.02}
        self.v.repose()
        self.v.pose(pisoTex=pt, pisoColor=pc, paredTex=at, paredColor=ac, muebles=self._lista_muebles(), bbX=bx, bbZ=bz,
                    bbRot=brot, **self.v._casa_pet)
        self._marcar()
        self.cambio.emit()

    def _asiento(self, lugar) -> tuple[float, float, float, float] | None:
        """(x, alto, z, giro) del lugar donde está sentado alguien, o None si está parado."""
        if not lugar:
            return None
        i, plaza = lugar
        m = self.casa.datos["muebles"][i]
        lx, ly, lz = modelo.PLAZAS[m["id"]][plaza]
        cx, cz = self._temporal.get(i, (m["cx"], m["cz"]))
        w, p = modelo.celdas_girado(m["id"], m["rot"])
        x0, z0 = (cx + w / 2 - modelo.COLUMNAS / 2) * CELDA, (cz + p / 2 - modelo.FILAS / 2) * CELDA
        th = math.radians(m["rot"])
        return x0 + lx * math.cos(th) + lz * math.sin(th), ly, z0 - lx * math.sin(th) + lz * math.cos(th), float(m["rot"])

    def _marcar(self, fantasma: tuple[str, int, int, int] | None = None, ok: bool = True):
        """El cuadrado de abajo: el del mueble elegido, o el fantasma del que se está por poner."""
        if fantasma:
            item, cx, cz, rot = fantasma
            w, p = modelo.celdas_girado(item, rot)
            self.v.pose(selVis=True, selFantasma=True, selOk=ok, selX=(cx + w / 2 - modelo.COLUMNAS / 2) * CELDA,
                        selZ=(cz + p / 2 - modelo.FILAS / 2) * CELDA, selW=w * CELDA, selD=p * CELDA)
            return
        if self.seleccion is not None and self.seleccion < len(self.casa.datos["muebles"]):
            m = self.casa.datos["muebles"][self.seleccion]
            cx, cz = self._temporal.get(self.seleccion, (m["cx"], m["cz"]))
            w, p = modelo.celdas_girado(m["id"], m["rot"])
            self.v.pose(selVis=True, selFantasma=False, selOk=ok, selX=(cx + w / 2 - modelo.COLUMNAS / 2) * CELDA,
                        selZ=(cz + p / 2 - modelo.FILAS / 2) * CELDA, selW=w * CELDA, selD=p * CELDA)
        else:
            self.v.pose(selVis=False)

    # --- Acciones de los paneles ---------------------------------------------------------------------------
    def empezar_colocar(self, item: str, color: str):
        self.seleccion = None
        self.colocando = {"item": item, "color": color, "rot": 0}
        self._marcar()
        self.cambio.emit()

    def cancelar(self):
        self.colocando = None
        self._arrastre = None
        self._temporal.clear()
        self.refrescar()

    def girar(self):
        if self.colocando:
            self.colocando["rot"] = (self.colocando["rot"] + 90) % 360
        elif self.seleccion is not None:
            self.casa.girar_mueble(self.seleccion)
            self.refrescar()

    def puede_sentar(self) -> int:
        """Cuántos lugares tiene el mueble elegido (0 si no se puede sentar nadie)."""
        return self.casa.plazas(self.seleccion) if self.mueble_seleccionado() else 0

    def sentar(self, quien: str):
        if self.mueble_seleccionado() and self.casa.sentar(quien, self.seleccion, 0 if quien == "bb" else min(1, self.puede_sentar() - 1)):
            self.casa.datos["sentado"]["falda"] = False
            self.casa.guardar()
            self.refrescar()

    def sentar_los_dos(self):
        """Cada uno en su lugar si hay dos lugares; si hay uno, BiriBiri sentado con la mascota en la falda."""
        if not self.mueble_seleccionado():
            return
        if self.puede_sentar() >= 2:
            self.casa.sentar("bb", self.seleccion, 0)
            self.casa.sentar("mascota", self.seleccion, 1)
            self.casa.datos["sentado"]["falda"] = False
        else:
            self.casa.sentar("bb", self.seleccion, 0)
            self.casa.datos["sentado"]["falda"] = True
            self.casa.datos["sentado"]["mascota"] = None
        self.casa.guardar()
        self.refrescar()

    def falda(self):
        """BiriBiri sentado con la mascota en la falda."""
        if self.mueble_seleccionado() and self.casa.sentar("bb", self.seleccion, 0):
            self.casa.datos["sentado"]["falda"] = True
            self.casa.datos["sentado"]["mascota"] = None
            self.casa.guardar()
            self.refrescar()

    def parar_a_todos(self):
        self.casa.parar()
        self.refrescar()

    def guardar_seleccionado(self):
        if self.seleccion is not None:
            self.casa.guardar_mueble(self.seleccion)
            self.seleccion = None
            self.refrescar()

    def pintar_seleccionado(self, color: str):
        if self.seleccion is not None and self.casa.pintar_mueble(self.seleccion, color):
            self.refrescar()

    def mueble_seleccionado(self) -> dict | None:
        if self.seleccion is not None and self.seleccion < len(self.casa.datos["muebles"]):
            return self.casa.datos["muebles"][self.seleccion]
        return None

    # --- El mouse ------------------------------------------------------------------------------------------
    @staticmethod
    def _celda(x: float, z: float, w: int, p: int, dx: float = 0.0, dz: float = 0.0) -> tuple[int, int]:
        """La celda de arriba a la izquierda para que el mueble (de w × p celdas) quede centrado donde está el mouse."""
        cx = round(x / CELDA + modelo.COLUMNAS / 2 - dx - w / 2)
        cz = round(z / CELDA + modelo.FILAS / 2 - dz - p / 2)
        return max(0, min(modelo.COLUMNAS - w, cx)), max(0, min(modelo.FILAS - p, cz))

    def _evento(self, tipo: str, x: float, z: float, indice: int):
        d = self.casa.datos
        if tipo == "press_fuera" or tipo == "release_fuera":
            if tipo == "release_fuera" and self._arrastre:
                self._soltar()
            return
        if tipo.endswith("_fuera"):
            return
        # Poniendo un mueble nuevo
        if self.colocando:
            c = self.colocando
            w, p = modelo.celdas_girado(c["item"], c["rot"])
            cx, cz = self._celda(x, z, w, p)
            ok = self.casa.cabe(c["item"], cx, cz, c["rot"])
            if tipo in ("mover", "arrastre"):
                self._marcar((c["item"], cx, cz, c["rot"]), ok)
            elif tipo == "press" and ok:
                i = self.casa.poner_mueble(c["item"], cx, cz, c["rot"], c["color"])
                if i is not None:
                    if d["inventario"].get(c["item"], 0) < 1:
                        self.colocando = None
                    self.seleccion = i
                    self.refrescar()
            return
        if tipo == "press":
            if indice >= 0 and indice < len(d["muebles"]):
                m = d["muebles"][indice]
                w, p = modelo.celdas_girado(m["id"], m["rot"])
                self.seleccion = indice
                self._arrastre = {"tipo": "mueble", "i": indice, "dx": x / CELDA + modelo.COLUMNAS / 2 - (m["cx"] + w / 2),
                                  "dz": z / CELDA + modelo.FILAS / 2 - (m["cz"] + p / 2), "ok": True}
            elif indice in (-2, -3):
                quien = "bb" if indice == -2 else "mascota"
                self._arrastre = {"tipo": quien}
                d["sentado"]["falda"] = False          # agarrarlos los levanta (y la mascota se baja de la falda)
                self.casa.parar(quien)
                self.seleccion = None
            else:
                self.seleccion = None
            self._marcar()
            self.cambio.emit()
        elif tipo == "arrastre" and self._arrastre:
            a = self._arrastre
            if a["tipo"] == "mueble":
                m = d["muebles"][a["i"]]
                w, p = modelo.celdas_girado(m["id"], m["rot"])
                cx, cz = self._celda(x, z, w, p, a["dx"], a["dz"])
                a["ok"] = self.casa.cabe(m["id"], cx, cz, m["rot"], sin=a["i"])
                self._temporal = {a["i"]: (cx, cz)}
                self.v.pose(muebles=self._lista_muebles())
                self._marcar(ok=a["ok"])
            else:
                quien = "bb" if a["tipo"] == "bb" else "mascota"
                cx = max(0.0, min(modelo.COLUMNAS - 1.0, x / CELDA + modelo.COLUMNAS / 2 - 0.5))
                cz = max(0.0, min(modelo.FILAS - 1.0, z / CELDA + modelo.FILAS / 2 - 0.5))
                d[quien]["cx"], d[quien]["cz"] = cx, cz
                px, pz = modelo.celda_a_mundo(cx, cz)
                if quien == "bb":
                    self.v.pose(bbX=px, bbZ=pz)
                else:
                    self.v._casa_pet.update(petPos=px, petZ=pz)
                    self.v.pose(petPos=px, petZ=pz)
        elif tipo == "release" and self._arrastre:
            self._arrastre["sobre"] = indice
            self._soltar()

    def _soltar(self):
        a, self._arrastre = self._arrastre, None
        if a and a["tipo"] == "mueble":
            nuevo = self._temporal.pop(a["i"], None)
            self._temporal.clear()
            if nuevo and a.get("ok"):
                self.casa.mover_mueble(a["i"], *nuevo)
        elif a:
            sobre = a.get("sobre", -1)
            if 0 <= sobre < len(self.casa.datos["muebles"]) and self.casa.plazas(sobre):
                self.casa.sentar(a["tipo"], sobre, 0)
            self.casa.guardar()
        self.refrescar()
