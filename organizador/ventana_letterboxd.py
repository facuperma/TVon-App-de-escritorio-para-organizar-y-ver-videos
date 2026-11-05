"""Ventana de Letterboxd: tu watchlist y las mejor puntuadas, marcando las que ya están en la biblioteca
(también si la tenés con el título en otro idioma)."""
import json
import re
import requests
from urllib.parse import quote_plus

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import archive, letterboxd
from .temas import tema
from .db import Biblioteca
from .tareas import en_segundo_plano
from bs4 import BeautifulSoup

ROL = Qt.UserRole
# El buscador de ext.to, en la categoría Películas (cat=1)
BUSCAR_TORRENT = "https://ext.to/browse/?cat=1&q={}"
# Los subtítulos: el buscador de OpenSubtitles en el idioma elegido (subdivx no deja armar su búsqueda con un link)
BUSCAR_SUBTITULOS = "https://www.opensubtitles.org/es/search2/sublanguageid-{idioma}/moviename-{texto}"
IDIOMAS_OS = {"es": "spa", "en": "eng", "pt": "por", "it": "ita", "fr": "fre", "de": "ger"}
MAX_TRADUCCIONES = 120  # por vez: Wikidata es gratis, no hay que abusar


class VentanaLetterboxd(QWidget):
    def __init__(self, bib: Biblioteca, descargas=None, torrents=None):
        """descargas / torrents: los gestores de TorrentVision, para bajar sin salir de acá."""
        super().__init__(None, Qt.Window)
        self.bib = bib
        self.descargas = descargas
        self.torrents = torrents
        self._esperando: dict | None = None  # la película de la que se espera un link magnet
        self._traduciendo = False
        try:
            self._traducciones: dict[str, list[str]] = json.loads(bib.config("letterboxd_traducciones") or "{}")
        except ValueError:
            self._traducciones = {}
        QGuiApplication.clipboard().dataChanged.connect(self._portapapeles)
        self.setWindowTitle("Letterboxd — TorrentVision")
        self.resize(820, 600)
        self._listas: dict[str, list[dict]] = {}  # lo ya traído, para no volver a pedirlo
        self._vista = "watchlist"

        self.usuario = QLineEdit(bib.config("letterboxd_usuario"),
                                 placeholderText="Tu usuario de Letterboxd o el link de tu perfil (letterboxd.com/… o boxd.it/…)",
                                 clearButtonEnabled=True)
        self.usuario.returnPressed.connect(lambda: self._cargar("watchlist", forzar=True))
        self.btn_watchlist = QPushButton("📋 Mi watchlist", checkable=True, checked=True)
        self.btn_mejores = QPushButton("🏆 Las 500 mejor puntuadas", checkable=True)
        grupo = QButtonGroup(self)
        for b in (self.btn_watchlist, self.btn_mejores):
            grupo.addButton(b)
        self.btn_watchlist.clicked.connect(lambda: self._cargar("watchlist", forzar=True))
        self.btn_mejores.clicked.connect(lambda: self._cargar("mejores"))
        fila = QHBoxLayout()
        fila.addWidget(self.usuario, 1)
        fila.addWidget(self.btn_watchlist)
        fila.addWidget(self.btn_mejores)

        self.chk_ocultar = QCheckBox("Ocultar las que ya tengo")
        self.chk_ocultar.toggled.connect(self._mostrar)
        self.estado = QLabel(objectName="pista")

        self.lista = QTreeWidget()
        self.lista.setHeaderLabels(["Película", "Año", "En tu biblioteca", "Subtítulos"])
        # Un clic en «💬 Buscar» (columna Subtítulos) abre la búsqueda de sus subtítulos ya hecha
        self.lista.itemClicked.connect(lambda item, columna: columna == 3 and self._subtitulos(item))
        self.lista.setRootIsDecorated(False)
        self.lista.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lista.itemDoubleClicked.connect(lambda item: self._buscar([item]))

        btn_buscar = QPushButton("⬇ Bajarla", objectName="primario")
        btn_buscar.setToolTip("Si es de dominio público, la baja gratis del Internet Archive.\n"
                              "Si no, abre la búsqueda del torrent ya hecha: copiá el link magnet y TorrentVision\n"
                              "lo toma solo y la pone a bajar (también con doble clic en la película)")
        btn_buscar.clicked.connect(lambda: self._buscar())
        btn_ficha = QPushButton("Ver en Letterboxd")
        btn_ficha.clicked.connect(lambda: self._abrir_ficha(self.lista.selectedItems()))
        abajo = QHBoxLayout()
        abajo.addWidget(self.chk_ocultar)
        abajo.addStretch()
        abajo.addWidget(btn_ficha)
        abajo.addWidget(btn_buscar)

        capa = QVBoxLayout(self)
        capa.addLayout(fila)
        capa.addWidget(QLabel("Letterboxd no deja iniciar sesión desde otras apps: se lee tu watchlist pública, "
                              "como la ve cualquiera. Doble clic en una película para bajarla.",
                              objectName="pista", wordWrap=True))
        capa.addWidget(self.lista, 1)
        capa.addWidget(self.estado)
        capa.addLayout(abajo)

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self._listas:
            self._cargar("watchlist" if self.usuario.text().strip() else "mejores")

    def _cargar(self, vista: str, forzar: bool = False):
        self._vista = vista
        (self.btn_watchlist if vista == "watchlist" else self.btn_mejores).setChecked(True)
        if vista in self._listas and not forzar:
            return self._mostrar()
        if vista == "watchlist":
            try:
                usuario = letterboxd.usuario_valido(self.usuario.text())
            except letterboxd.ErrorLetterboxd as e:
                self.lista.clear()
                return self.estado.setText(str(e))
            self.bib.guardar_config("letterboxd_usuario", usuario)
            trabajo = lambda: letterboxd.watchlist(usuario)  # noqa: E731
        else:
            trabajo = letterboxd.mejor_puntuadas
        self.lista.clear()
        self.estado.setText("Leyendo Letterboxd…")

        def listo(pelis):
            self._listas[vista] = pelis
            if self._vista == vista:
                self._mostrar()

        def fallo(mensaje):
            if self._vista == vista:
                self.estado.setText(mensaje)

        en_segundo_plano(trabajo, listo, fallo)

    def _mostrar(self):
        pelis = self._listas.get(self._vista)
        if pelis is None:
            return
        nombres = [n for (n,) in self.bib.con.execute("SELECT nombre FROM archivos WHERE tipo = 'video'")]
        claves = letterboxd.claves_biblioteca(nombres)
        self.lista.clear()
        tengo = 0
        for p in pelis:
            esta = letterboxd.en_biblioteca(p, claves, self._traducciones.get(self._clave(p), []))
            tengo += esta
            if esta and self.chk_ocultar.isChecked():
                continue
            item = QTreeWidgetItem([p["titulo"], p["anio"], "✓ Ya la tenés" if esta else "", "💬 Buscar"])
            item.setToolTip(3, "Abrir la búsqueda de sus subtítulos")
            vinculo = item.font(3)
            vinculo.setUnderline(True)
            item.setFont(3, vinculo)
            item.setForeground(3, QBrush(QColor(tema(self.bib.config("tema")).vinculo)))
            item.setData(0, ROL, p)
            if esta:
                for col in range(3):
                    item.setForeground(col, QBrush(QColor("#86efac")))
            self.lista.addTopLevelItem(item)
        nombre = "tu watchlist" if self._vista == "watchlist" else "las mejor puntuadas"
        self.estado.setText(f"{len(pelis)} películas en {nombre} · {tengo} ya en tu biblioteca · "
                            f"{len(pelis) - tengo} para bajar")
        self._traducir(pelis, claves)

    @staticmethod
    def _clave(p: dict) -> str:
        return f"{p['titulo']}|{p['anio']}"

    def _traducir(self, pelis: list[dict], claves: set[str]):
        """Las que no aparecieron pero tienen el año de alguna de la biblioteca: se buscan sus títulos
        en otros idiomas (Wikidata), por si la tenés como «El padrino» y Letterboxd dice «The Godfather»."""
        if self._traduciendo:
            return
        anios = {c.rsplit("|", 1)[1] for c in claves if c.rsplit("|", 1)[1]}
        pendientes = [p for p in pelis if p["anio"] in anios and self._clave(p) not in self._traducciones
                      and not letterboxd.en_biblioteca(p, claves)][:MAX_TRADUCCIONES]
        if not pendientes:
            return
        self._traduciendo = True

        def trabajo():
            hechas = {}
            for p in pendientes:
                try:
                    hechas[self._clave(p)] = letterboxd.titulos_en_otros_idiomas(p["titulo"], p["anio"])
                except Exception:  # noqa: BLE001 - sin internet o Wikidata ocupado: se intenta otro día
                    break
            return hechas

        def listo(hechas):
            self._traduciendo = False
            if hechas:
                self._traducciones.update(hechas)
                self.bib.guardar_config("letterboxd_traducciones", json.dumps(self._traducciones, ensure_ascii=False))
                self._mostrar()

        def fallo(_mensaje):
            self._traduciendo = False

        en_segundo_plano(trabajo, listo, fallo)

    def _seleccion(self, items) -> list[dict]:
        return [i.data(0, ROL) for i in items if i.data(0, ROL)]

    def _abrir_ficha(self, items):
        for p in self._seleccion(items)[:5]:
            QDesktopServices.openUrl(QUrl(p["url"]))

    def _buscar(self, items=None):
        """Lo más cerca posible de bajarla: si es de dominio público, del Internet Archive (gratis y legal);
        si no, la búsqueda del torrent ya hecha, y el link magnet que copies se pone a bajar solo."""
        pelis = self._seleccion(items if items is not None else self.lista.selectedItems())
        if not pelis:
            return self.estado.setText("Elegí una película de la lista")
        p = pelis[0]
        self.estado.setText(f"Buscando «{p['titulo']}»…")

        def en_archive():
            _total, encontradas = archive.buscar(p["titulo"], filas=10)
            buscada = letterboxd.clave(p["titulo"])
            return next((e for e in encontradas if e.get("anio") == p["anio"]
                         and letterboxd.clave(e["titulo"]) == buscada), None)

        en_segundo_plano(en_archive, lambda libre: self._ofrecer(p, libre), lambda _m: self._ofrecer(p, None))

    def _ofrecer(self, p: dict, libre: dict | None):
        if libre and self.descargas is not None and QMessageBox.question(
            self, "Dominio público",
            f"«{p['titulo']}» ({p['anio']}) es de dominio público: está gratis y legal en el Internet Archive.\n\n"
            "¿La bajo de ahí?",
        ) == QMessageBox.Yes:
            if self.bib.agregar_descarga(libre["identificador"], libre["titulo"], libre["anio"]):
                self.descargas.despertar()
            return self.estado.setText(f"Bajando «{p['titulo']}» del Internet Archive (🎞 Dominio público)")
        texto = f"{p['titulo']} {p['anio']}".strip()
        # Copiado también, por si la página no muestra la búsqueda hecha: se pega con Ctrl+V en su buscador
        QGuiApplication.clipboard().setText(texto)
        busqueda = self.bib.config("letterboxd_busqueda") or BUSCAR_TORRENT
        QDesktopServices.openUrl(QUrl(busqueda.format(quote_plus(texto))))
        self._esperando = p
        self.estado.setText(f"Se abrió la búsqueda y se copió «{texto}» (si no aparece buscada, pegalo con Ctrl+V "
                            "en el buscador). Copiá el link magnet del torrent: TorrentVision lo toma solo.")

    def _subtitulos(self, item):
        """La búsqueda de los subtítulos de la película, ya hecha, en el primer idioma configurado.
        También copia «Título Año», por si se prefiere buscar en otra página (subdivx)."""
        p = item.data(0, ROL)
        if not p:
            return
        texto = f"{p['titulo']} {p['anio']}".strip()
        idioma = ((self.bib.config("idiomas_subtitulos") or "es").split(",")[0].strip().lower() or "es")[:2]
        QGuiApplication.clipboard().setText(texto)
        QDesktopServices.openUrl(QUrl(BUSCAR_SUBTITULOS.format(idioma=IDIOMAS_OS.get(idioma, "spa"),
                                                               texto=quote_plus(texto))))
        self.estado.setText(f"Se abrió la búsqueda de subtítulos de «{texto}» (también quedó copiado). Bajá el .srt "
                            "o .zip a Descargas: TorrentVision lo pone solo junto a la película.")

    def _portapapeles(self):
        """Si después de buscar una película se copia un link magnet, se ofrece bajarlo."""
        p = self._esperando
        texto = QGuiApplication.clipboard().text().strip()
        if p is None or self.torrents is None or not re.match(r"(?i)magnet:\?xt=urn:bt", texto):
            return
        self._esperando = None
        if QMessageBox.question(self, "Bajar con torrent",
                                f"¿Bajo «{p['titulo']}» ({p['anio']}) con el link magnet que copiaste?") != QMessageBox.Yes:
            return
        try:
            self.torrents.agregar(texto)
            self.estado.setText(f"«{p['titulo']}» se está bajando: mirá el avance en 🧲 Torrents")
        except Exception as e:  # noqa: BLE001 - aria2 no arrancó, link roto…
            self.estado.setText(f"No se pudo agregar el torrent: {e}")
