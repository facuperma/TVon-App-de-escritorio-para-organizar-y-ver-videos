"""Subtítulos de subtis.io para las películas que se acaban de bajar.

Subtis (https://subtis.io) junta subtítulos de SubDivX y SUBDL y tiene una API pública (api.subt.is), sin
Cloudflare: se le puede preguntar directo, sin abrir el navegador. Solo tiene subtítulos EN ESPAÑOL y solo de
películas (no de series), así que se usa solo cuando el idioma elegido es alguna variante de español.

Se busca, en este orden: por el tamaño exacto del archivo (si es el mismo «release», el subtítulo queda justo),
por el nombre del archivo y, si no, por título y año, eligiendo el subtítulo cuyo nombre más se parece al del video
(misma resolución, mismo grupo). Si no aparece nada, no pasa nada.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from .red import ErrorRed, bajar_bytes, pedir_json
from .subtitulos import _anio_y_episodio
from .titulos import titulo_de

API = "https://api.subt.is/v1"
WEB = "https://subtis.io"


def sirve_para(idioma: str) -> bool:
    """¿Sirve subtis para este idioma? Solo tiene español (cualquier variante: es, es_AR, es_419…)."""
    return (idioma or "").lower().replace("-", "_").split("_")[0] == "es"


def _pedir(camino: str) -> dict | None:
    try:
        return pedir_json(API + camino, timeout=20)
    except ErrorRed as e:
        if e.codigo in (400, 404):      # «no encontrado»: no es un error
            return None
        raise


def _fichas(nombre: str) -> set[str]:
    return {f for f in re.split(r"[^a-z0-9]+", Path(nombre).stem.lower()) if f}


def _parecido(nombre_video: str, nombre_sub: str) -> float:
    a, b = _fichas(nombre_video), _fichas(nombre_sub)
    return len(a & b) / max(1, len(a | b))


def buscar(ruta_video: str) -> dict | None:
    """El subtítulo de subtis para este video: {"link", "nombre", "titulo", "como"} o None si no hay."""
    video = Path(ruta_video)
    anio, episodio = _anio_y_episodio(video.name)
    if episodio:                        # subtis no tiene series
        return None
    try:
        tamano = video.stat().st_size
    except OSError:
        tamano = 0
    # 1. El mismo archivo (mismo tamaño en bytes): el subtítulo es justo para este release
    if tamano:
        r = _pedir(f"/subtitle/find/file/bytes/{tamano}")
        if r and r.get("subtitle"):
            return {"link": r["subtitle"]["subtitle_link"], "nombre": r["subtitle"]["subtitle_file_name"],
                    "titulo": r.get("title", {}).get("title_name", ""), "como": "mismo archivo"}
    # 2. Por el nombre del archivo
    r = _pedir("/subtitle/find/file/name/" + quote(video.name))
    if r and r.get("subtitle"):
        return {"link": r["subtitle"]["subtitle_link"], "nombre": r["subtitle"]["subtitle_file_name"],
                "titulo": r.get("title", {}).get("title_name", ""), "como": "mismo nombre"}
    # 3. Por título (y año): el subtítulo con el nombre más parecido al del video
    titulo = titulo_de(video.name)
    if not titulo:
        return None
    r = _pedir("/titles/search/" + quote(titulo))
    candidatos = [t for t in (r or {}).get("results", []) if t.get("type") == "movie"]
    if anio:
        candidatos = [t for t in candidatos if str(t.get("year")) == str(anio)]
    if not candidatos:
        return None
    elegido = max(candidatos, key=lambda t: _parecido(titulo, t.get("title_name", "")))
    r = _pedir("/subtitles/movie/" + quote(elegido["slug"]))
    resultados = [x["subtitle"] for x in (r or {}).get("results", []) if x.get("subtitle")]
    if not resultados:
        return None
    mejor = max(resultados, key=lambda s: (_parecido(video.name, s.get("title_file_name", "")), s.get("queried_times", 0)))
    return {"link": mejor["subtitle_link"], "nombre": mejor["subtitle_file_name"],
            "titulo": elegido.get("title_name", titulo), "como": "por título"}


def bajar(ruta_video: str, sufijo: str = "es") -> str | None:
    """Busca y deja el subtítulo junto al video (video.es.srt). Devuelve la ruta, o None si no hay
    (o si ya había un subtítulo en español al lado)."""
    video = Path(ruta_video)
    destino = video.with_name(f"{video.stem}.{sufijo}.srt")
    if destino.exists():
        return None
    encontrado = buscar(ruta_video)
    if not encontrado:
        return None
    datos = bajar_bytes(encontrado["link"], timeout=40)
    if len(datos) < 200 or b"-->" not in datos[:20000]:
        return None                     # no es un .srt (página de error o archivo vacío)
    destino.write_bytes(datos)
    return str(destino)
