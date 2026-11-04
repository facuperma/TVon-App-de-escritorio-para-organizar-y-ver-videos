"""Temas de TorrentVision: el azul de siempre y once estilos retro de los reproductores de los 2000.

Cada tema es una paleta, una letra, una forma de botón y una animación para la banda de arriba.
Son estilos inspirados en esa época, con nombres y diseños propios (sin logos ni marcas de nadie).
"""
from dataclasses import dataclass


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

    # Colores de estado de la lista (a medias / vista / vínculo), legibles sobre el fondo del tema
    @property
    def pendiente(self) -> str:
        return "#a15c00" if self.claro else "#facc15"

    @property
    def vista(self) -> str:
        return "#16803c" if self.claro else "#86efac"

    @property
    def vinculo(self) -> str:
        return self.acento if self.claro else "#9fc2ff"


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

POR_ID = {t.id: t for t in TEMAS}


def tema(id_: str | None) -> Tema:
    return POR_ID.get(id_ or "", TEMAS[0])


def estilo(t: Tema) -> str:
    """La hoja de estilo completa de la app para el tema."""
    r = t.radio
    rc = max(0, r - 2)
    barra_texto = "#ffffff" if t.id in ("luna", "noventa") else t.texto
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
"""
