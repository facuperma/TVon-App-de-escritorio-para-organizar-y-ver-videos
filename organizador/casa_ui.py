"""La habitación en pantalla: conecta el modelo (casa.py) con la escena 3D (vista3d.py). Arma los muebles en segundo plano,
muestra el piso, las paredes y los adornos, y se encarga de lo que se hace con el mouse: arrastrar muebles (con la
cuadrícula de medias celdas a la vista), adornos y la bandera por la pared, a BiriBiri y a su mascota (soltarlos sobre un
sillón los sienta), y poner un mueble nuevo del inventario. También el «probador»: mientras se edita a BiriBiri, la
habitación se vacía y quedan los dos parados en el medio, para verlos bien."""
from __future__ import annotations

import math

from PySide6.QtCore import QObject, QUrl, Signal

from . import casa as modelo
from . import muebles, vista3d
from .tareas import en_segundo_plano

CELDA = modelo.CELDA
SUB = modelo.SUB
HIP = 0.42 * 0.74 * 0.62       # altura de la cadera de BiriBiri en la habitación (cuerpo × escala de casa)
# Alto de la caja invisible con la que se agarra cada mueble
ALTOS = {"sillon": 0.55, "silla_gamer": 1.0, "mesa": 0.25, "lampara": 0.85, "tele": 0.78, "planta": 0.5, "alfombra": 0.03,
         "estante": 0.95, "cama": 0.55, "heladera": 1.0}
SIN_MARCO = ("reloj", "espejo", "guirnalda", "ventana")       # adornos que no llevan un marco de madera atrás
ADORNO = 1000                  # los índices de los adornos en la escena empiezan acá (los de muebles, en 0)


def _url(ruta) -> str:
    return QUrl.fromLocalFile(str(ruta)).toString()


def _nan(v: float) -> bool:
    return v != v


class EscenaCasa(QObject):
    cambio = Signal()       # cambió algo que los paneles tienen que mostrar (selección, inventario, monedas…)

    def __init__(self, vista, casa: modelo.Casa, solo_mirar: bool = False):
        super().__init__()
        self.v = vista
        self.casa = casa
        self.solo_mirar = solo_mirar            # la casa de un amigo: se mira, no se toca
        self.carpeta = vista3d.CARPETA / "casa"
        self.seleccion: int | None = None       # el mueble elegido
        self.sel_adorno: int | None = None      # o el adorno elegido
        self.colocando: dict | None = None      # {"item", "color", "rot"}: un mueble del inventario que se está por poner
        self.probador = False
        self._arrastre: dict | None = None
        self._construyendo: set[tuple[str, str]] = set()
        self._temporal: dict[int, tuple[float, float]] = {}      # el mueble que se está arrastrando, en su lugar de ahora
        self.vida = None                         # la vida propia de los personajes (vida.py), si la tienen
        vista.casa_evento.connect(self._evento)
        self.v.pose(grillaTex=_url(muebles.textura_grilla(self.carpeta)))
        self.refrescar()

    @property
    def ocupado(self) -> bool:
        """¿Se está haciendo algo con el mouse? (la vida propia espera)"""
        return bool(self._arrastre or self.colocando or self.probador)

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

    @staticmethod
    def centro_mueble(m: dict, cx: float | None = None, cz: float | None = None) -> tuple[float, float]:
        cx = m["cx"] if cx is None else cx
        cz = m["cz"] if cz is None else cz
        w, p = modelo.celdas_girado(m["id"], m["rot"])
        return (cx + w / 2 - modelo.COLUMNAS / 2) * CELDA, (cz + p / 2 - modelo.FILAS / 2) * CELDA

    def _lista_muebles(self) -> list[dict]:
        if self.probador:
            return []
        lista = []
        for i, m in enumerate(self.casa.datos["muebles"]):
            cx, cz = self._temporal.get(i, (m["cx"], m["cz"]))
            ancho, fondo = modelo.CATALOGO[m["id"]]["celdas"]
            glb = muebles.archivo(m["id"], m["color"], self.carpeta)
            if not glb.exists():
                self._construir(m["id"], m["color"])
            x, z = self.centro_mueble(m, cx, cz)
            lista.append({"src": _url(glb) if glb.exists() else "", "x": x, "z": z, "rot": m["rot"], "i": i, "w": ancho * CELDA,
                          "d": fondo * CELDA, "h": ALTOS.get(m["id"], 0.6)})
        return lista

    def _lista_adornos(self) -> list[dict]:
        if self.probador:
            return []
        lista = []
        for i, a in enumerate(self.casa.datos["adornos"]):
            w, h = modelo.ADORNOS[a["id"]]["tam"]
            lista.append({"tex": _url(muebles.textura_adorno(a["id"], self.carpeta)), "x": a["x"], "y": a["y"], "w": w, "h": h,
                          "marco": a["id"] not in SIN_MARCO, "i": ADORNO + i})
        return lista

    def refrescar(self):
        d = self.casa.datos
        pt, pc = self._acabado(modelo.PISOS, d["piso"], "piso")
        at, ac = self._acabado(modelo.PAREDES, d["pared"], "pared")
        bx, bz = modelo.celda_a_mundo(d["bb"]["cx"], d["bb"]["cz"])
        mx, mz = modelo.celda_a_mundo(d["mascota"]["cx"], d["mascota"]["cz"])
        brot = float(d["bb"]["rot"])
        self.v._casa_pet = {"petPos": mx, "petZ": mz, "petRotY": float(d["mascota"]["rot"]), "petY": 0.0}
        self.v._casa_bb = dict(self.vida.extra_bb()) if self.vida else {}
        s = d["sentado"]
        if self.probador:               # los dos parados en el medio, sin muebles alrededor
            bx, bz, brot = -0.22, 0.25, 0.0
            self.v._casa_pet = {"petPos": 0.24, "petZ": 0.3, "petRotY": -25.0, "petY": 0.0}
            self.v._casa_bb = {}
        else:
            asiento_bb = self._asiento(s["bb"])
            if asiento_bb:              # BiriBiri sentado: con las piernas para adelante y las manos sobre las piernas
                bx, y, bz, brot = asiento_bb
                self.v._casa_bb = {"liX": -90, "ldX": -90, "aiX": -42, "aiZ": -9, "adX": -42, "adZ": 9, "reposo": 0.3,
                                   "pY": y + 0.02 - HIP, "sombra": False}
            asiento_pet = self._asiento(s["mascota"])
            if s["falda"] and asiento_bb:   # la mascota en la falda
                adelante = 0.1
                th = math.radians(brot)
                self.v._casa_pet = {"petPos": bx + adelante * math.sin(th), "petZ": bz + adelante * math.cos(th), "petRotY": brot,
                                    "petY": asiento_bb[1] + 0.05}
            elif asiento_pet:           # la mascota sentada en su lugar (se hunde un poco en el almohadón)
                self.v._casa_pet = {"petPos": asiento_pet[0], "petZ": asiento_pet[2], "petRotY": asiento_pet[3],
                                    "petY": asiento_pet[1] - 0.02}
            if self.vida:
                self.v._casa_pet.update(self.vida.extra_pet())
        b = d["bandera"]
        self.v.repose()
        self.v.pose(pisoTex=pt, pisoColor=pc, paredTex=at, paredColor=ac, muebles=self._lista_muebles(),
                    adornos=self._lista_adornos(), bbX=bx, bbZ=bz, bbRot=brot, bandCasaX=b["x"], bandCasaY=b["y"],
                    grilla=bool(self.colocando or (self._arrastre and self._arrastre["tipo"] == "mueble")), **self.v._casa_pet)
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
        x0, z0 = self.centro_mueble(m, cx, cz)
        th = math.radians(m["rot"])
        return x0 + lx * math.cos(th) + lz * math.sin(th), ly, z0 - lx * math.sin(th) + lz * math.cos(th), float(m["rot"])

    def frente_del_asiento(self, i: int, plaza: int, distancia: float = 0.3) -> tuple[float, float, float]:
        """Dónde pararse para sentarse en ese lugar: delante del asiento (x, z, giro)."""
        x, _y, z, rot = self._asiento([i, plaza])
        th = math.radians(rot)
        return x + distancia * math.sin(th), z + distancia * math.cos(th), rot

    def _marcar(self, fantasma: tuple[str, float, float, int] | None = None, ok: bool = True):
        """El cuadrado de abajo: el del mueble elegido, o el fantasma del que se está por poner."""
        if fantasma:
            item, cx, cz, rot = fantasma
            w, p = modelo.celdas_girado(item, rot)
            self.v.pose(selVis=True, selFantasma=True, selOk=ok, selX=(cx + w / 2 - modelo.COLUMNAS / 2) * CELDA,
                        selZ=(cz + p / 2 - modelo.FILAS / 2) * CELDA, selW=w * CELDA, selD=p * CELDA)
            return
        m = self.mueble_seleccionado()
        if m and not self.probador:
            cx, cz = self._temporal.get(self.seleccion, (m["cx"], m["cz"]))
            w, p = modelo.celdas_girado(m["id"], m["rot"])
            self.v.pose(selVis=True, selFantasma=False, selOk=ok, selX=(cx + w / 2 - modelo.COLUMNAS / 2) * CELDA,
                        selZ=(cz + p / 2 - modelo.FILAS / 2) * CELDA, selW=w * CELDA, selD=p * CELDA)
        else:
            self.v.pose(selVis=False)

    # --- Probador ------------------------------------------------------------------------------------------
    def poner_probador(self, activo: bool):
        if activo == self.probador:
            return
        self.probador = activo
        self.cancelar()
        self.v.pose(zoomU=1.75 if activo else 1.0, panX=0.0, panY=-0.62 if activo else 0.0)

    # --- Acciones de los paneles ---------------------------------------------------------------------------
    def empezar_colocar(self, item: str, color: str | None):
        if self.solo_mirar:
            return
        if item in modelo.ADORNOS:          # los adornos se cuelgan en la pared y después se arrastran
            i = self.casa.poner_adorno(item)
            if i is not None:
                self.seleccion, self.sel_adorno = None, i
                self.refrescar()
            return
        self.seleccion = self.sel_adorno = None
        self.colocando = {"item": item, "color": color, "rot": 0}
        self.refrescar()

    def cancelar(self):
        self.colocando = None
        self._arrastre = None
        self._temporal.clear()
        self.refrescar()

    def girar(self):
        if self.colocando:
            self.colocando["rot"] = (self.colocando["rot"] + 45) % 360
        elif self.seleccion is not None:
            self.casa.girar_mueble(self.seleccion)
            self.refrescar()

    def guardar_seleccionado(self):
        if self.seleccion is not None:
            self.casa.guardar_mueble(self.seleccion)
            self.seleccion = None
        elif self.sel_adorno is not None:
            self.casa.guardar_adorno(self.sel_adorno)
            self.sel_adorno = None
        self.refrescar()

    def pintar_seleccionado(self, color: str):
        if self.seleccion is not None and self.casa.pintar_mueble(self.seleccion, color):
            self.refrescar()

    def mueble_seleccionado(self) -> dict | None:
        if self.seleccion is not None and self.seleccion < len(self.casa.datos["muebles"]):
            return self.casa.datos["muebles"][self.seleccion]
        return None

    def adorno_seleccionado(self) -> dict | None:
        if self.sel_adorno is not None and self.sel_adorno < len(self.casa.datos["adornos"]):
            return self.casa.datos["adornos"][self.sel_adorno]
        return None

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
            self.falda()
            return
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

    # --- El mouse ------------------------------------------------------------------------------------------
    @staticmethod
    def _celda(x: float, z: float, w: float, p: float, dx: float = 0.0, dz: float = 0.0) -> tuple[float, float]:
        """La media celda de arriba a la izquierda para que el mueble (w × p celdas) quede centrado donde está el mouse."""
        cx = round((x / CELDA + modelo.COLUMNAS / 2 - dx - w / 2) * SUB) / SUB
        cz = round((z / CELDA + modelo.FILAS / 2 - dz - p / 2) * SUB) / SUB
        return max(0.0, min(modelo.COLUMNAS - w, cx)), max(0.0, min(modelo.FILAS - p, cz))

    def _evento(self, tipo: str, x: float, z: float, indice: int, px: float = float("nan"), py: float = float("nan")):
        if self.solo_mirar or self.probador:
            return
        d = self.casa.datos
        fuera = tipo.endswith("_fuera")
        base = tipo[:-6] if fuera else tipo
        a = self._arrastre
        # Lo que se arrastra por la pared (adornos y la bandera) solo necesita la pared
        if a and a["tipo"] in ("adorno", "bandera"):
            if base == "arrastre" and not _nan(px):
                if a["tipo"] == "adorno":
                    self.casa.mover_adorno(a["i"], px - a["dx"], py - a["dy"], guardar=False)
                    self.v.pose(adornos=self._lista_adornos())
                else:
                    self.casa.mover_bandera(px - a["dx"], py - a["dy"], guardar=False)
                    b = d["bandera"]
                    self.v.pose(bandCasaX=b["x"], bandCasaY=b["y"])
            elif base == "release":
                self._arrastre = None
                self.casa.guardar()
                self.refrescar()
            return
        if base == "press" and indice >= ADORNO and indice - ADORNO < len(d["adornos"]) and not _nan(px):
            i = indice - ADORNO
            self.seleccion, self.sel_adorno = None, i
            self._arrastre = {"tipo": "adorno", "i": i, "dx": px - d["adornos"][i]["x"], "dy": py - d["adornos"][i]["y"]}
            self._marcar()
            self.cambio.emit()
            return
        if base == "press" and indice == -4 and not _nan(px):
            self._arrastre = {"tipo": "bandera", "dx": px - d["bandera"]["x"], "dy": py - d["bandera"]["y"]}
            return
        if fuera:
            if base == "release" and self._arrastre:
                self._soltar()
            return
        # Poniendo un mueble nuevo
        if self.colocando:
            c = self.colocando
            w, p = modelo.celdas_girado(c["item"], c["rot"])
            cx, cz = self._celda(x, z, w, p)
            ok = self.casa.cabe(c["item"], cx, cz, c["rot"])
            if base in ("mover", "arrastre"):
                self._marcar((c["item"], cx, cz, c["rot"]), ok)
            elif base == "press" and ok:
                i = self.casa.poner_mueble(c["item"], cx, cz, c["rot"], c["color"])
                if i is not None:
                    if d["inventario"].get(c["item"], 0) < 1:
                        self.colocando = None
                    self.seleccion = i
                    self.refrescar()
            return
        if base == "press":
            self.sel_adorno = None
            if 0 <= indice < len(d["muebles"]):
                m = d["muebles"][indice]
                w, p = modelo.celdas_girado(m["id"], m["rot"])
                self.seleccion = indice
                self._arrastre = {"tipo": "mueble", "i": indice, "dx": x / CELDA + modelo.COLUMNAS / 2 - (m["cx"] + w / 2),
                                  "dz": z / CELDA + modelo.FILAS / 2 - (m["cz"] + p / 2), "ok": True}
                self.v.pose(grilla=True)
            elif indice in (-2, -3):
                quien = "bb" if indice == -2 else "mascota"
                self._arrastre = {"tipo": quien}
                d["sentado"]["falda"] = False          # agarrarlos los levanta (y la mascota se baja de la falda)
                self.casa.parar(quien)
                if self.vida:
                    self.vida.soltar_control(quien)
                self.seleccion = None
            else:
                self.seleccion = None
            self._marcar()
            self.cambio.emit()
        elif base == "arrastre" and self._arrastre:
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
                quien = a["tipo"]
                cx = max(0.0, min(modelo.COLUMNAS - 1.0, x / CELDA + modelo.COLUMNAS / 2 - 0.5))
                cz = max(0.0, min(modelo.FILAS - 1.0, z / CELDA + modelo.FILAS / 2 - 0.5))
                d[quien]["cx"], d[quien]["cz"] = cx, cz
                wx, wz = modelo.celda_a_mundo(cx, cz)
                if quien == "bb":
                    self.v.pose(bbX=wx, bbZ=wz)
                else:
                    self.v._casa_pet.update(petPos=wx, petZ=wz)
                    self.v.pose(petPos=wx, petZ=wz)
        elif base == "release" and self._arrastre:
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


_PREVIA_QML = """
import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils

Item {
    id: raizPrevia
    property string src: ""
    property int estado: cargador.status
    property string error: cargador.errorString
    property string img: ""
    property bool es3d: true
    View3D {
        anchors.fill: parent
        visible: raizPrevia.es3d
        camera: camaraPrevia
        environment: SceneEnvironment { backgroundMode: SceneEnvironment.Transparent; antialiasingMode: SceneEnvironment.MSAA
                                        antialiasingQuality: SceneEnvironment.High }
        PerspectiveCamera { id: camaraPrevia; position: Qt.vector3d(0, 0.8, 2.7); eulerRotation.x: -14; fieldOfView: 32; clipNear: 0.05; clipFar: 50 }
        DirectionalLight { eulerRotation.x: -35; eulerRotation.y: -30; brightness: 2.1 }
        DirectionalLight { eulerRotation.x: -10; eulerRotation.y: 150; brightness: 0.8 }
        Node {
            NumberAnimation on eulerRotation.y { from: 0; to: 360; duration: 9000; loops: Animation.Infinite }
            RuntimeLoader { id: cargador; source: raizPrevia.src }
        }
    }
    Image { anchors.fill: parent; anchors.margins: 14; visible: !raizPrevia.es3d; source: raizPrevia.img; fillMode: Image.PreserveAspectFit
            smooth: true; mipmap: true }
}
"""


def crear_vista_previa(parent=None):
    """Una vista chiquita que muestra el mueble girando (o el dibujo del adorno) antes de comprarlo."""
    try:
        from PySide6.QtQuickWidgets import QQuickWidget
        from PySide6.QtCore import Qt
        archivo = vista3d.CARPETA / "previa.qml"
        archivo.parent.mkdir(parents=True, exist_ok=True)
        if not archivo.exists() or archivo.read_text(encoding="utf-8") != _PREVIA_QML:
            archivo.write_text(_PREVIA_QML, encoding="utf-8")
        w = QQuickWidget(parent)
        w.setResizeMode(QQuickWidget.SizeRootObjectToView)
        w.setAttribute(Qt.WA_AlwaysStackOnTop)
        w.setAttribute(Qt.WA_TranslucentBackground)
        w.setClearColor(Qt.transparent)
        w.setSource(QUrl.fromLocalFile(str(archivo)))
        return w if w.rootObject() is not None else None
    except Exception:  # noqa: BLE001 - sin Qt Quick 3D: no hay vista previa
        return None
