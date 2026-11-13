"""Los retoques de la interfaz que se hacen desde el menú de desarrollador (Ctrl+2, 3): colores, letra, tamaño, aire,
el orden y los nombres de los botones de la barra, qué controles del reproductor y qué secciones se ven, y el orden de
las columnas. Se guarda en la configuración («diseno») y se aplica encima del tema elegido; los presets son copias con
nombre («diseno_presets»)."""
from __future__ import annotations

import copy
import json
import re
from dataclasses import replace

from .temas import Tema

# Los colores que se pueden cambiar (campo del tema, para qué se usa)
COLORES = [
    ("fondo", "Fondo de la ventana"), ("barra", "Barra de botones"), ("panel", "Listas y campos"),
    ("panel_claro", "Tarjetas, cabeceras y menús"), ("borde", "Bordes"), ("texto", "Texto"), ("tenue", "Texto secundario"),
    ("titulo", "Títulos"), ("acento", "Acento (botón principal, pestaña elegida)"), ("seleccion", "Lo elegido"),
    ("hover", "Al pasar el mouse"), ("boton", "Botones"), ("boton_hover", "Botones al pasar el mouse"),
    ("boton_borde", "Borde de los botones"), ("boton_texto", "Texto de los botones"), ("fondo_hondo", "Fondo del video"),
]
# La barra de botones de arriba, en su orden de siempre («|» es una separación)
BARRA = ["archivos", "carpeta", "|", "dominio", "torrents", "letterboxd", "on", "|", "peliculas", "subtitulos"]
NOMBRES_BARRA = {"archivos": "Agregar archivos", "carpeta": "Agregar carpeta", "dominio": "Dominio público",
                 "torrents": "Torrents", "letterboxd": "Letterboxd", "on": "ON (celular)", "peliculas": "Películas (web)",
                 "subtitulos": "Subtítulos (web)"}
CONTROLES = {"atras15": "↺ 15 s", "play": "Reproducir / pausar", "adelante15": "15 s ↻", "stop": "Detener",
             "siguiente": "Siguiente", "mute": "Silenciar", "volumen": "Volumen", "porcentaje": "Porcentaje del volumen",
             "subs": "Subtítulos (CC)", "mas": "Menú «⋯»", "completa": "Pantalla completa"}
SECCIONES = {"izq": "Biblioteca y categorías", "detalles": "Detalles del archivo (ficha)", "buscador": "Buscador de arriba",
             "estado": "Barra de estado", "barra": "Barra de botones", "banda": "Banda del tema retro"}
COLUMNAS = {"izq": "Categorías", "centro": "Lista de videos", "der": "Reproductor"}
ESTILOS_BARRA = {"texto_icono": "Ícono y texto", "texto": "Solo texto", "icono": "Solo ícono", "texto_abajo": "Texto abajo del ícono"}

POR_DEFECTO = {"colores": {}, "letra": "", "tam_letra": 10, "radio": None, "aire": 100,
               "barra": {"orden": list(BARRA), "ocultos": [], "textos": {}, "estilo": "texto_icono"},
               "controles_ocultos": [], "secciones_ocultas": [], "columnas": ["izq", "centro", "der"]}
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def normalizar(d) -> dict:
    """Solo valores válidos (lo que viene de un archivo importado puede estar mal)."""
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except ValueError:
            d = {}
    if not isinstance(d, dict):
        d = {}
    r = copy.deepcopy(POR_DEFECTO)
    campos = {c for c, _ in COLORES}
    r["colores"] = {k: v.lower() for k, v in (d.get("colores") or {}).items() if k in campos and isinstance(v, str) and _HEX.fullmatch(v)}
    if isinstance(d.get("letra"), str):
        r["letra"] = d["letra"][:80]
    for clave, minimo, maximo in (("tam_letra", 7, 18), ("aire", 50, 180)):
        if isinstance(d.get(clave), (int, float)) and not isinstance(d.get(clave), bool):
            r[clave] = int(max(minimo, min(maximo, d[clave])))
    if isinstance(d.get("radio"), (int, float)) and not isinstance(d.get("radio"), bool):
        r["radio"] = int(max(0, min(24, d["radio"])))
    b = d.get("barra") or {}
    validos = set(BARRA) - {"|"}
    orden = [x for x in b.get("orden", []) if x in validos or x == "|"] if isinstance(b.get("orden"), list) else []
    faltan = [x for x in BARRA if x != "|" and x not in orden]
    r["barra"]["orden"] = (orden + faltan) if orden else list(BARRA)
    r["barra"]["ocultos"] = [x for x in b.get("ocultos", []) if x in validos] if isinstance(b.get("ocultos"), list) else []
    r["barra"]["textos"] = {k: str(v)[:40] for k, v in (b.get("textos") or {}).items() if k in validos and str(v).strip()}
    r["barra"]["estilo"] = b.get("estilo") if b.get("estilo") in ESTILOS_BARRA else "texto_icono"
    r["controles_ocultos"] = [x for x in d.get("controles_ocultos", []) if x in CONTROLES] if isinstance(d.get("controles_ocultos"), list) else []
    r["secciones_ocultas"] = [x for x in d.get("secciones_ocultas", []) if x in SECCIONES] if isinstance(d.get("secciones_ocultas"), list) else []
    cols = d.get("columnas")
    if isinstance(cols, list) and sorted(cols) == sorted(COLUMNAS):
        r["columnas"] = list(cols)
    return r


def cargar(bib) -> dict:
    return normalizar(bib.config("diseno") or "{}")


def guardar(bib, d: dict):
    bib.guardar_config("diseno", json.dumps(normalizar(d)))


def presets(bib) -> dict:
    try:
        datos = json.loads(bib.config("diseno_presets") or "{}")
    except ValueError:
        datos = {}
    return {str(k)[:40]: normalizar(v) for k, v in datos.items()} if isinstance(datos, dict) else {}


def guardar_presets(bib, todos: dict):
    bib.guardar_config("diseno_presets", json.dumps(todos))


def tema_con(t: Tema, d: dict) -> Tema:
    """El tema con los retoques encima."""
    cambios = dict(d.get("colores", {}))
    if d.get("letra"):
        cambios["letra"] = d["letra"]
    if d.get("radio") is not None:
        cambios["radio"] = d["radio"]
    return replace(t, **cambios) if cambios else t


def qss(d: dict) -> str:
    """Lo que se suma a la hoja de estilo: tamaño de letra y cuánto aire hay dentro de botones y filas."""
    partes = [f"QWidget {{ font-size: {d.get('tam_letra', 10)}pt; }}"]
    s = d.get("aire", 100) / 100
    if abs(s - 1) > 0.01:
        partes.append(f"QListWidget::item {{ padding: {round(9 * s)}px {round(12 * s)}px; }}")
        partes.append(f"QTreeWidget::item {{ padding: {round(9 * s)}px {round(10 * s)}px; }}")
        partes.append(f"QPushButton {{ padding: {round(8 * s)}px {round(16 * s)}px; }}")
        partes.append(f"QToolBar QToolButton {{ padding: {round(7 * s)}px {round(13 * s)}px; }}")
        partes.append(f"QLineEdit {{ padding: {round(9 * s)}px {round(13 * s)}px; }}")
    return "\n" + "\n".join(partes) + "\n"
