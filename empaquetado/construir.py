"""Genera TVon.exe (PyInstaller) y el instalador TVon-Setup-<versión>.exe (Inno Setup).

Uso, desde la carpeta del proyecto:
    .venv\\Scripts\\pip install pyinstaller
    .venv\\Scripts\\python empaquetado\\construir.py

Requiere Inno Setup 6 (https://jrsoftware.org/isinfo.php o `winget install JRSoftware.InnoSetup`).
"""
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "compilado"
APP = SALIDA / "dist" / "TVon"
QT = APP / "_internal" / "PySide6"

# Partes de Qt que TVon no usa (teclado virtual táctil, QML/Quick, PDF, OpenGL por software)
# (Quick y Qml se quedan: el Protagonista se dibuja con Qt Quick 3D)
SOBRANTES = [
    "opengl32sw.dll", "Qt6VirtualKeyboard.dll", "Qt6Pdf.dll",
    "plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll", "plugins/imageformats/qpdf.dll",
]
# Lo que PyInstaller suma al juntar los módulos QML y TorrentVision no usa (el navegador Chromium solo pesa ~200 MB)
SOBRANTES_PATRONES = [
    "Qt6WebEngine*", "QtWebEngineProcess.exe", "resources/qtwebengine*", "translations/qtwebengine_locales",
    "Qt6WebChannel*", "Qt6WebSockets*", "Qt6WebView*", "Qt63D*", "Qt6Charts*", "Qt6DataVisualization*", "Qt6Graphs*",
    "Qt6Location*", "Qt6Positioning*", "Qt6Pdf*", "Qt6Quick3DPhysics*", "Qt6Quick3DParticle*", "Qt6Quick3DXr*",
    "Qt6Quick3DSpatialAudio*", "Qt6SpatialAudio*", "Qt6QuickControls2*", "Qt6QuickDialogs2*", "Qt6QuickTemplates2*",
    "Qt6LabsStyleKit*", "Qt6Sensors*", "Qt6Scxml*", "Qt6StateMachine*", "Qt6RemoteObjects*", "Qt6TextToSpeech*",
    "Qt6Test*", "Qt6QuickTest*", "Qt6Bluetooth*", "Qt6Nfc*", "Qt6SerialPort*", "Qt6Designer*", "Qt6Help*",
    "Qt6VirtualKeyboard*", "Qt6HttpServer*", "Qt6Protobuf*", "Qt6Grpc*",
    "qml/Qt3D", "qml/Qt5Compat", "qml/QtCharts", "qml/QtDataVisualization", "qml/QtGraphs", "qml/QtLocation",
    "qml/QtMultimedia", "qml/QtPositioning", "qml/QtRemoteObjects", "qml/QtScxml", "qml/QtSensors", "qml/QtTest",
    "qml/QtTextToSpeech", "qml/QtWebChannel", "qml/QtWebEngine", "qml/QtWebSockets", "qml/QtWebView",
    "qml/QtNetwork", "qml/QtBluetooth", "qml/QtNfc", "qml/QtHttpServer", "qml/QtGrpc", "qml/QtProtobuf",
    "qml/QtQuick/Controls", "qml/QtQuick/Dialogs", "qml/QtQuick/VirtualKeyboard", "qml/QtQuick/Pdf",
    "qml/QtQuick/NativeStyle", "qml/QtQuick/Scene2D", "qml/QtQuick/Scene3D", "qml/QtQuick/Particles",
    "qml/QtQuick/Templates", "qml/QtQuick/Effects", "qml/QtQuick/tooling",
    "qml/QtQuick3D/Effects", "qml/QtQuick3D/MaterialEditor", "qml/QtQuick3D/ParticleEffects",
    "qml/QtQuick3D/Particles3D", "qml/QtQuick3D/Physics", "qml/QtQuick3D/SpatialAudio", "qml/QtQuick3D/designer",
    "qml/QtQuick3D/Xr", "qml/QtQuick3D/LightmapperOutputWindow.qml",
]


# Motor de torrents (GPL v2, https://aria2.github.io): se baja una vez y se verifica la huella
ARIA2_URL = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"
ARIA2_SHA256 = "67d015301eef0b612191212d564c5bb0a14b5b9c4796b76454276a4d28d9b288"
BIN = RAIZ / "organizador" / "bin"
import PySide6  # noqa: E402
PYSIDE = Path(PySide6.__file__).parent


def bajar_aria2():
    if (BIN / "aria2c.exe").exists():
        return
    print("== Bajando aria2")
    datos = urlopen(ARIA2_URL, timeout=120).read()
    if hashlib.sha256(datos).hexdigest() != ARIA2_SHA256:
        sys.exit("La huella de aria2 no coincide: no se usa")
    BIN.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        for nombre in z.namelist():
            if nombre.endswith("/aria2c.exe"):
                (BIN / "aria2c.exe").write_bytes(z.read(nombre))
            elif nombre.endswith("/COPYING"):
                (BIN / "aria2-LICENCIA.txt").write_bytes(z.read(nombre))


def version() -> str:
    return re.search(r'VERSION = "(.+?)"', (RAIZ / "main.py").read_text(encoding="utf-8")).group(1)


def apk_celular() -> Path:
    apks = sorted((RAIZ / "instalador").glob("TorrentVision-Android-*.apk"),
                  key=lambda a: [int(n) for n in re.findall(r"\d+", a.stem)])
    if not apks:
        sys.exit("Falta la APK del celular en instalador/ (android\\gradlew.bat assembleRelease)")
    return apks[-1]


def iscc() -> Path:
    candidatos = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for ruta in candidatos:
        if ruta.exists():
            return ruta
    sys.exit("No se encontró Inno Setup 6 (ISCC.exe). Instalalo con: winget install JRSoftware.InnoSetup")


def main():
    v = version()
    print("== Ícono")
    subprocess.run([sys.executable, str(RAIZ / "empaquetado" / "generar_icono.py")], check=True)
    bajar_aria2()
    print(f"== TVon {v}: ejecutable")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "TVon",
        "--icon", str(RAIZ / "organizador" / "icono.ico"),
        "--add-data", f"{RAIZ / 'organizador' / 'icono.png'};organizador",
        "--add-data", f"{RAIZ / 'organizador' / 'icono.ico'};organizador",
        "--add-data", f"{RAIZ / 'organizador' / 'paleta.dat'};organizador",
        # La app del celular (modo ON)
        "--add-data", f"{RAIZ / 'organizador' / 'web'};organizador/web",
        "--add-data", f"{RAIZ / 'organizador' / 'fuentes'};organizador/fuentes",
        # Torrents
        "--add-data", f"{BIN};organizador/bin",
        # La APK del celular: se baja escaneando el QR, sin internet
        "--add-data", f"{apk_celular()};organizador/apk",
        # Chromecast: zeroconf y pychromecast cargan partes propias que PyInstaller no ve solo
        "--collect-submodules", "zeroconf", "--collect-submodules", "pychromecast",
        # Cuentas guardadas en la PC (el servidor de cuentas corre adentro de la app)
        "--hidden-import", "servidor_social.servidor",
        # El Protagonista: Qt Quick 3D (y sus módulos QML)
        "--hidden-import", "PySide6.QtQuick3D", "--hidden-import", "PySide6.QtQuickWidgets",
        "--hidden-import", "PySide6.QtQml", "--hidden-import", "PySide6.QtQuick",
        # El lector de .glb de Qt Quick 3D (PyInstaller no lo junta solo)
        "--add-binary", f"{PYSIDE / 'plugins' / 'assetimporters' / 'assimp.dll'};PySide6/plugins/assetimporters",
        "--distpath", str(SALIDA / "dist"), "--workpath", str(SALIDA / "build"),
        "--specpath", str(SALIDA), str(RAIZ / "main.py"),
    ], check=True)

    print("== Recortando partes de Qt que no se usan")
    for nombre in SOBRANTES:
        (QT / nombre).unlink(missing_ok=True)
    for patron in SOBRANTES_PATRONES:
        for ruta in list(QT.glob(patron)):
            if ruta.is_dir():
                shutil.rmtree(ruta, ignore_errors=True)
            else:
                ruta.unlink(missing_ok=True)
    for qm in (QT / "translations").glob("*.qm"):
        if not qm.stem.endswith("_es"):
            qm.unlink()
    tamano = sum(f.stat().st_size for f in APP.rglob("*") if f.is_file())
    print(f"   {tamano / 1024**2:.0f} MB")

    print("== Prueba del Protagonista 3D con lo que quedó")
    prueba = SALIDA / "prueba_3d.png"
    prueba.unlink(missing_ok=True)
    r = subprocess.run([str(APP / "TVon.exe"), "--probar-3d", str(prueba)], timeout=180)
    if r.returncode != 0 or not prueba.exists():
        motivo = prueba.with_suffix(".txt")
        print("   motivo:", motivo.read_text(encoding="utf-8") if motivo.exists() else "(sin datos)")
        sys.exit(f"El Protagonista 3D no anda en el ejecutable (código {r.returncode}): falta algo de Qt Quick 3D")
    print("   OK:", prueba)

    print("== Instalador")
    subprocess.run([str(iscc()), f"/DVersion={v}", f"/DOrigen={APP}", f"/O{SALIDA}",
                    str(RAIZ / "empaquetado" / "TVon.iss")], check=True)
    instalador = SALIDA / f"TorrentVision-Setup-{v}.exe"
    print(f"\nListo: {instalador} ({instalador.stat().st_size / 1024**2:.0f} MB)")


if __name__ == "__main__":
    main()
