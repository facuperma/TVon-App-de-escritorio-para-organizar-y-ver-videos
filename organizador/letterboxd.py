"""Letterboxd: la watchlist pública de un usuario y las 500 películas mejor puntuadas (su lista oficial).

Letterboxd no da su API a cualquiera ni deja iniciar sesión desde otras apps: se lee la página
pública, como la ve cualquiera sin cuenta. Si la watchlist es privada, no se ve. Si Letterboxd
cambia su página, esto deja de encontrar películas y lo avisa.
"""
import html
import json
import re
import time
import unicodedata

from urllib.request import Request

from .red import AGENTE, ErrorRed, _abrir, bajar_bytes, pedir_json
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


# Partes de letterboxd.com que no son usuarios
_NO_USUARIOS = {"film", "films", "list", "lists", "official", "members", "people", "search", "settings", "activity",
                "journal", "pro", "about", "sign-in", "create-account", "tag", "director", "actor"}


def _link_corto(texto: str) -> str:
    """boxd.it/xxxx (el link de «Compartir» de Letterboxd) lleva al perfil: se sigue hasta ahí."""
    url = texto if texto.startswith("http") else "https://" + texto
    if not re.fullmatch(r"https://boxd\.it/[A-Za-z0-9]{2,12}/?", url):
        raise ErrorLetterboxd("Ese link no es de Letterboxd")
    try:
        with _abrir(Request(url, headers={"User-Agent": AGENTE}), 20) as r:
            return r.geturl()
    except (ErrorRed, OSError) as e:
        raise ErrorLetterboxd(f"No se pudo abrir el link de Letterboxd: {e}") from e


def usuario_valido(texto: str) -> str:
    """El usuario: escrito, o sacado del link del perfil o de la watchlist («letterboxd.com/fulano/watchlist/»),
    o del link corto que da Letterboxd al compartir («boxd.it/…»)."""
    t = texto.strip()
    if "boxd.it/" in t:
        t = _link_corto(t[t.index("boxd.it/"):].split()[0])
    if m := re.search(r"letterboxd\.com/@?([A-Za-z0-9_]{2,30})(?:[/?#]|$)", t):
        t = m.group(1)
    usuario = t.strip("/@ ")
    if not re.fullmatch(r"[A-Za-z0-9_]{2,30}", usuario) or usuario.lower() in _NO_USUARIOS:
        raise ErrorLetterboxd("Escribí tu usuario de Letterboxd o pegá el link de tu perfil "
                              "(letterboxd.com/usuario o el link corto boxd.it/…)")
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


def coincide_archive(encontrada: dict, titulo: str, anio: str) -> bool:
    """Si un resultado del Internet Archive es esta película: mismo año y mismo título, o el mismo título con
    algo más atrás («Nosferatu (1922)», «Nosferatu, eine Symphonie…»)."""
    if encontrada.get("anio") != anio:
        return False
    buscada = clave(titulo)
    de_archive = clave(re.sub(r"\s*\(\d{4}\)\s*$", "", encontrada["titulo"]))
    return de_archive == buscada or de_archive.startswith(buscada + " ")


def claves_biblioteca(nombres_archivo: list[str]) -> set[str]:
    """Las claves de los videos de la biblioteca: con año si el nombre lo trae («dune|2021»), así
    no se confunde una película con su remake; si no, solo el título («dune|»)."""
    claves = set()
    for nombre in nombres_archivo:
        titulo = titulo_de(nombre)
        anio = m.group(1) if (m := re.search(r"\b(19[2-9]\d|20[0-4]\d)\b", nombre[len(titulo):])) else ""
        claves.add(clave(titulo, anio))
    return claves


def en_biblioteca(peli: dict, claves: set[str], otros_titulos: list[str] = ()) -> bool:
    """Si ya está: por su título o por cualquiera de sus títulos en otros idiomas («El padrino»)."""
    for titulo in [peli["titulo"], *otros_titulos]:
        if clave(titulo, peli["anio"]) in claves or clave(titulo) in claves:
            return True
    return False


WIKIDATA = "https://www.wikidata.org/w/api.php"
IDIOMAS = "es|en|pt|it|fr|de|ja|ko|zh|ru|sv|da|pl"


def titulos_en_otros_idiomas(titulo: str, anio: str) -> list[str]:
    """Los títulos de la película en otros idiomas, según Wikidata (que es libre y no pide clave):
    «The Godfather» (1972) → «El padrino», «Il padrino», «Le Parrain»… Se elige la película cuya
    descripción dice ese año (así no se confunde con el libro, el juego o la remake)."""
    r = pedir_json(WIKIDATA, {"action": "wbsearchentities", "search": titulo, "language": "en", "type": "item",
                              "limit": 7, "format": "json"}, timeout=15)
    elegido = next((c["id"] for c in r.get("search", [])
                    if anio and anio in (c.get("description") or "") and "film" in (c.get("description") or "")),
                   None)
    if elegido is None:
        return []
    e = pedir_json(WIKIDATA, {"action": "wbgetentities", "ids": elegido, "props": "labels|aliases",
                              "languages": IDIOMAS, "format": "json"}, timeout=15)["entities"][elegido]
    nombres = {v["value"] for v in e.get("labels", {}).values()}
    nombres |= {a["value"] for lista in e.get("aliases", {}).values() for a in lista}
    nombres.discard(titulo)
    return sorted(nombres)[:40]


def detalle(url: str) -> dict:
    """Lo que muestra la página de una película (datos estructurados que Letterboxd pone para los buscadores):
    sinopsis, póster (como dirección), director, duración, géneros y puntaje. Lo que falte queda vacío."""
    pagina = _pagina(url)
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', pagina, re.S)
    datos = {}
    if m:
        try:
            datos = json.loads(re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S).strip())
        except ValueError:
            datos = {}
    if not isinstance(datos, dict):
        datos = {}
    minutos = 0
    if d := re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", str(datos.get("duration") or "")):
        minutos = int(d.group(1) or 0) * 60 + int(d.group(2) or 0)
    directores = [p.get("name", "") for p in datos.get("director") or [] if isinstance(p, dict)]
    generos = datos.get("genre") or []
    puntaje = (datos.get("aggregateRating") or {}).get("ratingValue")
    og = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', pagina)
    return {
        "sinopsis": html.unescape(datos.get("description") or (og.group(1) if og else "")).strip(),
        "poster_url": datos.get("image") or "",
        "director": ", ".join(d for d in directores if d),
        "minutos": minutos,
        "generos": [g for g in ([generos] if isinstance(generos, str) else generos) if isinstance(g, str)][:4],
        "puntaje": round(float(puntaje), 1) if isinstance(puntaje, (int, float)) else None,
    }
