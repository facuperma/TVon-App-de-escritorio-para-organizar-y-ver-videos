"""Poses de BiriBiri y lugares donde ponerlo en el reproductor.

Cada pose es un conjunto de ajustes de la escena 3D (ver vista3d.py): desplazamiento (pX, pY, pZ) y giro (rX, rY, rZ) del
cuerpo, giro de cada brazo (ai* = izquierdo, ad* = derecho), de cada pierna (li*, ld*) y de la cabeza (cab*), en grados.
Más lo que se mueve solo: ampBx (brazos que van y vienen), ondaI/ondaD (un brazo que saluda), giroB (brazos que giran
como molinos), ampP / ampPz (piernas), ampS (saltitos) y ritmo (velocidad). Lo que no figura vale 0 (esc, reposo: 1)."""
from __future__ import annotations

# Valores de arranque de todo lo que una pose puede tocar
BASE = {"pX": 0, "pY": 0, "pZ": 0, "rX": 0, "rY": 0, "rZ": 0,
        "aiX": 0, "aiY": 0, "aiZ": 0, "adX": 0, "adY": 0, "adZ": 0,
        "liX": 0, "liY": 0, "liZ": 0, "ldX": 0, "ldY": 0, "ldZ": 0,
        "cabX": 0, "cabY": 0, "cabZ": 0, "esc": 1, "reposo": 1,
        "ampBx": 0, "ondaI": 0, "ondaD": 0, "giroB": 0, "ampP": 0, "ampPz": 0, "ampS": 0, "ritmo": 6}

POSES: dict[str, tuple[str, dict]] = {
    "normal": ("Normal (según el lugar)", {}),
    "t": ("Pose en T", {"reposo": 0, "aiZ": -90, "adZ": 90}),
    "celebrando": ("Celebrando", {"reposo": 0, "aiZ": -108, "adZ": 108, "ampS": 0.07, "ritmo": 7, "ondaI": 14, "ondaD": 14,
                                  "cabX": -8}),
    "cruzados": ("Brazos cruzados", {"reposo": 0, "aiX": -62, "aiZ": 58, "adX": -72, "adZ": -58, "cabZ": 4}),
    "cintura": ("Manos en la cintura", {"reposo": 0, "aiZ": -34, "aiX": 12, "adZ": 34, "adX": 12}),
    "corriendo": ("Corriendo", {"reposo": 0, "aiZ": -14, "adZ": 14, "ampBx": 44, "ampP": 42, "ampS": 0.04, "ritmo": 9, "rX": 8, "rY": -42}),
    "acostado": ("Acostado, haciéndose el lindo", {"reposo": 0, "rZ": 90, "pX": 0.36, "pY": 0.14, "esc": 0.58,
                                                   "aiZ": -112, "adZ": 10, "adX": -10, "liX": -12, "ldX": -34, "ldZ": 4,
                                                   "cabZ": -48, "cabY": 0}),
    "sentado": ("Sentado con las piernas cruzadas", {"reposo": 0.3, "pY": -0.255, "liX": -90, "ldX": -90, "liY": 58, "ldY": -58,
                                                    "aiX": -38, "aiZ": -12, "adX": -38, "adZ": 12}),
    "vertical": ("Haciendo la vertical", {"reposo": 0, "rZ": 180, "pY": 0.92, "aiZ": -128, "adZ": 128, "liZ": -6, "ldZ": 6,
                                          "esc": 0.74, "ampS": 0}),
    "saludando": ("Saludando", {"reposo": 0.5, "adZ": 120, "ondaD": 20, "ritmo": 7, "cabZ": -5}),
    "volando": ("Volando", {"reposo": 0, "rZ": -90, "pX": -0.36, "pY": 0.46, "esc": 0.58, "adZ": 100, "aiZ": -100, "liX": 8,
                            "ldX": 8, "cabZ": 55, "ampS": 0.025, "ritmo": 3}),
    "nadando": ("Nadando", {"reposo": 0, "rZ": -90, "pX": -0.36, "pY": 0.46, "esc": 0.58, "cabZ": 55, "aiZ": -62, "adZ": 62, "ondaI": 38, "ondaD": 38, "ampPz": 16, "ritmo": 4.5}),
    "bailando": ("Bailando", {"reposo": 0, "aiZ": -108, "adZ": 62, "ondaI": 16, "ondaD": 16, "ampP": 18, "ampS": 0.05,
                              "ritmo": 8, "cabZ": 6}),
    "karate": ("Patada de karate", {"reposo": 0, "rY": -40, "aiZ": -70, "adZ": 100, "ldX": -92, "liZ": -4, "pY": 0.02,
                                    "cabY": 0}),
    "dormido": ("Parado dormido", {"reposo": 0.2, "aiX": 6, "adX": 6, "cabX": 28, "cabZ": 10, "rZ": 4}),
}

# Lugares del reproductor donde se puede poner a BiriBiri (además de la pantalla del logo)
LUGARES: dict[str, str] = {
    "ninguno": "En ningún otro lugar",
    "nadando": "Nadando en la pantalla del logo",
    "lista": "Sentado debajo de la lista de películas",
    "buscador": "Acostado arriba del buscador",
    "visor": "Saludando arriba del reproductor",
    "estado": "Parado en la barra de abajo",
}

# La pose que lleva en cada lugar cuando la pose elegida es «Normal»
POSE_DEL_LUGAR = {"nadando": "nadando", "lista": "sentado", "buscador": "acostado", "visor": "saludando",
                  "estado": "cruzados"}


# Poses acostadas o en el aire: en una vista ancha y baja (los lugares del reproductor) se las agranda y se las centra
HORIZONTALES = {"acostado": {"esc": 1.0, "pX": 0.57, "pY": 0.24},
                "nadando": {"esc": 0.95, "pX": -0.55, "pY": 0.5},
                "volando": {"esc": 0.95, "pX": -0.55, "pY": 0.5}}


def resolver(nombre: str, lugar: str | None = None) -> str:
    """La pose que se usa: la elegida o, si es «normal» y hay un lugar, la que le toca a ese lugar."""
    if nombre == "normal" and lugar in POSE_DEL_LUGAR:
        return POSE_DEL_LUGAR[lugar]
    return nombre if nombre in POSES else "normal"


def es_horizontal(nombre: str) -> bool:
    return nombre in HORIZONTALES


def ajustes(nombre: str, lugar: str | None = None) -> dict:
    """Todos los ajustes de una pose (los que no define, en su valor de arranque). Con un lugar (una vista ancha del
    reproductor), «normal» es la pose de ese lugar y las acostadas se agrandan y se centran."""
    nombre = resolver(nombre, lugar)
    datos = dict(BASE)
    datos.update(POSES[nombre][1])
    if lugar is not None and nombre in HORIZONTALES:
        datos.update(HORIZONTALES[nombre])
    return datos


def etiquetas() -> dict[str, str]:
    return {k: v[0] for k, v in POSES.items()}


# --- Qué hacen BiriBiri y su mascota juntos -----------------------------------------------------------------------
# Valores de partida de la mascota en la escena (ver vista3d.py): inclinación y asentir de la cabeza, cuánto y qué tan
# rápido mueve la cola, saltitos, hacia dónde mira, qué tan cerca está y lo que aparece (comida, plato, corazones…)
MASCOTA_BASE = {"petCabX": 0, "petCabZ": 0, "petCola": 22, "petRitmo": 7, "petSalto": 0, "petRotY": -28, "petPos": 0.4, "petZ": 0.0, "petEsc": 1.25,
                "comida": "", "plato": False, "corazones": False, "granos": False, "texto": ""}

# nombre: (etiqueta, ajustes de BiriBiri, ajustes de la mascota)
INTERACCIONES: dict[str, tuple[str, dict, dict]] = {
    "ninguna": ("Sin hacer nada juntos", {}, {}),
    "acariciar": ("Le hace mimos", {"reposo": 0, "adZ": 58, "adX": -18, "ondaD": 9, "ritmo": 7, "cabY": 24, "cabZ": -4},
                  {"petCabZ": -12, "petCabX": 6, "petCola": 38, "petRitmo": 11, "corazones": True}),
    "premio": ("Le da un premio", {"reposo": 0, "adZ": 42, "adX": -72, "cabY": 22},
               {"petRotY": -52, "petZ": -0.08, "petCabX": -20, "petCola": 40, "petRitmo": 12, "comida": "premio", "texto": "¡Ñam!"}),
    "plato": ("Le llena el plato", {"reposo": 0, "adZ": 30, "adX": -52, "cabY": 18, "cabX": 10},
              {"petRotY": -10, "petCabX": 38, "petCola": 30, "petRitmo": 13, "plato": True, "granos": True, "texto": "¡Ñam!"}),
    "pelota": ("Juegan a la pelota", {"reposo": 0, "adZ": 50, "adX": -76, "cabY": 22, "ondaD": 8, "ritmo": 5},
               {"petSalto": 0.12, "petZ": -0.24, "petPos": 0.46, "petCabX": -10, "petCola": 45, "petRitmo": 12, "comida": "pelota", "texto": "grito"}),
}
ETIQUETAS_INTERACCION = {k: v[0] for k, v in INTERACCIONES.items()}


def interaccion(nombre: str, animal: str) -> tuple[dict, dict]:
    """(ajustes de BiriBiri, ajustes de la mascota) de lo que hacen juntos; animal = «perro» o «gato»."""
    _etiqueta, bb, pet = INTERACCIONES.get(nombre, INTERACCIONES["ninguna"])
    mascota = dict(MASCOTA_BASE)
    mascota.update(pet)
    if mascota["comida"] == "premio":
        mascota["comida"] = "hueso" if animal == "perro" else "pescado"
    if mascota["texto"] == "grito":
        mascota["texto"] = "¡Guau!" if animal == "perro" else "¡Miau!"
    return dict(bb), mascota
