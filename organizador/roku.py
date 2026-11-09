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
            return self._json(llamar(lambda: _ficha(control, _entero(consulta.get("id")), consulta.get("modo", ""), desde)))
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
        lista = self.remoto.puente.llamar(lambda: subtitulos_del_video(self.remoto.bib, str(ruta)))
        try:
            sub = Subtitulos(lista[int(consulta.get("n", 0))])
        except (ValueError, IndexError, OSError):
            raise ErrorRemoto("Ese subtítulo no existe", 404) from None
        self._json({"cues": [[a, b, re.sub(r"\{\\[^}]*\}", "", t)] for a, b, t in sub.cues]})

    def _subtitulo_roku(self, consulta: dict):
        """Como el de ON, pero si el video convertido empieza más adelante («desde», en ms), los tiempos se corren
        para que coincidan con lo que el Roku cuenta desde 0."""
        desde = _entero(consulta.get("desde", 0))
        if not desde:
            return self._subtitulo(consulta)
        from .subtitulos import Subtitulos
        ruta = self._video_de(consulta)
        lista = self.remoto.puente.llamar(lambda: subtitulos_del_video(self.remoto.bib, str(ruta)))
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


def analizar(ruta: str) -> dict:
    """Códecs del primer video y del primer audio, y la duración (ms). {} si no hay ffprobe."""
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
    video = next((s for s in datos.get("streams", []) if s.get("codec_type") == "video"
                  and not (s.get("disposition") or {}).get("attached_pic")), {})
    audio = next((s for s in datos.get("streams", []) if s.get("codec_type") == "audio"), {})
    try:
        duracion = int(float((datos.get("format") or {}).get("duration") or 0) * 1000)
    except ValueError:
        duracion = 0
    def _inicio(flujo):
        try:
            return float(flujo.get("start_time") or 0)
        except ValueError:
            return 0.0

    info = {"video": video.get("codec_name", ""), "pixeles": video.get("pix_fmt", ""),
            "desfase": abs(_inicio(video) - _inicio(audio)) if audio else 0.0,
            "audio": audio.get("codec_name", ""), "canales": int(audio.get("channels") or 0), "duracion": duracion}
    _analisis[clave] = info
    return info


def modo_para_roku(ruta: str) -> str:
    """«» si el Roku lo reproduce tal cual; «audio» si hay que pasar el sonido a estéreo; «video» si también la imagen."""
    info = analizar(ruta)
    if not info:
        return ""
    video_bien = info["video"] == "h264" and info["pixeles"] in ("yuv420p", "yuvj420p", "")
    audio_bien = not info["audio"] or (info["audio"] in ("aac", "mp3") and info["canales"] <= 2)
    if video_bien:
        # Imagen y sonido que no empiezan juntos: el Roku se confunde al saltar (imagen congelada con sonido).
        # Pasando por la PC, ffmpeg los alinea
        return "" if audio_bien and info.get("desfase", 0) < 0.04 else "audio"
    return "video"


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
    if modo not in ("audio", "video"):
        modo = modo_para_roku(ruta) or ("video" if formato is None else "")
    if modo and not ffmpeg():
        raise ErrorRemoto("Este video necesita ffmpeg en la PC para verse en el Roku "
                          "(winget install Gyan.FFmpeg y reabrir TorrentVision)", 501)
    desde = 0
    if modo:
        base += f"&compat={modo}&desde={pos / 1000:.3f}"
        formato, desde, pos = "ts", pos, 0
        duracion = duracion or analizar(ruta).get("duracion", 0)
    guardado = control.bib.subtitulos_de(ruta)
    return {"id": aid, "titulo": f["titulo"] if not f["serie"] else f"{f['titulo']} · {f['nombre_lindo']}"[:120],
            "url": base, "formato": formato, "pos": pos, "dur": duracion, "desde": desde, "modo": modo,
            "retraso": guardado[1] if guardado else 0,
            "subtitulos": [{"n": s["n"], "texto": s["texto"][:60], "elegido": s["elegido"]} for s in f["subtitulos"]],
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
