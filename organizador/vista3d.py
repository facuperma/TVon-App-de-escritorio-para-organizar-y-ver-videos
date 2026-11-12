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
    // Poses (ver poses.py): desplazamiento y giro del cuerpo, giro de cada brazo y pierna (en grados) y de la cabeza, más lo que se mueve solo
    property real pX: 0
    property real pY: 0
    property real pZ: 0
    property real rX: 0
    property real rY: 0
    property real rZ: 0
    property real aiX: 0
    property real aiY: 0
    property real aiZ: 0
    property real adX: 0
    property real adY: 0
    property real adZ: 0
    property real liX: 0
    property real liY: 0
    property real liZ: 0
    property real ldX: 0
    property real ldY: 0
    property real ldZ: 0
    property real cabX: 0
    property real cabY: 0
    property real cabZ: 0
    property real esc: 1
    property real reposo: 1      // 1 = respira y mueve los brazos apenas; 0 = quieto en la pose
    property real ampBx: 0       // brazos que van y vienen (grados)
    property real ondaI: 0       // brazo izquierdo que saluda / se agita
    property real ondaD: 0
    property real giroB: 0       // brazos que giran como molinos (nadar)
    property real ampP: 0        // piernas que van y vienen
    property real ampPz: 0       // piernas que patean para los costados
    property real ampS: 0        // saltitos
    property real ritmo: 6
    // La mascota (perro o gato) parada al lado: dónde giran su cuello y su cola, cómo mueve la cabeza y la cola, y lo que
    // aparece cuando hacen algo juntos (comida, plato, corazones, un «¡Ñam!»)
    property bool conMascota: false
    property real cuelloY: 0.27
    property real cuelloZ: 0.13
    property real colaY: 0.26
    property real colaZ: -0.17
    property real petCabX: 0
    property real petCabZ: 0
    property real petCola: 22
    property real petRitmo: 7
    property real petSalto: 0
    property real petRotY: -28
    property real petPos: 0.33
    property real petZ: 0.06
    property real petY: 0
    property real petEsc: 1
    property string comida: ""
    property bool plato: false
    property bool granos: false
    property bool corazones: false
    property string texto: ""
    readonly property real zoomM: (raiz.conMascota && !raiz.busto) ? 1.45 : 1.0
    function anima(fase) { return raiz.ampBx * Math.sin(raiz.tiempo * raiz.ritmo + fase) + raiz.giroB * (raiz.tiempo * raiz.ritmo * 57.29578 + fase * 57.29578) }
    property real bandX: 0       // la bandera de fondo, acomodable (en porcentaje; ver avatar3d.NUMEROS)
    property real bandY: 0
    property real bandTam: 100
    property real bandGiro: 16
    property real bandCostado: -32
    property real zoomU: 1       // zoom con la rueda del mouse (solo en el editor)
    property real panX: 0        // mover la vista (clic derecho y arrastrar)
    property real panY: 0
    // La habitación (modo casa): piso y paredes con su textura, los muebles puestos y qué se está arrastrando o poniendo
    property bool casa: false
    property string pisoTex: ""
    property string paredTex: ""
    property color pisoColor: "#c8a070"
    property color paredColor: "#f1ece4"
    property var muebles: []
    property real bbX: 0
    property real bbZ: 0
    property real bbRot: 0
    property bool selVis: false
    property real selX: 0
    property real selZ: 0
    property real selW: 0.3
    property real selD: 0.3
    property bool selOk: true
    property bool selFantasma: false
    readonly property real anchoCasa: 3.6
    readonly property real fondoCasa: 2.4
    readonly property real altoPared: 1.7
    signal casaEvento(string tipo, real x, real z, int indice)
    function bajoMouse(px, py) {
        var hits = vista.pickAll(px, py)
        var suelo = null, indice = -1, hay = false, mueble = -1
        for (var i = 0; i < hits.length; i++) {
            var o = hits[i].objectHit
            if (o.objectName === "suelo") { if (suelo === null) suelo = hits[i].scenePosition }
            else if (o.indice !== undefined) {
                if (!hay) { indice = o.indice; hay = true }
                if (mueble < 0 && o.indice >= 0) mueble = o.indice
            }
        }
        return { suelo: suelo, indice: indice, mueble: mueble }
    }
    property real giroVert: 0     // arrastrando hacia arriba o abajo el muñeco da vueltas también de frente (360° en las dos direcciones)
    // Poses (la escena del logo): inclinación del cuerpo, brazo derecho extendido para empujar (0 a 1), hacia dónde mira
    // la cabeza y cuánto se balancea solo (0 = quieto en su lugar)
    property real inclinacion: 0
    // Las dos manos hacia adelante (empujar algo pesado), giro en el aire alrededor del centro del cuerpo y la sombra del piso
    property real manos: 0
    property real vuelo: 0
    property bool sombra: true
    property real empuje: 0
    property real mira: 0
    property real vaiven: 1
    // Escena liviana (la del logo, que se anima todo el tiempo): sin sombras ni oclusión, para llegar a 30 cuadros/s
    property bool liviano: false
    property real cuerpoK: 0.74      // cabezón y regordete: más tierno
    property real cabezaK: 1.45
    // La bandera de fondo (archivo PNG) flameando detrás: solo si la vista pide fondo
    property string bandera: ""
    property bool fondo: false
    readonly property real distFondo: raiz.busto ? 4.9 : 6.6 * raiz.zoomM + 0.7
    readonly property real visAlto: 2 * raiz.distFondo * Math.tan((raiz.busto ? 13.6 : 11.6) * Math.PI / 360)
    readonly property real anchoBandera: raiz.casa ? 1.5 : Math.min(raiz.visAlto * 0.62 * 1.5, raiz.visAlto * (raiz.width / Math.max(1, raiz.height)) * 1.0)
    readonly property real altoBandera: raiz.anchoBandera / 1.5
    readonly property int tiras: 44
    function onda(k) { return 0.06 * (0.18 + 0.82 * k) * Math.sin(k * 8.0 - raiz.tiempo * 3.4) }
    function giroTira(k) {
        var a = 0.06 * (0.18 + 0.82 * k)
        var pendiente = (0.06 * 0.82 * Math.sin(k * 8.0 - raiz.tiempo * 3.4) + a * 8.0 * Math.cos(k * 8.0 - raiz.tiempo * 3.4)) / raiz.anchoBandera
        return -Math.atan(pendiente) * 180 / Math.PI
    }
    property vector3d escala: Qt.vector3d(1, 1, 1)
    property real tiempo: 0
    property int cargadas: 0
    signal listo()
    NumberAnimation on tiempo { from: 0; to: 100000; duration: 100000000; loops: Animation.Infinite; running: !raiz.quieto }

    function url(parte) { return raiz.carpeta === "" ? "" : raiz.carpeta + "/" + parte + ".glb" }

    View3D {
        id: vista
        anchors.fill: parent
        camera: camara
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: raiz.liviano ? SceneEnvironment.Medium : SceneEnvironment.VeryHigh
            aoEnabled: !raiz.busto && !raiz.liviano; aoStrength: 40; aoDistance: 0.05; aoSoftness: 50
            tonemapMode: SceneEnvironment.TonemapModeFilmic
        }
        PerspectiveCamera {
            id: camara
            // Con margen para que entren los gorros, la galera y los rulos del afro
            position: raiz.casa ? Qt.vector3d(raiz.panX, 1.95 + raiz.panY, 4.75 / raiz.zoomU) : (raiz.busto ? Qt.vector3d(0, 0.88, 4.2) : Qt.vector3d((raiz.conMascota ? 0.14 : 0) + raiz.panX, (raiz.conMascota ? 0.74 : 0.62) + raiz.panY, 6.6 * raiz.zoomM / raiz.zoomU))
            eulerRotation.x: raiz.casa ? -17 : 0
            fieldOfView: raiz.casa ? 34 : (raiz.busto ? 13.6 : 11.6)
            clipNear: 0.1
        }
        DirectionalLight { eulerRotation.x: -30; eulerRotation.y: -30; brightness: 2.2; castsShadow: !raiz.busto && !raiz.liviano
                           shadowFactor: 25; shadowMapQuality: Light.ShadowMapQualityHigh; shadowBias: 0.4 }
        DirectionalLight { eulerRotation.x: -10; eulerRotation.y: 150; brightness: 0.9; color: "#bcd6ff" }
        DirectionalLight { eulerRotation.x: 20; eulerRotation.y: 20; brightness: 0.35 }

        // La bandera, hecha de tiras angostas que suben y bajan en ola (con la luz, cada tira se ve más clara o más oscura)
        Node {
            visible: raiz.fondo && raiz.bandera !== ""
            position: raiz.casa ? Qt.vector3d(raiz.bandX / 100 * 1.3, 1.0 + raiz.bandY / 100 * 0.5, -1.1)
                                : Qt.vector3d(raiz.anchoBandera * 0.08 + raiz.bandX / 100 * raiz.visAlto * 0.5,
                                              (raiz.busto ? 1.0 : 0.78) + raiz.bandY / 100 * raiz.visAlto * 0.4, -0.7)
            scale: Qt.vector3d(raiz.bandTam / 100 * (raiz.casa ? 0.6 : 1), raiz.bandTam / 100 * (raiz.casa ? 0.6 : 1), raiz.bandTam / 100)
            eulerRotation.z: raiz.casa ? raiz.bandGiro - 16 : raiz.bandGiro        // en diagonal, subiendo hacia un costado
            eulerRotation.y: raiz.casa ? raiz.bandCostado + 32 : raiz.bandCostado     // de costado, para que se vea bien
            Repeater3D {
                model: raiz.tiras
                Node {
                    property real k: index / (raiz.tiras - 1)
                    x: (k - 0.5) * raiz.anchoBandera
                    z: raiz.onda(k)
                    eulerRotation.y: raiz.giroTira(k)
                    Model {
                        source: "#Rectangle"
                        scale: Qt.vector3d(raiz.anchoBandera / (raiz.tiras - 1) / 100 * 1.2, raiz.altoBandera / 100, 1)
                        materials: PrincipledMaterial {
                            cullMode: Material.NoCulling
                            roughness: 0.9
                            baseColorMap: tela
                            emissiveMap: tela
                            emissiveFactor: Qt.vector3d(0.45, 0.45, 0.45)
                            Texture {
                                id: tela
                                source: raiz.bandera
                                tilingModeHorizontal: Texture.ClampToEdge
                                tilingModeVertical: Texture.ClampToEdge
                                scaleU: 1.0 / raiz.tiras
                                positionU: index / raiz.tiras
                            }
                        }
                    }
                }
            }
        }

        // La habitación: piso, tres paredes, los muebles y lo que se está acomodando
        Node {
            visible: raiz.casa
            Model {
                objectName: "suelo"; source: "#Rectangle"; pickable: true
                eulerRotation.x: -90
                scale: Qt.vector3d(raiz.anchoCasa / 100, raiz.fondoCasa / 100, 1)
                materials: PrincipledMaterial {
                    baseColor: raiz.pisoTex === "" ? raiz.pisoColor : "white"
                    baseColorMap: raiz.pisoTex === "" ? null : texPiso
                    roughness: 0.55
                    Texture { id: texPiso; source: raiz.pisoTex; tilingModeHorizontal: Texture.Repeat; tilingModeVertical: Texture.Repeat
                              scaleU: 4; scaleV: 3 }
                }
            }
            Model {      // pared del fondo
                source: "#Rectangle"; position: Qt.vector3d(0, raiz.altoPared / 2, -raiz.fondoCasa / 2)
                scale: Qt.vector3d(raiz.anchoCasa / 100, raiz.altoPared / 100, 1)
                materials: PrincipledMaterial {
                    baseColor: raiz.paredTex === "" ? raiz.paredColor : "white"
                    baseColorMap: raiz.paredTex === "" ? null : texPared
                    roughness: 0.9
                    Texture { id: texPared; source: raiz.paredTex; tilingModeHorizontal: Texture.Repeat; tilingModeVertical: Texture.Repeat
                              scaleU: 4; scaleV: 2 }
                }
            }
            Model {      // pared izquierda
                source: "#Rectangle"; position: Qt.vector3d(-raiz.anchoCasa / 2, raiz.altoPared / 2, 0); eulerRotation.y: 90
                scale: Qt.vector3d(raiz.fondoCasa / 100, raiz.altoPared / 100, 1)
                materials: PrincipledMaterial { baseColor: raiz.paredTex === "" ? raiz.paredColor : "white"; baseColorMap: raiz.paredTex === "" ? null : texPared2
                    roughness: 0.9
                    Texture { id: texPared2; source: raiz.paredTex; tilingModeHorizontal: Texture.Repeat; tilingModeVertical: Texture.Repeat
                              scaleU: 3; scaleV: 2 } }
            }
            Model {      // pared derecha
                source: "#Rectangle"; position: Qt.vector3d(raiz.anchoCasa / 2, raiz.altoPared / 2, 0); eulerRotation.y: -90
                scale: Qt.vector3d(raiz.fondoCasa / 100, raiz.altoPared / 100, 1)
                materials: PrincipledMaterial { baseColor: raiz.paredTex === "" ? raiz.paredColor : "white"; baseColorMap: raiz.paredTex === "" ? null : texPared3
                    roughness: 0.9
                    Texture { id: texPared3; source: raiz.paredTex; tilingModeHorizontal: Texture.Repeat; tilingModeVertical: Texture.Repeat
                              scaleU: 3; scaleV: 2 } }
            }
            Model {      // zócalo del fondo
                source: "#Cube"; position: Qt.vector3d(0, 0.04, -raiz.fondoCasa / 2 + 0.01)
                scale: Qt.vector3d(raiz.anchoCasa / 100, 0.0008, 0.0002)
                materials: PrincipledMaterial { baseColor: "#ffffff"; roughness: 0.6 }
            }
            Repeater3D {
                model: raiz.casa ? raiz.muebles : []
                Node {
                    property var m: modelData
                    position: Qt.vector3d(m.x, 0, m.z)
                    eulerRotation.y: m.rot
                    RuntimeLoader { source: m.src }
                    Model {      // una caja invisible del tamaño del mueble, para poder agarrarlo con el mouse
                        property int indice: m.i
                        source: "#Cube"; pickable: true
                        position: Qt.vector3d(0, m.h / 2, 0)
                        scale: Qt.vector3d(m.w / 100, m.h / 100, m.d / 100)
                        materials: PrincipledMaterial { opacity: 0.0; alphaMode: PrincipledMaterial.Blend; lighting: PrincipledMaterial.NoLighting }
                    }
                }
            }
            Model {      // el lugar elegido o el del mueble que se está arrastrando (verde si entra, rojo si no)
                visible: raiz.selVis
                source: "#Rectangle"; eulerRotation.x: -90
                position: Qt.vector3d(raiz.selX, 0.012, raiz.selZ)
                scale: Qt.vector3d(raiz.selW / 100, raiz.selD / 100, 1)
                materials: PrincipledMaterial { baseColor: raiz.selOk ? (raiz.selFantasma ? "#3ddc84" : "#ffd23f") : "#ff4d4d"
                    opacity: 0.55; alphaMode: PrincipledMaterial.Blend; lighting: PrincipledMaterial.NoLighting }
            }
            Model {      // cajas invisibles para agarrar a BiriBiri y a la mascota
                property int indice: -2
                source: "#Cube"; pickable: true
                position: Qt.vector3d(raiz.bbX, 0.3, raiz.bbZ); scale: Qt.vector3d(0.0035, 0.006, 0.0035)
                materials: PrincipledMaterial { opacity: 0.0; alphaMode: PrincipledMaterial.Blend; lighting: PrincipledMaterial.NoLighting }
            }
            Model {
                property int indice: -3
                visible: raiz.conMascota
                source: "#Cube"; pickable: true
                position: Qt.vector3d(raiz.petPos, 0.18, raiz.petZ); scale: Qt.vector3d(0.003, 0.004, 0.003)
                materials: PrincipledMaterial { opacity: 0.0; alphaMode: PrincipledMaterial.Blend; lighting: PrincipledMaterial.NoLighting }
            }
        }

        // La mascota: cuerpo, cabeza (gira en el cuello) y cola (gira en la base)
        Node {
            visible: raiz.conMascota && raiz.carpeta !== ""
            position: Qt.vector3d(raiz.petPos, raiz.petY + raiz.petSalto * Math.abs(Math.sin(raiz.tiempo * raiz.petRitmo * 0.6)), raiz.petZ)
            eulerRotation.y: raiz.petRotY
            scale: Qt.vector3d(raiz.petEsc, raiz.petEsc, raiz.petEsc)
            RuntimeLoader { source: raiz.conMascota ? raiz.url("mascota") : "" }
            Node {
                position: Qt.vector3d(0, raiz.cuelloY, raiz.cuelloZ)
                eulerRotation.x: raiz.petCabX + (raiz.quieto ? 0 : 3 * Math.sin(raiz.tiempo * 1.3))
                eulerRotation.z: raiz.petCabZ
                RuntimeLoader { source: raiz.conMascota ? raiz.url("mascota_cabeza") : ""; position: Qt.vector3d(0, -raiz.cuelloY, -raiz.cuelloZ) }
            }
            Node {
                position: Qt.vector3d(0, raiz.colaY, raiz.colaZ)
                eulerRotation.y: raiz.petCola * Math.sin(raiz.tiempo * raiz.petRitmo)
                RuntimeLoader { source: raiz.conMascota ? raiz.url("mascota_cola") : ""; position: Qt.vector3d(0, -raiz.colaY, -raiz.colaZ) }
            }
        }
        Model {
            visible: !raiz.busto && raiz.conMascota && raiz.carpeta !== "" && raiz.sombra
            source: "#Cylinder"; scale: Qt.vector3d(0.0026, 0.0001, 0.0017); position: Qt.vector3d(raiz.petPos, 0.001, raiz.petZ)
            materials: PrincipledMaterial { baseColor: "black"; opacity: 0.25; alphaMode: PrincipledMaterial.Blend
                                            lighting: PrincipledMaterial.NoLighting }
        }
        // El plato de comida, delante de la mascota, y los granitos que caen de la mano
        Node {
            visible: raiz.conMascota && raiz.plato
            position: Qt.vector3d(raiz.petPos - 0.05, 0, raiz.petZ + 0.24)
            Model { source: "#Cylinder"; position: Qt.vector3d(0, 0.014, 0); scale: Qt.vector3d(0.0015, 0.0003, 0.0015)
                    materials: PrincipledMaterial { baseColor: "#d4513d"; roughness: 0.4 } }
            Model { source: "#Cylinder"; position: Qt.vector3d(0, 0.03, 0); scale: Qt.vector3d(0.0011, 0.00012, 0.0011)
                    materials: PrincipledMaterial { baseColor: "#8a5a34"; roughness: 0.9 } }
        }
        Repeater3D {
            model: (raiz.conMascota && raiz.granos) ? 5 : 0
            Model {
                property real fase: (raiz.tiempo * 1.3 + index / 5) % 1
                source: "#Sphere"; scale: Qt.vector3d(0.00009, 0.00009, 0.00009)
                position: Qt.vector3d(0.27 + 0.03 * fase + 0.008 * index, 0.33 - 0.29 * fase * fase - 0.0 * index, 0.1 + 0.18 * fase)
                materials: PrincipledMaterial { baseColor: "#8a5a34"; roughness: 0.9 }
            }
        }

        // Sombra de apoyo, debajo de los pies
        Model {
            visible: !raiz.busto && raiz.carpeta !== "" && raiz.sombra
            source: "#Cylinder"; scale: Qt.vector3d(0.0042, 0.0001, 0.0028); position: Qt.vector3d(raiz.bbX, 0.001, raiz.bbZ + 0.02)
            materials: PrincipledMaterial { baseColor: "black"; opacity: 0.28; alphaMode: PrincipledMaterial.Blend
                                            lighting: PrincipledMaterial.NoLighting }
        }

        Node {
            id: pivote
            x: raiz.bbX
            z: raiz.bbZ
            eulerRotation.y: raiz.bbRot
            y: 0.5
            eulerRotation.z: raiz.vuelo
            eulerRotation.x: raiz.giroVert
        Node {
            id: cuerpo
            scale: Qt.vector3d(raiz.escala.x * raiz.esc, raiz.escala.y * raiz.esc, raiz.escala.z * raiz.esc)
            eulerRotation.x: raiz.rX
            eulerRotation.y: (raiz.quieto ? -16 : 15 * Math.sin(raiz.tiempo * 0.35) * raiz.vaiven) + raiz.giroMano + raiz.rY
            eulerRotation.z: raiz.inclinacion + raiz.rZ
            x: raiz.pX
            z: raiz.pZ
            y: -0.5 + raiz.pY + (raiz.quieto ? 0 : 0.012 * Math.abs(Math.sin(raiz.tiempo * 1.1))) + raiz.ampS * Math.abs(Math.sin(raiz.tiempo * raiz.ritmo))
            // Cuerpo más chico y cabeza más grande (cabezón): la altura total queda casi igual
            Node {
                id: tronco
                scale: Qt.vector3d(raiz.cuerpoK, raiz.cuerpoK, raiz.cuerpoK)
                RuntimeLoader { source: raiz.url("piernas"); onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
                Node {
                    position: Qt.vector3d(-0.07, 0.42, 0)
                    eulerRotation.x: raiz.liX + raiz.ampP * Math.sin(raiz.tiempo * raiz.ritmo)
                    eulerRotation.y: raiz.liY
                    eulerRotation.z: raiz.liZ - raiz.ampPz * Math.abs(Math.sin(raiz.tiempo * raiz.ritmo))
                    RuntimeLoader { source: raiz.url("pierna_i"); position: Qt.vector3d(0.07, -0.42, 0)
                                    onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
                }
                Node {
                    position: Qt.vector3d(0.07, 0.42, 0)
                    eulerRotation.x: raiz.ldX - raiz.ampP * Math.sin(raiz.tiempo * raiz.ritmo)
                    eulerRotation.y: raiz.ldY
                    eulerRotation.z: raiz.ldZ + raiz.ampPz * Math.abs(Math.cos(raiz.tiempo * raiz.ritmo))
                    RuntimeLoader { source: raiz.url("pierna_d"); position: Qt.vector3d(-0.07, -0.42, 0)
                                    onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
                }
                Node {
                    // Respirar: el torso se infla apenas
                    y: 0.43; scale.y: 1 + 0.022 * Math.sin(raiz.tiempo * 2.2); scale.x: 1 - 0.011 * Math.sin(raiz.tiempo * 2.2)
                    RuntimeLoader { source: raiz.url("torso"); y: -0.43; onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
                }
                Node {
                    position: Qt.vector3d(-0.155, 0.585, 0)
                    eulerRotation.z: (-4 - 2 * Math.sin(raiz.tiempo * 1.1)) * (1 - raiz.manos) * raiz.reposo + raiz.aiZ - raiz.ondaI * Math.sin(raiz.tiempo * raiz.ritmo)
                    eulerRotation.y: raiz.aiY
                    eulerRotation.x: 4 * Math.sin(raiz.tiempo * 0.8) * (1 - raiz.manos) * raiz.reposo - raiz.manos * 98 + raiz.aiX + raiz.anima(0)
                    RuntimeLoader { source: raiz.url("brazo_i"); position: Qt.vector3d(0.155, -0.585, 0)
                                    onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
                }
                Node {
                    position: Qt.vector3d(0.155, 0.585, 0)
                    eulerRotation.z: (4 + 2 * Math.sin(raiz.tiempo * 1.1 + 1)) * (1 - raiz.manos) * raiz.reposo + raiz.empuje * 80 + raiz.adZ + raiz.ondaD * Math.sin(raiz.tiempo * raiz.ritmo)
                    eulerRotation.y: raiz.adY
                    eulerRotation.x: -4 * Math.sin(raiz.tiempo * 0.8) * (1 - raiz.manos) * raiz.reposo - raiz.empuje * 35 - raiz.manos * 98 + raiz.adX - raiz.anima(3.14159)
                    RuntimeLoader { source: raiz.url("brazo_d"); position: Qt.vector3d(-0.155, -0.585, 0)
                                    onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
                    Node {
                        position: Qt.vector3d(0.07, -0.275, 0.035)      // más allá de la mano: así no queda adentro del puño
                        Node {      // un hueso
                            visible: raiz.comida === "hueso"
                            Model { source: "#Cylinder"; scale: Qt.vector3d(0.0003, 0.0014, 0.0003)
                                    materials: PrincipledMaterial { baseColor: "#f4efe2"; roughness: 0.6 } }
                            Repeater3D { model: 4
                                Model { source: "#Sphere"; scale: Qt.vector3d(0.00042, 0.00042, 0.00042)
                                        position: Qt.vector3d(index < 2 ? -0.014 : 0.014, index % 2 === 0 ? 0.07 : -0.07, 0)
                                        materials: PrincipledMaterial { baseColor: "#f4efe2"; roughness: 0.6 } } }
                        }
                        Node {      // un pescadito
                            visible: raiz.comida === "pescado"
                            Model { source: "#Sphere"; scale: Qt.vector3d(0.0004, 0.001, 0.00022)
                                    materials: PrincipledMaterial { baseColor: "#7aa7c7"; roughness: 0.4; metalness: 0.3 } }
                            Model { source: "#Cone"; position: Qt.vector3d(0, -0.09, 0); eulerRotation.x: 180; scale: Qt.vector3d(0.00036, 0.0005, 0.00012)
                                    materials: PrincipledMaterial { baseColor: "#6492b3"; roughness: 0.4 } }
                        }
                        Model {     // una pelota
                            visible: raiz.comida === "pelota"
                            source: "#Sphere"; scale: Qt.vector3d(0.0008, 0.0008, 0.0008)
                            materials: PrincipledMaterial { baseColor: "#e0432f"; roughness: 0.35 }
                        }
                    }
                }
            }
            Node {
                // La cabeza (más grande) mira para los costados y se inclina un poco; gira sobre el cuello
                position: Qt.vector3d(0, 0.64 * raiz.cuerpoK, 0)
                scale: Qt.vector3d(raiz.cabezaK, raiz.cabezaK, raiz.cabezaK)
                eulerRotation.y: (raiz.quieto ? 0 : 11 * Math.sin(raiz.tiempo * 0.55) * raiz.vaiven) + raiz.mira + raiz.cabY
                eulerRotation.z: (raiz.quieto ? 3 : 5 * Math.sin(raiz.tiempo * 0.9)) + raiz.cabZ
                eulerRotation.x: (raiz.quieto ? 0 : -3 + 3 * Math.sin(raiz.tiempo * 0.7)) + raiz.cabX
                RuntimeLoader { source: raiz.url("cabeza"); position: Qt.vector3d(0, -0.64, 0)
                                onStatusChanged: if (status === RuntimeLoader.Success) raiz.cuenta() }
            }
        }
        }
    }
    readonly property var petCabeza: { raiz.tiempo; return vista.mapFrom3DScene(Qt.vector3d(raiz.petPos, 0.46, raiz.petZ)) }
    Repeater {
        model: (raiz.conMascota && raiz.corazones) ? 3 : 0
        Text {
            property real fase: (raiz.tiempo * 0.6 + index / 3) % 1
            text: "♥"; color: "#ff4d79"; font.bold: true; font.pixelSize: Math.max(14, raiz.height * 0.075)
            x: raiz.petCabeza.x - width / 2 + (index - 1) * raiz.height * 0.04 + 5 * Math.sin(fase * 12.5)
            y: raiz.petCabeza.y - fase * raiz.height * 0.14 - raiz.height * 0.02
            opacity: 1 - fase
        }
    }
    Text {
        visible: raiz.conMascota && raiz.texto !== ""
        text: raiz.texto; color: "#e8503a"; font.bold: true; font.pixelSize: Math.max(13, raiz.height * 0.06)
        style: Text.Outline; styleColor: "white"
        x: raiz.petCabeza.x - width / 2 + raiz.width * 0.03
        y: raiz.petCabeza.y - raiz.height * 0.09 - 3 * Math.abs(Math.sin(raiz.tiempo * raiz.petRitmo * 0.6)) * raiz.height * 0.03
    }
    function cuenta() { raiz.cargadas += 1; if (raiz.cargadas >= 7) raiz.listo() }
    onCarpetaChanged: raiz.cargadas = 0

    MouseArea {
        anchors.fill: parent
        cursorShape: raiz.arrastrable ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.PointingHandCursor
        property real ultimo: 0
        property real ultimoY: 0
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        hoverEnabled: raiz.casa
        function evento(tipo, e) {
            var b = raiz.bajoMouse(e.x, e.y)
            var cual = (tipo === "release" || tipo === "arrastre") ? b.mueble : b.indice       // al soltar o arrastrar: el mueble que hay abajo
            if (b.suelo !== null) raiz.casaEvento(tipo, b.suelo.x, b.suelo.z, cual)
            else raiz.casaEvento(tipo + "_fuera", 0, 0, cual)
        }
        onPressed: function(e) { ultimo = e.x; ultimoY = e.y; if (raiz.casa && e.button === Qt.LeftButton) evento("press", e) }
        onReleased: function(e) { if (raiz.casa && e.button === Qt.LeftButton) evento("release", e) }
        onPositionChanged: function(e) {
            if (raiz.casa && !(pressedButtons & Qt.RightButton)) { evento(pressed ? "arrastre" : "mover", e); ultimo = e.x; ultimoY = e.y; return }
            if (!raiz.arrastrable && !raiz.casa) return
            if (pressedButtons & Qt.RightButton) {
                // Mover la vista: lo que se arrastra sigue al mouse
                var porPixel = raiz.casa ? 2 * 4.75 / raiz.zoomU * Math.tan(17 * Math.PI / 180) / Math.max(1, raiz.height)
                                         : 2 * 6.6 * raiz.zoomM / raiz.zoomU * Math.tan(11.6 * Math.PI / 360) / Math.max(1, raiz.height)
                raiz.panX -= (e.x - ultimo) * porPixel
                raiz.panY += (e.y - ultimoY) * porPixel
            } else {
                raiz.giroMano += (e.x - ultimo) * 0.7
                raiz.giroVert += (e.y - ultimoY) * 0.7
            }
            ultimo = e.x; ultimoY = e.y
        }
        onWheel: function(w) {
            if (raiz.arrastrable || raiz.casa)
                raiz.zoomU = Math.max(0.4, Math.min(4.0, raiz.zoomU * (w.angleDelta.y > 0 ? 1.1 : 1 / 1.1)))
        }
        onDoubleClicked: if (raiz.arrastrable || raiz.casa) { raiz.giroMano = 0; raiz.giroVert = 0; raiz.zoomU = 1; raiz.panX = 0; raiz.panY = 0 }
        onClicked: if (!raiz.arrastrable) puente.tocar()
    }
}
"""


ESC_CASA = 0.62      # en la habitación BiriBiri y su mascota son más chicos que los muebles


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
        casa_evento = Signal(str, float, float, int)     # lo que pasa con el mouse en la habitación (ver EscenaCasa)

        def __init__(self, spec: dict | None = None, encuadre: str = "cuerpo", arrastrable: bool = False,
                     quieto: bool = False, parent=None, fondo: bool = False, con_pose: bool = True, lugar: str | None = None,
                     casa: bool = False):
            super().__init__(parent)
            self._con_pose = con_pose and encuadre != "busto"   # el busto del botón no hace poses
            self._lugar = lugar
            self._casa = casa
            self._casa_pet: dict = {}       # dónde está la mascota en la habitación (lo pone EscenaCasa)
            self._casa_bb: dict = {}        # y cómo está BiriBiri (sentado, por ejemplo)
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
                raiz.setProperty("fondo", fondo)
                raiz.setProperty("casa", casa)
                QObject.connect(raiz, SIGNAL("listo()"), self._avisar_listo)
                QObject.connect(raiz, SIGNAL("casaEvento(QString,double,double,int)"), self._avisar_casa)
            self.poner(spec or avatar3d.PREDETERMINADO)

        def _avisar_listo(self):
            self.listo.emit()

        def _avisar_casa(self, tipo, x, z, indice):
            self.casa_evento.emit(tipo, x, z, indice)

        def repose(self):
            """Vuelve a poner la pose con lo último que se sabe (la habitación cambió dónde y cómo están sentados)."""
            if getattr(self, "_spec_actual", None) is not None:
                self.poner(self._spec_actual)

        def poner(self, spec: dict):
            from .protagonista3d import ESCALA
            s = avatar3d.normalizar(spec)
            self._spec_actual = s
            self._escala = ESCALA.get(s["cuerpo"], ESCALA["normal"])
            self._poner_bandera(s["bandera"])
            self.pose(bandX=s["bandera_x"], bandY=s["bandera_y"], bandTam=s["bandera_tam"], bandGiro=s["bandera_giro"],
                      bandCostado=s["bandera_costado"])
            if self._con_pose:
                from . import mascotas, poses
                animal = mascotas.tipo(s["mascota"])
                ajustes = poses.ajustes(s["pose"], self._lugar)
                bb, pet = poses.interaccion(s["interaccion"], animal) if animal else ({}, dict(poses.MASCOTA_BASE))
                if animal and s["interaccion"] != "ninguna" and not self._casa:
                    ajustes = {**poses.ajustes("normal"), **bb}      # lo que hacen juntos manda sobre la pose elegida
                if self._casa:       # en la habitación son más chicos que el mobiliario y están donde los dejaste
                    ajustes = {**ajustes, "esc": ajustes["esc"] * ESC_CASA, **self._casa_bb}
                    pet = {**pet, "petEsc": pet["petEsc"] * ESC_CASA, **self._casa_pet}
                self.pose(**ajustes)
                self.pose(conMascota=bool(animal), **pet, **(mascotas.pivotes(s["mascota"]) if animal else {}))
            else:
                self.pose(conMascota=False)
            self._constructor.pedir(id(self), s)

        def _poner_bandera(self, codigo: str):
            """La bandera de fondo (si la vista la muestra): el dibujo de ese país, en la escena."""
            try:
                raiz = self.rootObject()
            except RuntimeError:
                return
            if raiz is None or not raiz.property("fondo"):
                return
            from . import banderas
            archivo = banderas.ruta(codigo, CARPETA) if codigo != "ninguna" else None
            raiz.setProperty("bandera", QUrl.fromLocalFile(str(archivo)).toString() if archivo else "")

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
                    raiz.setProperty(clave, valor if isinstance(valor, (bool, str, list, dict)) else float(valor))

        def imagen(self) -> QPixmap:
            return QPixmap.fromImage(self.grabFramebuffer())

    return Protagonista3D


_Protagonista3D = None
ultimo_error = ""   # por qué no se pudo usar Qt Quick 3D (para diagnosticar)


def crear(spec: dict | None = None, encuadre: str = "cuerpo", arrastrable: bool = False, parent=None, fondo: bool = False,
          con_pose: bool = True, lugar: str | None = None, casa: bool = False):
    """El Protagonista nuevo (Qt Quick 3D) o, si no se puede, el anterior. Los dos tienen poner(spec) y tocado."""
    global _Protagonista3D, ultimo_error
    if disponible():
        try:
            if _Protagonista3D is None:
                _Protagonista3D = _clase()
            vista = _Protagonista3D(spec, encuadre, arrastrable, parent=parent, fondo=fondo, con_pose=con_pose, lugar=lugar, casa=casa)
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
