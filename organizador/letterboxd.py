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


# Qué es una película para Wikidata (P31): película, largometraje, animada, documental, cortometraje, de TV…
_PELICULAS = {"Q11424", "Q24869", "Q202866", "Q93204", "Q24862", "Q506240", "Q226730", "Q20650540", "Q229390",
              "Q17123180", "Q130232", "Q21191270"}
_ES_PELICULA = re.compile(r"(?i)\b(pel[ií]cula|film|largometraje|documental|cortometraje)\b")


def _primer_valor(claims: dict, propiedad: str):
    for c in claims.get(propiedad, []):
        valor = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if valor:
            return valor
    return None


# Wikimedia pide que cada programa se identifique con su nombre y una página del proyecto
AGENTE_WIKIMEDIA = ("TorrentVision/1.10 (https://github.com/facuperma/TVon-App-de-escritorio-para-organizar-y-ver-videos)"
                    " python-urllib")


def _wikidata(params: dict, timeout: int = 15) -> dict:
    """Un pedido a Wikidata; si dice que hay demasiados pedidos (429), espera un poco y reintenta una vez."""
    for intento in range(2):
        try:
            return pedir_json(WIKIDATA, params, timeout=timeout, cabeceras={"User-Agent": AGENTE_WIKIMEDIA})
        except ErrorRed as e:
            if e.codigo != 429 or intento:
                raise ErrorLetterboxd("Wikidata está ocupado: probá de nuevo en un minuto" if e.codigo == 429
                                      else f"No se pudo buscar: {e}") from e
            time.sleep(4)
    return {}


# Series para Wikidata (P31): serie de TV, miniserie, web, animada, anime
_SERIES = {"Q5398426", "Q1259759", "Q526877", "Q581714", "Q63952888", "Q117467246", "Q15416"}
_ES_SERIE = re.compile(r"(?i)\b(serie|series|miniserie|miniseries|sitcom|telenovela|anime)\b")
_TEMPORADA = re.compile(r"(?i)\b(?:temporada|temp\.?|season|seasson|t)\s*(\d{1,2})\b")
_EPISODIO = re.compile(r"(?i)\b(?:cap[ií]tulo|cap\.?|episodio|episode|ep\.?|e)\s*(\d{1,3})\b")
_SXE = re.compile(r"(?i)\bs(\d{1,2})\s*e(\d{1,3})\b|\b(\d{1,2})x(\d{1,3})\b")
_COMPLETA = re.compile(r"(?i)\b(complet[ao]s?|complete|entera|todas las temporadas|all seasons)\b")


def interpretar_busqueda(texto: str) -> dict:
    """«Twin peaks temporada 2» → título «Twin peaks», temporada 2. Entiende temporada/season/T2, capítulo/episodio,
    S02E05 y 2x05, y «completa». Lo que queda es el nombre para buscar."""
    t = " " + texto.strip() + " "
    temporada = episodio = None
    if m := _SXE.search(t):
        temporada, episodio = int(m.group(1) or m.group(3)), int(m.group(2) or m.group(4))
        t = t[:m.start()] + " " + t[m.end():]
    if m := _TEMPORADA.search(t):
        temporada = int(m.group(1))
        t = t[:m.start()] + " " + t[m.end():]
    if m := _EPISODIO.search(t):
        episodio = int(m.group(1))
        t = t[:m.start()] + " " + t[m.end():]
    completa = bool(_COMPLETA.search(t))
    t = _COMPLETA.sub(" ", t)
    titulo = re.sub(r"\s+", " ", t).strip(" -·,")
    return {"titulo": titulo, "temporada": temporada, "episodio": episodio, "completa": completa}


def texto_torrent(p: dict, pedido: dict | None = None) -> str:
    """Lo que se busca en la página de torrents: el título original (en inglés) y, para una película, el año; para
    una serie, la temporada y el capítulo como se nombran los torrents («Twin Peaks S02», «… S02E05», «… complete»)."""
    pedido = pedido or {}
    titulo = p["titulo"]
    if p.get("tipo") != "serie":
        return f"{titulo} {p.get('anio', '')}".strip()
    t, e = pedido.get("temporada"), pedido.get("episodio")
    if t and e:
        return f"{titulo} S{t:02d}E{e:02d}"
    if t:
        return f"{titulo} season {t}"
    return f"{titulo} complete" if pedido.get("completa") else titulo


def buscar_peliculas(texto: str, maximo: int = 20) -> list[dict]:
    """Películas que se llaman así (en castellano o en inglés), con año, para elegir y bajar.

    Letterboxd no deja usar su buscador desde otras apps (responde 403), pero sí abrir la página de una película por
    su número de IMDb: Wikidata (libre, sin clave) da los candidatos con su IMDb, y la vista previa (póster,
    sinopsis) sale de Letterboxd como en las listas. Cada una: titulo (en inglés, el que sirve para buscar el
    torrent), titulo_es, anio, descripcion y url (Letterboxd)."""
    texto = interpretar_busqueda(texto)["titulo"] or texto.strip()
    if len(texto) < 2:
        return []
    ids: list[str] = []
    descripciones: dict[str, str] = {}
    for idioma in ("es", "en"):
        r = _wikidata({"action": "wbsearchentities", "search": texto, "language": idioma,
                       "uselang": "es", "type": "item", "limit": 20, "format": "json"})
        for c in r.get("search", []):
            if c["id"] not in ids:
                ids.append(c["id"])
                descripciones[c["id"]] = c.get("description") or ""
    if not ids:
        return []
    entidades = {}
    for i in range(0, len(ids), 40):
        e = _wikidata({"action": "wbgetentities", "ids": "|".join(ids[i:i + 40]), "props": "claims|labels|sitelinks",
                       "languages": "es|en|mul", "sitefilter": "eswiki|enwiki", "format": "json"}, timeout=20)
        entidades.update(e.get("entities", {}))
    pelis, vistas = [], set()
    for qid in ids:
        ent = entidades.get(qid) or {}
        claims = ent.get("claims", {})
        imdb = _primer_valor(claims, "P345")
        if not isinstance(imdb, str) or not imdb.startswith("tt") or imdb in vistas:
            continue
        tipos = {c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P31", [])}
        descripcion = descripciones.get(qid, "")
        if tipos & _SERIES or (_ES_SERIE.search(descripcion) and not tipos & _PELICULAS):
            tipo = "serie"
        elif tipos & _PELICULAS or _ES_PELICULA.search(descripcion):
            tipo = "pelicula"
        else:
            continue  # el libro, el videojuego, el personaje…
        vistas.add(imdb)
        etiquetas = ent.get("labels", {})
        # Wikidata guarda cada vez más títulos originales como «mul» (todos los idiomas) en vez de «en»
        en = etiquetas.get("en", {}).get("value", "") or etiquetas.get("mul", {}).get("value", "")
        es = etiquetas.get("es", {}).get("value", "")
        fecha = _primer_valor(claims, "P580" if tipo == "serie" else "P577") or _primer_valor(claims, "P577")
        anio = ""
        if isinstance(fecha, dict) and (m := re.match(r"[+-]?(\d{4})", fecha.get("time", ""))):
            anio = m.group(1)
        # Letterboxd no tiene series: su vista previa sale de Wikipedia (en castellano si hay)
        wiki = ""
        enlaces = ent.get("sitelinks", {})
        for sitio, idioma in (("eswiki", "es"), ("enwiki", "en")):
            if sitio in enlaces:
                wiki = f"https://{idioma}.wikipedia.org/wiki/{enlaces[sitio]['title'].replace(' ', '_')}"
                break
        url = f"https://letterboxd.com/imdb/{imdb}/" if tipo == "pelicula" else (wiki or f"https://www.imdb.com/title/{imdb}/")
        pelis.append({"titulo": en or es, "titulo_es": es or en, "anio": anio, "tipo": tipo, "wiki": wiki,
                      "descripcion": descripcion, "url": url})
        if len(pelis) >= maximo:
            break
    return pelis


def detalle_wikipedia(url: str) -> dict:
    """Resumen de Wikipedia (para las series, que Letterboxd no tiene): primer párrafo y su imagen."""
    m = re.match(r"https://(\w+)\.wikipedia\.org/wiki/(.+)", url)
    datos = {}
    if m:
        try:
            datos = pedir_json(f"https://{m.group(1)}.wikipedia.org/api/rest_v1/page/summary/{m.group(2)}", timeout=15,
                               cabeceras={"User-Agent": AGENTE_WIKIMEDIA})
        except ErrorRed:
            datos = {}
    imagen = (datos.get("originalimage") or datos.get("thumbnail") or {}).get("source", "")
    return {"sinopsis": datos.get("extract", ""), "poster_url": imagen, "director": "", "minutos": 0, "generos": [],
            "puntaje": 0}


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
