"""Cliente de las cuentas de TorrentVision (servidor_social/): cuenta sin correo, muñequito, puntos y amigos.

Lo que se ve no sale de la PC con su nombre: se manda una huella (SHA-256) de cada película o capítulo visto, que el
servidor usa para no contarlo dos veces sin saber cuál es."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import fichas

TIEMPO = 20


class ErrorSocial(Exception):
    def __init__(self, mensaje: str, codigo: int = 0):
        super().__init__(mensaje)
        self.codigo = codigo


def direccion_valida(url: str) -> str:
    """HTTPS siempre; HTTP solo para un servidor en esta PC o en la red de la casa (para probar)."""
    url = (url or "").strip().rstrip("/")
    partes = urlparse(url)
    if partes.scheme not in ("https", "http") or not partes.hostname:
        raise ErrorSocial("Escribí la dirección del servidor, por ejemplo https://cuentas.ejemplo.com")
    if partes.scheme == "http":
        host = partes.hostname
        try:
            privada = host == "localhost" or ipaddress.ip_address(host).is_private
        except ValueError:
            privada = False
        if not privada:
            raise ErrorSocial("En internet el servidor tiene que usar https:// (la contraseña viaja en el pedido)")
    return url


LOCAL = "local"
_local: str | None = None
_cerrojo = threading.Lock()


def es_local(base: str) -> bool:
    return (base or "").strip().lower() in ("", LOCAL)


def servidor_local() -> str:
    """Hasta que haya un servidor en internet: el mismo servidor de cuentas corre adentro de TorrentVision, solo
    para esta PC (127.0.0.1, puerto libre), con la base en %LOCALAPPDATA%\\TVon\\cuentas.db."""
    global _local
    with _cerrojo:
        if _local is None:
            from servidor_social.servidor import crear_servidor
            carpeta = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TVon"
            carpeta.mkdir(parents=True, exist_ok=True)
            srv = crear_servidor(0, str(carpeta / "cuentas.db"), "127.0.0.1")
            threading.Thread(target=srv.serve_forever, daemon=True, name="cuentas-local").start()
            _local = f"http://127.0.0.1:{srv.server_address[1]}"
        return _local


class Cliente:
    def __init__(self, base: str, token: str = ""):
        # origen = lo que se guarda en la configuración ("local" o la dirección del servidor)
        self.origen = LOCAL if es_local(base) else direccion_valida(base)
        self.base = servidor_local() if self.origen == LOCAL else self.origen
        self.token = token

    def _pedir(self, metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
        cabeceras = {"Content-Type": "application/json", "User-Agent": "TorrentVision"}
        if self.token:
            cabeceras["Authorization"] = f"Bearer {self.token}"
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        pedido = urllib.request.Request(self.base + ruta, data=datos, method=metodo, headers=cabeceras)
        try:
            with urllib.request.urlopen(pedido, timeout=TIEMPO) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                mensaje = json.loads(e.read() or b"{}").get("error") or f"Error {e.code}"
            except ValueError:
                mensaje = f"Error {e.code}"
            raise ErrorSocial(mensaje, e.code) from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise ErrorSocial(f"No se pudo conectar con el servidor de cuentas: {getattr(e, 'reason', e)}") from None

    # Cuenta
    def registrar(self, nombre: str, clave: str) -> dict:
        r = self._pedir("POST", "/registro", {"nombre": nombre, "clave": clave})
        self.token = r["token"]
        return r

    def entrar(self, nombre: str, clave: str) -> dict:
        r = self._pedir("POST", "/entrar", {"nombre": nombre, "clave": clave})
        self.token = r["token"]
        return r

    def recuperar(self, nombre: str, codigo: str, nueva: str) -> dict:
        r = self._pedir("POST", "/recuperar", {"nombre": nombre, "codigo": codigo, "nueva": nueva})
        self.token = r["token"]
        return r

    def salir(self):
        try:
            self._pedir("POST", "/salir", {})
        finally:
            self.token = ""

    def yo(self) -> dict:
        return self._pedir("GET", "/yo")

    def guardar_avatar(self, avatar: dict) -> dict:
        return self._pedir("POST", "/avatar", {"avatar": avatar})

    def enviar_vistas(self, items: list[dict]) -> dict:
        return self._pedir("POST", "/vistas", {"items": items})

    # Amigos
    def amigos(self) -> dict:
        return self._pedir("GET", "/amigos")

    def pedir_amistad(self, nombre: str) -> dict:
        return self._pedir("POST", "/amigos/pedir", {"nombre": nombre})

    def responder(self, nombre: str, aceptar: bool) -> dict:
        return self._pedir("POST", "/amigos/responder", {"nombre": nombre, "aceptar": aceptar})

    def quitar(self, nombre: str) -> dict:
        return self._pedir("POST", "/amigos/quitar", {"nombre": nombre})


def huella(clave: str) -> str:
    return hashlib.sha256(("torrentvision|" + clave).encode()).hexdigest()


def vistas_de_biblioteca(bib) -> list[dict]:
    """Las películas y capítulos que terminaste de ver (90 % o más), como huellas. Del hilo de la interfaz."""
    items, vistas = [], set()
    for ruta, (_pos, _dur, visto) in bib.progresos().items():
        if not visto:
            continue
        nombre = Path(ruta).name
        clave = fichas.clave_de(nombre)[0]
        if clave.startswith("serie|"):
            ep = fichas.episodio(nombre)
            if not ep:
                continue
            clave, tipo = f"{clave}|{ep[0]}x{ep[1]}", "episodio"
        else:
            tipo = "pelicula"
        if clave not in vistas:
            vistas.add(clave)
            items.append({"huella": huella(clave), "tipo": tipo})
    return items
