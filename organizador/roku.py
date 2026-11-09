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

import hashlib
import html
import os
import json
import re
import select
import socket
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote

import subprocess
import sys

from . import seguridad
from .remoto import ErrorRemoto, _entero, _Manejador, _Servidor, ffmpeg, subtitulos_del_video

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
        # Sincronización automática de subtítulos para el video del Roku: -1 = no, 0..99 = avance
        self.sincronizando = -1
        self.ultimo_aviso = ""

    def latido(self, huella: str, nombre: str, ip: str, datos: dict) -> list[dict]:
        """Registra el latido y devuelve (y vacía) las órdenes pendientes de ese Roku."""
        with self._cerrojo:
            self._latidos[huella] = {
                "t": time.time(), "nombre": nombre, "ip": ip,
                "estado": str(datos.get("estado", "inactivo"))[:20],
                "pos": _entero(datos.get("pos")), "dur": _entero(datos.get("dur")),
                "id": _entero(datos.get("id")), "titulo": str(datos.get("titulo", ""))[:120],
                # Los subtítulos que tiene el video en el Roku y cuál está puesto (-1: ninguno), para el celular
                "subs": [str(x)[:60] for x in datos.get("subs", [])][:30] if isinstance(datos.get("subs"), list) else [],
                "sub": _entero(datos.get("sub", -1)) if datos.get("sub") is not None else -1,
                "retraso": _entero(datos.get("retraso", 0)), "escala": float(datos.get("escala") or 1.0),
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

    def guardar_subs_si_cambio(self, huella: str, clave: tuple) -> bool:
        with self._cerrojo:
            antes = getattr(self, "_subs_guardados", {}).get(huella)
            self._subs_guardados = {**getattr(self, "_subs_guardados", {}), huella: clave}
        return antes is not None and antes != clave

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


def _ips_locales() -> list[str]:
    """Las IPv4 de esta PC en redes privadas (la de la casa primero). Con una VPN (Radmin, Hamachi…) la búsqueda
    salía por la placa de la VPN y el Roku no la escuchaba: hay que preguntar por cada placa."""
    ips = set()
    try:
        ips.update(i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    try:
        ips.add(ip_local_hacia("192.168.1.1"))  # la de la ruta por defecto
    except OSError:
        pass
    privadas = [ip for ip in ips if seguridad.ip_permitida(ip) and not ip.startswith("127.")]
    return sorted(privadas, key=lambda ip: (not ip.startswith("192.168."), ip))


def _escanear_red(ip_pc: str, tiempo: float = 0.6) -> list[str]:
    """Plan B: pregunta a todas las IPs de la red de la casa (/24) si tienen el control de Roku (puerto 8060)."""
    base = ip_pc.rsplit(".", 1)[0]
    encontradas: list[str] = []

    def probar(ip):
        try:
            with socket.create_connection((ip, PUERTO_ECP), timeout=tiempo):
                encontradas.append(ip)
        except OSError:
            pass

    hilos = [threading.Thread(target=probar, args=(f"{base}.{n}",), daemon=True) for n in range(1, 255)
             if f"{base}.{n}" != ip_pc]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(tiempo + 0.5)
    return encontradas


def buscar_rokus(espera: float = 2.5, conocidas: list[str] | tuple = ()) -> list[dict]:
    """Los Roku de la red de la casa: SSDP (como la app oficial) por cada placa de red; si no aparece ninguno,
    se prueban las IPs ya conocidas y se recorre la red. [{"ip", "nombre"}]"""
    ips: list[str] = []
    pregunta = (b"M-SEARCH * HTTP/1.1\r\nHost: 239.255.255.250:1900\r\nMan: \"ssdp:discover\"\r\n"
                b"ST: roku:ecp\r\nMX: 2\r\n\r\n")
    socks = []
    locales = _ips_locales()
    for local in locales or ["0.0.0.0"]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.bind((local, 0))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            if local != "0.0.0.0":
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local))
            s.setblocking(False)
            socks.append(s)
        except OSError:
            continue
    try:
        fin = time.time() + espera
        enviadas = 0
        while time.time() < fin:
            if enviadas < 3 and time.time() > fin - espera + enviadas * 0.8:
                for s in socks:
                    try:
                        s.sendto(pregunta, ("239.255.255.250", 1900))
                    except OSError:
                        pass
                enviadas += 1
            listos = select.select(socks, [], [], 0.2)[0] if socks else []
            for s in listos:
                try:
                    datos, (ip, _p) = s.recvfrom(2048)
                except OSError:
                    continue
                if b"roku:ecp" in datos.lower() and ip not in ips and seguridad.ip_permitida(ip):
                    ips.append(ip)
    finally:
        for s in socks:
            s.close()
    if not ips:
        for ip in conocidas:
            if ip and ip not in ips and _pedir_ecp(ip, "/query/device-info", tiempo=1.5):
                ips.append(ip)
    if not ips:
        for local in locales:
            if local.startswith(("192.168.", "10.", "172.")):
                ips.extend(ip for ip in _escanear_red(local) if ip not in ips)
    rokus = []
    for ip in ips:
        info = _pedir_ecp(ip, "/query/device-info") or b""
        if b"<device-info" not in info:
            continue  # tenía el puerto abierto pero no es un Roku
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
            ][:3000]}))
        if ruta == "/roku/serie":
            return self._json(llamar(lambda: _episodios(control, consulta.get("c", ""))))
        if ruta == "/roku/ficha":
            desde = _entero(consulta["desde"]) if "desde" in consulta else None
            aid = _entero(consulta.get("id"))
            modo = decidir_modo(str(self._video_de({"id": aid})), consulta.get("modo", ""), (desde or 0) / 1000)
            return self._json(llamar(lambda: _ficha(control, aid, modo, desde)))
        if ruta == "/roku/video":
            return self._video(consulta)
        if ruta == "/roku/subtitulo":
            return self._subtitulo_roku(consulta)
        if ruta == "/roku/subs":
            return self._subs_roku(consulta)
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
        if ruta == "/roku/sincronizar":
            self._sesion(consulta)
            return self._json(self.remoto.puente.llamar(lambda: self.remoto.control.accion_roku_sincronizar()) or {})
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

    def _subs_roku(self, consulta: dict):
        """Los diálogos de un subtítulo como lista [inicio ms, fin ms, texto]: el Roku los dibuja él (blancos, con
        sombra) y así se puede correr el retraso y sincronizar. Sin las etiquetas de formato del .srt."""
        from .subtitulos import Subtitulos
        ruta = self._video_de(consulta)
        lista = self.remoto.puente.llamar(lambda: subtitulos_del_roku(self.remoto.bib, str(ruta)))
        try:
            sub = Subtitulos(lista[int(consulta.get("n", 0))])
        except (ValueError, IndexError, OSError):
            raise ErrorRemoto("Ese subtítulo no existe", 404) from None
        limpio = []
        for a, b, t in sorted(sub.cues):
            t = re.sub(r"\{\\[^}]*\}|<[^>]+>", "", t).replace("&nbsp;", " ").replace("&amp;", "&").strip()
            if t and b > a:
                limpio.append([a, b, t])
        self._json({"cues": limpio})

    def _subtitulo_roku(self, consulta: dict):
        """Como el de ON, pero si el video convertido empieza más adelante («desde», en ms), los tiempos se corren
        para que coincidan con lo que el Roku cuenta desde 0."""
        desde = _entero(consulta.get("desde", 0))
        if not desde:
            return self._subtitulo(consulta)
        from .subtitulos import Subtitulos
        ruta = self._video_de(consulta)
        lista = self.remoto.puente.llamar(lambda: subtitulos_del_roku(self.remoto.bib, str(ruta)))
        try:
            sub = Subtitulos(lista[int(consulta.get("n", 0))])
        except (ValueError, IndexError, OSError):
            raise ErrorRemoto("Ese subtítulo no existe", 404) from None

        def tiempo(ms):
            return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
        bloques = []
        for a, b, texto in sub.cues:
            if b - desde <= 0:
                continue
            bloques.append(f"{len(bloques) + 1}\n{tiempo(max(0, a - desde))} --> {tiempo(b - desde)}\n{texto}\n")
        self._responder(200, "\n".join(bloques).encode("utf-8"), "application/x-subrip; charset=utf-8",
                        {"Cache-Control": "no-store"})

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
        if aid > 0 and "sub" in datos:
            clave = (aid, _entero(datos.get("sub", -1)), _entero(datos.get("retraso", 0)))
            if self.remoto.roku.guardar_subs_si_cambio(huella, clave):
                try:
                    self.remoto.puente.llamar(lambda: self.remoto.control.guardar_subs_roku(*clave))
                except ErrorRemoto:
                    pass
        # «detenido»: el Roku salió del video (atrás o Parar): se guarda ya, sin esperar los 10 s
        if aid > 0 and dur > 0 and datos.get("estado") in ("reproduciendo", "pausa", "terminado", "detenido") \
                and (datos.get("estado") in ("terminado", "detenido") or self.remoto.roku.guardar_progreso_ahora(huella)):
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


# --- Qué puede reproducir el Roku tal cual ---------------------------------------------------------------
# El Roku Express no decodifica video HEVC de 10 bits (los «x265 10bit» de los torrents) y con sonido 5.1 (AAC 5.1,
# AC3, DTS) queda mudo según la tele. La PC mira cada video con ffprobe y, si hace falta, lo convierte mientras se ve:
# solo el sonido (barato) o también la imagen, con la placa de video si se puede (NVENC).

_analisis: dict[tuple[str, float], dict] = {}
_nvenc: bool | None = None


def _entero_seguro(valor, defecto=0) -> int:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return defecto


def _moov_al_final(ruta: str) -> bool:
    """¿Es un .mp4/.mov con el índice (moov) después de los datos? Así no se puede empezar a verlo por la red ni
    saltar rápido: el Roku espera (o falla). Se mira solo el principio de la lista de bloques del archivo."""
    if Path(ruta).suffix.lower() not in (".mp4", ".m4v", ".mov"):
        return False
    try:
        with open(ruta, "rb") as f:
            posicion, total = 0, os.fstat(f.fileno()).st_size
            for _ in range(64):
                f.seek(posicion)
                cabecera = f.read(16)
                if len(cabecera) < 8:
                    return False
                tamano, tipo = int.from_bytes(cabecera[:4], "big"), cabecera[4:8]
                if tipo == b"moov":
                    return False
                if tipo == b"mdat":
                    return True
                if tamano == 1 and len(cabecera) >= 16:
                    tamano = int.from_bytes(cabecera[8:16], "big")
                if tamano < 8 or posicion + tamano >= total:
                    return False
                posicion += tamano
    except OSError:
        return False
    return False


_CODECS_TEXTO = {"subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text"}


def analizar(ruta: str) -> dict:
    """Lo que hace falta saber de un video para decidir cómo mandarlo al Roku (ffprobe). {} si no hay ffprobe."""
    exe = ffmpeg()
    if not exe:
        return {}
    try:
        clave = (ruta, Path(ruta).stat().st_mtime)
    except OSError:
        return {}
    if clave in _analisis:
        return _analisis[clave]
    sonda = Path(exe).with_name("ffprobe.exe" if exe.lower().endswith(".exe") else "ffprobe")
    try:
        r = subprocess.run([str(sonda), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", ruta],
                           capture_output=True, timeout=30,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        datos = json.loads(r.stdout or b"{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {}
    flujos = datos.get("streams", [])
    formato = datos.get("format") or {}
    video = next((s for s in flujos if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), {})
    audios = [s for s in flujos if s.get("codec_type") == "audio"]
    # La pista de sonido: la marcada como principal; si no, la primera
    elegido = next((i for i, a in enumerate(audios) if (a.get("disposition") or {}).get("default")), 0)
    audio = audios[elegido] if audios else {}
    subs = []
    for i, st in enumerate(s for s in flujos if s.get("codec_type") == "subtitle"):
        if st.get("codec_name") in _CODECS_TEXTO:
            tags = st.get("tags") or {}
            subs.append({"i": i, "idioma": (tags.get("language") or "").lower(), "titulo": tags.get("title") or ""})

    def _inicio(flujo):
        try:
            return float(flujo.get("start_time") or 0)
        except ValueError:
            return 0.0

    def _fps(texto):
        try:
            a, b = str(texto).split("/")
            return float(a) / float(b) if float(b) else 0.0
        except (ValueError, ZeroDivisionError):
            return 0.0

    info = {"video": video.get("codec_name", ""), "pixeles": video.get("pix_fmt", ""),
            "perfil": video.get("profile", ""), "nivel": _entero_seguro(video.get("level")),
            "ancho": _entero_seguro(video.get("width")), "alto": _entero_seguro(video.get("height")),
            "fps": _fps(video.get("avg_frame_rate") or video.get("r_frame_rate")),
            "bitrate": _entero_seguro(formato.get("bit_rate")),
            "desfase": abs(_inicio(video) - _inicio(audio)) if audio else 0.0,
            "audio": audio.get("codec_name", ""), "canales": _entero_seguro(audio.get("channels")),
            "audio_idx": elegido, "subs": subs, "moov_al_final": _moov_al_final(ruta),
            "duracion": _entero_seguro(float(formato.get("duration") or 0) * 1000 if str(formato.get("duration") or "0").replace(".", "", 1).isdigit() else 0)}
    _analisis[clave] = info
    return info


def evaluar(ruta: str) -> tuple[str, list[str]]:
    """(modo, motivos). «» si el Roku lo reproduce tal cual; «audio» si la PC solo lo vuelve a empaquetar (con el sonido
    en estéreo si hace falta); «video» si además hay que convertir la imagen. Es estricto a propósito: es más seguro
    pasar por la PC que dejar que el Roku se trabe."""
    info = analizar(ruta)
    if not info:
        return "", []
    motivos_video, motivos_audio = [], []
    if not info["video"]:
        # Solo sonido (una grabación en .mp4): se reproduce con pantalla negra
        if info["audio"] and not (info["audio"] in ("aac", "mp3") and 0 < info["canales"] <= 2):
            return "audio", ["solo sonido, no estéreo"]
        return "", []
    if info["video"] != "h264":
        motivos_video.append(f"imagen {info['video'] or 'desconocida'}")
    if info["pixeles"] not in ("yuv420p", "yuvj420p", ""):
        motivos_video.append(f"color {info['pixeles']}")
    if info["perfil"] and info["perfil"].split(" ")[0] not in ("Baseline", "Constrained", "Main", "High") \
            or info["perfil"] in ("High 10", "High 4:2:2", "High 4:4:4 Predictive", "High 10 Intra"):
        motivos_video.append(f"perfil {info['perfil']}")
    if info["nivel"] > 42:
        motivos_video.append(f"nivel {info['nivel'] / 10:g}")
    if info["ancho"] > 1920 or info["alto"] > 1088:
        motivos_video.append(f"{info['ancho']}x{info['alto']}")
    if info["fps"] > 61:
        motivos_video.append(f"{info['fps']:g} cuadros por segundo")
    if info["bitrate"] > 20_000_000:
        motivos_video.append(f"{info['bitrate'] / 1e6:.0f} Mbps")
    if info["audio"] and not (info["audio"] in ("aac", "mp3") and 0 < info["canales"] <= 2):
        motivos_audio.append(f"sonido {info['audio']} {info['canales']} canales")
    if info["desfase"] >= 0.04:
        motivos_audio.append("imagen y sonido desfasados")
    if info["moov_al_final"]:
        motivos_audio.append("índice al final del archivo")
    if motivos_video:
        return "video", motivos_video + motivos_audio
    if motivos_audio:
        return "audio", motivos_audio
    return "", []


def modo_para_roku(ruta: str) -> str:
    return evaluar(ruta)[0]


MODOS = ("", "audio", "video", "soft")   # de menos a más conversión; «soft» = por programa (sin placa de video)


def orden_conversion(exe: str, ruta: str, modo: str, segundos: float, limite: float | None = None,
                     salida: str = "pipe:1") -> list[str]:
    """El comando de ffmpeg que arma el video para el Roku (mpegts) desde «segundos». Lo usa la conversión y la
    prueba previa, así que se prueba exactamente lo que se va a mandar."""
    info = analizar(ruta)
    sin_imagen = not info.get("video")
    if sin_imagen:
        video = ["-vn"]
    elif modo == "audio":
        video = ["-c:v", "copy"]
        if info.get("video") in ("h264", ""):
            # Algunos .mp4 tienen los parámetros del video donde se pierden al pasar a mpegts y la imagen no arranca:
            # se repiten en cada cuadro clave
            video += ["-bsf:v", "h264_mp4toannexb,dump_extra=freq=keyframe"]
    elif modo == "soft":
        video = ["-vf", "scale='min(1280,iw)':-2,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "24", "-profile:v", "main", "-level", "4.0", "-g", "48"]
    else:
        escala = ["-vf", "scale='min(1920,iw)':-2,format=yuv420p"]
        video = escala + (["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0",
                           "-profile:v", "high", "-g", "48"] if nvenc_disponible() else
                          ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-profile:v", "high", "-g", "48"])
    orden = [exe, "-hide_banner", "-loglevel", "error", "-fflags", "+genpts", "-ss", f"{segundos:.3f}", "-i", ruta,
             *([] if sin_imagen else ["-map", "0:v:0"]), "-map", f"0:a:{info.get('audio_idx', 0)}?", "-sn", "-dn",
             "-map_metadata", "-1",
             *video, "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-af", "aresample=async=1"]
    if limite:
        orden += ["-t", f"{limite:g}"]
    return orden + ["-f", "mpegts", salida]


_pruebas: dict[tuple, str | None] = {}


def verificar(ruta: str, modo: str, desde: float = 0.0) -> str | None:
    """Prueba previa: arma 6 s del video como lo mandaría y comprueba que se pueda decodificar, que tenga imagen
    (perfil y tamaño) y sonido. None si está bien; si no, qué falló (la PC entonces usa un modo más seguro)."""
    exe = ffmpeg()
    if not exe:
        return None
    try:
        clave = (ruta, Path(ruta).stat().st_mtime, modo, int(desde // 60))
    except OSError:
        return None
    if clave in _pruebas:
        return _pruebas[clave]
    marca = dict(creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    sonda = str(Path(exe).with_name("ffprobe.exe" if exe.lower().endswith(".exe") else "ffprobe"))
    motivo = None
    try:
        r = subprocess.run(orden_conversion(exe, ruta, modo, desde, limite=4), capture_output=True, timeout=90, **marca)
        datos = r.stdout
        if r.returncode != 0 or len(datos) < 20_000:
            motivo = "ffmpeg no pudo armar el video: " + r.stderr.decode(errors="replace")[:120]
        else:
            q = subprocess.run([sonda, "-v", "error", "-print_format", "json", "-show_streams", "-"],
                               input=datos, capture_output=True, timeout=30, **marca)
            flujos = json.loads(q.stdout or b"{}").get("streams", [])
            vid = next((f for f in flujos if f.get("codec_type") == "video"), None)
            if analizar(ruta).get("video") and (not vid or not vid.get("width") or not vid.get("height")
                                                or not vid.get("profile")):
                motivo = "la imagen no se reconoce"
            else:
                d = subprocess.run([exe, "-v", "error", "-i", "pipe:0", "-f", "null", "-"], input=datos,
                                   capture_output=True, timeout=60, **marca)
                errores = d.stderr.decode(errors="replace").strip()
                if d.returncode != 0 or errores:
                    motivo = "errores al decodificar: " + errores[:120]
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        motivo = f"la prueba falló: {e}"
    _pruebas[clave] = motivo
    return motivo


def decidir_modo(ruta: str, pedido: str = "", desde: float = 0.0) -> str:
    """Cómo mandar este video al Roku: lo que dice el análisis, lo que ya falló antes en la tele («pedido») y una
    prueba previa de lo que se va a mandar. Siempre se queda con el modo más seguro de los tres."""
    modo = max((pedido if pedido in MODOS else "", evaluar(ruta)[0]), key=MODOS.index)
    if Path(ruta).suffix.lower() not in (".mkv", ".mp4", ".m4v", ".mov") and not modo:
        modo = "audio"          # AVI, WMV, TS…: el Roku no los abre directo
    if modo == "audio" and verificar(ruta, "audio", desde):   # donde va a empezar a verse
        return "video"
    return modo


# --- Subtítulos que vienen dentro del video (mkv) ---------------------------------------------------------

_extrayendo: set[str] = set()


def _carpeta_incluidos() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TVon" / "subs_incluidos"
    base.mkdir(parents=True, exist_ok=True)
    return base


def subtitulos_incluidos(ruta: str) -> list[str]:
    """Los subtítulos de texto que lleva el video adentro, ya pasados a .srt. La primera vez se extraen en segundo
    plano (en un mkv grande lleva un rato): hasta que estén listos no aparecen en la lista."""
    info = analizar(ruta)
    pistas = info.get("subs") or []
    if not pistas:
        return []
    try:
        st = Path(ruta).stat()
    except OSError:
        return []
    clave = hashlib.sha1(f"{ruta}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:16]
    carpeta = _carpeta_incluidos()
    # Español primero, después inglés, después el resto (máximo 4)
    orden = sorted(pistas, key=lambda p: (p["idioma"][:2] not in ("es", "sp"), p["idioma"][:2] != "en", p["i"]))[:4]
    destinos = [carpeta / f"{clave}_{p['i']}_{p['idioma'] or 'und'}.srt" for p in orden]
    if all(d.is_file() for d in destinos):
        return [str(d) for d in destinos]
    if clave not in _extrayendo and ffmpeg():
        _extrayendo.add(clave)

        def trabajo():
            try:
                for p, d in zip(orden, destinos):
                    if d.is_file():
                        continue
                    tmp = d.with_suffix(".tmp.srt")
                    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", ruta, "-map", f"0:s:{p['i']}", "-c:s", "srt",
                                    str(tmp)], capture_output=True, timeout=1800,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                    if tmp.is_file() and tmp.stat().st_size > 20:
                        tmp.replace(d)
                    else:
                        tmp.unlink(missing_ok=True)
            except (OSError, subprocess.TimeoutExpired):
                pass
            finally:
                _extrayendo.discard(clave)
        threading.Thread(target=trabajo, daemon=True).start()
    return [str(d) for d in destinos if d.is_file()]


def texto_subtitulo(ruta_sub: str, ruta_video: str) -> str:
    """Cómo se llama un subtítulo en el Roku: «Español (nombre.srt)» o «Incluido: Español»."""
    from .subtitulos import IDIOMAS, descripcion
    p = Path(ruta_sub)
    if p.parent == _carpeta_incluidos():
        m = re.fullmatch(r"[0-9a-f]+_(\d+)_(.+)", p.stem)
        idioma = m.group(2) if m else ""
        return "Incluido: " + IDIOMAS.get(idioma[:3], IDIOMAS.get(idioma[:2], idioma if idioma != "und" else "sin idioma"))
    return descripcion(ruta_sub, ruta_video)


def subtitulos_del_roku(bib, ruta: str) -> list[str]:
    """Los subtítulos que ve el Roku: los de junto al video, el elegido a mano en la PC y los que lleva adentro."""
    lista = subtitulos_del_video(bib, ruta)
    return lista + [s for s in subtitulos_incluidos(ruta) if s not in lista]


def nvenc_disponible() -> bool:
    """¿Esta PC puede convertir a H.264 con la placa de video (NVIDIA)? Se prueba una vez."""
    global _nvenc
    if _nvenc is None:
        exe = ffmpeg()
        try:
            r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                                "testsrc=size=320x240:rate=10", "-t", "0.5", "-c:v", "h264_nvenc", "-pix_fmt",
                                "yuv420p", "-f", "null", "-"], capture_output=True, timeout=30,
                               creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            _nvenc = r.returncode == 0
        except (OSError, subprocess.TimeoutExpired, TypeError):
            _nvenc = False
    return _nvenc


def _ficha(control, aid: int, modo: str, desde_ms: int | None = None) -> dict:
    """Lo que el Roku necesita para reproducir un video: dirección, formato, desde dónde y subtítulos.
    Si hay que convertirlo, el video convertido empieza en «desde» (el Roku suma ese corrimiento a su posición)."""
    f = control.ficha_archivo(aid)
    (_a, ruta, _t), = control._archivos([aid])
    formato = FORMATOS.get(Path(ruta).suffix.lower())
    base = f"/roku/video?id={aid}"
    pos = f["posicion"] if desde_ms is None else max(0, int(desde_ms))
    duracion = f["duracion"]
    if modo not in MODOS:
        modo = decidir_modo(ruta, "")
    if modo and not ffmpeg():
        raise ErrorRemoto("Este video necesita ffmpeg en la PC para verse en el Roku "
                          "(winget install Gyan.FFmpeg y reabrir TorrentVision)", 501)
    desde = 0
    if modo:
        base += f"&compat={modo}&desde={pos / 1000:.3f}"
        formato, desde, pos = "ts", pos, 0
        duracion = duracion or analizar(ruta).get("duracion", 0)
    guardado = control.bib.subtitulos_de(ruta)
    subs = subtitulos_del_roku(control.bib, ruta)
    return {"id": aid, "titulo": f["titulo"] if not f["serie"] else f"{f['titulo']} · {f['nombre_lindo']}"[:120],
            "url": base, "formato": formato, "pos": pos, "dur": duracion, "desde": desde, "modo": modo,
            "retraso": guardado[1] if guardado else 0,
            "subtitulos": [{"n": i, "texto": texto_subtitulo(sub, ruta)[:60],
                            "elegido": (sub == guardado[0]) if guardado else i == 0} for i, sub in enumerate(subs)],
            # El siguiente capítulo, solo en las series (una película con números en el nombre no tiene «siguiente»)
            "siguiente": (f["siguiente"] or 0) if f["serie"] else 0,
            # La intro de la serie (ms), si ya se detectó: el Roku ofrece saltarla
            "intro": list(intro) if (intro := control.ventana.intro_de(ruta)) else []}


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
