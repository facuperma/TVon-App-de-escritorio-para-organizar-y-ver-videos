"""Arma el .zip del canal TorrentVision para Roku y, si se le pasa la IP del Roku, lo instala (modo desarrollador).

Uso:
    python roku/instalar.py                     # solo arma el zip
    python roku/instalar.py 192.168.1.36 CLAVE  # arma el zip y lo instala en el Roku

Antes, en el Roku: activar el modo desarrollador (en el control remoto: Inicio ×3, Arriba ×2, Derecha, Izquierda,
Derecha, Izquierda, Derecha), elegir una contraseña y dejar que reinicie. Esa es la CLAVE.
"""
from __future__ import annotations

import sys
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

RAIZ = Path(__file__).parent
SALIDA = RAIZ.parent / "instalador" / "TorrentVision-Roku.zip"
INCLUIR = ("manifest", "source", "components", "images")


def armar_zip(destino: Path = SALIDA) -> Path:
    destino.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre in INCLUIR:
            ruta = RAIZ / nombre
            archivos = [ruta] if ruta.is_file() else sorted(p for p in ruta.rglob("*") if p.is_file())
            for a in archivos:
                z.write(a, a.relative_to(RAIZ).as_posix())
    return destino


def instalar(ip: str, clave: str, paquete: Path) -> str:
    base = f"http://{ip}"
    manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None, base, "rokudev", clave)
    abrir = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(manager)).open
    limite = uuid.uuid4().hex
    partes = []
    for campo, valor in (("mysubmit", "Install"),):
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{valor}\r\n'.encode())
    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="archive"; filename="{paquete.name}"\r\n'
                  "Content-Type: application/zip\r\n\r\n".encode() + paquete.read_bytes() + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    pedido = urllib.request.Request(f"{base}/plugin_install", data=b"".join(partes), method="POST",
                                    headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    try:
        with abrir(pedido, timeout=60) as r:
            html = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"El Roku respondió {e.code}: revisá la IP y la contraseña del modo desarrollador.") from e
    except OSError as e:
        raise SystemExit(f"No pude hablar con el Roku en {ip}: {e}") from e
    return "Install Success" if "Install Success" in html or "Application Received" in html else html[-400:]


if __name__ == "__main__":
    zip_ = armar_zip()
    print(f"Armado: {zip_} ({zip_.stat().st_size // 1024} KB)")
    if len(sys.argv) >= 3:
        print("Instalando en el Roku…", instalar(sys.argv[1], sys.argv[2], zip_))
