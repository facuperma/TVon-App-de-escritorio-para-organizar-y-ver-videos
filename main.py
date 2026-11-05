import os
import re
import shutil
import sys
import time
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from organizador.db import Biblioteca
from organizador import inicio_windows
from organizador.inicio_windows import ARGUMENTO
from organizador.tema import ESTILO
from organizador.ventana import Ventana

VERSION = "1.9.5"
INSTANCIA = "TVon-una-sola-vez"

# Empaquetado con PyInstaller, los recursos están en sys._MEIPASS
RECURSOS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))


def carpeta_datos() -> Path:
    """Dónde se guarda la biblioteca: siempre %LOCALAPPDATA%\\TVon, se abra instalado o desde el
    código fuente. Así las categorías, la configuración, el certificado de ON y los celulares
    vinculados son los mismos (antes cada forma de abrirlo tenía su propia biblioteca)."""
    carpeta = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TVon"
    carpeta.mkdir(parents=True, exist_ok=True)
    proyecto = Path(__file__).parent
    if not getattr(sys, "frozen", False) and not (carpeta / "biblioteca.db").exists():
        # Primera vez con esta versión desde el código: se lleva la biblioteca de la carpeta del proyecto
        for nombre in ("biblioteca.db", "on_certificado.pem", "on_clave.pem"):
            if (proyecto / nombre).exists():
                shutil.copy2(proyecto / nombre, carpeta / nombre)
    return carpeta


def main():
    if sys.platform == "win32":
        # Sin esto, Windows agrupa la app con Python y muestra el ícono de Python en la barra de tareas
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TVon")
    app = QApplication(sys.argv)
    app.setApplicationName("TVon")
    app.setApplicationVersion(VERSION)
    # El .ico trae el logo sin el margen de la sombra: en la barra de título se ve más grande
    icono = RECURSOS / "organizador" / "icono.ico"
    app.setWindowIcon(QIcon(str(icono if icono.exists() else RECURSOS / "organizador" / "icono.png")))
    segundo_plano = ARGUMENTO in sys.argv
    # Un solo TVon a la vez: si ya está abierto (p. ej. junto al reloj), se le pide que se muestre
    if avisar_al_abierto(mostrar=not segundo_plano):
        return
    app.setStyle("Fusion")
    # «Arrancar con Windows» tiene que abrir esta copia (la instalada), no otra vieja o la del código
    inicio_windows.corregir()
    app.setStyleSheet(ESTILO)
    biblioteca = Biblioteca(carpeta_datos() / "biblioteca.db")
    ventana = Ventana(biblioteca)
    servidor = QLocalServer()
    QLocalServer.removeServer(INSTANCIA)
    servidor.setSocketOptions(QLocalServer.UserAccessOption)  # otros usuarios de la PC no pueden hablarle
    servidor.listen(INSTANCIA)
    servidor.newConnection.connect(lambda: _pedido_de_otra_instancia(servidor, ventana))
    if segundo_plano:
        ventana.iniciar_en_segundo_plano()  # arrancó con Windows
    else:
        ventana.show()
    sys.exit(app.exec())


def _numeros(version: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", version))


def avisar_al_abierto(mostrar: bool) -> bool:
    """True si ya hay un TVon abierto (y, si se pide, le dice que se muestre).
    Si el abierto es una versión más vieja (por ejemplo, quedó junto al reloj desde antes de
    actualizar), se cierra solo y deja arrancar a esta: así nunca se ve la versión vieja."""
    otro = QLocalSocket()
    otro.connectToServer(INSTANCIA)
    if not otro.waitForConnected(500):
        return False
    otro.write(f"{'mostrar' if mostrar else 'version'} {VERSION}".encode())
    otro.waitForBytesWritten(500)
    se_va = otro.waitForReadyRead(1500) and bytes(otro.readAll()) == b"me-voy"
    otro.disconnectFromServer()
    if not se_va:
        return True
    # Esperar a que termine de cerrarse (hasta 10 s)
    for _ in range(100):
        time.sleep(0.1)
        prueba = QLocalSocket()
        prueba.connectToServer(INSTANCIA)
        if not prueba.waitForConnected(100):
            return False
        prueba.disconnectFromServer()
    return True


def _pedido_de_otra_instancia(servidor: QLocalServer, ventana: Ventana):
    conexion = servidor.nextPendingConnection()
    if not conexion.waitForReadyRead(500):
        return conexion.disconnectFromServer()
    partes = bytes(conexion.readAll()).decode(errors="ignore").split()
    pedido, otra_version = (partes + ["", ""])[:2]
    if otra_version and _numeros(otra_version) > _numeros(VERSION):
        # Se abrió una versión más nueva: esta se va y le deja el lugar
        conexion.write(b"me-voy")
        conexion.waitForBytesWritten(500)
        conexion.disconnectFromServer()
        ventana._salir_del_todo()
        return
    if pedido == "mostrar":
        ventana._volver_del_segundo_plano()
    conexion.disconnectFromServer()


if __name__ == "__main__":
    main()
