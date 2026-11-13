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


_TODOS: list[tuple[str, str]] | None = None


def todos() -> list[tuple[str, str]]:
    """[(código, nombre)] de todos los idiomas y variantes, ordenados por nombre. Primero cada idioma solo
    (es, en, pt…) y después sus variantes por país."""
    global _TODOS
    if _TODOS is None:
        vistos, lista = set(), []
        for loc in QLocale.matchingLocales(QLocale.AnyLanguage, QLocale.AnyScript, QLocale.AnyTerritory):
            if loc.language() in (QLocale.C, QLocale.AnyLanguage):
                continue
            codigo = loc.name()
            base = codigo.split("_")[0]
            if base not in vistos:
                vistos.add(base)
                nombre = loc.nativeLanguageName() or QLocale.languageToString(loc.language())
                en_ingles = QLocale.languageToString(loc.language())
                lista.append((base, nombre[:1].upper() + nombre[1:] + (f" — {en_ingles}" if en_ingles.lower() != nombre.lower() else "")))
            if codigo not in vistos:
                vistos.add(codigo)
                lista.append((codigo, _nombre(loc)))
        lista.sort(key=lambda x: (x[1].split(" (")[0].split(" —")[0].lower(), "_" in x[0], x[1].lower()))
        _TODOS = lista
    return _TODOS


def nombre_de(codigo: str) -> str:
    return next((n for c, n in todos() if c == codigo), codigo)


def base(codigo: str) -> str:
    """es_AR → es · pt_BR → pt-BR (OpenSubtitles distingue portugués de Brasil y chino) · zh_Hans_CN → zh-CN."""
    partes = (codigo or "").replace("-", "_").split("_")
    if not partes[0]:
        return ""
    if partes[0] == "pt" and "BR" in partes:
        return "pt-BR"
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
        self.resize(520, 600)
        capa = QVBoxLayout(self)
        texto = ("¡Bienvenido a TorrentVision! " if primera_vez else "") + (
            "Elegí en qué idioma querés los subtítulos. Cuando bajes una película, TorrentVision los busca solo "
            "en ese idioma (se puede cambiar cuando quieras en Configuración → Preferencias).")
        capa.addWidget(QLabel(texto, wordWrap=True))
        self.filtro = QLineEdit(placeholderText="🔎 Buscar: español, english, Argentina, pt_BR…")
        capa.addWidget(self.filtro)
        self.lista = QListWidget()
        capa.addWidget(self.lista, 1)
        elegir = actual or del_sistema()
        for codigo, nombre in todos():
            item = QListWidgetItem(f"{nombre}   ·   {codigo}")
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
