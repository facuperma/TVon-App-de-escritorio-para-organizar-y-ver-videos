"""Letterboxd: la watchlist pública de un usuario y las 500 películas mejor puntuadas (su lista oficial).

Letterboxd no da su API a cualquiera ni deja iniciar sesión desde otras apps: se lee la página
pública, como la ve cualquiera sin cuenta. Si la watchlist es privada, no se ve. Si Letterboxd
cambia su página, esto deja de encontrar películas y lo avisa.
"""
import html
import re
import time
import unicodedata

from .red import ErrorRed, bajar_bytes
from .titulos import titulo_de

MEJOR_PUNTUADAS = "https://letterboxd.com/official/list/letterboxds-top-500-films/"
MAX_PAGINAS = 12  # 28 por página: hasta 336 películas de la watchlist
_POSTER = re.compile(r'<div[^>]*data-component-class="LazyPoster"[^>]*>')


class ErrorLetterboxd(Exception):
    pass


def _pagina(url: str) -> str:
    try:
        return bajar_bytes(url, timeout=20, cabeceras={"Accept-Language": "es,en"}).decode("utf-8", "ignore")
    except ErrorRed as e:
        if e.codigo == 404:
            raise ErrorLetterboxd("Ese usuario no existe en Letterboxd") from e
        raise ErrorLetterboxd(f"Letterboxd no respondió: {e}") from e


def _atributo(etiqueta: str, nombre: str) -> str:
    m = re.search(nombre + r'="([^"]*)"', etiqueta)
    return html.unescape(m.group(1)) if m else ""


def _peliculas(base: str, max_paginas: int) -> list[dict]:
    """Las películas de una lista de Letterboxd, página por página."""
    pelis, vistas = [], set()
    for n in range(1, max_paginas + 1):
        pagina = _pagina(base if n == 1 else f"{base}page/{n}/")
        for etiqueta in _POSTER.findall(pagina):
            slug = _atributo(etiqueta, "data-item-slug")
            if not slug or slug in vistas:
                continue
            vistas.add(slug)
            nombre = _atributo(etiqueta, "data-item-name")
            m = re.fullmatch(r"(.*) \((\d{4})\)", nombre)
            pelis.append({"titulo": m.group(1) if m else nombre, "anio": m.group(2) if m else "",
                          "url": f"https://letterboxd.com/film/{slug}/"})
        if f"page/{n + 1}/" not in pagina:
            break
        time.sleep(0.5)  # sin apurar a Letterboxd
    return pelis


def usuario_valido(texto: str) -> str:
    """El usuario, aunque se pegue el link del perfil («letterboxd.com/fulano/»)."""
    usuario = texto.strip().rstrip("/").rsplit("/", 1)[-1]
    if not re.fullmatch(r"[A-Za-z0-9_]{2,30}", usuario):
        raise ErrorLetterboxd("Escribí tu usuario de Letterboxd (el que aparece en letterboxd.com/usuario)")
    return usuario


def watchlist(usuario: str) -> list[dict]:
    pelis = _peliculas(f"https://letterboxd.com/{usuario_valido(usuario)}/watchlist/", MAX_PAGINAS)
    if not pelis:
        raise ErrorLetterboxd("La watchlist está vacía o es privada (en Letterboxd: Settings → Privacy)")
    return pelis


def mejor_puntuadas() -> list[dict]:
    return _peliculas(MEJOR_PUNTUADAS, 5)


def clave(titulo: str, anio: str = "") -> str:
    """Para comparar títulos: sin tildes, signos ni mayúsculas, y con el año si se sabe."""
    t = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"^(the|a|an|el|la|los|las)\s+", "", re.sub(r"[^a-z0-9]+", " ", t).strip())
    return f"{t}|{anio}"


def claves_biblioteca(nombres_archivo: list[str]) -> set[str]:
    """Las claves de los videos de la biblioteca: con año si el nombre lo trae («dune|2021»), así
    no se confunde una película con su remake; si no, solo el título («dune|»)."""
    claves = set()
    for nombre in nombres_archivo:
        titulo = titulo_de(nombre)
        anio = m.group(1) if (m := re.search(r"\b(19[2-9]\d|20[0-4]\d)\b", nombre[len(titulo):])) else ""
        claves.add(clave(titulo, anio))
    return claves


def en_biblioteca(peli: dict, claves: set[str]) -> bool:
    return clave(peli["titulo"], peli["anio"]) in claves or clave(peli["titulo"]) in claves
