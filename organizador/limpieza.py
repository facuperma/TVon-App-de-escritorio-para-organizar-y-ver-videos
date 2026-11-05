"""Lo que queda en la carpeta de donde vino una película (la del torrent o del .zip) después de moverla:
se rescatan los subtítulos y lo demás (nfo, txt, imágenes, muestras, accesos directos…) va a la Papelera."""
import os
import re
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QFile

from .db import EXT_IMAGEN, EXT_VIDEO
from .subtitulos import _anio_y_episodio, extraer_comprimido, idioma_de
from .titulos import es_extra

SUBTITULOS = {".srt", ".vtt", ".ass", ".ssa", ".sub", ".idx"}
COMPRIMIDOS = {".zip", ".rar", ".7z"}
COMPRIMIDO_MAX = 50 * 1024 * 1024  # los de subtítulos son chicos; uno grande no se abre ni se borra
# Lo que traen los torrents además de la película y no hace falta una vez que se movió
BASURA = {
    ".nfo", ".txt", ".url", ".lnk", ".website", ".exe", ".msi", ".bat", ".cmd", ".scr", ".sfv", ".md5", ".sha1",
    ".nzb", ".torrent", ".htm", ".html", ".ini", ".db", ".dat", ".log", ".diz", ".part", ".aria2", ".!qb",
    ".!ut", ".bc!", ".tmp", ".xml", ".json", ".m3u", ".nfo-orig", ".srr", ".sfk", ".par2",
} | EXT_IMAGEN
OTRO_CHICO = 5 * 1024 * 1024  # un archivo desconocido más chico que esto también se toma como basura


def _a_la_papelera(ruta: Path) -> bool:
    resultado = QFile.moveToTrash(str(ruta))
    return resultado[0] if isinstance(resultado, tuple) else bool(resultado)


def se_puede_limpiar(carpeta: Path, protegidas: set[Path]) -> bool:
    """Nunca una carpeta de la biblioteca, Descargas, Videos, la del usuario o una raíz de disco,
    ni una que contenga a alguna de ellas."""
    carpeta = carpeta.resolve()
    if len(carpeta.parts) <= 2 or carpeta == Path.home().resolve():
        return False
    return all(carpeta != p and carpeta not in p.parents for p in protegidas)


def _clasificar(carpeta: Path):
    """(subtítulos, comprimidos, basura, videos de verdad, otros) de toda la carpeta (hasta 3 niveles)."""
    subs, comprimidos, basura, videos, otros = [], [], [], [], []
    for actual, subcarpetas, archivos in os.walk(carpeta):
        if len(Path(actual).relative_to(carpeta).parts) >= 3:
            subcarpetas[:] = []
        for nombre in archivos:
            ruta = Path(actual, nombre)
            ext = ruta.suffix.lower()
            try:
                peso = ruta.stat().st_size
            except OSError:
                peso = 0
            if ext in SUBTITULOS:
                subs.append(ruta)
            elif ext in EXT_VIDEO:
                (basura if es_extra(ruta, peso) else videos).append(ruta)
            elif ext in COMPRIMIDOS:
                (comprimidos if peso <= COMPRIMIDO_MAX else otros).append(ruta)
            elif ext in BASURA or peso < OTRO_CHICO:
                basura.append(ruta)
            else:
                otros.append(ruta)
    return subs, comprimidos, basura, videos, otros


_OTROS_IDIOMAS = {
    "fr": re.compile(r"(?i)(?<![a-z])(fr|fre|fra|french|fran[cç]ais)(?![a-z])"),
    "pt": re.compile(r"(?i)(?<![a-z])(pt|por|pt-br|portuguese|portugu[eê]s|brazil\w*)(?![a-z])"),
    "it": re.compile(r"(?i)(?<![a-z])(ita|italian|italiano)(?![a-z])"),
    "de": re.compile(r"(?i)(?<![a-z])(ger|deu|german|deutsch)(?![a-z])"),
}


def _idioma(sub: Path) -> str:
    """es/en como en el resto de TorrentVision; además fr, pt, it y de si el nombre lo dice."""
    for codigo, patron in _OTROS_IDIOMAS.items():
        if patron.search(sub.stem):
            return codigo
    return idioma_de(sub)


def _destino_sub(sub: Path, videos: list[Path], principal: Path) -> Path:
    """Junto al video que le corresponde (en una serie, el de su capítulo), con su idioma en el nombre:
    «Película.es.srt». Si no se sabe de qué capítulo es, conserva su nombre al lado de la película."""
    episodio = _anio_y_episodio(sub.name)[1]
    video = principal
    if episodio is not None:
        video = next((v for v in videos if _anio_y_episodio(v.name)[1] == episodio), None)
        if video is None:
            return _libre(principal.parent / sub.name)
    return _libre(video.parent / f"{video.stem}.{_idioma(sub)}{sub.suffix.lower()}")


def _libre(ruta: Path) -> Path:
    n = 2
    nueva = ruta
    while nueva.exists():
        nueva = ruta.with_name(f"{ruta.stem}.{n}{ruta.suffix}")
        n += 1
    return nueva


def _igual(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def limpiar_origen(carpeta: Path, video_nuevo: Path, protegidas: set[Path]) -> tuple[list[str], bool]:
    """Después de mover `video_nuevo` desde `carpeta`: rescata los subtítulos que hayan quedado (también los
    de subcarpetas como «Subs» y los de adentro de .zip/.rar/.7z chicos) y manda la carpeta a la Papelera.
    No hace nada si quedan otras películas o archivos que no parecen basura.
    Devuelve (rutas de los subtítulos rescatados, si la carpeta se borró)."""
    if not carpeta.is_dir() or not se_puede_limpiar(carpeta, protegidas):
        return [], False
    subs, comprimidos, _basura, videos, otros = _clasificar(carpeta)
    if videos or otros:
        return [], False
    # Los subtítulos de adentro de los comprimidos, a una carpeta temporal
    temporal = Path(tempfile.mkdtemp(prefix="tv_subs_"))
    try:
        for i, comprimido in enumerate(comprimidos):
            destino_tmp = temporal / str(i)
            destino_tmp.mkdir()
            if extraer_comprimido(comprimido, destino_tmp):
                subs += [p for p in destino_tmp.rglob("*") if p.is_file() and p.suffix.lower() in SUBTITULOS]
        videos_destino = [v for v in video_nuevo.parent.iterdir() if v.suffix.lower() in EXT_VIDEO]
        ya_estan = [s for s in video_nuevo.parent.iterdir() if s.suffix.lower() in SUBTITULOS]
        rescatados = []
        for sub in subs:
            if any(_igual(sub, s) for s in ya_estan):
                continue  # ya estaba al lado de la película (por ejemplo, el que se trajo al mover)
            nuevo = _destino_sub(sub, videos_destino, video_nuevo)
            try:
                shutil.copy2(sub, nuevo)
            except OSError:
                return rescatados, False  # si un subtítulo no se pudo rescatar, la carpeta no se toca
            ya_estan.append(nuevo)
            rescatados.append(str(nuevo))
    finally:
        shutil.rmtree(temporal, ignore_errors=True)
    return rescatados, _a_la_papelera(carpeta)
