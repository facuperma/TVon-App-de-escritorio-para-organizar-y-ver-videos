"""Lectura de subtítulos externos (.srt y .vtt)."""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from bisect import bisect_right
from pathlib import Path

EXT_SUBTITULOS = {".srt", ".vtt"}
# Así vienen los de subdivx. El tar de Windows (bsdtar) abre los tres.
EXT_COMPRIMIDOS = {".zip", ".rar", ".7z"}

_TIEMPO = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})")
# Etiquetas HTML (<i>, <font ...>) y de estilo ASS ({\an8})
_ETIQUETAS = re.compile(r"<[^>]+>|\{\\[^}]*\}")


def _a_ms(texto: str) -> int | None:
    m = _TIEMPO.search(texto)
    if not m:
        return None
    h, mi, s, frac = m.groups()
    return ((int(h or 0) * 60 + int(mi)) * 60 + int(s)) * 1000 + int(frac.ljust(3, "0"))


def _leer_texto(ruta: Path) -> str:
    datos = ruta.read_bytes()
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            pass
    return datos.decode("latin-1")


def leer_texto(ruta: Path) -> str:
    """El texto del subtítulo, adivinando la codificación (UTF-8 o Windows-1252)."""
    return _leer_texto(Path(ruta))


class Subtitulos:
    def __init__(self, ruta: str | Path):
        texto = _leer_texto(Path(ruta)).replace("\r\n", "\n").replace("\r", "\n")
        cues = []
        for bloque in re.split(r"\n\s*\n", texto):
            lineas = bloque.strip("\n").split("\n")
            for i, linea in enumerate(lineas):
                if "-->" not in linea:
                    continue
                ini, fin = linea.split("-->", 1)
                a, b = _a_ms(ini), _a_ms(fin)
                cuerpo = _ETIQUETAS.sub("", "\n".join(lineas[i + 1:])).strip()
                if a is not None and b is not None and cuerpo:
                    cues.append((a, b, cuerpo))
                break
        cues.sort()
        self.cues = cues
        self._inicios = [c[0] for c in cues]

    def texto_en(self, ms: int) -> str:
        """Texto visible en el instante ms (puede haber varias líneas superpuestas)."""
        i = bisect_right(self._inicios, ms)
        return "\n".join(t for a, b, t in self.cues[max(0, i - 5):i] if a <= ms < b)


IDIOMAS = {"es": "Español", "spa": "Español", "en": "Inglés", "eng": "Inglés"}


def subtitulos_junto_a(ruta_video: str) -> list[str]:
    """Subtítulos con el mismo nombre del video, como hace VLC (video.srt, video.es.srt, …).
    Orden de preferencia: nombre exacto, español, el resto alfabético."""
    video = Path(ruta_video)
    candidatos = [
        p for p in video.parent.glob(glob.escape(video.stem) + "*")
        if p.suffix.lower() in EXT_SUBTITULOS
        and (p.stem == video.stem or p.stem.startswith(video.stem + "."))
    ]
    candidatos.sort(key=lambda p: (p.stem != video.stem,
                                   IDIOMAS.get(p.stem.rsplit(".", 1)[-1].lower()) != "Español",
                                   p.name.lower()))
    return [str(p) for p in candidatos]


def buscar_junto_a(ruta_video: str) -> str | None:
    candidatos = subtitulos_junto_a(ruta_video)
    return candidatos[0] if candidatos else None


def descripcion(ruta_sub: str, ruta_video: str) -> str:
    """«video.es.srt» -> «Español (video.es.srt)»."""
    extra = Path(ruta_sub).stem[len(Path(ruta_video).stem):].strip(".")
    nombre = Path(ruta_sub).name
    return f"{IDIOMAS.get(extra.lower(), extra)} ({nombre})" if extra else nombre


def _palabras(texto: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", texto.lower()))


def _tar(argumentos: list[str], timeout: int) -> subprocess.CompletedProcess | None:
    tar = Path(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe")
    try:
        return subprocess.run([str(tar) if tar.exists() else "tar", *argumentos], capture_output=True,
                              timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except (subprocess.TimeoutExpired, OSError):
        return None


def listar_comprimido(archivo: Path) -> list[str]:
    """Los nombres de los archivos que trae un .zip/.rar/.7z ([] si no se puede abrir)."""
    resultado = _tar(["-tf", str(archivo)], 60)
    if resultado is None or resultado.returncode != 0:
        return []
    return [n for n in resultado.stdout.decode("utf-8", "replace").splitlines() if n and not n.endswith("/")]


def extraer_comprimido(archivo: Path, carpeta: Path, timeout: int = 60) -> bool:
    resultado = _tar(["-xf", str(archivo), "-C", str(carpeta)], timeout)
    return resultado is not None and resultado.returncode == 0


_ESPANOL = re.compile(r"(?i)(?<![a-z])(es|spa|esp|spanish|espa[nñ]ol|latino|castellano)(?![a-z])")
_INGLES = re.compile(r"(?i)(?<![a-z])(en|eng|english|ingl[eé]s)(?![a-z])")


def idioma_de(sub: Path) -> str:
    """«es» o «en» según el nombre del subtítulo (en duda, español: es lo que se baja de subdivx)."""
    return "en" if _INGLES.search(sub.stem) and not _ESPANOL.search(sub.stem) else "es"


def colocar_subtitulo(archivo: Path, ruta_video: str, idioma: str = "es") -> str | None:
    """Pone un subtítulo descargado (suelto o comprimido) junto al video, como «video.es.srt».
    Si el comprimido trae varios, elige el que más se parece al nombre del video.
    Devuelve la ruta nueva, o None si no había subtítulos."""
    video = Path(ruta_video)
    with tempfile.TemporaryDirectory() as carpeta:
        if archivo.suffix.lower() in EXT_COMPRIMIDOS:
            extraer_comprimido(archivo, Path(carpeta))
            candidatos = [p for p in Path(carpeta).rglob("*") if p.suffix.lower() in EXT_SUBTITULOS]
        else:
            candidatos = [archivo]
        if not candidatos:
            return None
        nombre = _palabras(video.stem)
        elegido = max(candidatos, key=lambda p: (len(_palabras(p.stem) & nombre), p.stat().st_size))
        destino = video.with_name(f"{video.stem}.{idioma}{elegido.suffix.lower()}")
        n = 2
        while destino.exists():
            destino = video.with_name(f"{video.stem}.{idioma}{n}{elegido.suffix.lower()}")
            n += 1
        shutil.copyfile(elegido, destino)
    archivo.unlink(missing_ok=True)  # ya está junto al video: no queda suelto en Descargas
    return str(destino)


_ANIO = re.compile(r"(?<!\d)(19\d\d|20\d\d)(?!\d)")
_EPISODIO = re.compile(r"(?i)(?<![a-z0-9])s?(\d{1,2})[ex](\d{1,3})(?!\d)")


def _anio_y_episodio(nombre: str) -> tuple[str | None, tuple[int, int] | None]:
    anio = _ANIO.search(re.sub(r"\[[^\]]*\]", " ", nombre))  # «[339191]» es el número del aporte en subdivx
    episodio = _EPISODIO.search(nombre)
    return (anio.group(1) if anio else None,
            (int(episodio.group(1)), int(episodio.group(2))) if episodio else None)


def video_del_subtitulo(nombres: list[str], videos: list[str]) -> str | None:
    """El video de la biblioteca al que corresponde un subtítulo bajado, por su nombre (el del
    .zip, la carpeta o el .srt): mismo título, y mismo año y capítulo si los dos lo dicen.
    None si no hay ninguno o si hay más de uno posible (mejor no adivinar)."""
    from .titulos import titulo_de
    posibles = set()
    for nombre in nombres:
        titulo = titulo_de(nombre).lower()
        anio, episodio = _anio_y_episodio(nombre)
        if not titulo:
            continue
        for video in videos:
            v = Path(video).name
            if titulo_de(v).lower() != titulo:
                continue
            anio_v, episodio_v = _anio_y_episodio(v)
            if anio and anio_v and anio != anio_v:
                continue
            if episodio != episodio_v:  # un capítulo con su capítulo; una película con su película
                continue
            posibles.add(video)
        if len(posibles) == 1:
            return posibles.pop()
        posibles.clear()
    return None


def nombres_de_comprimido(archivo: Path) -> list[str]:
    """El nombre del comprimido y, si es .zip, el de los subtítulos que trae adentro."""
    nombres = [archivo.stem]
    if archivo.suffix.lower() == ".zip":
        import zipfile
        try:
            with zipfile.ZipFile(archivo) as z:
                nombres += [Path(n).name for n in z.namelist() if Path(n).suffix.lower() in EXT_SUBTITULOS]
        except (OSError, zipfile.BadZipFile):
            pass
    return nombres
