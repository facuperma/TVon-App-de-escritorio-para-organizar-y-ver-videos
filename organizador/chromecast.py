"""Chromecast: mandar la película a la tele, como en Netflix.

La PC busca los Chromecast de la red, les sirve el video por HTTP y los maneja (pausa, adelantar,
volumen). El servidor solo le contesta a la IP del Chromecast elegido y la dirección del video
cambia en cada transmisión. Lo que el Chromecast no reproduce (MKV, AVI, video HEVC, sonido DTS
o AC3) lo convierte ffmpeg mientras se ve; en ese caso adelantar vuelve a pedir el video desde ahí.

Todo lo que habla con el Chromecast corre en un hilo propio, de a una orden por vez: la ventana
nunca se traba esperando a la tele.
"""
import json
import re
import secrets
import socket
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .subtitulos import leer_texto
from .titulos import nombre_lindo

# Lo que el receptor de Chromecast reproduce tal cual (contenedor, video y sonido)
DIRECTO_CONTENEDOR = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/mp4", ".webm": "video/webm"}
DIRECTO_VIDEO = {"h264", "vp8", "vp9"}
DIRECTO_AUDIO = {"aac", "mp3", "opus", "vorbis", "flac", None}
BUSQUEDA_S = 8
_SIN_VENTANA = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class ErrorCast(Exception):
    pass


def buscar_ffmpeg() -> str | None:
    from .remoto import ffmpeg  # el mismo que usa ON para el celular
    return ffmpeg()


def codecs(ruta: str) -> tuple[str | None, str | None]:
    """(video, sonido) según ffprobe; (None, None) si no hay ffprobe."""
    exe = buscar_ffmpeg()
    if not exe:
        return None, None
    try:
        r = subprocess.run([str(Path(exe).with_name("ffprobe.exe")), "-v", "error", "-show_entries",
                            "stream=codec_type,codec_name", "-of", "json", ruta],
                           capture_output=True, text=True, timeout=15, creationflags=_SIN_VENTANA)
        flujos = json.loads(r.stdout or "{}").get("streams", [])
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None, None
    primero = lambda tipo: next((f.get("codec_name") for f in flujos if f.get("codec_type") == tipo), None)  # noqa: E731
    return primero("video"), primero("audio")


def modo_para(ruta: str) -> str | None:
    """None si va tal cual; «audio» si solo hay que pasar el sonido a AAC; «video» si hay que
    convertir todo. Sin ffprobe se decide por la extensión."""
    extension = Path(ruta).suffix.lower()
    video, audio = codecs(ruta)
    if video is None:
        if extension in DIRECTO_CONTENEDOR:
            return None
    elif extension in DIRECTO_CONTENEDOR and video in DIRECTO_VIDEO and audio in DIRECTO_AUDIO:
        return None
    elif video == "h264":
        return "audio"
    if not buscar_ffmpeg():
        raise ErrorCast("El Chromecast no puede reproducir este video tal cual y hace falta ffmpeg para "
                        "convertirlo (winget install Gyan.FFmpeg y volver a abrir TorrentVision)")
    return "video" if video != "h264" else "audio"


def srt_a_vtt(texto: str) -> str:
    """El Chromecast solo lee WebVTT: «00:01:02,500» pasa a «00:01:02.500»."""
    texto = texto.lstrip("﻿")
    if texto.lstrip().upper().startswith("WEBVTT"):
        return texto
    return "WEBVTT\n\n" + re.sub(r"(\d{1,2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", texto.replace("\r\n", "\n"))


def ip_hacia(host: str) -> str:
    """La IP de esta PC en la red del Chromecast (la que él puede alcanzar)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 8009))
        return s.getsockname()[0]
    finally:
        s.close()


# --- Servidor del video ---------------------------------------------------------------------

class _Manejador(BaseHTTPRequestHandler):
    server_version = "TVon"
    sys_version = ""

    def log_message(self, *_):
        pass

    def do_HEAD(self):
        self.do_GET(solo_cabeceras=True)

    def do_GET(self, solo_cabeceras=False):
        t = self.server.transmision
        if not t or self.client_address[0] != t["ip_cast"]:
            return self._responder(403, b"")
        if self.path == f"/{t['token']}/sub.vtt" and t.get("vtt"):
            return self._responder(200, b"" if solo_cabeceras else t["vtt"], "text/vtt; charset=utf-8")
        if self.path.split("?")[0] != f"/{t['token']}/video":
            return self._responder(404, b"")
        try:
            if t["modo"]:
                self._convertido(t, solo_cabeceras)
            else:
                self._archivo(Path(t["ruta"]), t["tipo"], solo_cabeceras)
        except (ConnectionError, OSError):
            pass  # el Chromecast cortó (adelantó o se detuvo)

    def _cabeceras_comunes(self):
        # El receptor de Chromecast es una página web: sin esto no puede leer los subtítulos
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str = "text/plain"):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self._cabeceras_comunes()
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta: Path, tipo: str, solo_cabeceras: bool):
        """El archivo tal cual, por partes (Range): el Chromecast adelanta sin bajarlo entero."""
        total = ruta.stat().st_size
        inicio, fin, codigo = 0, total - 1, 200
        if m := re.fullmatch(r"bytes=(\d*)-(\d*)", (self.headers.get("Range") or "").strip()):
            if m.group(1):
                inicio = int(m.group(1))
                fin = min(int(m.group(2)), total - 1) if m.group(2) else total - 1
            elif m.group(2):
                inicio = max(0, total - int(m.group(2)))
            if inicio > fin:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{total}")
                self.end_headers()
                return
            codigo = 206
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fin - inicio + 1))
        if codigo == 206:
            self.send_header("Content-Range", f"bytes {inicio}-{fin}/{total}")
        self._cabeceras_comunes()
        self.end_headers()
        if solo_cabeceras:
            return
        with open(ruta, "rb") as f:
            f.seek(inicio)
            falta = fin - inicio + 1
            while falta > 0 and (bloque := f.read(min(256 * 1024, falta))):
                self.wfile.write(bloque)
                falta -= len(bloque)

    def _convertido(self, t: dict, solo_cabeceras: bool):
        """ffmpeg convierte mientras se ve, a MP4 por fragmentos (lo que el Chromecast acepta sin
        saber el tamaño). Arranca desde donde se pidió; adelantar vuelve a pedirlo desde ahí."""
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self._cabeceras_comunes()
        self.send_header("Connection", "close")
        self.end_headers()
        if solo_cabeceras:
            return
        video = ["-c:v", "copy"] if t["modo"] == "audio" else [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-level", "4.1"]
        orden = [buscar_ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{t['desde_s']:.3f}", "-i", t["ruta"],
                 "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn", *video, "-c:a", "aac", "-b:a", "192k", "-ac", "2",
                 "-movflags", "frag_keyframe+empty_moov+default_base_moof", "-f", "mp4", "pipe:1"]
        proceso = subprocess.Popen(orden, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, creationflags=_SIN_VENTANA)
        try:
            while bloque := proceso.stdout.read(128 * 1024):
                self.wfile.write(bloque)
        finally:
            proceso.kill()  # el Chromecast cortó o adelantó: ffmpeg no queda trabajando de más
            proceso.wait()
            self.close_connection = True


class _Servidor(ThreadingHTTPServer):
    daemon_threads = True
    transmision: dict | None = None


# --- Transmisor -----------------------------------------------------------------------------

class Transmisor(QObject):
    """Los Chromecast de la red y lo que se está transmitiendo. Las señales llegan al hilo de la
    ventana; los métodos se pueden llamar desde ahí sin esperar a la red."""
    dispositivos_cambiados = Signal(list)   # [{"id", "nombre", "modelo"}]
    estado_cambiado = Signal()
    mensaje = Signal(str)

    def __init__(self):
        super().__init__()
        self._hilo = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chromecast")
        self._casts: dict[str, object] = {}
        self._navegador = None
        self.dispositivos: list[dict] = []
        self.buscando = False
        self._servidor: _Servidor | None = None
        self._cast = None
        self.transmision: dict | None = None  # {"nombre", "titulo", "ruta", "modo", "desde_s", "duracion_ms"}

    @staticmethod
    def disponible() -> bool:
        try:
            import pychromecast  # noqa: F401
        except ImportError:
            return False
        return True

    def _en_hilo(self, funcion, *args):
        def envoltura():
            try:
                funcion(*args)
            except ErrorCast as e:
                self.mensaje.emit(str(e))
            except Exception as e:  # noqa: BLE001 - la red o el Chromecast: se avisa y se sigue
                self.mensaje.emit(f"Chromecast: {e}")
            finally:
                self.estado_cambiado.emit()
        self._hilo.submit(envoltura)

    # Buscar

    def buscar(self):
        if self.buscando:
            return
        self.buscando = True
        self.estado_cambiado.emit()
        self._en_hilo(self._buscar)

    def _buscar(self):
        import pychromecast
        try:
            casts, navegador = pychromecast.get_chromecasts(timeout=BUSQUEDA_S)
            if self._navegador:
                self._navegador.stop_discovery()
            self._navegador = navegador
            self._casts = {str(c.uuid): c for c in casts}
            self.dispositivos = sorted(({"id": str(c.uuid), "nombre": c.cast_info.friendly_name,
                                         "modelo": c.cast_info.model_name or ""} for c in casts),
                                       key=lambda d: d["nombre"].lower())
            self.dispositivos_cambiados.emit(self.dispositivos)
            if not casts:
                self.mensaje.emit("No se encontró ningún Chromecast: tiene que estar prendido y en la misma red "
                                  "que la PC. Si Windows pregunta por el firewall, permití TorrentVision.")
        finally:
            self.buscando = False

    # Transmitir

    def transmitir(self, dispositivo: str, ruta: str, posicion_ms: int = 0, subtitulo: str | None = None):
        self._en_hilo(self._transmitir, dispositivo, ruta, max(0, posicion_ms), subtitulo)

    def _transmitir(self, dispositivo: str, ruta: str, posicion_ms: int, subtitulo: str | None):
        cast = self._casts.get(dispositivo)
        if cast is None:
            raise ErrorCast("Ese Chromecast ya no está en la red: buscalo de nuevo")
        self.mensaje.emit(f"Conectando con {cast.cast_info.friendly_name}…")
        cast.wait(timeout=15)
        modo = modo_para(ruta)
        if self._cast is not None and self._cast is not cast:
            self._detener()
        self._cast = cast
        vtt = None
        if subtitulo and Path(subtitulo).is_file():
            vtt = srt_a_vtt(leer_texto(Path(subtitulo))).encode("utf-8")
        from .remoto import duracion_ms
        self.transmision = {"nombre": cast.cast_info.friendly_name, "titulo": nombre_lindo(Path(ruta).name),
                            "ruta": ruta, "modo": modo, "vtt": vtt,
                            "tipo": DIRECTO_CONTENEDOR.get(Path(ruta).suffix.lower(), "video/mp4"),
                            "duracion_ms": duracion_ms(ruta), "desde_s": 0.0}
        self._cargar(posicion_ms / 1000)

    def _cargar(self, segundos: float):
        """Pide al Chromecast el video desde ese punto (con una dirección nueva cada vez)."""
        t, cast = self.transmision, self._cast
        servidor = self._asegurar_servidor()
        t["token"] = secrets.token_urlsafe(24)
        t["ip_cast"] = socket.gethostbyname(cast.cast_info.host)
        t["desde_s"] = segundos if t["modo"] else 0.0
        servidor.transmision = t
        base = f"http://{ip_hacia(cast.cast_info.host)}:{servidor.server_address[1]}/{t['token']}"
        mc = cast.media_controller
        extra = {"subtitles": f"{base}/sub.vtt", "subtitles_lang": "es-AR", "subtitle_id": 1} if t["vtt"] else {}
        # Convertido, el video empieza en «desde_s»: para el Chromecast es una transmisión en vivo
        mc.play_media(f"{base}/video", "video/mp4" if t["modo"] else t["tipo"], title=t["titulo"],
                      current_time=None if t["modo"] else segundos,
                      stream_type="LIVE" if t["modo"] else "BUFFERED", **extra)
        mc.block_until_active(timeout=20)
        if t["vtt"]:
            mc.enable_subtitle(1)
        self.mensaje.emit(f"📺 Transmitiendo a {t['nombre']}")

    def _asegurar_servidor(self) -> _Servidor:
        if self._servidor is None:
            self._servidor = _Servidor(("0.0.0.0", 0), _Manejador)
            threading.Thread(target=self._servidor.serve_forever, daemon=True, name="cast-http").start()
        return self._servidor

    # Controles (con transmisión en curso)

    def _controlador(self):
        if self._cast is None or self.transmision is None:
            raise ErrorCast("No hay nada transmitiéndose al Chromecast")
        return self._cast.media_controller

    def play_pausa(self):
        def hacer():
            mc = self._controlador()
            mc.pause() if mc.status.player_state == "PLAYING" else mc.play()
        self._en_hilo(hacer)

    def ir_a(self, ms: int):
        def hacer():
            mc = self._controlador()
            segundos = max(0.0, ms / 1000)
            if self.transmision["modo"]:
                self._cargar(segundos)  # convertido: se pide de nuevo desde ahí
            else:
                mc.seek(segundos)
        self._en_hilo(hacer)

    def adelantar(self, ms: int):
        self.ir_a(self.posicion_ms() + ms)

    def volumen(self, valor: int):
        self._en_hilo(lambda: self._cast and self._cast.set_volume(max(0, min(100, valor)) / 100))

    def detener(self):
        self._en_hilo(self._detener)

    def _detener(self):
        cast, self._cast = self._cast, None
        self.transmision = None
        if self._servidor:
            self._servidor.transmision = None
        if cast is not None:
            try:
                cast.media_controller.stop()
                cast.quit_app()
            except Exception:  # noqa: BLE001 - la tele ya se había desconectado
                pass

    def cerrar(self):
        if self.transmision:
            self._detener()
        if self._navegador:
            self._navegador.stop_discovery()
        if self._servidor:
            self._servidor.shutdown()
        self._hilo.shutdown(wait=False, cancel_futures=True)

    # Estado (para la ventana y el celular)

    def posicion_ms(self) -> int:
        t = self.transmision
        if not t or self._cast is None:
            return 0
        s = self._cast.media_controller.status
        actual = s.adjusted_current_time or s.current_time or 0
        return int((t["desde_s"] + actual) * 1000)

    def estado(self) -> dict:
        t = self.transmision
        info = {"disponible": self.disponible(), "buscando": self.buscando, "dispositivos": self.dispositivos,
                "transmision": None}
        if t and self._cast is not None:
            s = self._cast.media_controller.status
            duracion = t["duracion_ms"] or int((s.duration or 0) * 1000)
            info["transmision"] = {
                "dispositivo": t["nombre"], "titulo": t["titulo"], "posicion": self.posicion_ms(),
                "duracion": duracion, "estado": {"PLAYING": "reproduciendo", "PAUSED": "pausa",
                                                 "BUFFERING": "cargando"}.get(s.player_state, "cargando"),
                "volumen": round((self._cast.status.volume_level if self._cast.status else 0) * 100),
            }
        return info
