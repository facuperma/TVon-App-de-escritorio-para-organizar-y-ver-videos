"""Temas de TorrentVision: el azul de siempre y once estilos retro de los reproductores de los 2000.

Cada tema es una paleta, una letra, una forma de botón y una animación para la banda de arriba.
Son estilos inspirados en esa época, con nombres y diseños propios (sin logos ni marcas de nadie).
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Tema:
    id: str
    nombre: str
    epoca: str            # de qué se inspira, en pocas palabras
    descripcion: str
    animacion: str        # la de la banda de arriba (banda_retro.py)
    fondo: str
    fondo_hondo: str
    panel: str
    panel_claro: str
    borde: str
    texto: str
    tenue: str
    acento: str
    acento_texto: str     # texto sobre el acento
    seleccion: str
    hover: str
    titulo: str           # títulos y textos destacados
    barra: str            # fondo de la barra de herramientas (puede ser un degradé)
    boton: str            # fondo de los botones (puede ser un degradé)
    boton_hover: str
    boton_borde: str
    boton_texto: str
    letra: str
    radio: int = 6
    borde_boton: str = "1px solid"   # «2px outset» para los botones en relieve de los 90
    lcd_fondo: str = "#000000"       # la pantallita de la banda (marquesina)
    lcd_texto: str = "#00ff66"
    lcd_letra: str = "Lucida Console"
    claro: bool = False   # tema claro (texto oscuro): para elegir colores de estado legibles
    # La forma de los botones: «recto», «pildora» (bordes del todo redondos), «ovalo» (esquinas elípticas)
    # o «circulo» (los del reproductor redondos, con Play como un orbe grande)
    forma: str = "recto"
    # Los menús desplegables: «clasico», «biselado» (en relieve, de 1998), «cristal» (vidrio con brillo),
    # «neon» (borde de luz) o «lcd» (pantallita verde)
    menu: str = "clasico"
    # Detalles propios de los botones de cada tema (hoja de estilo que se suma al final)
    boton_extra: str = ""
    # El estilo moderno: más aire, bordes redondeados, listas con filas bien separadas (ver _moderno)
    moderno: bool = False

    # Colores de estado de la lista (a medias / vista / vínculo), legibles sobre el fondo del tema
    @property
    def pendiente(self) -> str:
        """«A medias»: amarillo (o naranja/fucsia si el texto del tema ya es amarillo), legible sobre su fondo."""
        return color_estado(self, (48, 32, 320))

    @property
    def vista(self) -> str:
        """«Vista»: verde (o celeste/azul si el texto del tema ya es verde), legible sobre su fondo."""
        return color_estado(self, (140, 190, 215), evitar=self.pendiente)

    @property
    def vinculo(self) -> str:
        return color_estado(self, (215, 200, 260), evitar=self.vista)


def _luminancia(hexa: str) -> float:
    """Luminancia relativa (WCAG) de un color #rrggbb."""
    def canal(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _tono(hexa: str) -> tuple[float, float]:
    """(tono en grados, «viveza» 0-1): saturación por brillo, alta solo en colores vivos y claros (#39ff6a)."""
    import colorsys
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s * v


def _hls(tono: float, luz: float, sat: float) -> str:
    import colorsys
    r, g, b = colorsys.hls_to_rgb(tono / 360, luz, sat)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def color_estado(t: "Tema", tonos: tuple[float, ...], evitar: str | None = None) -> str:
    """El color de un estado de la lista (a medias, vista…) calculado para el fondo del tema: el primer tono
    que no se confunda con el texto normal (ni con el otro estado), con la luz justa para leerse bien
    (contraste 4.5:1 como mínimo) sobre la lista y sobre el fondo."""
    texto_tono, texto_sat = _tono(t.texto)
    evitar_tono = _tono(evitar)[0] if evitar else None

    def lejos(a: float, b: float) -> bool:
        d = abs(a - b) % 360
        return min(d, 360 - d) >= 40

    elegido = next((h for h in tonos if (texto_sat < 0.4 or lejos(h, texto_tono))
                    and (evitar_tono is None or lejos(h, evitar_tono))), tonos[-1])
    fondos = (t.panel, t.fondo)
    oscuro = _luminancia(t.panel) < 0.2
    # Desde el color más vivo, se aclara (fondo oscuro) u oscurece (fondo claro) hasta que se lea
    pasos = [0.62 + i * 0.03 for i in range(12)] if oscuro else [0.42 - i * 0.03 for i in range(12)]
    for luz in pasos:
        c = _hls(elegido, max(0.05, min(0.95, luz)), 0.9)
        if all(contraste(c, f) >= 4.5 for f in fondos):
            return c
    return _hls(elegido, 0.9 if oscuro else 0.15, 0.9)


def _brillo(arriba: str, abajo: str, corte: float = 0.5, medio: str | None = None) -> str:
    """Degradé vertical con «brillo» (la mitad de arriba más clara), el de los botones de gel."""
    medio = medio or arriba
    return (f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {arriba}, stop:{corte - 0.01} {medio}, "
            f"stop:{corte} {abajo}, stop:1 {abajo})")


def _degrade(*colores: str, horizontal: bool = False) -> str:
    x2, y2 = (1, 0) if horizontal else (0, 1)
    paradas = ", ".join(f"stop:{i / (len(colores) - 1):.2f} {c}" for i, c in enumerate(colores))
    return f"qlineargradient(x1:0, y1:0, x2:{x2}, y2:{y2}, {paradas})"


TEMAS: list[Tema] = [
    Tema("moderno", "Moderno", "TorrentVision 2026", "Negro bien negro, grises bien grises, mucho aire entre las cosas y "
         "una letra moderna (Inter): el estilo de ahora.", "ninguna",
         fondo="#0b0b0e", fondo_hondo="#000000", panel="#17171c", panel_claro="#202027", borde="#30303a",
         texto="#f2f2f5", tenue="#a0a0ab", acento="#4c8dff", acento_texto="#ffffff", seleccion="#25508f",
         hover="#24242c", titulo="#ffffff", barra="#1a1a21", boton="#34343f", boton_hover="#41414e",
         boton_borde="#474754", boton_texto="#f2f2f5", letra="Inter", radio=8, moderno=True,
         lcd_fondo="#000000", lcd_texto="#8fb8ff", lcd_letra="Inter"),

    Tema("marino", "Azul noche", "TorrentVision", "El de siempre: azul marino, prolijo y tranquilo.", "ninguna",
         fondo="#0f1729", fondo_hondo="#0a1020", panel="#131d33", panel_claro="#1f2d4d", borde="#24334f",
         texto="#dbe2ef", tenue="#7a8599", acento="#3d7bfd", acento_texto="#ffffff", seleccion="#2a4a8c",
         hover="#1c2a47", titulo="#ffffff", barra="#131d33", boton="#1f2d4d", boton_hover="#2a3d66",
         boton_borde="#2c3f66", boton_texto="#dbe2ef", letra="Segoe UI",
         lcd_fondo="#0a1020", lcd_texto="#9fc2ff", lcd_letra="Segoe UI"),

    Tema("galaxia", "Galaxia P2P", "Programas para compartir de 2004", "Azul profundo con estrellas que pasan "
         "por la banda, botones de cristal celeste y la marquesina con lo que estás viendo.", "estrellas",
         fondo="#070d1f", fondo_hondo="#030714", panel="#0d1833", panel_claro="#15284f", borde="#1f3b70",
         texto="#d6e6ff", tenue="#6f88b8", acento="#2fb4ff", acento_texto="#001022", seleccion="#1d5fb0",
         hover="#13305e", titulo="#8fd8ff",
         barra=_degrade("#1b3a78", "#0b1838", "#050b1e"),
         boton=_brillo("#3d74c9", "#173a7a", 0.5, "#2a5aa8"), boton_hover=_brillo("#5a95f0", "#1f4c9c", 0.5, "#3a72cc"),
         boton_borde="#4b86e0", boton_texto="#ffffff", letra="Verdana", radio=9,
         lcd_fondo="#020611", lcd_texto="#4fd2ff", lcd_letra="Verdana"),

    Tema("llama", "Lámpara de llama", "Reproductores con skins de 1999", "Gris metálico con relieve, pantallita "
         "LCD verde con el título corriendo y un ecualizador que salta mientras se reproduce.", "ecualizador",
         fondo="#23232b", fondo_hondo="#14141a", panel="#2d2d38", panel_claro="#3c3c4a", borde="#55556a",
         texto="#d8d8e0", tenue="#8a8aa0", acento="#3cd63c", acento_texto="#000000", seleccion="#24456e",
         hover="#373746", titulo="#00e000",
         barra=_degrade("#4a4a5c", "#2a2a36", "#1c1c24"),
         boton=_degrade("#5a5a6e", "#383846"), boton_hover=_degrade("#6c6c84", "#444456"),
         boton_borde="#76768e", boton_texto="#e6e6ee", letra="Tahoma", radio=2, borde_boton="2px outset",
         lcd_fondo="#000000", lcd_texto="#00e000", lcd_letra="Lucida Console"),

    Tema("luna", "Luna", "El escritorio de 2001", "Ventanas beige, barra azul brillante y botones redondeados "
         "que se ponen naranjas al pasar el mouse. En la banda, el cielo con nubes y la loma verde.", "nubes",
         fondo="#ece9d8", fondo_hondo="#ffffff", panel="#f6f4ea", panel_claro="#ffffff", borde="#7f9db9",
         texto="#000000", tenue="#5a5a5a", acento="#316ac5", acento_texto="#ffffff", seleccion="#316ac5",
         hover="#c1d2ee", titulo="#0a246a",
         barra=_degrade("#3d95ff", "#0a5fd8", "#0050c8", "#0a5fd8"),
         boton=_degrade("#ffffff", "#ecebe6", "#d6d0c5"), boton_hover=_degrade("#fff6e0", "#fde5b0", "#f8b048"),
         boton_borde="#003c74", boton_texto="#000000", letra="Tahoma", radio=4,
         lcd_fondo="#0a5fd8", lcd_texto="#ffffff", lcd_letra="Tahoma", claro=True),

    Tema("luna_noche", "Luna de noche", "El escritorio de 2001, de noche", "La misma esencia de las ventanas "
         "de 2001 en modo oscuro: barra azul profundo, botones redondeados que se encienden en naranja y el "
         "botón verde de siempre. En la banda, el campo de noche: la loma bajo la luna, estrellas y luciérnagas.",
         "noche",
         fondo="#1b2130", fondo_hondo="#11151f", panel="#232b3c", panel_claro="#2d374c", borde="#3c5686",
         texto="#e4e9f3", tenue="#9aa6bd", acento="#3d82ea", acento_texto="#ffffff", seleccion="#2a5cb8",
         hover="#2b3b5e", titulo="#a9caff",
         barra=_degrade("#2c66cc", "#123f98", "#0a327e", "#123f98"),
         boton=_degrade("#3e4a60", "#2e3749", "#232a39"), boton_hover=_degrade("#4a4a4c", "#4a3d2c", "#5a4320"),
         boton_borde="#5f82bd", boton_texto="#eef2fa", letra="Tahoma", radio=4,
         lcd_fondo="#0a2a66", lcd_texto="#ffffff", lcd_letra="Tahoma"),

    Tema("gel", "Gel azul", "Las computadoras transparentes de 2000", "Gris perla con botones de gel azul "
         "que brillan como caramelo. En la banda, gotas de gel que respiran.", "gotas",
         fondo="#e9eaee", fondo_hondo="#f7f7f9", panel="#f2f2f5", panel_claro="#ffffff", borde="#a9aebb",
         texto="#111111", tenue="#5f6470", acento="#1f7ae0", acento_texto="#ffffff", seleccion="#3d8ef0",
         hover="#d7e6fa", titulo="#0b3f8c",
         barra=_degrade("#fbfbfc", "#dcdee4", "#c9ccd4"),
         boton=_brillo("#cfe6ff", "#2b84ee", 0.5, "#8cc2ff"), boton_hover=_brillo("#e2f0ff", "#4a9bff", 0.5, "#a8d2ff"),
         boton_borde="#1d5fb8", boton_texto="#06224d", letra="Lucida Grande", radio=12,
         lcd_fondo="#dfe9f5", lcd_texto="#0b3f8c", lcd_letra="Lucida Grande", claro=True),

    Tema("cristal", "Cristal negro", "El reproductor de vidrio de 2006", "Negro brillante como un piano, "
         "reflejos de vidrio y luz azul. En la banda, una aurora que ondula.", "aurora",
         fondo="#0b0b0d", fondo_hondo="#000000", panel="#141418", panel_claro="#202027", borde="#2e2e38",
         texto="#e8ecf2", tenue="#8a919e", acento="#3fa9f5", acento_texto="#00121f", seleccion="#1b4f7a",
         hover="#1c1c24", titulo="#bfe3ff",
         barra=_brillo("#3a3a44", "#08080a", 0.5, "#1c1c22"),
         boton=_brillo("#4a4a56", "#0e0e12", 0.48, "#26262e"), boton_hover=_brillo("#3f84c4", "#0b2a46", 0.48, "#1f5689"),
         boton_borde="#50505e", boton_texto="#f0f4fa", letra="Segoe UI", radio=10,
         lcd_fondo="#000000", lcd_texto="#7cc8ff", lcd_letra="Segoe UI"),

    Tema("plata", "Plata cepillada", "La jukebox de metal de 2003", "Aluminio cepillado con una pantallita "
         "verde agua en el medio, como la de los reproductores de música de esa época.", "brillo",
         fondo="#d9d9d9", fondo_hondo="#f2f2f2", panel="#e4e4e4", panel_claro="#f7f7f7", borde="#8c8c8c",
         texto="#1a1a1a", tenue="#5c5c5c", acento="#5d7fa8", acento_texto="#ffffff", seleccion="#7a9cc8",
         hover="#cfd6df", titulo="#202020",
         barra=_degrade("#f0f0f0", "#c8c8c8", "#b2b2b2", "#c8c8c8"),
         boton=_degrade("#fafafa", "#d6d6d6", "#bdbdbd"), boton_hover=_degrade("#ffffff", "#e4e4e4", "#cccccc"),
         boton_borde="#7a7a7a", boton_texto="#111111", letra="Lucida Sans Unicode", radio=7,
         lcd_fondo="#d4e2c4", lcd_texto="#1d2b14", lcd_letra="Lucida Sans Unicode", claro=True),

    Tema("mula", "Mula verde", "Las redes de intercambio de 2003", "Blanco y verde, amigable, con flechitas "
         "que suben y bajan en la banda como en las transferencias de antes.", "flechas",
         fondo="#f3f8f1", fondo_hondo="#ffffff", panel="#ffffff", panel_claro="#ffffff", borde="#9cc59a",
         texto="#13301a", tenue="#557a5c", acento="#2e9e4f", acento_texto="#ffffff", seleccion="#56b86f",
         hover="#dcefdc", titulo="#1f6b35",
         barra=_degrade("#e9f6e6", "#c4e3bf", "#a8d4a1"),
         boton=_brillo("#ffffff", "#cfe9ca", 0.5, "#eef8ec"), boton_hover=_brillo("#ffffff", "#a9dca1", 0.5, "#e0f3dc"),
         boton_borde="#5aa65f", boton_texto="#133a1c", letra="Verdana", radio=5,
         lcd_fondo="#103b1d", lcd_texto="#a8ff9e", lcd_letra="Verdana", claro=True),

    Tema("fosforo", "Fósforo", "Los monitores de tubo", "Negro absoluto y letras verde fósforo con brillo, "
         "líneas de barrido y una lluvia de letras en la banda.", "lluvia",
         fondo="#030a04", fondo_hondo="#000000", panel="#06110a", panel_claro="#0b1d10", borde="#145a26",
         texto="#39ff6a", tenue="#1f9e45", acento="#39ff6a", acento_texto="#001a06", seleccion="#0f4d20",
         hover="#0a2412", titulo="#9cffb5",
         barra="#020703", boton="#04140a", boton_hover="#0b2e16", boton_borde="#1fa748", boton_texto="#5cff86",
         letra="Lucida Console", radio=0,
         lcd_fondo="#000000", lcd_texto="#39ff6a", lcd_letra="Lucida Console"),

    Tema("neon", "Neón Y2K", "El cambio de milenio", "Violeta, fucsia y cian con cromo. En la banda, la "
         "grilla infinita hacia un sol de atardecer.", "grilla",
         fondo="#14062b", fondo_hondo="#0a0218", panel="#1e0a3d", panel_claro="#2c1257", borde="#5b2a9e",
         texto="#f3e6ff", tenue="#a98bd6", acento="#ff2fd6", acento_texto="#1a0024", seleccion="#7a1fa8",
         hover="#2e1460", titulo="#22e4ff",
         barra=_degrade("#3a0d6e", "#1a0640", "#ff2fd6", horizontal=True),
         boton=_brillo("#f4f4ff", "#7d7da8", 0.5, "#c9c9e6"), boton_hover=_brillo("#ffffff", "#ff7ae6", 0.5, "#ffc2f2"),
         boton_borde="#22e4ff", boton_texto="#1a0033", letra="Trebuchet MS", radio=14,
         lcd_fondo="#0a0218", lcd_texto="#22e4ff", lcd_letra="Trebuchet MS"),

    Tema("aero", "Burbujas Aero", "El optimismo de 2007", "Cielo celeste, verde agua y vidrio con brillo; "
         "burbujas que suben por la banda.", "burbujas",
         fondo="#e6f4fb", fondo_hondo="#ffffff", panel="#f4fbff", panel_claro="#ffffff", borde="#8fc7e3",
         texto="#0b3247", tenue="#4f7a8f", acento="#1ba3d6", acento_texto="#ffffff", seleccion="#5cc3e8",
         hover="#d2eef9", titulo="#0a6c8f",
         barra=_degrade("#bfe8fb", "#7fcff2", "#55c2a8"),
         boton=_brillo("#ffffff", "#9fdcf2", 0.5, "#e4f7fd"), boton_hover=_brillo("#ffffff", "#7fe0c4", 0.5, "#dcf9ef"),
         boton_borde="#3aa7cf", boton_texto="#063246", letra="Segoe UI", radio=16,
         lcd_fondo="#0d6f93", lcd_texto="#e9fbff", lcd_letra="Segoe UI", claro=True),

    Tema("noventa", "Escritorio 98", "Las ventanas grises de 1998", "Gris clásico con botones en relieve, "
         "barra azul marino y el protector de pantalla de estrellas en la banda.", "warp",
         fondo="#c0c0c0", fondo_hondo="#ffffff", panel="#c0c0c0", panel_claro="#ffffff", borde="#808080",
         texto="#000000", tenue="#404040", acento="#000080", acento_texto="#ffffff", seleccion="#000080",
         hover="#d4d0c8", titulo="#000080",
         barra=_degrade("#000080", "#1084d0", horizontal=True),
         boton="#c0c0c0", boton_hover="#d4d0c8", boton_borde="#dfdfdf", boton_texto="#000000",
         letra="MS Sans Serif", radio=0, borde_boton="2px outset",
         lcd_fondo="#000000", lcd_texto="#ffffff", lcd_letra="MS Sans Serif", claro=True),
]

# Forma y menús de los temas de arriba
_FORMAS = {
    "galaxia": ("pildora", "cristal"), "llama": ("recto", "biselado"), "luna": ("pildora", "clasico"),
    "luna_noche": ("pildora", "clasico"),
    "gel": ("circulo", "cristal"), "cristal": ("circulo", "cristal"), "plata": ("ovalo", "clasico"),
    "mula": ("pildora", "clasico"), "fosforo": ("recto", "lcd"), "neon": ("ovalo", "neon"),
    "aero": ("circulo", "cristal"), "noventa": ("recto", "biselado"),
}
TEMAS = [replace(t, forma=_FORMAS[t.id][0], menu=_FORMAS[t.id][1]) if t.id in _FORMAS else t for t in TEMAS]

# Botones con personalidad para los temas de la primera tanda
_EXTRAS = {
    "marino": """
QPushButton { border-bottom: 2px solid #0a1020; }
QPushButton:hover { border-color: #3d7bfd; }
QPushButton:pressed { border-bottom: 1px solid #3d7bfd; padding-top: 7px; }
""",
    "galaxia": """
QPushButton { border: 1px solid #6fb8ff; border-bottom: 2px solid #0b1838; }
QPushButton:hover { border: 1px solid #c8ecff; color: #ffffff; }
QWidget#controles QPushButton { border: 1px solid #2fb4ff; }
QToolBar QToolButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3d74c9, stop:1 #173a7a);
    border: 1px solid #6fb8ff; }
""",
    "llama": """
QPushButton { border: 2px outset #8a8aa2; }
QPushButton:pressed { border: 2px inset #8a8aa2; background: #23232b; color: #00e000; }
QWidget#controles QPushButton, QWidget#controles QToolButton { color: #00e000; font-family: "Lucida Console";
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3c3c4a, stop:1 #1c1c24); }
""",
    "luna": """
QPushButton { border: 1px solid #003c74; border-radius: 4px; }
QPushButton:hover { border: 2px solid #f8b048; padding: 5px 11px; }
QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e5e3dc, stop:1 #f6f4ec); }
QPushButton#primario { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8fd16a, stop:0.5 #3c9d27,
    stop:1 #2f8a1c); color: #ffffff; border: 1px solid #1f6b11; font-weight: 700; }
""",
    "luna_noche": """
QPushButton { border: 1px solid #5f82bd; border-radius: 4px; }
QPushButton:hover { border: 2px solid #f0a040; padding: 5px 11px; color: #ffffff; }
QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d2330, stop:1 #2e3749); }
QPushButton#primario { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6fb84f, stop:0.5 #2f8a1c,
    stop:1 #1f6b11); color: #ffffff; border: 1px solid #144d0a; font-weight: 700; }
""",
    "gel": """
QPushButton { border: 1px solid #1d5fb8; color: #06224d; }
QPushButton:hover { border: 1px solid #0b3f8c; }
QPushButton#primario { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffd9a8, stop:0.49 #ffb24a,
    stop:0.5 #ff8a00, stop:1 #ffb84d); border: 1px solid #b85f00; color: #3a1a00; }
""",
    "cristal": """
QPushButton { border: 1px solid #50505e; border-top: 1px solid #8a8a9a; }
QPushButton:hover { border: 1px solid #3fa9f5; color: #ffffff; }
QWidget#controles QPushButton:hover { border: 2px solid #7cc8ff; }
""",
    "plata": """
QPushButton { border: 1px solid #7a7a7a; border-bottom: 2px solid #5a5a5a; border-top: 1px solid #ffffff; }
QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #bdbdbd, stop:1 #fafafa);
    border-top: 2px solid #5a5a5a; border-bottom: 1px solid #ffffff; }
QWidget#controles QPushButton { background: qradialgradient(cx:0.5, cy:0.3, radius:0.8, stop:0 #ffffff, stop:1 #c4c4c4); }
""",
    "mula": """
QPushButton { border: 2px solid #5aa65f; color: #133a1c; }
QPushButton:hover { background: #dcefdc; border-color: #2e9e4f; }
QPushButton#primario { background: #2e9e4f; color: #ffffff; border-color: #1f6b35; }
""",
    "fosforo": """
QPushButton, QToolBar QToolButton { border: 1px dashed #39ff6a; background: transparent; color: #5cff86; }
QPushButton { font-size: 9pt; padding: 5px 6px; }
QPushButton:hover, QToolBar QToolButton:hover { background: #39ff6a; color: #000000; border-style: solid; }
QPushButton:pressed { background: #9cffb5; color: #000000; }
""",
    "neon": """
QPushButton { border: 2px solid #22e4ff; }
QPushButton:hover { border: 2px solid #ff2fd6; color: #2a0040; }
QPushButton#primario { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff2fd6, stop:1 #22e4ff);
    color: #ffffff; border: 2px solid #ffffff; }
""",
    "aero": """
QPushButton { border: 1px solid #3aa7cf; border-top: 1px solid #ffffff; }
QPushButton:hover { border: 1px solid #1ba3d6; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff,
    stop:0.49 #c9f2e6, stop:0.5 #7fe0c4, stop:1 #b8f0e0); }
""",
    "noventa": """
QPushButton { border-top: 2px solid #ffffff; border-left: 2px solid #ffffff; border-right: 2px solid #404040;
    border-bottom: 2px solid #404040; }
QPushButton:pressed { border-top: 2px solid #404040; border-left: 2px solid #404040; border-right: 2px solid #ffffff;
    border-bottom: 2px solid #ffffff; padding-top: 7px; padding-left: 13px; }
QPushButton:focus { outline: 1px dotted #000000; }
""",
}
TEMAS = [replace(t, boton_extra=_EXTRAS[t.id]) if t.id in _EXTRAS else t for t in TEMAS]

# Diez más: cassette, vinilo, arcade, osciloscopio, océano, fuego, caramelo, teletexto, radio y videoclub
TEMAS += [
    Tema("casete", "Casete 85", "Los walkman y los casetes de los 80", "Beige, naranja y marrón de cinta. "
         "En la banda, un casete con sus dos carretes girando mientras suena.", "casete",
         fondo="#efe3c8", fondo_hondo="#fbf4e4", panel="#f6ead2", panel_claro="#fffaf0", borde="#b98c55",
         texto="#3b2414", tenue="#7a5a3c", acento="#e0661f", acento_texto="#ffffff", seleccion="#c9762f",
         hover="#f1d9b5", titulo="#8a3a10",
         barra=_degrade("#3b2414", "#6b3d1e", "#e0661f", horizontal=True),
         boton=_degrade("#fff7e6", "#e8cfa6"), boton_hover=_degrade("#fffaf0", "#f3c58a"),
         boton_borde="#9b6a3a", boton_texto="#3b2414", letra="Arial Rounded MT Bold", radio=6,
         lcd_fondo="#2a1a10", lcd_texto="#ffb347", lcd_letra="Arial Rounded MT Bold", claro=True,
         forma="ovalo", menu="clasico"),

    Tema("vinilo", "Disquería", "Los tocadiscos y la madera", "Madera oscura, dorado y negro de vinilo. "
         "En la banda gira un disco con sus surcos y la púa encima.", "vinilo",
         fondo="#1c120c", fondo_hondo="#0f0905", panel="#2a1b12", panel_claro="#3a2618", borde="#6b4a2a",
         texto="#f1e2c8", tenue="#b39470", acento="#d4a24c", acento_texto="#1c120c", seleccion="#7a5222",
         hover="#33221a", titulo="#f3c771",
         barra=_degrade("#5a3820", "#3a2414", "#24160c"),
         boton=_brillo("#4a3220", "#24160c", 0.5, "#3a2618"), boton_hover=_brillo("#6a4a2a", "#3a2414", 0.5, "#523620"),
         boton_borde="#d4a24c", boton_texto="#f3e3c2", letra="Georgia", radio=16,
         lcd_fondo="#0f0905", lcd_texto="#f3c771", lcd_letra="Georgia", forma="circulo", menu="cristal"),

    Tema("arcade", "Arcade 8 bits", "Los fichines de los 80", "Negro de sala de juegos, colores chillones y "
         "letra de pixel. En la banda marchan los marcianitos.", "pixeles",
         fondo="#0a0a14", fondo_hondo="#000000", panel="#11112a", panel_claro="#1c1c40", borde="#ff2e88",
         texto="#f2f2ff", tenue="#8f8fc8", acento="#ffe14d", acento_texto="#14002a", seleccion="#ff2e88",
         hover="#22224a", titulo="#3cf2ff",
         barra="#000000", boton="#14143a", boton_hover="#2a2a6a", boton_borde="#3cf2ff", boton_texto="#ffe14d",
         letra="Consolas", radio=0, borde_boton="2px solid",
         lcd_fondo="#000000", lcd_texto="#ffe14d", lcd_letra="Consolas", forma="recto", menu="lcd"),

    Tema("osciloscopio", "Osciloscopio", "Los aparatos de laboratorio", "Gris verdoso de instrumento, una "
         "cuadrícula y la onda que se dibuja en la pantalla, más alta cuando hay sonido.", "osciloscopio",
         fondo="#1d2420", fondo_hondo="#111613", panel="#252e29", panel_claro="#303b35", borde="#4d5d53",
         texto="#d6e6dc", tenue="#8fa79a", acento="#7cff9a", acento_texto="#06210f", seleccion="#2f5a3d",
         hover="#2c3631", titulo="#a6ffbb",
         barra=_degrade("#3a4640", "#252e29", "#1a201c"),
         boton=_degrade("#46534c", "#2e3833"), boton_hover=_degrade("#56665d", "#36423b"),
         boton_borde="#7a8c82", boton_texto="#e2f0e7", letra="Tahoma", radio=3, borde_boton="2px outset",
         lcd_fondo="#06140b", lcd_texto="#7cff9a", lcd_letra="Lucida Console", forma="recto", menu="biselado"),

    Tema("oceano", "Océano", "Los protectores de pantalla de peces", "Azul profundo de mar, turquesa y "
         "espuma. En la banda, olas que van y vienen y burbujas que suben.", "olas",
         fondo="#06243a", fondo_hondo="#031624", panel="#0a3150", panel_claro="#114268", borde="#1f6f96",
         texto="#d8f3ff", tenue="#7fb3cc", acento="#2fe0d0", acento_texto="#022a26", seleccion="#147a9c",
         hover="#0e3c5e", titulo="#9cf1ff",
         barra=_degrade("#0e5a86", "#083b5c", "#04243a"),
         boton=_brillo("#3aa3d0", "#0d4f75", 0.5, "#2786b2"), boton_hover=_brillo("#5fd6e8", "#11708f", 0.5, "#3cb4cc"),
         boton_borde="#5fd6e8", boton_texto="#ffffff", letra="Trebuchet MS", radio=18,
         lcd_fondo="#031624", lcd_texto="#9cf1ff", lcd_letra="Trebuchet MS", forma="pildora", menu="cristal"),

    Tema("fuego", "Fuego", "Las visualizaciones de música de 2000", "Negro con brasas: rojo, naranja y "
         "amarillo. En la banda, llamas que crecen con lo que suena.", "fuego",
         fondo="#140604", fondo_hondo="#080201", panel="#200a06", panel_claro="#33100a", borde="#7a2310",
         texto="#ffe6d6", tenue="#d08a6a", acento="#ff6a1a", acento_texto="#1a0500", seleccion="#a8320f",
         hover="#2c0e08", titulo="#ffc04d",
         barra=_degrade("#3a0a04", "#7a1a08", "#ff6a1a", horizontal=True),
         boton=_brillo("#ff9a4d", "#a8320f", 0.5, "#e0641f"), boton_hover=_brillo("#ffc04d", "#d04a12", 0.5, "#ff8a2a"),
         boton_borde="#ffc04d", boton_texto="#1a0500", letra="Impact", radio=8,
         lcd_fondo="#080201", lcd_texto="#ffc04d", lcd_letra="Impact", forma="ovalo", menu="neon"),

    Tema("caramelo", "Caramelo", "Las computadoras de colores de 1999", "Rosa chicle, frutilla y blanco "
         "translúcido, todo redondo como un caramelo. En la banda flotan corazones.", "corazones",
         fondo="#ffe8f3", fondo_hondo="#fff6fb", panel="#fff0f7", panel_claro="#ffffff", borde="#f29ac4",
         texto="#4a0f2c", tenue="#a3567b", acento="#ff3d8b", acento_texto="#ffffff", seleccion="#ff7ab0",
         hover="#ffd6ea", titulo="#c2185b",
         barra=_degrade("#ffd1e6", "#ff9ec9", "#ff6fa8"),
         boton=_brillo("#ffffff", "#ff9ec9", 0.5, "#ffe0ef"), boton_hover=_brillo("#ffffff", "#ff6fa8", 0.5, "#ffd1e6"),
         boton_borde="#ff3d8b", boton_texto="#4a0f2c", letra="Comic Sans MS", radio=20,
         lcd_fondo="#ff3d8b", lcd_texto="#ffffff", lcd_letra="Comic Sans MS", claro=True,
         forma="circulo", menu="cristal"),

    Tema("teletexto", "Teletexto", "Las páginas de texto de la tele", "Negro y los siete colores puros de la "
         "tele, en bloques. En la banda pasan las páginas con su número.", "teletexto",
         fondo="#000000", fondo_hondo="#000000", panel="#000000", panel_claro="#0a0a0a", borde="#0000ff",
         texto="#ffffff", tenue="#00ffff", acento="#ffff00", acento_texto="#000000", seleccion="#0000ff",
         hover="#1a1a1a", titulo="#ffff00",
         barra="#0000ff", boton="#000000", boton_hover="#ff00ff", boton_borde="#00ff00", boton_texto="#00ffff",
         letra="Courier New", radio=0, borde_boton="2px solid",
         lcd_fondo="#000000", lcd_texto="#ffff00", lcd_letra="Courier New", forma="recto", menu="lcd"),

    Tema("radio", "Radio a válvulas", "Las radios de madera con dial", "Nogal, bronce y un dial ámbar "
         "iluminado. En la banda, la aguja recorre las emisoras.", "dial",
         fondo="#2b1a10", fondo_hondo="#1a0f08", panel="#3a2416", panel_claro="#4a301d", borde="#8a6038",
         texto="#f5e3c4", tenue="#c4a07a", acento="#ffb84d", acento_texto="#2b1a10", seleccion="#8a5a28",
         hover="#45301f", titulo="#ffcf7a",
         barra=_degrade("#6a4224", "#4a2c16", "#2b1a10"),
         boton=_brillo("#c8a06a", "#7a5430", 0.5, "#a88050"), boton_hover=_brillo("#e8c08a", "#9a6a3a", 0.5, "#c89a60"),
         boton_borde="#ffcf7a", boton_texto="#2b1a10", letra="Palatino Linotype", radio=14,
         lcd_fondo="#3a2008", lcd_texto="#ffcf7a", lcd_letra="Palatino Linotype", forma="ovalo", menu="biselado"),

    Tema("vhs", "Videoclub", "Los casetes de video y el «PLAY»", "Azul de pantalla de video, letras blancas "
         "con sombra y franjas de tracking que pasan por la banda.", "vhs",
         fondo="#0b1a8a", fondo_hondo="#06106a", panel="#0f22a0", panel_claro="#1630b8", borde="#5a74ff",
         texto="#ffffff", tenue="#b6c2ff", acento="#ffffff", acento_texto="#0b1a8a", seleccion="#3f5cff",
         hover="#1a32c0", titulo="#ffffff",
         barra=_degrade("#06106a", "#0b1a8a"), boton="#0b1a8a", boton_hover="#2a46e0", boton_borde="#ffffff",
         boton_texto="#ffffff", letra="Lucida Console", radio=2, borde_boton="2px solid",
         lcd_fondo="#06106a", lcd_texto="#ffffff", lcd_letra="Lucida Console", forma="recto", menu="lcd"),
]

POR_ID = {t.id: t for t in TEMAS}


def tema(id_: str | None) -> Tema:
    return POR_ID.get(id_ or "", TEMAS[0])


def _formas(t: Tema) -> str:
    """La forma de los botones y campos según el tema."""
    if t.forma == "pildora":
        return f"""
QPushButton, QToolBar QToolButton {{ border-radius: 15px; padding: 6px 9px; }}
QLineEdit {{ border-radius: 14px; padding: 5px 14px; }}
QWidget#controles QPushButton, QWidget#controles QToolButton {{ border-radius: 13px; padding: 4px 10px; }}
"""
    if t.forma == "ovalo":
        # Esquinas elípticas (más anchas que altas): botones con forma de pastilla aplastada
        return f"""
QPushButton, QToolBar QToolButton {{
    border-top-left-radius: 18px 10px; border-top-right-radius: 18px 10px;
    border-bottom-left-radius: 18px 10px; border-bottom-right-radius: 18px 10px; padding: 6px 9px;
}}
QLineEdit, QGroupBox, QListWidget, QTreeWidget {{
    border-top-left-radius: 22px 12px; border-top-right-radius: 22px 12px;
    border-bottom-left-radius: 22px 12px; border-bottom-right-radius: 22px 12px;
}}
QLineEdit {{ padding: 5px 16px; }}
"""
    if t.forma == "circulo":
        # Los botones del reproductor, redondos; Play, un orbe grande con brillo
        return f"""
QPushButton, QToolBar QToolButton {{ border-radius: 15px; padding: 6px 9px; }}
QLineEdit {{ border-radius: 14px; padding: 5px 14px; }}
QWidget#controles QPushButton, QWidget#controles QToolButton {{
    min-width: 28px; min-height: 28px; border-radius: 15px; padding: 1px 6px;
}}
QWidget#controles QPushButton#play {{
    min-width: 40px; min-height: 40px; max-width: 40px; max-height: 40px; border-radius: 21px; padding: 0;
    border: 2px solid {t.acento};
    background: qradialgradient(cx:0.5, cy:0.35, radius:0.75, fx:0.5, fy:0.2, stop:0 #ffffff, stop:0.35 {t.acento},
                                stop:1 {t.boton_borde});
}}
QWidget#controles QPushButton#play:hover {{ border-color: #ffffff; }}
"""
    return ""


def _menus(t: Tema) -> str:
    """Los menús desplegables (barra de menú, clic derecho, listas desplegables) con estilo de época."""
    if t.menu == "biselado":
        return f"""
QMenu {{ background: {t.panel}; border: 2px outset {t.panel_claro}; padding: 2px; border-radius: 0; }}
QMenu::item {{ padding: 4px 22px 4px 20px; }}
QMenu::item:selected {{ background: {t.seleccion}; color: #ffffff; }}
QMenu::separator {{ height: 2px; background: {t.borde}; border-bottom: 1px solid {t.panel_claro}; margin: 3px 4px; }}
QMenuBar::item:selected {{ background: {t.seleccion}; color: #ffffff; border-radius: 0; }}
QComboBox QAbstractItemView {{ border: 2px outset {t.panel_claro}; selection-background-color: {t.seleccion}; }}
"""
    if t.menu == "cristal":
        return f"""
QMenu {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t.panel_claro}, stop:1 {t.panel});
    border: 1px solid {t.boton_borde}; border-radius: 10px; padding: 6px;
}}
QMenu::item {{ padding: 6px 24px 6px 18px; border-radius: 8px; }}
QMenu::item:selected {{
    color: {t.acento_texto};
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.45 {t.acento}, stop:0.5 {t.seleccion},
                                stop:1 {t.acento});
}}
QMenu::separator {{ height: 1px; background: {t.boton_borde}; margin: 5px 12px; }}
QMenuBar::item:selected {{ border-radius: 10px; }}
QComboBox QAbstractItemView {{ border-radius: 8px; selection-background-color: {t.acento}; }}
"""
    if t.menu == "neon":
        return f"""
QMenu {{ background: {t.fondo_hondo}; border: 2px solid {t.acento}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 6px 24px 6px 18px; border-radius: 10px; color: {t.texto}; }}
QMenu::item:selected {{
    color: #ffffff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {t.acento}, stop:1 {t.titulo});
}}
QMenu::separator {{ height: 1px; background: {t.titulo}; margin: 5px 12px; }}
QComboBox QAbstractItemView {{ border: 2px solid {t.acento}; selection-background-color: {t.acento}; }}
"""
    if t.menu == "lcd":
        return f"""
QMenu {{ background: #000000; border: 2px solid {t.lcd_texto}; padding: 3px; border-radius: 0; font-family: "{t.lcd_letra}"; }}
QMenu::item {{ color: {t.lcd_texto}; padding: 4px 22px 4px 16px; }}
QMenu::item:selected {{ background: {t.lcd_texto}; color: #000000; }}
QMenu::separator {{ height: 1px; background: {t.lcd_texto}; margin: 3px 6px; }}
QComboBox QAbstractItemView {{ background: #000000; color: {t.lcd_texto}; selection-background-color: {t.lcd_texto};
    selection-color: #000000; }}
"""
    return ""


def _mix(a: str, b: str, f: float) -> str:
    """Un color entre a y b (f = 0 es a, 1 es b)."""
    ca = [int(a[k:k + 2], 16) for k in (1, 3, 5)]
    cb = [int(b[k:k + 2], 16) for k in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * f):02x}" for x, y in zip(ca, cb))


def _moderno(t: Tema) -> str:
    """La capa del estilo moderno: se suma al final y pisa lo de arriba. Cada zona con su gris (la barra de opciones, la
    de botones, las listas, las tarjetas), botones con forma de botón (degradé y sombra abajo), categorías como tarjetas
    separadas y filas de la lista con una línea entre cada una. Todo sale de los colores del tema (así el menú de
    desarrollador los puede cambiar)."""
    alto = _mix(t.boton, "#ffffff", 0.07)
    bajo = _mix(t.boton, "#000000", 0.28)
    alto_h = _mix(t.boton_hover, "#ffffff", 0.08)
    bajo_h = _mix(t.boton_hover, "#000000", 0.22)
    sombra = _mix(t.fondo, "#000000", 0.7)
    sep = _mix(t.panel, "#ffffff", 0.07)
    alterna = _mix(t.panel, "#ffffff", 0.025)
    tarjeta_borde = _mix(t.panel_claro, "#ffffff", 0.06)
    manija = _mix(t.panel_claro, "#ffffff", 0.12)
    manija_h = _mix(t.panel_claro, "#ffffff", 0.25)
    boton = (f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {alto}, stop:1 {bajo}); color: {t.boton_texto}; "
             f"border: 1px solid {t.boton_borde}; border-bottom: 2px solid {sombra}; border-radius: 9px;")
    hover = (f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {alto_h}, stop:1 {bajo_h}); "
             f"border-color: {_mix(t.boton_borde, t.acento, 0.5)};")
    apretado = (f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {bajo}, stop:1 {alto}); "
                f"border-bottom: 1px solid {t.boton_borde};")
    acento_alto, acento_bajo = _mix(t.acento, "#ffffff", 0.12), _mix(t.acento, "#000000", 0.15)
    acento_sombra = _mix(t.acento, "#000000", 0.55)
    return f"""
QMenuBar {{ background: {t.fondo}; border-bottom: 1px solid {t.borde}; padding: 4px 8px; }}
QMenuBar::item {{ padding: 7px 13px; margin: 0 2px; border-radius: 8px; }}
QMenuBar::item:selected {{ background: {t.hover}; }}
QToolBar {{ background: {t.barra}; border: none; border-bottom: 1px solid {t.borde}; padding: 8px 12px; spacing: 8px; }}
QToolBar::separator {{ background: {t.borde}; width: 1px; margin: 4px 8px; }}
QToolBar QToolButton {{ {boton} padding: 7px 13px; }}
QToolBar QToolButton:hover {{ {hover} }}
QToolBar QToolButton:pressed {{ {apretado} }}
QToolButton {{ padding: 7px 12px; border-radius: 9px; }}
QToolButton:hover {{ background: {t.hover}; }}
QMenu {{ background: {t.panel_claro}; border: 1px solid {t.borde}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 8px 28px 8px 14px; border-radius: 7px; margin: 1px 2px; }}
QMenu::item:selected {{ background: {t.seleccion}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {t.borde}; margin: 6px 10px; }}
QToolTip {{ background: {t.panel_claro}; color: {t.texto}; border: 1px solid {t.borde}; border-radius: 6px; padding: 6px 9px; }}
QLabel#titulo {{ font-size: 12pt; font-weight: 600; color: {t.titulo}; padding: 2px 0 4px 2px; }}
QLabel#pista {{ color: {t.tenue}; }}
QListWidget, QTreeWidget {{
    background: {t.panel}; alternate-background-color: {alterna}; border: 1px solid {t.borde}; border-radius: 12px;
    padding: 6px; outline: none;
}}
QListWidget::item {{
    background: {t.panel_claro}; border: 1px solid {tarjeta_borde}; border-radius: 9px; margin: 3px 2px; padding: 9px 12px;
}}
QListWidget::item:hover {{ background: {t.hover}; border-color: {t.boton_borde}; }}
QListWidget::item:selected {{ background: {t.seleccion}; border-color: {t.acento}; color: #ffffff; }}
QTreeWidget::item {{ padding: 9px 10px; border: none; border-bottom: 1px solid {sep}; }}
QTreeWidget::item:hover {{ background: {t.hover}; }}
QTreeWidget::item:selected {{ background: {t.seleccion}; color: #ffffff; border-bottom: 1px solid {t.seleccion}; }}
QHeaderView::section {{
    background: {t.panel_claro}; color: {t.tenue}; font-weight: 600; font-size: 9pt; padding: 9px 10px; border: none;
    border-bottom: 1px solid {t.borde}; border-right: 1px solid {t.borde};
}}
QHeaderView::section:hover {{ background: {t.hover}; color: {t.texto}; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {manija}; border-radius: 4px; min-height: 40px; margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: {manija_h}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {manija}; border-radius: 4px; min-width: 40px; margin: 2px 0; }}
QScrollBar::handle:horizontal:hover {{ background: {manija_h}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; width: 0; height: 0; }}
QLineEdit {{ padding: 9px 13px; border-radius: 10px; background: {t.panel}; border: 1px solid {t.borde}; }}
QLineEdit:focus {{ border: 1px solid {t.acento}; }}
QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox {{ padding: 7px 12px; border-radius: 9px; background: {t.panel_claro}; border: 1px solid {t.borde}; }}
QComboBox:hover, QSpinBox:hover {{ border-color: {t.boton_borde}; }}
QComboBox QAbstractItemView {{ background: {t.panel_claro}; border: 1px solid {t.borde}; border-radius: 8px; selection-background-color: {t.seleccion}; padding: 4px; }}
QPushButton {{ {boton} padding: 8px 16px; font-weight: 500; }}
QPushButton:hover {{ {hover} }}
QPushButton:pressed {{ {apretado} }}
QPushButton:checked {{ background: {t.seleccion}; border-color: {t.acento}; color: #ffffff; }}
QPushButton:disabled {{ background: {t.panel}; border-color: {t.borde}; color: {t.tenue}; }}
QPushButton:focus {{ border-color: {t.acento}; }}
QPushButton#primario {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {acento_alto}, stop:1 {acento_bajo});
    color: {t.acento_texto}; border: 1px solid {t.acento}; border-bottom: 2px solid {acento_sombra}; font-weight: 600;
}}
QPushButton#primario:hover {{ background: {_mix(t.acento, "#ffffff", 0.18)}; }}
QPushButton#peligro {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8a2b2b, stop:1 #5c1d1d); border: 1px solid #b91c1c;
    border-bottom: 2px solid #2a0b0b; color: #fecaca; font-weight: 600;
}}
QPushButton#chico {{ padding: 4px 10px; border-radius: 7px; }}
QWidget#controles QPushButton, QWidget#controles QToolButton {{ padding: 5px 8px; border-radius: 8px; }}
QWidget#controles QToolButton {{ {boton} }}
QWidget#controles QToolButton:hover {{ {hover} }}
QTabWidget::pane {{ border: none; border-top: 1px solid {t.borde}; border-radius: 0; top: -1px; }}
QTabBar::tab {{
    background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0; padding: 10px 16px;
    margin-right: 4px; color: {t.tenue}; font-weight: 500;
}}
QTabBar::tab:hover:!selected {{ color: {t.texto}; background: {t.hover}; }}
QTabBar::tab:selected {{ background: transparent; color: {t.titulo}; border-bottom: 2px solid {t.acento}; }}
QGroupBox {{ border: 1px solid {t.borde}; border-radius: 12px; margin-top: 20px; padding: 16px 10px 10px; background: {t.panel}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: {t.tenue}; font-weight: 600; background: transparent; }}
QSplitter::handle {{ background: transparent; width: 10px; }}
QStatusBar {{ background: {t.barra}; color: {t.tenue}; border-top: 1px solid {t.borde}; padding: 3px 10px; }}
QSlider::groove:horizontal {{ height: 4px; background: {t.panel_claro}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.acento}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #ffffff; border: none; width: 14px; margin: -5px 0; border-radius: 7px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {t.boton_borde}; background: {t.panel_claro}; }}
QCheckBox::indicator:checked {{ background: {t.acento}; border-color: {t.acento}; }}
QWidget#vacio {{ background: {t.fondo_hondo}; }}
"""


def estilo(t: Tema) -> str:
    """La hoja de estilo completa de la app para el tema."""
    r = t.radio
    rc = max(0, r - 2)
    barra_texto = "#ffffff" if t.id in ("luna", "luna_noche", "noventa") else t.texto
    return f"""
QWidget {{ background: {t.fondo}; color: {t.texto}; font-size: 10pt; font-family: "{t.letra}"; }}
QToolBar {{ background: {t.barra}; border: none; padding: 6px; spacing: 6px; }}
QToolBar QToolButton {{ color: {barra_texto}; background: transparent; }}
QToolButton {{ padding: 6px 10px; border-radius: {r}px; }}
QToolButton:hover {{ background: {t.hover}; color: {t.texto}; }}
QLabel#titulo {{ font-size: 11pt; font-weight: 600; color: {t.titulo}; }}
QLabel#pista {{ color: {t.tenue}; }}
QToolButton[encendido="true"] {{ color: #4ade80; font-weight: 600; }}
QLabel#enVivo {{ color: #ff8080; font-weight: 600; }}
QLabel#insignia {{
    background: {t.acento}; color: {t.acento_texto}; border-radius: 8px; font-size: 8pt; font-weight: 700; padding: 0 4px;
}}
QPushButton#interruptor {{ font-size: 12pt; font-weight: 600; padding: 10px; }}
QPushButton#interruptor:checked {{ background: #14532d; border-color: #22c55e; color: #dcfce7; }}
QPushButton#chico {{ padding: 2px 8px; font-size: 9pt; color: {t.acento}; }}
QPushButton#primario {{ background: {t.acento}; color: {t.acento_texto}; border-color: {t.acento}; font-weight: 600; }}
QPushButton#peligro {{ background: #5c1d1d; border-color: #b91c1c; color: #fecaca; font-weight: 600; }}
QPushButton#peligro:hover {{ background: #7f1d1d; }}
QPushButton#peligro:disabled {{ background: transparent; border-color: {t.borde}; color: {t.tenue}; }}
QFrame#panelSiguiente {{ background: {t.panel}; border: 1px solid {t.acento}; border-radius: {r + 4}px; }}
QFrame#panelSiguiente QLabel {{ background: transparent; }}
QDoubleSpinBox, QSpinBox, QComboBox {{
    background: {t.panel}; border: 1px solid {t.borde}; border-radius: {r}px; padding: 3px 6px;
}}
QToolButton::menu-indicator {{ image: none; }}
QWidget#vacio {{ background: {t.fondo_hondo}; }}
QWidget#vacio QLabel {{ color: {t.tenue}; font-size: 12pt; background: transparent; }}
QLabel#chip {{
    background: {t.seleccion}; color: {"#ffffff" if t.claro else t.texto}; border: 1px solid {t.acento};
    border-radius: 10px; padding: 2px 10px;
}}
QMenuBar {{ background: {t.panel}; border-bottom: 1px solid {t.borde}; padding: 2px 4px; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; border-radius: {rc}px; }}
QMenuBar::item:selected {{ background: {t.hover}; }}
QMenu {{ background: {t.panel}; border: 1px solid {t.borde}; }}
QMenu::item:selected {{ background: {t.seleccion}; color: #ffffff; }}
QMenu::item:disabled {{ color: {t.tenue}; }}
QMenu::separator {{ height: 1px; background: {t.borde}; margin: 4px 8px; }}
QLineEdit, QListWidget, QTreeWidget, QGroupBox, QTextBrowser, QPlainTextEdit {{
    background: {t.panel}; border: 1px solid {t.borde}; border-radius: {r}px;
}}
QLineEdit {{ padding: 5px 8px; }}
QLineEdit:focus {{ border-color: {t.acento}; }}
QListWidget::item, QTreeWidget::item {{ padding: 4px; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {t.seleccion}; color: #ffffff; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {t.hover}; }}
QHeaderView::section {{
    background: {t.panel_claro}; color: {t.texto}; font-weight: 600; padding: 5px 6px;
    border: none; border-right: 2px solid {t.borde}; border-bottom: 2px solid {t.borde};
}}
QHeaderView::section:hover {{ background: {t.hover}; }}
QTreeWidget::item {{ border-right: 1px solid {t.borde}; }}
QGroupBox {{ margin-top: 14px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; color: {t.titulo}; }}
QPushButton {{
    background: {t.boton}; color: {t.boton_texto}; border: {t.borde_boton} {t.boton_borde}; border-radius: {r}px;
    padding: 6px 12px;
}}
QPushButton:hover {{ background: {t.boton_hover}; }}
QPushButton:pressed {{ background: {t.acento}; color: {t.acento_texto}; {"border-style: inset;" if "outset" in t.borde_boton else ""} }}
QPushButton:checked {{ background: {t.seleccion}; color: #ffffff; }}
QWidget#controles QPushButton, QWidget#controles QToolButton {{ padding: 3px 5px; }}
QLabel#volumen {{ color: {t.titulo}; font-weight: 700; }}
QPushButton:disabled, QWidget:disabled {{ color: {t.tenue}; }}
QSlider::groove:horizontal {{ height: 6px; background: {t.borde}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {t.acento}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {t.boton if t.radio < 4 else "#ffffff"}; border: 1px solid {t.boton_borde};
    width: 14px; margin: -5px 0; border-radius: {7 if t.radio >= 4 else 0}px;
}}
QSplitter::handle {{ background: {t.fondo_hondo}; width: 3px; }}
QStatusBar {{ background: {t.panel}; color: {t.tenue}; }}
QScrollBar:vertical {{ background: {t.fondo}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {t.boton_borde}; border-radius: {min(5, r)}px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QTabWidget::pane {{ border: 1px solid {t.borde}; border-radius: {r}px; }}
QTabBar::tab {{ background: {t.panel}; border: 1px solid {t.borde}; padding: 6px 14px; margin-right: 2px;
    border-top-left-radius: {r}px; border-top-right-radius: {r}px; }}
QTabBar::tab:selected {{ background: {t.boton}; color: {t.boton_texto}; }}
QWidget#bandaRetro {{ background: {t.lcd_fondo}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{ width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid {t.boton_texto}; }}
""" + _formas(t) + _menus(t) + t.boton_extra + (_moderno(t) if t.moderno else "")
