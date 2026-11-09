"""El Protagonista en pantalla con Qt Quick 3D (la placa de video): luz, sombras suaves, bordes lisos y una animación
de reposo (respira, mira para los costados, mueve un poco los brazos). Las formas las arma protagonista3d en otro
hilo y quedan en caché; mientras tanto se sigue viendo el anterior.

Si esta PC no puede usar Qt Quick 3D, crear() devuelve el muñequito anterior (avatar3d.Munequito)."""
from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import SIGNAL, QObject, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QPixmap

from . import avatar3d

CARPETA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TVon" / "protagonista"

_ESCENA = """
import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils

Item {
    id: raiz
    property string carpeta: ""
    property bool arrastrable: false
    property bool busto: false
    property bool quieto: false
    property real giroMano: 0
    // Poses (la escena del logo): inclinación del cuerpo, brazo derecho extendido para empujar (0 a 1), hacia dónde mira
    // la cabeza y cuánto se balancea solo (0 = quieto en su lugar)
    property real inclinacion: 0
    property real empuje: 0
    property real mira: 0
    property real vaiven: 1
    // Escena liviana (la del logo, que se anima todo el tiempo): sin sombras ni oclusión, para llegar a 30 cuadros/s
    property bool liviano: false
    property vector3d escala: Qt.vector3d(1, 1, 1)
    property real tiempo: 0
    property int cargadas: 0
    signal listo()
    NumberAnimation on tiempo { from: 0; to: 100000; duration: 100000000; loops: Animation.Infinite; running: !raiz.quieto }

    function url(parte) { return raiz.carpeta === "" ? "" : raiz.carpeta + "/" + parte + ".glb" }

    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: raiz.liviano ? SceneEnvironment.Medium : SceneEnvironment.VeryHigh
            aoEnabled: !raiz.busto && !raiz.liviano; aoStrength: 40; aoDistance: 0.05; aoSoftness: 50
            tonemapMode: SceneEnvironment.TonemapModeFilmic
        }
        PerspectiveCamera {
            // Con margen para que entren los gorros, la galera y los rulos del afro
            position: raiz.busto ? Qt.vector3d(0, 0.88, 4.2) : Qt.vector3d(0, 0.62, 6.6)
            fieldOfView: raiz.busto ? 13.6 : 11.6
            clipNear: 0.1
        }
        DirectionalLight { eulerRotation.x: -30; eulerRotation.y: -30; brightness: 2.2; castsShadow: !raiz.busto && !raiz.liviano
                           shadowFactor: 25; shadowMapQuality: Light.ShadowMapQualityHigh; shadowBias: 0.4 }
        DirectionalLight { eulerRotation.x: -10; eulerRotation.y: 150; brightness: 0.9; color: "#bcd6ff" }
        DirectionalLight { eulerRotation.x: 20; eulerRotation.y: 20; brightness: 0.35 }

        // Sombra de apoyo, debajo de los pies
        Model {
            visible: !raiz.busto && raiz.carpeta !== ""
            source: "#Cylinder"; scale: Qt.vector3d(0.0042, 0.0001, 0.0028); position: Qt.vector3d(0, 0.001, 0.02)
            materials: PrincipledMaterial { baseColor: "black"; opacity: 0.28; alphaMode: PrincipledMaterial.Blend
                                            lighting: PrincipledMaterial.NoLighting }
        }

        Node {
            id: cuerpo
            scale: raiz.escala
            eulerRotation.y: (raiz.quieto ? -16 : 15 * Math.sin(raiz.tiempo * 0.35) * raiz.vaiven) + raiz.giroMano
            eulerRotation.z: raiz.inclinacion
            y: raiz.quieto ? 0 : 0.006 * Math.abs(Math.sin(raiz.tiempo * 1.1))
            RuntimeLoader { source: raiz.url("piernas"); onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
            Node {
                // Respirar: el torso se infla apenas
                y: 0.43; scale.y: 1 + 0.012 * Math.sin(raiz.tiempo * 2.2); scale.x: 1 + 0.006 * Math.sin(raiz.tiempo * 2.2)
                RuntimeLoader { source: raiz.url("torso"); y: -0.43; onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
            }
            Node {
                position: Qt.vector3d(-0.155, 0.585, 0)
                eulerRotation.z: -4 - 2 * Math.sin(raiz.tiempo * 1.1); eulerRotation.x: 4 * Math.sin(raiz.tiempo * 0.8)
                RuntimeLoader { source: raiz.url("brazo_i"); position: Qt.vector3d(0.155, -0.585, 0)
                                onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
            }
            Node {
                position: Qt.vector3d(0.155, 0.585, 0)
                eulerRotation.z: 4 + 2 * Math.sin(raiz.tiempo * 1.1 + 1) + raiz.empuje * 80
                eulerRotation.x: -4 * Math.sin(raiz.tiempo * 0.8) - raiz.empuje * 35
                RuntimeLoader { source: raiz.url("brazo_d"); position: Qt.vector3d(-0.155, -0.585, 0)
                                onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
            }
            Node {
                // La cabeza mira para los costados y se inclina un poco
                position: Qt.vector3d(0, 0.64, 0)
                eulerRotation.y: (raiz.quieto ? 0 : 11 * Math.sin(raiz.tiempo * 0.55) * raiz.vaiven) + raiz.mira
                eulerRotation.z: raiz.quieto ? 3 : 3 * Math.sin(raiz.tiempo * 0.9)
                eulerRotation.x: raiz.quieto ? 0 : -3 + 3 * Math.sin(raiz.tiempo * 0.7)
                RuntimeLoader { source: raiz.url("cabeza"); position: Qt.vector3d(0, -0.64, 0)
                                onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
            }
        }
    }
    function cuenta() { raiz.cargadas += 1; if (raiz.cargadas >= 5) raiz.listo() }
    onCarpetaChanged: raiz.cargadas = 0

    MouseArea {
        anchors.fill: parent
        cursorShape: raiz.arrastrable ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.PointingHandCursor
        property real ultimo: 0
        onPressed: function(e) { ultimo = e.x }
        onPositionChanged: function(e) { if (raiz.arrastrable) { raiz.giroMano += (e.x - ultimo) * 0.7; ultimo = e.x } }
        onClicked: if (!raiz.arrastrable) puente.tocar()
    }
}
"""


class _Constructor(QObject):
    """Arma los Protagonistas de a uno, en otro hilo (lo último pedido por cada vista es lo que vale)."""
    hecho = Signal(object, str)   # id de la vista, carpeta

    def __init__(self):
        super().__init__()
        self._cond = threading.Condition()
        self._pedidos: dict[int, dict] = {}
        threading.Thread(target=self._bucle, daemon=True, name="protagonista").start()

    def pedir(self, vista_id: int, spec: dict):
        with self._cond:
            self._pedidos[vista_id] = spec
            self._cond.notify()

    def _bucle(self):
        from . import protagonista3d
        while True:
            with self._cond:
                while not self._pedidos:
                    self._cond.wait()
                vista_id, spec = next(iter(self._pedidos.items()))
                del self._pedidos[vista_id]
            try:
                carpeta = protagonista3d.construir(spec, CARPETA)
                self.hecho.emit(vista_id, str(carpeta))
            except Exception:  # noqa: BLE001 - una forma rara no tiene que tirar la app
                pass
            _limpiar_cache()


_constructor: _Constructor | None = None


def _limpiar_cache(maximo: int = 40):
    """Quedan los últimos looks armados (los .glb de cada uno ocupan algunos MB)."""
    try:
        looks = sorted((d for d in CARPETA.iterdir() if d.is_dir() and d.name != "formas"),
                       key=lambda d: d.stat().st_mtime, reverse=True)
        for viejo in looks[maximo:]:
            for f in viejo.iterdir():
                f.unlink(missing_ok=True)
            viejo.rmdir()
        formas = sorted((CARPETA / "formas").glob("*.npz"), key=lambda f: f.stat().st_mtime, reverse=True)
        for vieja in formas[200:]:
            vieja.unlink(missing_ok=True)
    except OSError:
        pass


def _archivo_escena() -> Path:
    CARPETA.mkdir(parents=True, exist_ok=True)
    archivo = CARPETA / "escena.qml"
    if not archivo.exists() or archivo.read_text(encoding="utf-8") != _ESCENA:
        archivo.write_text(_ESCENA, encoding="utf-8")
    return archivo


class _Puente(QObject):
    tocado = Signal()

    @Slot()
    def tocar(self):
        self.tocado.emit()


def disponible() -> bool:
    try:
        from PySide6 import QtQuick3D, QtQuickWidgets  # noqa: F401
    except ImportError:
        return False
    return os.environ.get("TVON_SIN_3D") != "1"


def _clase():
    from PySide6.QtQuickWidgets import QQuickWidget

    class Protagonista3D(QQuickWidget):
        tocado = Signal()
        listo = Signal()

        def __init__(self, spec: dict | None = None, encuadre: str = "cuerpo", arrastrable: bool = False,
                     quieto: bool = False, parent=None):
            super().__init__(parent)
            global _constructor
            if _constructor is None:
                _constructor = _Constructor()
            self._constructor = _constructor
            self._constructor.hecho.connect(self._hecho)
            self.setResizeMode(QQuickWidget.SizeRootObjectToView)
            self.setAttribute(Qt.WA_AlwaysStackOnTop)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setClearColor(Qt.transparent)
            self._puente = _Puente()
            self._puente.tocado.connect(self.tocado)
            self.rootContext().setContextProperty("puente", self._puente)
            self.setSource(QUrl.fromLocalFile(str(_archivo_escena())))
            raiz = self.rootObject()
            if raiz is not None:
                raiz.setProperty("busto", encuadre == "busto")
                raiz.setProperty("arrastrable", arrastrable)
                raiz.setProperty("quieto", quieto)
                QObject.connect(raiz, SIGNAL("listo()"), self._avisar_listo)
            self.poner(spec or avatar3d.PREDETERMINADO)

        def _avisar_listo(self):
            self.listo.emit()

        def poner(self, spec: dict):
            from .protagonista3d import ESCALA
            s = avatar3d.normalizar(spec)
            self._escala = ESCALA.get(s["cuerpo"], ESCALA["normal"])
            self._constructor.pedir(id(self), s)

        def _hecho(self, vista_id: int, carpeta: str):
            if vista_id != id(self):
                return
            try:
                raiz = self.rootObject()
            except RuntimeError:
                return
            if raiz is not None:
                url = QUrl.fromLocalFile(carpeta).toString()
                from PySide6.QtGui import QVector3D
                raiz.setProperty("escala", QVector3D(*getattr(self, "_escala", (1, 1, 1))))
                if raiz.property("carpeta") == url:
                    QTimer.singleShot(0, self.listo.emit)   # ya estaba: no se vuelve a cargar
                else:
                    raiz.setProperty("carpeta", url)

        def pose(self, **valores):
            """Cambia la pose: inclinacion (grados), empuje (0 a 1), mira (grados), vaiven (0 a 1), giroMano (grados)."""
            try:
                raiz = self.rootObject()
            except RuntimeError:
                return
            if raiz is not None:
                for clave, valor in valores.items():
                    raiz.setProperty(clave, valor if isinstance(valor, bool) else float(valor))

        def imagen(self) -> QPixmap:
            return QPixmap.fromImage(self.grabFramebuffer())

    return Protagonista3D


_Protagonista3D = None
ultimo_error = ""   # por qué no se pudo usar Qt Quick 3D (para diagnosticar)


def crear(spec: dict | None = None, encuadre: str = "cuerpo", arrastrable: bool = False, parent=None):
    """El Protagonista nuevo (Qt Quick 3D) o, si no se puede, el anterior. Los dos tienen poner(spec) y tocado."""
    global _Protagonista3D, ultimo_error
    if disponible():
        try:
            if _Protagonista3D is None:
                _Protagonista3D = _clase()
            vista = _Protagonista3D(spec, encuadre, arrastrable, parent=parent)
            if vista.rootObject() is not None:
                return vista
            ultimo_error = " | ".join(e.toString() for e in vista.errors()) or "sin escena"
        except Exception as e:  # noqa: BLE001 - sin Qt Quick 3D en esta PC: el de antes
            ultimo_error = repr(e)
    else:
        ultimo_error = "no está Qt Quick 3D"
    return avatar3d.Munequito(spec, encuadre=encuadre, arrastrable=arrastrable, parent=parent)


class Miniaturas(QObject):
    """Fotos chicas de Protagonistas (para la lista de amigos): se arman de a uno en una vista escondida."""
    lista = Signal(str, QPixmap)   # clave del pedido, imagen

    def __init__(self, alto: int = 96):
        super().__init__()
        self._alto = alto
        self._cola: list[tuple[str, dict]] = []
        self._vista = None
        self._actual: str | None = None

    def pedir(self, clave: str, spec: dict):
        self._cola.append((clave, spec))
        if self._actual is None:
            QTimer.singleShot(0, self._siguiente)

    def _siguiente(self):
        if not self._cola:
            self._actual = None
            return
        self._actual, spec = self._cola.pop(0)
        if self._vista is None:
            self._vista = crear(spec, "busto")
            self._vista.setAttribute(Qt.WA_DontShowOnScreen)
            self._vista.resize(self._alto, self._alto)
            self._vista.show()
            if hasattr(self._vista, "listo"):
                self._vista.listo.connect(lambda: QTimer.singleShot(250, self._sacar))
            else:
                QTimer.singleShot(50, self._sacar)
        self._vista.poner(spec)
        if not hasattr(self._vista, "listo"):
            QTimer.singleShot(50, self._sacar)

    def _sacar(self):
        if self._actual is None or self._vista is None:
            return
        pix = self._vista.imagen() if hasattr(self._vista, "imagen") else avatar3d.imagen({}, self._alto, "busto")
        self.lista.emit(self._actual, pix)
        QTimer.singleShot(0, self._siguiente)
