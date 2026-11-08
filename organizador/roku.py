"""Roku: un canal propio (carpeta roku/) que ve la biblioteca de esta PC por la red de la casa.

El Roku no puede comprobar el certificado propio de TorrentVision, así que tiene su servidor aparte, en HTTP,
con estas protecciones:
  * solo IPs de la red privada (igual que ON);
  * el token del Roku (que se consigue aprobando un código en la PC o en el celular) solo sirve acá: con él no se
    puede manejar el mouse, el teclado ni la pantalla por el servidor de ON, y el de un celular no sirve en el Roku;
  * solo lectura de la biblioteca (video, subtítulos, pósters) y el «latido» con el que el Roku avisa por dónde va
    y recibe las órdenes del celular.
"""
from __future__ import annotations

import html
import json
import re
import socket
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote

from . import seguridad
from .remoto import ErrorRemoto, _entero, _Manejador, _Servidor, ffmpeg

PUERTO_ROKU = 8770
PUERTO_ECP = 8060            # el control externo que trae todo Roku (abrir el canal desde la PC)
SEGUNDOS_CONECTADO = 9       # sin latidos por más tiempo que esto, el Roku figura como desconectado
MAXIMO_FILA = 120
NOMBRE_LIMITE = 40
FORMATOS = {".mkv": "mkv", ".mp4": "mp4", ".m4v": "mp4", ".mov": "mp4"}


class EstadoRoku:
    """Qué Roku están conectados, por dónde van y qué órdenes les esperan."""

    def __init__(self):
        self._cerrojo = threading.Lock()
        self._latidos: dict[str, dict] = {}   # huella de sesión -> último latido
        self._ordenes: dict[str, list] = {}   # huella de sesión -> órdenes pendientes
        self._guardado: dict[str, float] = {}
        # «Conectar el Roku» desde el celular: los Roku de la red y qué está pasando
        self.encontrados: list[dict] = []
        self.buscando = False
        self.conectando = ""

    def latido(self, huella: str, nombre: str, ip: str, datos: dict) -> list[dict]:
        """Registra el latido y devuelve (y vacía) las órdenes pendientes de ese Roku."""
        with self._cerrojo:
            self._latidos[huella] = {
                "t": time.time(), "nombre": nombre, "ip": ip,
                "estado": str(datos.get("estado", "inactivo"))[:20],
                "pos": _entero(datos.get("pos")), "dur": _entero(datos.get("dur")),
                "id": _entero(datos.get("id")), "titulo": str(datos.get("titulo", ""))[:120],
            }
            return self._ordenes.pop(huella, [])

    def conectados(self) -> list[dict]:
        ahora = time.time()
        with self._cerrojo:
            vivos = [{"huella": h, **d} for h, d in self._latidos.items() if ahora - d["t"] <= SEGUNDOS_CONECTADO]
        return sorted(vivos, key=lambda d: -d["t"])

    def ultimo(self) -> dict | None:
        lista = self.conectados()
        return lista[0] if lista else None

    def encolar(self, orden: dict) -> int:
        """La orden va a todos los Roku conectados; devuelve a cuántos."""
        vivos = self.conectados()
        with self._cerrojo:
            for d in vivos:
                cola = self._ordenes.setdefault(d["huella"], [])
                cola.append(orden)
                del cola[:-20]  # si el Roku no contesta, no se acumulan órdenes viejas
        return len(vivos)

    def olvidar(self, huella: str):
        with self._cerrojo:
            self._latidos.pop(huella, None)
            self._ordenes.pop(huella, None)

    def guardar_progreso_ahora(self, huella: str) -> bool:
        """True como mucho una vez cada 10 s por Roku (para no escribir la base en cada latido)."""
        ahora = time.time()
        with self._cerrojo:
            if ahora - self._guardado.get(huella, 0) < 10:
                return False
            self._guardado[huella] = ahora
            return True


def abrir_canal_por_ecp(ip: str, contenido: int | None = None, canal: str = "dev") -> bool:
    """Le pide al Roku (con su control externo, puerto 8060) que abra el canal, si todavía no está abierto.
    Solo a IPs de la red de la casa."""
    if not seguridad.ip_permitida(ip):
        return False
    consulta = f"?contentId={int(contenido)}&mediaType=movie" if contenido else ""
    pedido = urllib.request.Request(f"http://{ip}:{PUERTO_ECP}/launch/{canal}{consulta}", data=b"", method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=4):
            return True
    except OSError:
        return False


def _pedir_ecp(ip: str, ruta: str, metodo: str = "GET", tiempo: float = 3) -> bytes | None:
    if not seguridad.ip_permitida(ip):
        return None
    pedido = urllib.request.Request(f"http://{ip}:{PUERTO_ECP}{ruta}", data=b"" if metodo == "POST" else None,
                                    method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=tiempo) as r:
            return r.read(65536)
    except OSError:
        return None


def _etiqueta(xml: bytes, *nombres: str) -> str:
    texto = xml.decode("utf-8", "replace")
    for nombre in nombres:
        m = re.search(rf"<{nombre}>([^<]{{1,80}})</{nombre}>", texto)
        if m and m.group(1).strip():
            return html.unescape(m.group(1).strip())
    return ""


def buscar_rokus(espera: float = 2.5) -> list[dict]:
    """Los Roku de la red de la casa (SSDP, como hace la app oficial): [{"ip", "nombre"}]."""
    ips: list[str] = []
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        s.settimeout(0.3)
        pregunta = (b"M-SEARCH * HTTP/1.1\r\nHost: 239.255.255.250:1900\r\nMan: \"ssdp:discover\"\r\n"
                    b"ST: roku:ecp\r\nMX: 2\r\n\r\n")
        fin = time.time() + espera
        enviadas = 0
        while time.time() < fin:
            if enviadas < 3 and time.time() > fin - espera + enviadas * 0.8:
                s.sendto(pregunta, ("239.255.255.250", 1900))
                enviadas += 1
            try:
                datos, (ip, _p) = s.recvfrom(2048)
            except OSError:
                continue
            if b"roku:ecp" in datos.lower() and ip not in ips and seguridad.ip_permitida(ip):
                ips.append(ip)
    finally:
        s.close()
    rokus = []
    for ip in ips:
        info = _pedir_ecp(ip, "/query/device-info") or b""
        nombre = _etiqueta(info, "user-device-name", "friendly-device-name", "default-device-name", "model-name")
        rokus.append({"ip": ip, "nombre": nombre or f"Roku ({ip})"})
    return rokus


def ip_local_hacia(ip: str) -> str:
    """La IP de esta PC en la red por la que se llega a ese aparato."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((ip, PUERTO_ECP))  # UDP: no manda nada, solo elige la interfaz
        return s.getsockname()[0]
    finally:
        s.close()


def vincular_por_ecp(ip: str, puerto_pc: int, pase: str, canal: str = "dev") -> bool:
    """Abre el canal en el Roku con un pase de un solo uso: el Roku se vincula solo, sin código.
    Si el canal ya está abierto, el pase le llega como «input» (sin reabrirlo)."""
    contenido = quote(f"v|{ip_local_hacia(ip)}|{puerto_pc}|{pase}", safe="")
    consulta = f"?contentId={contenido}&mediaType=movie"
    activa = _pedir_ecp(ip, "/query/active-app") or b""
    ruta = "/input" if f'id="{canal}"'.encode() in activa else f"/launch/{canal}"
    return _pedir_ecp(ip, ruta + consulta, "POST", 5) is not None


class _ManejadorRoku(_Manejador):
    """El servidor del Roku (HTTP). Reusa de ON el video por partes, los subtítulos y los pósters."""

    server_version = "TVon-Roku"

    # --- Rutas ---------------------------------------------------------------------------------

    def _get(self, ruta: str, consulta: dict):
        if ruta == "/roku/hola":
            return self._json({"tvon": 1, "roku": 1, "id": self.remoto.id_pc})
        if ruta == "/roku/solicitud":
            estado, token = self.remoto.estado_vinculo(str(consulta.get("id", ""))[:40], self.client_address[0])
            return self._json({"estado": estado, "token": token, "id": self.remoto.id_pc})
        token = self._sesion(consulta)
        control = self.remoto.control
        llamar = self.remoto.puente.llamar
        if ruta == "/roku/inicio":
            return self._json(llamar(lambda: _filas(control)))
        if ruta == "/roku/catalogo":
            return self._json(llamar(lambda: {"items": [
                _item(t) for t in control.catalogo(consulta.get("tipo", "todo"), "", consulta.get("q", "")[:80], "titulo")
            ][:400]}))
        if ruta == "/roku/serie":
            return self._json(llamar(lambda: _episodios(control, consulta.get("c", ""))))
        if ruta == "/roku/ficha":
            return self._json(llamar(lambda: _ficha(control, _entero(consulta.get("id")), consulta.get("modo", ""))))
        if ruta == "/roku/video":
            return self._video(consulta)
        if ruta == "/roku/subtitulo":
            return self._subtitulo(consulta)
        if ruta == "/roku/poster":
            return self._poster(consulta.get("c", ""))
        del token
        raise ErrorRemoto("No existe", 404)

    def _post(self, ruta: str, consulta: dict):
        if self.headers.get("X-TVon") != "1":
            raise ErrorRemoto("Falta la cabecera X-TVon", 403)
        if ruta == "/roku/solicitar":
            return self._solicitar_roku()
        if ruta == "/roku/pase":
            return self._usar_pase()
        if ruta == "/roku/latido":
            return self._latido(consulta)
        raise ErrorRemoto("No existe", 404)

    # --- Sesión del Roku -------------------------------------------------------------------------

    def _sesion(self, consulta: dict) -> str:
        token = str(consulta.get("t", ""))[:200]
        if not self.remoto.sesion_valida(token, roku=True):
            raise ErrorRemoto("Este Roku no está vinculado", 401)
        return token

    def _solicitar_roku(self):
        ip = self.client_address[0]
        if self.remoto.demasiados_intentos(ip):
            raise ErrorRemoto("Demasiados intentos: esperá 10 minutos", 429)
        datos = self._cuerpo()
        nombre = "Roku " + str(datos.get("nombre", "")).strip()[:NOMBRE_LIMITE]
        resultado = self.remoto.solicitar_vinculo("Roku", nombre.strip(), ip, roku=True)
        if resultado is None:
            raise ErrorRemoto("Ya hay un pedido de este Roku esperando en la PC", 409)
        self._json({"id": resultado, "codigo": self.remoto.codigo_vinculo(resultado, roku=True)})

    def _usar_pase(self):
        """El Roku que la PC abrió desde el celular («Conectar un Roku») canjea su pase por un token."""
        ip = self.client_address[0]
        if self.remoto.demasiados_intentos(ip):
            raise ErrorRemoto("Demasiados intentos: esperá 10 minutos", 429)
        datos = self._cuerpo()
        nombre = ("Roku " + str(datos.get("nombre", "")).strip()[:NOMBRE_LIMITE]).strip()
        token = self.remoto.usar_pase_roku(str(datos.get("pase", ""))[:80], ip, nombre)
        if not token:
            raise ErrorRemoto("El pase venció o ya se usó: volvé a tocar «Conectar un Roku» en el celular", 403)
        self._json({"token": token, "id": self.remoto.id_pc})

    def _latido(self, consulta: dict):
        token = self._sesion(consulta)
        datos = self._cuerpo()
        huella = seguridad.huella_sesion(token)
        nombre = self.remoto.nombre_de_sesion(huella)
        ordenes = self.remoto.roku.latido(huella, nombre, self.client_address[0], datos)
        # Por dónde va queda en la misma base que la PC y el celular (seguir viendo en cualquier lado)
        aid, pos, dur = _entero(datos.get("id")), _entero(datos.get("pos")), _entero(datos.get("dur"))
        if aid > 0 and dur > 0 and datos.get("estado") in ("reproduciendo", "pausa", "terminado") \
                and (datos.get("estado") == "terminado" or self.remoto.roku.guardar_progreso_ahora(huella)):
            posicion = dur if datos.get("estado") == "terminado" else pos
            try:
                self.remoto.puente.llamar(lambda: self.remoto.control.accion_progreso_celular(aid, posicion, dur))
            except ErrorRemoto:
                pass
        self._json({"ordenes": ordenes})


# --- Lo que se le muestra al Roku (todo plano y chico: el Roku Express tiene poca memoria) --------------

def _item(t: dict) -> dict:
    return {"tipo": t["tipo"], "id": t.get("id") or 0, "clave": t["clave"], "titulo": t["titulo"],
            "sub": " · ".join(x for x in (t.get("anio") or "", t.get("sub") or "") if x),
            "sinopsis": (t.get("sinopsis") or "")[:300],
            "poster": f"/roku/poster?c={_quitar(t['clave'])}" if t.get("poster") else "",
            "progreso": t.get("progreso") or 0, "visto": bool(t.get("visto"))}


def _quitar(clave: str) -> str:
    from urllib.parse import quote
    return quote(clave, safe="")


def _filas(control) -> dict:
    inicio = control.inicio()
    filas = [("Seguir viendo", inicio["seguir"]), ("A continuación", inicio["siguientes"]),
             ("Agregado hace poco", inicio["recientes"]), ("Favoritos", inicio["favoritos"]),
             ("Películas", control.catalogo("pelicula", "", "", "titulo")),
             ("Series", control.catalogo("serie", "", "", "titulo"))]
    return {"filas": [{"titulo": nombre, "items": [_item(t) for t in lista[:MAXIMO_FILA]]}
                      for nombre, lista in filas if lista],
            "peliculas": inicio["peliculas"], "series": inicio["series"]}


def _episodios(control, clave: str) -> dict:
    serie = control.serie(clave)
    lista = []
    for temp in serie["temporadas"]:
        for e in temp["episodios"]:
            if e["existe"]:
                lista.append({"id": e["id"], "titulo": f"T{temp['numero']} · {e['episodio']}  {e['titulo']}"[:90],
                              "visto": e["visto"], "progreso": e["progreso"] or 0})
    return {"titulo": serie["titulo"], "episodios": lista, "seguir": serie["seguir"]}


def _ficha(control, aid: int, modo: str) -> dict:
    """Lo que el Roku necesita para reproducir un video: dirección, formato, desde dónde y subtítulos."""
    f = control.ficha_archivo(aid)
    (_a, ruta, _t), = control._archivos([aid])
    formato = FORMATOS.get(Path(ruta).suffix.lower())
    base = f"/roku/video?id={aid}"
    if modo in ("audio", "video") or formato is None:
        if not ffmpeg():
            raise ErrorRemoto("Este video necesita ffmpeg en la PC para verse en el Roku "
                              "(winget install Gyan.FFmpeg y reabrir TorrentVision)", 501)
        base += f"&compat={modo if modo in ('audio', 'video') else 'video'}&desde=0"
        formato, pos = "ts", 0  # la conversión no se puede adelantar: arranca de cero
    else:
        pos = f["posicion"]
    return {"id": aid, "titulo": f["titulo"] if not f["serie"] else f"{f['titulo']} · {f['nombre_lindo']}"[:120],
            "url": base, "formato": formato, "pos": pos, "dur": f["duracion"],
            "subtitulos": [{"n": s["n"], "texto": s["texto"][:60], "elegido": s["elegido"]} for s in f["subtitulos"]],
            "siguiente": f["siguiente"] or 0}


def iniciar_servidor(remoto) -> _Servidor | None:
    """Levanta el servidor del Roku en el primer puerto libre desde 8770 (o None si no hay)."""
    for puerto in range(PUERTO_ROKU, PUERTO_ROKU + 10):
        try:
            servidor = _Servidor(("0.0.0.0", puerto), _ManejadorRoku, remoto)
        except OSError:
            continue
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        return servidor
    return None


def datos_json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode()
