"""Ventana de Letterboxd: tu watchlist, las mejor puntuadas y la búsqueda de cualquier película, marcando las
que ya están en la biblioteca (también si la tenés con el título en otro idioma)."""
import html
import json
import re
import requests
from urllib.parse import quote_plus

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import archive, letterboxd
from .temas import tema
from .db import Biblioteca
from .red import bajar_bytes
from .tareas import en_segundo_plano
from bs4 import BeautifulSoup

ROL = Qt.UserRole
# El buscador de ext.to, en la categoría Películas (cat=1)
BUSCAR_TORRENT = "https://ext.to/browse/?cat=1&q={}"
# Las series: sin categoría (la de películas las dejaba afuera)
BUSCAR_TORRENT_TODO = "https://ext.to/browse/?q={}"
# Los subtítulos: el buscador de OpenSubtitles en el idioma elegido (subdivx no deja armar su búsqueda con un link)
BUSCAR_SUBTITULOS = "https://www.opensubtitles.org/es/search2/sublanguageid-{idioma}/moviename-{texto}"
IDIOMAS_OS = {"es": "spa", "en": "eng", "pt": "por", "it": "ita", "fr": "fre", "de": "ger"}
MAX_TRADUCCIONES = 120  # por vez: Wikidata es gratis, no hay que abusar


class VentanaLetterboxd(QWidget):
    def __init__(self, bib: Biblioteca, descargas=None, torrents=None, solo_busqueda: bool = False, al_reproducir=None):
        """descargas / torrents: los gestores de TorrentVision, para bajar sin salir de acá.
        solo_busqueda: la ventana «Buscar» (sin la watchlist): arriba lo que ya tenés, abajo lo que se puede bajar.
        al_reproducir(ruta): para reproducir lo que ya está en la biblioteca."""
        super().__init__(None, Qt.Window)
        self.solo_busqueda = solo_busqueda
        self.al_reproducir = al_reproducir
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
        self.resize(1040, 640)
        self._detalles: dict[str, tuple[dict, bytes | None]] = {}  # url -> (datos, póster) ya traídos
        self._previsto = ""
        self._listas: dict[str, list[dict]] = {}  # lo ya traído, para no volver a pedirlo
        self._vista = "watchlist"

        self.usuario = QLineEdit(bib.config("letterboxd_usuario"),
                                 placeholderText="Tu usuario de Letterboxd o el link de tu perfil (letterboxd.com/… o boxd.it/…)",
                                 clearButtonEnabled=True)
        self.usuario.returnPressed.connect(lambda: self._cargar("watchlist", forzar=True))
        self.btn_watchlist = QPushButton("📋 Mi watchlist", checkable=True, checked=True)
        self.btn_mejores = QPushButton("🏆 Las 500 mejor puntuadas", checkable=True)
        self.btn_busqueda = QPushButton("🔎 Buscar", checkable=True)
        grupo = QButtonGroup(self)
        for b in (self.btn_watchlist, self.btn_mejores, self.btn_busqueda):
            grupo.addButton(b)
        # Cualquier película por nombre (en castellano o en inglés), para bajarla
        self.busqueda = QLineEdit(placeholderText="Buscar película o serie (El padrino, Twin Peaks temporada 2…) y Enter",
                                  clearButtonEnabled=True)
        self.busqueda.returnPressed.connect(lambda: self.buscar_texto(self.busqueda.text()))
        self.btn_busqueda.clicked.connect(lambda: self.buscar_texto(self.busqueda.text()))
        self._texto_buscado = ""
        self.btn_watchlist.clicked.connect(lambda: self._cargar("watchlist", forzar=True))
        self.btn_mejores.clicked.connect(lambda: self._cargar("mejores"))
        fila = QHBoxLayout()
        fila.addWidget(self.usuario, 1)
        fila.addWidget(self.btn_watchlist)
        fila.addWidget(self.btn_mejores)
        fila_busqueda = QHBoxLayout()
        fila_busqueda.addWidget(self.busqueda, 1)
        fila_busqueda.addWidget(self.btn_busqueda)

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
        # La vista previa se pide un momento después de pararse en una película (no al pasar rápido con las flechas)
        self._espera = QTimer(self, singleShot=True, interval=250)
        self._espera.timeout.connect(self._previsualizar)
        self.lista.currentItemChanged.connect(lambda *_: self._espera.start())
        self.panel = self._armar_panel()

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
        capa.addLayout(fila_busqueda)
        pista = QLabel("Se lee tu watchlist pública. Doble clic en una película para bajarla.",
                       objectName="pista", wordWrap=True)
        capa.addWidget(pista)
        # La ventana «Buscar»: primero lo que ya está en la biblioteca (con su categoría)
        self.caja_local = QWidget()
        capa_local = QVBoxLayout(self.caja_local)
        capa_local.setContentsMargins(0, 0, 0, 0)
        self.lbl_local = QLabel(objectName="titulo")
        self.lista_local = QTreeWidget()
        self.lista_local.setHeaderLabels(["En tu biblioteca", "Categoría"])
        self.lista_local.setRootIsDecorated(False)
        self.lista_local.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lista_local.setMaximumHeight(170)
        self.lista_local.itemDoubleClicked.connect(self._reproducir_local)
        fila_local = QHBoxLayout()
        fila_local.addWidget(self.lbl_local, 1)
        self.btn_bajar_igual = QPushButton("🔎 Buscar para bajar")
        self.btn_bajar_igual.clicked.connect(lambda: self.buscar_texto(self.busqueda.text(), online=True))
        fila_local.addWidget(self.btn_bajar_igual)
        capa_local.addLayout(fila_local)
        capa_local.addWidget(self.lista_local)
        capa.addWidget(self.caja_local)
        self.caja_local.hide()
        if solo_busqueda:
            self.setWindowTitle("Buscar — TorrentVision")
            for w in (self.usuario, self.btn_watchlist, self.btn_mejores, pista, self.chk_ocultar):
                w.hide()
        self.division = division = QSplitter(Qt.Horizontal)
        division.addWidget(self.lista)
        division.addWidget(self.panel)
        division.setStretchFactor(0, 3)
        division.setStretchFactor(1, 2)
        division.setChildrenCollapsible(False)
        capa.addWidget(division, 1)
        capa.addWidget(self.estado)
        capa.addLayout(abajo)

    def _armar_panel(self) -> QWidget:
        """La vista previa: portada, título, datos y sinopsis de la película elegida."""
        panel = QWidget()
        panel.setMinimumWidth(260)
        self.portada = QLabel(alignment=Qt.AlignCenter)
        self.portada.setFixedSize(200, 300)
        self.portada.setStyleSheet("background: rgba(127,127,127,0.15); border-radius: 6px;")
        self.prev_titulo = QLabel(wordWrap=True, textFormat=Qt.RichText)
        self.prev_datos = QLabel(wordWrap=True, objectName="pista")
        self.prev_sinopsis = QLabel(wordWrap=True, alignment=Qt.AlignTop | Qt.AlignLeft)
        self.prev_sinopsis.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Lo que se va a buscar en la página de torrents: se puede corregir antes de bajar (doble clic o ⬇ Bajarla)
        self.texto_torrent = QLineEdit(clearButtonEnabled=True,
                                       placeholderText="Lo que se busca en la página de torrents")
        self.texto_torrent.setToolTip("Se arma solo (título original, año; para series «season 2» o «S02E05»).\n"
                                      "Cambialo si querés buscar otra cosa (otra calidad, otro idioma…)")
        self.texto_torrent.returnPressed.connect(lambda: self._buscar())
        desplazable = QScrollArea(widgetResizable=True, frameShape=QScrollArea.NoFrame)
        desplazable.setWidget(self.prev_sinopsis)
        capa = QVBoxLayout(panel)
        capa.addWidget(self.portada, 0, Qt.AlignHCenter)
        capa.addWidget(self.prev_titulo)
        capa.addWidget(self.prev_datos)
        capa.addWidget(desplazable, 1)
        capa.addWidget(QLabel("Buscar el torrent como:", objectName="pista"))
        capa.addWidget(self.texto_torrent)
        self._vista_previa_vacia()
        return panel

    def _vista_previa_vacia(self, texto: str = "Elegí una película para ver su portada y de qué trata."):
        self.portada.clear()
        self.prev_titulo.clear()
        self.prev_datos.clear()
        self.prev_sinopsis.setText(texto)

    def _previsualizar(self):
        item = self.lista.currentItem()
        p = item.data(0, ROL) if item else None
        if not p:
            return self._vista_previa_vacia()
        self._previsto = p["url"]
        pedido = letterboxd.interpretar_busqueda(self._texto_buscado) if self._vista == "busqueda" else None
        self.texto_torrent.setText(letterboxd.texto_torrent(p, pedido))
        titulo = p.get("titulo_es") or p["titulo"]
        self.prev_titulo.setText(f"<b style='font-size: 14pt'>{html.escape(titulo)}</b> {p['anio']}")
        if p["url"] in self._detalles:
            return self._poner_detalle(p, *self._detalles[p["url"]])
        self.portada.clear()
        self.prev_datos.clear()
        self.prev_sinopsis.setText("Cargando…")

        def traer():
            datos = letterboxd.detalle_wikipedia(p["url"]) if "wikipedia.org" in p["url"] else letterboxd.detalle(p["url"])
            imagen = None
            if datos["poster_url"]:
                try:
                    imagen = bajar_bytes(datos["poster_url"], timeout=20)
                except Exception:  # noqa: BLE001 - sin portada, el resto se muestra igual
                    pass
            return datos, imagen

        def listo(resultado):
            self._detalles[p["url"]] = resultado
            if self._previsto == p["url"]:
                self._poner_detalle(p, *resultado)

        def fallo(mensaje):
            if self._previsto == p["url"]:
                self.prev_sinopsis.setText(f"No se pudo traer la vista previa: {mensaje}")

        en_segundo_plano(traer, listo, fallo)

    def _poner_detalle(self, p: dict, datos: dict, imagen: bytes | None):
        pixmap = QPixmap()
        if imagen and pixmap.loadFromData(imagen):
            self.portada.setPixmap(pixmap.scaled(self.portada.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.portada.setText("Sin portada")
        partes = [f"Dirigida por {datos['director']}" if datos["director"] else "",
                  f"{datos['minutos']} min" if datos["minutos"] else "", " · ".join(datos["generos"]),
                  f"★ {datos['puntaje']}" if datos["puntaje"] else ""]
        self.prev_datos.setText("  ·  ".join(x for x in partes if x))
        self.prev_sinopsis.setText(datos["sinopsis"] or "Letterboxd no tiene sinopsis de esta película.")

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self._listas and not self.solo_busqueda:
            self._cargar("watchlist" if self.usuario.text().strip() else "mejores")

    def buscar_texto(self, texto: str, online: bool | None = None):
        """Busca películas y series que se llamen así. En la ventana «Buscar», primero en la biblioteca: si ya la
        tenés, se muestra con su categoría (y se busca para bajar solo si se pide); si no, directo para bajar."""
        texto = texto.strip()
        if len(texto) < 2:
            self.busqueda.setFocus()
            return self.estado.setText("Escribí el nombre de una película o serie")
        self.busqueda.setText(texto)
        self._texto_buscado = texto
        tenes = self._mostrar_locales(texto) if self.solo_busqueda else 0
        solo_locales = online is False or (online is None and tenes)
        # Si solo se muestra lo que ya tenés, esa lista ocupa todo; si también se busca para bajar, va arriba y chica
        self.division.setVisible(not solo_locales)
        self.lista_local.setMaximumHeight(16777215 if solo_locales else 190)
        if solo_locales:
            self.lista.clear()
            self._vista_previa_vacia("Ya la tenés: doble clic arriba para verla. Si querés otra copia, "
                                     "tocá «🔎 Buscar para bajar».")
            return self.estado.setText(f"{tenes} en tu biblioteca para «{texto}»")
        self._cargar("busqueda", forzar=True)

    def _mostrar_locales(self, texto: str) -> int:
        """Lo que ya está en la biblioteca con ese nombre (también buscando solo el título, sin «temporada 2»)."""
        titulo = letterboxd.interpretar_busqueda(texto)["titulo"] or texto
        filas = {}
        for t in {texto, titulo}:
            for aid, ruta, nombre, tipo in self.bib.listar_archivos("todos", None, t):
                if tipo == "video":
                    filas[aid] = (ruta, nombre)
        nombres_cat = {cid: nombre for cid, nombre, _n in self.bib.listar_categorias()}
        self.lista_local.clear()
        for aid, (ruta, nombre) in sorted(filas.items(), key=lambda f: f[1][1].lower())[:200]:
            categorias = ", ".join(sorted(nombres_cat[c] for c in self.bib.categorias_de(aid) if c in nombres_cat))
            item = QTreeWidgetItem([nombre, categorias or "—"])
            item.setToolTip(0, ruta)
            item.setData(0, ROL, ruta)
            self.lista_local.addTopLevelItem(item)
        self.lbl_local.setText(f"✓ Ya tenés {len(filas)}" if filas else "")
        self.caja_local.setVisible(bool(filas))
        return len(filas)

    def _reproducir_local(self, item):
        ruta = item.data(0, ROL)
        if ruta and self.al_reproducir:
            self.al_reproducir(ruta)

    def _cargar(self, vista: str, forzar: bool = False):
        self._vista = vista
        {"watchlist": self.btn_watchlist, "mejores": self.btn_mejores}.get(vista, self.btn_busqueda).setChecked(True)
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
        elif vista == "busqueda":
            texto = self._texto_buscado
            trabajo = lambda: letterboxd.buscar_peliculas(texto)  # noqa: E731
        else:
            trabajo = letterboxd.mejor_puntuadas
        self.lista.clear()
        self._vista_previa_vacia()
        self.estado.setText(f"Buscando «{self._texto_buscado}»…" if vista == "busqueda" else "Leyendo Letterboxd…")

        def listo(pelis):
            self._listas[vista] = pelis
            if self._vista == vista:
                self._mostrar()
                if vista == "busqueda" and pelis:
                    self.lista.setCurrentItem(self.lista.topLevelItem(0))  # su vista previa, ya

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
            otros = self._traducciones.get(self._clave(p), []) + ([p["titulo_es"]] if p.get("titulo_es") else [])
            esta = letterboxd.en_biblioteca(p, claves, otros)
            tengo += esta
            if esta and self.chk_ocultar.isChecked():
                continue
            nombre = p["titulo"]
            if p.get("titulo_es") and p["titulo_es"].lower() != p["titulo"].lower():
                nombre = f"{p['titulo_es']} ({p['titulo']})"
            item = QTreeWidgetItem([nombre, p["anio"], "✓ Ya la tenés" if esta else "", "💬 Buscar"])
            if p.get("descripcion"):
                item.setToolTip(0, p["descripcion"])
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
        if self._vista == "busqueda":
            return self.estado.setText(
                f"{len(pelis)} resultados para «{self._texto_buscado}». Doble clic: abre la búsqueda del torrent y, al "
                "copiar el link magnet, se pone a bajar sola." if pelis else
                f"No encontré películas ni series que se llamen «{self._texto_buscado}». Probá con el título original.")
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
            if p.get("tipo") == "serie":
                return None
            _total, encontradas = archive.buscar(p["titulo"], filas=10)
            return next((e for e in encontradas if letterboxd.coincide_archive(e, p["titulo"], p["anio"])), None)

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
        # El texto del cuadro «Buscar el torrent como» si es el de esta película (pudo corregirse); si no, se arma
        texto = self.texto_torrent.text().strip() if self._previsto == p["url"] else ""
        if not texto:
            pedido = letterboxd.interpretar_busqueda(self._texto_buscado) if self._vista == "busqueda" else None
            texto = letterboxd.texto_torrent(p, pedido)
        pagina = BUSCAR_TORRENT_TODO if p.get("tipo") == "serie" else BUSCAR_TORRENT
        self.estado.setText(f"Buscando el torrent de «{texto}» en ext.to…")

        def buscar_ext_to() -> str | None:
            """El primer link magnet de la búsqueda (en segundo plano: acá no se toca la interfaz)."""
            respuesta = requests.get(pagina.format(quote_plus(texto)), timeout=15)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, "html.parser")
            return next((a["href"] for a in soup.find_all("a", href=True)
                         if re.match(r"(?i)magnet:\?xt=urn:bt", a["href"])), None)

        def listo(magnet: str | None):
            if not magnet:
                return self._abrir_busqueda(p, texto)
            # Con _esperando puesto, copiar el magnet lo pone a bajar solo (_portapapeles)
            self._esperando = p
            QGuiApplication.clipboard().setText(magnet)

        en_segundo_plano(buscar_ext_to, listo, lambda _m: self._abrir_busqueda(p, texto))

    def _abrir_busqueda(self, p: dict, texto: str):
        """Si ext.to no se pudo leer (Cloudflare, sin internet, sin resultados): la búsqueda en el navegador."""
        # Copiado también, por si la página no muestra la búsqueda hecha: se pega con Ctrl+V en su buscador
        QGuiApplication.clipboard().setText(texto)
        busqueda = self.bib.config("letterboxd_busqueda") or (
            BUSCAR_TORRENT_TODO if p.get("tipo") == "serie" else BUSCAR_TORRENT)
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
        """Si después de buscar una película se copia un link magnet, se pone a bajar solo (sin preguntar).
        Solo el primero que se copie después de la búsqueda: los siguientes se ignoran hasta buscar otra."""
        p = self._esperando
        texto = QGuiApplication.clipboard().text().strip()
        if p is None or self.torrents is None or not re.match(r"(?i)magnet:\?xt=urn:bt", texto):
            return
        self._esperando = None
        try:
            self.torrents.agregar(texto)
            self.estado.setText(f"«{p['titulo']}» se está bajando: mirá el avance en 🧲 Torrents")
        except Exception as e:  # noqa: BLE001 - aria2 no arrancó, link roto…
            self.estado.setText(f"No se pudo agregar el torrent: {e}")
