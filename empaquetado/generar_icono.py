"""Genera organizador/icono.ico (varios tamaños) a partir de organizador/icono.png.

Uso: .venv\\Scripts\\python empaquetado\\generar_icono.py
"""
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "organizador" / "icono.png"
DESTINO = RAIZ / "organizador" / "icono.ico"
TAMANOS = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def reducir(imagen: QImage, lado: int) -> QImage:
    # Reducir a la mitad por pasos da bordes más limpios que un salto de 1024 a 16
    while imagen.width() >= lado * 2:
        imagen = imagen.scaled(imagen.width() // 2, imagen.height() // 2,
                               Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return imagen.scaled(lado, lado, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def recortado(imagen: QImage) -> QImage:
    """El logo entero (cuadrado redondeado con su borde), sin el margen transparente de la
    sombra: así ocupa todo el ícono y se ve más grande en cualquier tamaño."""
    lado = imagen.width()
    margen = round(lado * 60 / 1024)  # el cuadrado va de 72 a 952 en el logo de 1024
    return imagen.copy(margen, margen, lado - 2 * margen, lado - 2 * margen)


def png_de(imagen: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    imagen.save(buffer, "PNG")
    return bytes(buffer.data())


def dib_de(imagen: QImage) -> bytes:
    """El formato clásico de los .ico (mapa de bits de 32 bits + máscara): la barra de tareas y la caché de
    íconos de Windows lo leen siempre; un PNG adentro del .ico solo es seguro en el tamaño de 256."""
    imagen = imagen.convertToFormat(QImage.Format_ARGB32)
    lado = imagen.width()
    cabecera = struct.pack("<IiiHHIIiiII", 40, lado, lado * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    filas = []
    for y in range(lado - 1, -1, -1):              # de abajo hacia arriba
        linea = bytes(imagen.constScanLine(y))[:lado * 4]   # BGRA en memoria (ARGB32 little endian)
        filas.append(linea)
    ancho_mascara = ((lado + 31) // 32) * 4
    mascara = bytes(ancho_mascara * lado)          # todo 0: la transparencia la da el alfa
    return cabecera + b"".join(filas) + mascara


def main():
    original = QImage(str(ORIGEN)).convertToFormat(QImage.Format_ARGB32)
    sin_margen = recortado(original)
    imagenes = [png_de(reducir(sin_margen, lado)) if lado >= 256 else dib_de(reducir(sin_margen, lado))
                for lado in TAMANOS]
    # Formato ICO: cabecera, una entrada de 16 bytes por tamaño y los PNG a continuación
    cabecera = struct.pack("<HHH", 0, 1, len(TAMANOS))
    desplazamiento = len(cabecera) + 16 * len(TAMANOS)
    entradas = b""
    for lado, datos in zip(TAMANOS, imagenes):
        entradas += struct.pack("<BBBBHHII", lado % 256, lado % 256, 0, 0, 1, 32, len(datos), desplazamiento)
        desplazamiento += len(datos)
    DESTINO.write_bytes(cabecera + entradas + b"".join(imagenes))
    print(f"{DESTINO.name}: {len(TAMANOS)} tamaños, {DESTINO.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
