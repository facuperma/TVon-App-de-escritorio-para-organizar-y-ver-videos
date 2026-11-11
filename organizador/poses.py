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
    "celebrando": ("Celebrando", {"reposo": 0, "aiZ": -120, "adZ": 120, "ampS": 0.07, "ritmo": 7, "ondaI": 12, "ondaD": 12,
                                  "cabX": -8}),
    "cruzados": ("Brazos cruzados", {"reposo": 0, "aiX": -62, "aiZ": 58, "adX": -72, "adZ": -58, "cabZ": 4}),
    "cintura": ("Manos en la cintura", {"reposo": 0, "aiZ": -34, "aiX": 12, "adZ": 34, "adX": 12}),
    "corriendo": ("Corriendo", {"reposo": 0, "ampBx": 48, "ampP": 42, "ampS": 0.04, "ritmo": 9, "rX": 8, "rY": -42}),
    "acostado": ("Acostado, haciéndose el lindo", {"reposo": 0, "rZ": 90, "pX": 0.36, "pY": 0.14, "esc": 0.58,
                                                   "aiZ": -168, "adZ": 8, "adX": -10, "liX": -12, "ldX": -34, "ldZ": 4,
                                                   "cabZ": -48, "cabY": 0}),
    "sentado": ("Sentado con las piernas cruzadas", {"reposo": 0.3, "pY": -0.31, "liX": -90, "ldX": -90, "liY": 58, "ldY": -58,
                                                    "aiX": -38, "aiZ": -12, "adX": -38, "adZ": 12}),
    "vertical": ("Haciendo la vertical", {"reposo": 0, "rZ": 180, "pY": 0.92, "aiZ": -128, "adZ": 128, "liZ": -6, "ldZ": 6,
                                          "esc": 0.74, "ampS": 0}),
    "saludando": ("Saludando", {"reposo": 0.5, "adZ": 150, "ondaD": 22, "ritmo": 7, "cabZ": -5}),
    "volando": ("Volando", {"reposo": 0, "rZ": -90, "pX": -0.36, "pY": 0.46, "esc": 0.58, "adZ": 178, "aiZ": 4, "liX": 8,
                            "ldX": 8, "cabZ": 55, "ampS": 0.025, "ritmo": 3}),
    "nadando": ("Nadando", {"reposo": 0, "rZ": -90, "pX": -0.36, "pY": 0.46, "esc": 0.58, "cabZ": 55, "giroB": 0.55, "ampPz": 16, "ritmo": 5}),
    "bailando": ("Bailando", {"reposo": 0, "aiZ": -125, "adZ": 70, "ondaI": 18, "ondaD": 18, "ampP": 18, "ampS": 0.05,
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


# Cómo se agranda y se centra la pose del lugar en una vista ancha y baja (en el editor es alta y angosta)
AJUSTE_LUGAR = {"nadando": {"esc": 0.95, "pX": -0.55, "pY": 0.5}, "buscador": {"esc": 1.0, "pX": 0.57, "pY": 0.24}}


def ajustes(nombre: str, lugar: str | None = None) -> dict:
    """Todos los ajustes de una pose (los que no define, en su valor de arranque). «normal» + lugar = la pose del lugar."""
    if nombre == "normal" and lugar in POSE_DEL_LUGAR:
        nombre = POSE_DEL_LUGAR[lugar]
    datos = dict(BASE)
    datos.update(POSES.get(nombre, POSES["normal"])[1])
    if lugar in AJUSTE_LUGAR and nombre == POSE_DEL_LUGAR.get(lugar):
        datos.update(AJUSTE_LUGAR[lugar])      # en esos lugares la vista es ancha: se lo agranda y se lo centra
    return datos


def etiquetas() -> dict[str, str]:
    return {k: v[0] for k, v in POSES.items()}
