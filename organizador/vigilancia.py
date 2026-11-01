"""Biblioteca automática, en un hilo propio:

- Mueve los videos terminados de Descargas a la carpeta de videos.
- Revisa las carpetas de la biblioteca (Videos y Documentos) y suma los videos nuevos.
- Pone junto a su video los subtítulos que se bajan a Descargas (sueltos, en .zip/.rar/.7z o ya
  descomprimidos en una carpeta), si por el nombre se sabe de qué video son.
- Descomprime los .zip/.rar/.7z de Descargas que traen videos.
Cada video que llega va a la carpeta de su categoría (Videos\\Peliculas\\<título>) con sus subtítulos.
"""
import glob
import os
import shutil
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QFile, QObject, Signal

from .db import EXT_VIDEO, Biblioteca
from .descargas import nombre_seguro
from .subtitulos import (
    EXT_COMPRIMIDOS, EXT_SUBTITULOS, _anio_y_episodio, colocar_subtitulo, extraer_comprimido, idioma_de, listar_comprimido,
    nombres_de_comprimido, subtitulos_junto_a, video_del_subtitulo,
)
from .titulos import titulo_de

INTERVALO_S = 10            # revisión de Descargas
INTERVALO_ESCANEO_S = 60    # revisión de las carpetas de la biblioteca
QUIETO_S = 20               # un archivo sin cambios hace este tiempo se considera terminado
RECIENTE_S = 30 * 24 * 3600  # subcarpetas de Descargas creadas en el último mes (torrents)
MUESTRA_MAX = 300 * 1024 * 1024
ESPERA_SUBTITULO_S = 15 * 60  # cuánto se espera el subtítulo pedido a subdivx
SUBTITULO_RECIENTE_S = 2 * 24 * 3600  # subtítulos de Descargas que se ubican solos: los de los últimos 2 días
# Carpetas que no se recorren (además de las que empiezan con «.» o «$»)
IGNORAR = {"node_modules", "__pycache__", "appdata", "site-packages", "venv", "env"}


def en_uso(ruta: Path) -> bool:
    """True si otro programa tiene el archivo abierto (p. ej. todavía lo está descargando)."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateFileW.restype = wintypes.HANDLE
    # Abrir sin compartir (dwShareMode=0) falla si alguien más lo tiene abierto
    manejador = kernel32.CreateFileW(str(ruta), 0x80000000 | 0x40000000, 0, None, 3, 0x80, None)
    if manejador in (None, ctypes.c_void_p(-1).value):
        return True
    kernel32.CloseHandle(manejador)
    return False


def destino_libre(destino: Path) -> Path:
    """«video.mp4» -> «video (2).mp4» si ya existe."""
    n = 2
    candidato = destino
    while candidato.exists():
        candidato = destino.with_name(f"{destino.stem} ({n}){destino.suffix}")
        n += 1
    return candidato


def borrar_carpetas_vacias(carpeta: Path, raiz: Path):
    """Saca las carpetas que quedaron vacías, de `carpeta` hacia arriba sin llegar a `raiz`
    (si quedan .txt o .nfo, las deja)."""
    raiz = raiz.resolve()
    carpeta = carpeta.resolve()
    while carpeta != raiz and raiz in carpeta.parents:
        try:
            carpeta.rmdir()
        except OSError:
            return
        carpeta = carpeta.parent


def mover_video(video: Path, carpeta: Path) -> tuple[Path, dict[str, str]]:
    """Mueve el video y sus subtítulos; devuelve la ruta nueva y {sub viejo: sub nuevo}."""
    carpeta.mkdir(parents=True, exist_ok=True)
    carpeta = carpeta.resolve()  # misma forma de ruta que guarda la biblioteca
    nuevo = destino_libre(carpeta / video.name)
    subtitulos = {}
    # Los subtítulos con el mismo nombre viajan con el video
    for sub in video.parent.glob(glob.escape(video.stem) + "*"):
        if sub.suffix.lower() in EXT_SUBTITULOS and (sub.stem == video.stem or sub.stem.startswith(video.stem + ".")):
            sub_nuevo = carpeta / (nuevo.stem + sub.name[len(video.stem):])
            shutil.move(str(sub), str(sub_nuevo))
            subtitulos[str(sub)] = str(sub_nuevo)
    shutil.move(str(video), str(nuevo))
    return nuevo, subtitulos


def carpeta_de_categoria(bib: Biblioteca, titulo: str) -> Path:
    """Videos\\Peliculas\\<título>: la carpeta de cada película o serie."""
    return Path(bib.config("carpeta_videos")) / "Peliculas" / nombre_seguro(titulo)


def es_muestra(video: Path) -> bool:
    """Los torrents suelen traer un «sample» de un minuto."""
    return "sample" in video.stem.lower() and video.stat().st_size < MUESTRA_MAX


def traer_subtitulos(origen: Path, video: Path) -> str | None:
    """Pone junto al video (como «video.es.srt») un subtítulo que quedó en la carpeta de donde vino
    con otro nombre (los torrents y los .zip los traen como «Subs\\Spanish.srt» o con el nombre de
    la película). Si en esa carpeta hay otros videos, solo uno cuyo nombre diga que es de este.
    `origen` tiene que ser la carpeta propia del video (la del torrent o del .zip), nunca Descargas."""
    if subtitulos_junto_a(str(video)) or not origen.is_dir():
        return None
    subs, otros_videos = [], False
    for actual, subcarpetas, archivos in os.walk(origen):
        if len(Path(actual).relative_to(origen).parts) >= 2:
            subcarpetas[:] = []
        for nombre in archivos:
            extension = Path(nombre).suffix.lower()
            if extension in EXT_SUBTITULOS:
                subs.append(Path(actual, nombre))
            elif extension in EXT_VIDEO:
                otros_videos = True
    if otros_videos:
        subs = [s for s in subs if video_del_subtitulo([s.name], [str(video)])]
    else:
        # Aunque sea el último que queda: nunca el subtítulo de otro capítulo
        episodio = _anio_y_episodio(video.name)[1]
        subs = [s for s in subs if _anio_y_episodio(s.name)[1] in (None, episodio)]
    # Uno por idioma (primero el español); entre varios, el más grande (el completo, no el «forced»)
    colocados = []
    for idioma in ("es", "en"):
        del_idioma = [s for s in subs if idioma_de(s) == idioma]
        if del_idioma and (sub := colocar_subtitulo(max(del_idioma, key=lambda s: s.stat().st_size),
                                                    str(video), idioma)):
            colocados.append(sub)
    return colocados[0] if colocados else None


class Vigilante(QObject):
    archivos_nuevos = Signal(int)
    movido = Signal(str)  # ruta nueva del video
    descargado = Signal(str)  # video que acaba de bajar (para buscarle subtítulos)
    subtitulo_listo = Signal(str, str)  # video, subtítulo colocado junto a él
    subtitulo_fallido = Signal(str)  # mensaje

    def __init__(self, ruta_db: Path):
        super().__init__()
        self.ruta_db = ruta_db
        self._despertar = threading.Event()
        self._parar = threading.Event()
        self._escanear_ya = True
        self._esperando: tuple[str, float] | None = None  # (video, desde cuándo) esperando subtítulo
        self._sin_video: set[tuple[str, float]] = set()  # subtítulos de Descargas que no son de ningún video
        self._comprimidos: dict[tuple[str, float], bool] = {}  # comprimidos de Descargas: ¿traen videos?
        self._hilo = threading.Thread(target=self._bucle, daemon=True)

    def iniciar(self):
        self._hilo.start()

    def despertar(self):
        """Revisar ya (p. ej. después de cambiar la configuración o de mover videos)."""
        self._escanear_ya = True
        self._sin_video.clear()  # un subtítulo que no era de ningún video puede serlo ahora
        self._despertar.set()

    def esperar_subtitulo(self, ruta_video: str):
        """El subtítulo que se baje a Descargas en los próximos minutos es para este video."""
        self._esperando = (ruta_video, time.time())
        self._despertar.set()

    def detener(self):
        self._parar.set()
        self._despertar.set()

    def _bucle(self):
        bib = Biblioteca(self.ruta_db)
        vistos: dict[Path, tuple] = {}
        ultimo_escaneo = 0.0
        while not self._parar.is_set():
            try:
                llegaron = 0
                if bib.config("mover_descargas") == "1":
                    llegaron += self._extraer_videos(bib)
                    llegaron += self._revisar_descargas(bib, vistos)
                if self._escanear_ya or time.monotonic() - ultimo_escaneo > INTERVALO_ESCANEO_S:
                    self._escanear_ya = False
                    ultimo_escaneo = time.monotonic()
                    if nuevos := self._escanear(bib):
                        llegaron += nuevos
                        self.archivos_nuevos.emit(nuevos)
                if llegaron:
                    # El subtítulo que se bajó antes que su video ya tiene con quién ir
                    self._sin_video.clear()
                if self._esperando:
                    self._buscar_subtitulo(bib)
                else:
                    self._ubicar_subtitulos(bib)
            except OSError:
                pass  # carpeta inaccesible o archivo que desapareció: se reintenta en la próxima vuelta
            # Esperando un subtítulo, se mira más seguido
            self._despertar.wait(2 if self._esperando else INTERVALO_S)
            self._despertar.clear()

    def _a_su_categoria(self, bib: Biblioteca, video: Path, carpeta_propia: Path | None) -> Path:
        """Mueve un video que llegó a Videos\\Peliculas\\<título> con sus subtítulos (también los
        que quedaron en `carpeta_propia` con otro nombre) y lo mete en la categoría <título>."""
        titulo = titulo_de(video.name)
        nuevo, subtitulos = mover_video(video, carpeta_de_categoria(bib, titulo))
        if carpeta_propia is not None:
            traer_subtitulos(carpeta_propia, nuevo)
            for carpeta in sorted(carpeta_propia.rglob("*"), reverse=True):  # «Subs\» y demás que quedaron vacías
                if carpeta.is_dir():
                    try:
                        carpeta.rmdir()
                    except OSError:
                        pass
        if bib.id_de_ruta(str(video)) is None:
            bib.agregar_archivos([nuevo])
            self.descargado.emit(str(nuevo))
        else:
            bib.mover_ruta(video, nuevo, subtitulos)
        if (aid := bib.id_de_ruta(str(nuevo))) is not None:
            bib.asignar(aid, bib.categoria_id(titulo), True)
        self.movido.emit(str(nuevo))
        return nuevo

    def _extraer_videos(self, bib: Biblioteca) -> int:
        """Los .zip/.rar/.7z de Descargas que traen videos: se descomprimen, cada video va a la
        carpeta de su categoría con sus subtítulos, y el comprimido va a la Papelera."""
        origen = Path(bib.config("carpeta_descargas_sistema"))
        if not origen.is_dir():
            return 0
        ahora = time.time()
        llegaron = 0
        for archivo in origen.iterdir():
            if archivo.suffix.lower() not in EXT_COMPRIMIDOS or not archivo.is_file():
                continue
            info = archivo.stat()
            clave = (str(archivo), info.st_mtime)
            if ahora - info.st_mtime > SUBTITULO_RECIENTE_S or ahora - info.st_mtime <= QUIETO_S:
                continue
            if clave not in self._comprimidos:
                self._comprimidos[clave] = any(Path(n).suffix.lower() in EXT_VIDEO for n in listar_comprimido(archivo))
            if not self._comprimidos[clave] or en_uso(archivo):
                continue
            # Se descomprime en el mismo disco que Videos: después mover es instantáneo
            temporal = Path(bib.config("carpeta_videos")) / ".tvon_descomprimiendo" / nombre_seguro(archivo.stem)
            shutil.rmtree(temporal, ignore_errors=True)
            temporal.mkdir(parents=True)
            try:
                if not extraer_comprimido(archivo, temporal, timeout=3600):
                    self._comprimidos[clave] = False  # dañado o con contraseña: no se reintenta
                    continue
                for video in [p for p in temporal.rglob("*") if p.suffix.lower() in EXT_VIDEO]:
                    if not es_muestra(video):
                        self._a_su_categoria(bib, video, temporal)
                        llegaron += 1
            finally:
                shutil.rmtree(temporal, ignore_errors=True)
                borrar_carpetas_vacias(temporal.parent, Path(bib.config("carpeta_videos")))
            if self._comprimidos[clave]:
                QFile.moveToTrash(str(archivo))
        return llegaron

    def _revisar_descargas(self, bib: Biblioteca, vistos: dict) -> int:
        origen = Path(bib.config("carpeta_descargas_sistema")).resolve()
        destino = Path(bib.config("carpeta_videos"))
        if not origen.is_dir() or origen == destino.resolve():
            return 0
        llegaron = 0
        actuales = {}
        for archivo, info in self._videos_descargas(origen):
            firma = (info.st_size, info.st_mtime)
            actuales[archivo] = firma
            # Terminado: mismo tamaño que en la vuelta anterior y quieto hace un rato
            # (uTorrent y los navegadores usan otra extensión mientras bajan: .!ut, .crdownload, .part)
            if vistos.get(archivo) != firma or info.st_size == 0 or time.time() - info.st_mtime <= QUIETO_S:
                continue
            try:
                if en_uso(archivo):
                    # El programa de torrents lo sigue compartiendo (o se está mirando):
                    # se muestra ya desde Descargas y se mueve cuando lo suelte
                    if bib.agregar_archivos([archivo]):
                        self.archivos_nuevos.emit(1)
                        self.descargado.emit(str(archivo))
                    continue
                # La carpeta del torrent (no Descargas): de ahí salen también sus subtítulos
                partes = archivo.relative_to(origen).parts
                self._a_su_categoria(bib, archivo, origen / partes[0] if len(partes) > 1 else None)
                borrar_carpetas_vacias(archivo.parent, origen)
                llegaron += 1
            except OSError:
                pass  # se reintenta en la próxima vuelta, sin frenar a los demás
        vistos.clear()
        vistos.update(actuales)
        return llegaron

    def _buscar_subtitulo(self, bib: Biblioteca):
        video, desde = self._esperando
        if time.time() - desde > ESPERA_SUBTITULO_S:
            self._esperando = None
            return
        origen = Path(bib.config("carpeta_descargas_sistema"))
        for archivo in origen.iterdir():
            if (archivo.suffix.lower() not in EXT_SUBTITULOS | EXT_COMPRIMIDOS or not archivo.is_file()
                    or archivo.stat().st_ctime < desde - 5):
                continue
            if time.time() - archivo.stat().st_mtime < 2 or en_uso(archivo):
                continue  # el navegador lo está terminando de guardar
            self._esperando = None
            if sub := colocar_subtitulo(archivo, video):
                self.subtitulo_listo.emit(video, sub)
            else:
                self.subtitulo_fallido.emit(f"{archivo.name} no tiene subtítulos (.srt o .vtt) adentro")
            return

    def _ubicar_subtitulos(self, bib: Biblioteca):
        """Subtítulos bajados sin pedirlos desde TVon (p. ej. desde subdivx en el navegador): si el
        nombre dice de qué video son, se ponen junto a él como «video.es.srt»."""
        origen = Path(bib.config("carpeta_descargas_sistema"))
        if not origen.is_dir():
            return
        ahora = time.time()
        videos = None
        for elemento in origen.iterdir():
            try:
                info = elemento.stat()
            except OSError:
                continue
            clave = (str(elemento), info.st_mtime)
            if clave in self._sin_video or ahora - info.st_mtime > SUBTITULO_RECIENTE_S or ahora - info.st_mtime < 3:
                continue
            if elemento.is_dir():
                # Un .zip que ya se descomprimió: una carpeta con solo subtítulos
                adentro = [p for p in elemento.iterdir()]
                subs = [p for p in adentro if p.suffix.lower() in EXT_SUBTITULOS]
                if not subs or len(adentro) > 10 or len(subs) != len(adentro):
                    continue
                nombres = [elemento.name] + [p.name for p in subs]
            elif elemento.suffix.lower() in EXT_SUBTITULOS:
                nombres = [elemento.name]
            elif elemento.suffix.lower() in EXT_COMPRIMIDOS:
                if clave not in self._comprimidos:
                    self._comprimidos[clave] = any(Path(n).suffix.lower() in EXT_VIDEO
                                                   for n in listar_comprimido(elemento))
                if self._comprimidos[clave]:
                    continue  # trae videos: lo descomprime _extraer_videos
                nombres = nombres_de_comprimido(elemento)
                if elemento.suffix.lower() == ".zip" and len(nombres) == 1:
                    self._sin_video.add(clave)  # un .zip sin subtítulos adentro: no es para TVon
                    continue
                if en_uso(elemento):
                    continue
            else:
                continue
            if videos is None:
                videos = [ruta for _id, ruta, _nombre, tipo in bib.listar_archivos("video") if Path(ruta).exists()]
            video = video_del_subtitulo(nombres, videos)
            # Si el video ya tiene subtítulo en español, no se le agrega otro
            if video is None or any(Path(s).stem.lower().endswith((".es", ".spa")) or Path(s).stem == Path(video).stem
                                    for s in subtitulos_junto_a(video)):
                self._sin_video.add(clave)
                continue
            if elemento.is_dir():
                sub = colocar_subtitulo(max(subs, key=lambda p: p.stat().st_size), video)
                try:
                    elemento.rmdir()  # quedó vacía
                except OSError:
                    pass
            else:
                sub = colocar_subtitulo(elemento, video)
            if sub:
                self.subtitulo_listo.emit(video, sub)
            else:
                self._sin_video.add(clave)

    def _videos_descargas(self, origen: Path):
        """(ruta, stat) de los videos de Descargas: los sueltos y los de las carpetas
        recientes (los torrents bajan cada película en su carpeta)."""
        for actual, subcarpetas, archivos in os.walk(origen):
            if Path(actual) == origen:
                # Las carpetas viejas son del usuario, no descargas en curso: no se tocan
                subcarpetas[:] = [d for d in subcarpetas if not d.startswith((".", "$"))
                                  and d.lower() not in IGNORAR
                                  and time.time() - os.stat(os.path.join(actual, d)).st_ctime < RECIENTE_S]
            for nombre in archivos:
                archivo = Path(actual, nombre)
                if archivo.suffix.lower() not in EXT_VIDEO:
                    continue
                info = archivo.stat()
                if actual != str(origen) and es_muestra(archivo):
                    continue
                yield archivo, info

    def _escanear(self, bib: Biblioteca) -> int:
        conocidas = bib.rutas_conocidas()
        nuevas = []
        for carpeta in bib.carpetas_biblioteca():
            raiz = Path(carpeta)
            if not raiz.is_dir():
                continue
            for actual, subcarpetas, archivos in os.walk(raiz.resolve()):
                if self._parar.is_set():
                    return 0
                subcarpetas[:] = [d for d in subcarpetas
                                  if not d.startswith((".", "$")) and d.lower() not in IGNORAR]
                for nombre in archivos:
                    if Path(nombre).suffix.lower() in EXT_VIDEO:
                        ruta = os.path.join(actual, nombre)
                        if ruta not in conocidas:
                            nuevas.append(Path(ruta))
        return bib.agregar_archivos(nuevas) if nuevas else 0
