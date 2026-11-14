"""El idioma de los subtítulos: todos los idiomas con todas sus variantes por país (los de Qt/CLDR, cientos),
la ventana para elegirlo la primera vez que se abre TorrentVision y el código que usan las páginas de subtítulos."""
from __future__ import annotations

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

CLAVE = "idioma"          # en la config: el código elegido (es_AR, en_US, pt_BR, zh_Hans_CN…)


def _nombre(loc: QLocale) -> str:
    idioma = loc.nativeLanguageName() or QLocale.languageToString(loc.language())
    pais = loc.nativeTerritoryName() if hasattr(loc, "nativeTerritoryName") else loc.nativeCountryName()
    en_ingles = QLocale.languageToString(loc.language())
    texto = idioma[:1].upper() + idioma[1:]
    if pais:
        texto += f" ({pais})"
    if en_ingles and en_ingles.lower() != idioma.lower():
        texto += f" — {en_ingles}"
    return texto


# Una opción por idioma; variantes solo donde los subtítulos cambian de verdad (español, portugués, chino).
# Primero los más usados; después el resto, por nombre.
_COMUNES = [
    ("es_AR", "Español (Argentina)"), ("es_ES", "Español (España)"), ("en", "English — Inglés"),
    ("pt_BR", "Português (Brasil) — Portugués"), ("pt_PT", "Português (Portugal) — Portugués"),
    ("fr", "Français — Francés"), ("it", "Italiano"), ("de", "Deutsch — Alemán"),
    ("ja", "日本語 — Japonés"), ("ko", "한국어 — Coreano"), ("zh_CN", "中文 简体 — Chino simplificado"),
    ("zh_TW", "中文 繁體 — Chino tradicional"), ("ru", "Русский — Ruso"), ("ar", "العربية — Árabe"),
]
_OTROS = [
    ("bg", "Български — Búlgaro"), ("ca", "Català — Catalán"), ("cs", "Čeština — Checo"), ("da", "Dansk — Danés"),
    ("el", "Ελληνικά — Griego"), ("eu", "Euskara — Vasco"), ("fa", "فارسی — Persa"), ("fi", "Suomi — Finés"),
    ("gl", "Galego — Gallego"), ("he", "עברית — Hebreo"), ("hi", "हिन्दी — Hindi"), ("hr", "Hrvatski — Croata"),
    ("hu", "Magyar — Húngaro"), ("id", "Bahasa Indonesia — Indonesio"), ("nl", "Nederlands — Neerlandés"),
    ("no", "Norsk — Noruego"), ("pl", "Polski — Polaco"), ("ro", "Română — Rumano"), ("sk", "Slovenčina — Eslovaco"),
    ("sr", "Српски — Serbio"), ("sv", "Svenska — Sueco"), ("th", "ไทย — Tailandés"), ("tr", "Türkçe — Turco"),
    ("uk", "Українська — Ucraniano"), ("vi", "Tiếng Việt — Vietnamita"),
]


def todos() -> list[tuple[str, str]]:
    """[(código, nombre)]: los más usados primero y después el resto por nombre."""
    return _COMUNES + sorted(_OTROS, key=lambda x: x[1].split(" —")[0].lower())


def mas_cercano(codigo: str) -> str:
    """La opción de la lista para cualquier código: es_MX/es_419 → es_AR (español latino), es_ES → es_ES,
    en_US → en, pt → pt_BR, zh_Hant_TW → zh_TW…"""
    codigos = [c for c, _n in todos()]
    if codigo in codigos:
        return codigo
    partes = (codigo or "").replace("-", "_").split("_")
    idioma = partes[0].lower()
    if idioma == "es":
        return "es_ES" if "ES" in partes else "es_AR"
    if idioma == "pt":
        return "pt_PT" if "PT" in partes else "pt_BR"
    if idioma == "zh":
        return "zh_TW" if {"Hant", "TW", "HK", "MO"} & set(partes) else "zh_CN"
    if idioma == "nb" or idioma == "nn":
        return "no"
    return idioma if idioma in codigos else ""


def nombre_de(codigo: str) -> str:
    cercano = mas_cercano(codigo)
    return next((n for c, n in todos() if c == cercano), codigo)


def base(codigo: str) -> str:
    """es_AR → es · pt_BR → pt-BR (OpenSubtitles distingue portugués de Brasil y chino) · zh_Hans_CN → zh-CN."""
    partes = (codigo or "").replace("-", "_").split("_")
    if not partes[0]:
        return ""
    if partes[0] == "pt":
        return "pt-BR" if "BR" in partes else "pt-PT"
    if partes[0] == "zh":
        return "zh-TW" if ("Hant" in partes or "TW" in partes or "HK" in partes) else "zh-CN"
    return partes[0].lower()


def del_sistema() -> str:
    return QLocale.system().name()


def guardar(bib, codigo: str):
    """Guarda el idioma y lo pone primero en los idiomas de subtítulos (los demás se conservan)."""
    bib.guardar_config(CLAVE, codigo)
    actuales = [i.strip() for i in (bib.config("idiomas_subtitulos") or "").split(",") if i.strip()]
    nuevo = base(codigo)
    if nuevo:
        bib.guardar_config("idiomas_subtitulos", ",".join([nuevo] + [i for i in actuales if i != nuevo]))


class DialogoIdioma(QDialog):
    """Elegir el idioma de los subtítulos, con buscador (hay cientos de variantes)."""

    def __init__(self, actual: str = "", parent=None, primera_vez: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Idioma de los subtítulos — TorrentVision")
        self.resize(480, 640)
        capa = QVBoxLayout(self)
        texto = ("¡Bienvenido a TorrentVision! " if primera_vez else "") + (
            "Elegí en qué idioma querés los subtítulos. Cuando bajes una película, TorrentVision los busca solo "
            "en ese idioma (se puede cambiar cuando quieras en Configuración → Preferencias).")
        capa.addWidget(QLabel(texto, wordWrap=True))
        self.filtro = QLineEdit(placeholderText="🔎 Buscar: español, inglés, Brasil…")
        capa.addWidget(self.filtro)
        self.lista = QListWidget()
        capa.addWidget(self.lista, 1)
        elegir = mas_cercano(actual or del_sistema()) or "es_AR"
        for codigo, nombre in todos():
            item = QListWidgetItem(nombre)
            item.setData(Qt.UserRole, codigo)
            self.lista.addItem(item)
            if codigo == elegir:
                self.lista.setCurrentItem(item)
        if self.lista.currentItem() is None:
            b = base(elegir)
            for i in range(self.lista.count()):
                if self.lista.item(i).data(Qt.UserRole) == b:
                    self.lista.setCurrentRow(i)
                    break
        self.filtro.textChanged.connect(self._filtrar)
        self.lista.itemDoubleClicked.connect(lambda _i: self.accept())
        botones = QDialogButtonBox(QDialogButtonBox.Ok | (QDialogButtonBox.NoButton if primera_vez else QDialogButtonBox.Cancel))
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        capa.addWidget(botones)
        if self.lista.currentItem():      # al abrirse, el elegido queda en el medio de la lista
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.lista.scrollToItem(self.lista.currentItem(), QListWidget.PositionAtCenter))

    def _filtrar(self, texto: str):
        t = texto.strip().lower()
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            item.setHidden(bool(t) and t not in item.text().lower())

    def elegido(self) -> str:
        item = self.lista.currentItem()
        return item.data(Qt.UserRole) if item else ""
