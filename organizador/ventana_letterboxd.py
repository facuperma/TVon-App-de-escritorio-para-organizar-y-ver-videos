"""Ventana de Letterboxd: tu watchlist y las mejor puntuadas, marcando las que ya están en la biblioteca."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import letterboxd
from .db import Biblioteca
from .tareas import en_segundo_plano

ROL = Qt.UserRole
SITIO_PELICULAS = "https://ext.to/"


class VentanaLetterboxd(QWidget):
    def __init__(self, bib: Biblioteca):
        super().__init__(None, Qt.Window)
        self.bib = bib
        self.setWindowTitle("Letterboxd — TorrentVision")
        self.resize(820, 600)
        self._listas: dict[str, list[dict]] = {}  # lo ya traído, para no volver a pedirlo
        self._vista = "watchlist"

        self.usuario = QLineEdit(bib.config("letterboxd_usuario"), placeholderText="Tu usuario de Letterboxd",
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
        self.lista.setHeaderLabels(["Película", "Año", "En tu biblioteca"])
        self.lista.setRootIsDecorated(False)
        self.lista.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lista.itemDoubleClicked.connect(lambda item: self._abrir_ficha([item]))

        btn_buscar = QPushButton("🔎 Buscar para bajar", objectName="primario")
        btn_buscar.setToolTip("Copia «Título Año» y abre la página de películas: pegalo en su buscador\n"
                              "y el link magnet, en 🧲 Torrents")
        btn_buscar.clicked.connect(self._buscar)
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
                              "como la ve cualquiera.", objectName="pista", wordWrap=True))
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
            esta = letterboxd.en_biblioteca(p, claves)
            tengo += esta
            if esta and self.chk_ocultar.isChecked():
                continue
            item = QTreeWidgetItem([p["titulo"], p["anio"], "✓ Ya la tenés" if esta else ""])
            item.setData(0, ROL, p)
            if esta:
                for col in range(3):
                    item.setForeground(col, QBrush(QColor("#86efac")))
            self.lista.addTopLevelItem(item)
        nombre = "tu watchlist" if self._vista == "watchlist" else "las mejor puntuadas"
        self.estado.setText(f"{len(pelis)} películas en {nombre} · {tengo} ya en tu biblioteca · "
                            f"{len(pelis) - tengo} para bajar")

    def _seleccion(self, items) -> list[dict]:
        return [i.data(0, ROL) for i in items if i.data(0, ROL)]

    def _abrir_ficha(self, items):
        for p in self._seleccion(items)[:5]:
            QDesktopServices.openUrl(QUrl(p["url"]))

    def _buscar(self):
        pelis = self._seleccion(self.lista.selectedItems())
        if not pelis:
            return self.estado.setText("Elegí una película de la lista")
        p = pelis[0]
        QGuiApplication.clipboard().setText(f"{p['titulo']} {p['anio']}".strip())
        QDesktopServices.openUrl(QUrl(SITIO_PELICULAS))
        self.estado.setText(f"Se copió «{p['titulo']} {p['anio']}»: pegalo en el buscador de la página "
                            "y el link magnet, en 🧲 Torrents")
