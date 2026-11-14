"""Modo simple: navegar las películas y series que ya tenés como en la app del celular (o Netflix).

A la izquierda, una grilla de pósters (Películas · Series, con buscador). Al elegir uno, en el lugar del reproductor
aparece su ficha grande: póster, año, géneros, puntaje y de qué trata, con «▶ Reproducir» (y en las series, la lista
de capítulos). No tiene botones de organizar ni de bajar: es solo para elegir qué ver, cómodo.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from . import fichas as F
from .titulos import nombre_lindo

ANCHO, ALTO = 150, 225          # el póster de cada tarjeta
ROL = Qt.UserRole


def _tarjeta(ruta_poster: str | None, titulo: str, progreso: float = 0.0, visto: bool = False) -> QPixmap:
    """El póster con las puntas redondeadas (o uno dibujado con el título, si no hay), con la barrita de
    «por dónde ibas» abajo y un ✓ si ya la viste."""
    pix = QPixmap(ANCHO, ALTO)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
    forma = QPainterPath()
    forma.addRoundedRect(QRectF(0, 0, ANCHO, ALTO), 10, 10)
    p.setClipPath(forma)
    imagen = QPixmap(ruta_poster) if ruta_poster else QPixmap()
    if not imagen.isNull():
        esc = imagen.scaled(ANCHO, ALTO, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        p.drawPixmap(int((ANCHO - esc.width()) / 2), int((ALTO - esc.height()) / 2), esc)
    else:
        tono = (sum(map(ord, titulo)) * 37) % 360
        g = QLinearGradient(0, 0, ANCHO, ALTO)
        g.setColorAt(0, QColor.fromHsl(tono, 120, 70))
        g.setColorAt(1, QColor.fromHsl((tono + 40) % 360, 140, 30))
        p.fillRect(pix.rect(), g)
        f = QFont()
        f.setPixelSize(17)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff"))
        p.drawText(QRectF(10, 10, ANCHO - 20, ALTO - 20), Qt.AlignCenter | Qt.TextWordWrap, titulo)
    if progreso > 0.02 and not visto:
        p.fillRect(QRectF(0, ALTO - 6, ANCHO, 6), QColor(0, 0, 0, 170))
        p.fillRect(QRectF(0, ALTO - 6, ANCHO * min(1.0, progreso), 6), QColor("#e50914"))
    if visto:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 150, 70, 230))
        p.drawEllipse(QRectF(ANCHO - 34, 8, 26, 26))
        p.setPen(QColor("white"))
        f = QFont()
        f.setPixelSize(16)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(ANCHO - 34, 8, 26, 26), Qt.AlignCenter, "✓")
    p.setClipping(False)
    p.setPen(QColor(255, 255, 255, 40))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(0.5, 0.5, ANCHO - 1, ALTO - 1), 10, 10)
    p.end()
    return pix


class GrillaSimple(QWidget):
    """La grilla de pósters con las pestañas Películas · Series y el buscador."""
    elegido = Signal(dict)          # {"tipo": "pelicula"|"serie", ...}
    reproducir = Signal(str)        # doble clic en una película
    salir = Signal()
    menu_pedido = Signal(dict, QPoint)   # clic derecho en un póster (el menú lo arma la ventana, como en la lista)

    def __init__(self, bib, parent=None):
        super().__init__(parent)
        self.bib = bib
        self.setObjectName("modoSimple")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(14, 12, 8, 8)
        capa.setSpacing(10)
        arriba = QHBoxLayout()
        titulo = QLabel("🎬 Tu videoteca")
        titulo.setStyleSheet("font-size: 17pt; font-weight: 700; background: transparent;")
        arriba.addWidget(titulo)
        arriba.addSpacing(12)
        self.btn_pelis = QPushButton("Películas", checkable=True, checked=True)
        self.btn_series = QPushButton("Series", checkable=True)
        for b in (self.btn_pelis, self.btn_series):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(32)
            arriba.addWidget(b)
        self.btn_pelis.clicked.connect(lambda: self._pestana("pelicula"))
        self.btn_series.clicked.connect(lambda: self._pestana("serie"))
        arriba.addStretch(1)
        self.buscador = QLineEdit(placeholderText="🔎 Buscar…", clearButtonEnabled=True)
        self.buscador.setMinimumHeight(32)
        self.buscador.setMaximumWidth(280)
        self.buscador.textChanged.connect(self._filtrar)
        arriba.addWidget(self.buscador)
        salir = QPushButton("✕ Salir del modo simple")
        salir.setCursor(Qt.PointingHandCursor)
        salir.setMinimumHeight(32)
        salir.clicked.connect(self.salir)
        arriba.addWidget(salir)
        capa.addLayout(arriba)

        self.grilla = QListWidget()
        self.grilla.setViewMode(QListView.IconMode)
        self.grilla.setIconSize(QSize(ANCHO, ALTO))
        self.grilla.setGridSize(QSize(ANCHO + 26, ALTO + 54))
        self.grilla.setResizeMode(QListView.Adjust)
        self.grilla.setMovement(QListView.Static)
        self.grilla.setUniformItemSizes(True)
        self.grilla.setWordWrap(True)
        self.grilla.setSpacing(6)
        self.grilla.setFrameShape(QListWidget.NoFrame)
        self.grilla.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.grilla.verticalScrollBar().setSingleStep(24)
        from . import suave
        suave.activar(self.grilla)
        self.grilla.setStyleSheet("QListWidget { background: transparent; } "
                                  "QListWidget::item { border-radius: 12px; padding: 6px; } ")
        self.grilla.currentItemChanged.connect(lambda item, _a: item and self.elegido.emit(item.data(ROL)))
        self.grilla.itemDoubleClicked.connect(self._doble)
        self.grilla.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grilla.customContextMenuRequested.connect(self._menu)
        capa.addWidget(self.grilla, 1)
        self.vacio = QLabel("", alignment=Qt.AlignCenter, objectName="pista", wordWrap=True)
        capa.addWidget(self.vacio)
        self.vacio.hide()
        # Abajo a la izquierda: esconder lo que ya viste (se recuerda)
        abajo = QHBoxLayout()
        self.btn_vistas = QPushButton("👁 Ocultar las vistas", checkable=True, objectName="chico",
                                      toolTip="Esconder las películas y series que ya viste completas")
        self.btn_vistas.setCursor(Qt.PointingHandCursor)
        self.btn_vistas.setChecked(bib.config("simple_ocultar_vistas") == "1")
        self.btn_vistas.toggled.connect(self._ocultar_vistas)
        abajo.addWidget(self.btn_vistas)
        abajo.addStretch(1)
        capa.addLayout(abajo)
        self.tipo = "pelicula"
        if self.btn_vistas.isChecked():
            self.btn_vistas.setText("👁 Mostrar las vistas")
        self._cache: dict[tuple, QIcon] = {}

    def _pestana(self, tipo: str):
        self.tipo = tipo
        self.btn_pelis.setChecked(tipo == "pelicula")
        self.btn_series.setChecked(tipo == "serie")
        self.cargar()

    def cargar(self):
        """Arma la grilla con lo que hay ahora en la biblioteca (y las fichas que ya se encontraron)."""
        peliculas, series = F.agrupar(self.bib)
        todas = F.fichas(self.bib)
        progresos = self.bib.progresos()
        actual = self.grilla.currentItem().data(ROL).get("clave") if self.grilla.currentItem() else None
        self.grilla.blockSignals(True)
        self.grilla.clear()
        elementos = []
        if self.tipo == "pelicula":
            for p in peliculas:
                fi = todas.get(p["clave"])
                pos, dur, visto = progresos.get(p["ruta"], (0, 0, False))
                titulo = (fi or {}).get("titulo") or p["titulo"]
                elementos.append({"tipo": "pelicula", "clave": p["clave"], "titulo": titulo,
                                  "anio": (fi or {}).get("anio") or p["anio"], "ruta": p["ruta"], "ficha": fi,
                                  "progreso": (pos / dur) if dur else 0.0, "visto": bool(visto)})
        else:
            for s in series.values():
                fi = todas.get(s["clave"])
                caps = s["episodios"]
                vistos = sum(1 for e in caps if progresos.get(e["ruta"], (0, 0, False))[2])
                titulo = (fi or {}).get("titulo") or s["titulo"]
                elementos.append({"tipo": "serie", "clave": s["clave"], "titulo": titulo, "anio": (fi or {}).get("anio"),
                                  "episodios": caps, "ficha": fi, "progreso": vistos / max(1, len(caps)),
                                  "visto": vistos == len(caps) and bool(caps)})
        elementos.sort(key=lambda e: e["titulo"].lower())
        for e in elementos:
            clave_icono = (F.poster(e["ficha"]), e["titulo"], round(e["progreso"], 2), e["visto"])
            if clave_icono not in self._cache:
                self._cache[clave_icono] = QIcon(_tarjeta(*clave_icono))
            # Sin póster el título ya está dibujado en la tarjeta: abajo va solo el año (no repetirlo)
            titulo = e["titulo"] if clave_icono[0] else ""
            extra = f"{len(e['episodios'])} capítulos" if e["tipo"] == "serie" else str(e.get("anio") or "")
            texto = "\n".join(x for x in (titulo, extra) if x) or " "
            item = QListWidgetItem(self._cache[clave_icono], texto)
            item.setData(ROL, e)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setToolTip(e["titulo"])
            self.grilla.addItem(item)
            if e["clave"] == actual:
                self.grilla.setCurrentItem(item)
        self.grilla.blockSignals(False)
        self.vacio.setVisible(not elementos)
        self.vacio.setText("Todavía no hay películas en tu biblioteca." if self.tipo == "pelicula"
                           else "Todavía no hay series en tu biblioteca.")
        self._filtrar(self.buscador.text())

    def _ocultar_vistas(self, si: bool):
        self.bib.guardar_config("simple_ocultar_vistas", "1" if si else "0")
        self.btn_vistas.setText("👁 Mostrar las vistas" if si else "👁 Ocultar las vistas")
        self._filtrar(self.buscador.text())

    def _filtrar(self, texto: str):
        t = texto.strip().lower()
        sin_vistas = self.btn_vistas.isChecked()
        for i in range(self.grilla.count()):
            item = self.grilla.item(i)
            e = item.data(ROL)
            item.setHidden((bool(t) and t not in e["titulo"].lower()) or (sin_vistas and e["visto"]))

    def _menu(self, pos):
        item = self.grilla.itemAt(pos)
        if item is not None:
            self.grilla.setCurrentItem(item)
            self.menu_pedido.emit(item.data(ROL), self.grilla.viewport().mapToGlobal(pos))

    def _doble(self, item):
        e = item.data(ROL)
        if e["tipo"] == "pelicula":
            self.reproducir.emit(e["ruta"])


class FichaSimple(QWidget):
    """La ficha grande, en el lugar del reproductor."""
    reproducir = Signal(str)
    en_ventana = Signal(str)

    def __init__(self, bib, parent=None):
        super().__init__(parent)
        self.bib = bib
        self.setObjectName("fichaSimple")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(18, 16, 18, 16)
        capa.setSpacing(14)
        arriba = QHBoxLayout()
        arriba.setSpacing(20)
        self.poster = QLabel(alignment=Qt.AlignTop | Qt.AlignHCenter)
        self.poster.setFixedWidth(240)
        arriba.addWidget(self.poster)
        datos = QVBoxLayout()
        datos.setSpacing(8)
        # Con hoja de estilo: el tema pone el tamaño de letra de todos los QLabel y le ganaría a setFont
        self.titulo = QLabel(wordWrap=True)
        self.titulo.setStyleSheet("font-size: 26pt; font-weight: 800; background: transparent;")
        self.meta = QLabel(wordWrap=True, objectName="pista")
        self.meta.setStyleSheet("font-size: 12pt; background: transparent;")
        self.sinopsis = QLabel(wordWrap=True, alignment=Qt.AlignTop | Qt.AlignLeft)
        self.sinopsis.setStyleSheet("font-size: 13pt; line-height: 140%; background: transparent;")
        self.sinopsis.setTextInteractionFlags(Qt.TextSelectableByMouse)
        desplazable = QScrollArea(widgetResizable=True, frameShape=QScrollArea.NoFrame)
        desplazable.setWidget(self.sinopsis)
        desplazable.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.boton = QPushButton("▶  Reproducir", objectName="primario")
        self.boton.setCursor(Qt.PointingHandCursor)
        self.boton.setMinimumHeight(44)
        self.boton.setStyleSheet("font-size: 13pt; font-weight: 700; padding: 8px 26px;")
        self.boton.clicked.connect(self._reproducir)
        datos.addWidget(self.titulo)
        datos.addWidget(self.meta)
        desplazable.setMinimumHeight(170)
        desplazable.setMaximumHeight(320)
        datos.addWidget(desplazable)
        datos.addSpacing(6)
        fila = QHBoxLayout()
        fila.addWidget(self.boton)
        # Como en el modo normal: verla en una ventana aparte (que se puede dejar siempre encima)
        self.btn_ventana = QPushButton("⧉ Ventana", toolTip="Abrir en una ventana aparte")
        self.btn_ventana.setCursor(Qt.PointingHandCursor)
        self.btn_ventana.setMinimumHeight(44)
        self.btn_ventana.clicked.connect(lambda: self._ruta and self.en_ventana.emit(self._ruta))
        fila.addWidget(self.btn_ventana)
        fila.addStretch(1)
        datos.addLayout(fila)
        datos.addStretch(1)
        arriba.addLayout(datos, 1)
        capa.addLayout(arriba, 3)
        self.capitulos = QListWidget()
        self.capitulos.itemDoubleClicked.connect(lambda it: self.reproducir.emit(it.data(ROL)))
        self.capitulos.setMinimumHeight(140)
        capa.addWidget(self.capitulos, 2)
        self._ruta = ""
        self.mostrar(None)

    def mostrar(self, e: dict | None):
        if not e:
            self.titulo.setText("Elegí una película o una serie")
            self.meta.setText("")
            self.sinopsis.setText("Tocá un póster de la izquierda para ver de qué trata. Doble clic para verla.")
            self.poster.clear()
            self.boton.hide()
            self.btn_ventana.hide()
            self.capitulos.hide()
            return
        fi = e.get("ficha") or {}
        pix = _tarjeta(F.poster(fi), e["titulo"], 0.0, False).scaled(240, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.poster.setPixmap(pix)
        self.titulo.setText(e["titulo"])
        partes = []
        if e.get("anio"):
            partes.append(str(e["anio"]))
        if F.generos(fi):
            partes.append(" · ".join(F.generos(fi)[:4]))
        if fi.get("puntaje"):
            partes.append(f"⭐ {float(fi['puntaje']):.1f}")
        if e["tipo"] == "serie":
            partes.append(f"{len(e['episodios'])} capítulos")
        self.meta.setText("   ·   ".join(partes))
        self.sinopsis.setText(fi.get("sinopsis") or "Todavía no hay una descripción de esta. TorrentVision la busca "
                              "sola en internet; si salió mal, en el modo normal: clic derecho → Corregir ficha.")
        progresos = self.bib.progresos()
        self.boton.show()
        self.btn_ventana.show()
        if e["tipo"] == "pelicula":
            self._ruta = e["ruta"]
            pos, dur, visto = progresos.get(e["ruta"], (0, 0, False))
            self.boton.setText("▶  Seguir viendo" if pos > 60000 and not visto else "▶  Reproducir")
            self.capitulos.hide()
            return
        self.capitulos.clear()
        siguiente = None
        for cap in e["episodios"]:
            pos, dur, visto = progresos.get(cap["ruta"], (0, 0, False))
            marca = "✓ " if visto else ("◐ " if pos > 60000 else "    ")
            item = QListWidgetItem(f"{marca}T{cap['temporada']} · Capítulo {cap['episodio']}   —   {nombre_lindo(cap['nombre'])}")
            item.setData(ROL, cap["ruta"])
            self.capitulos.addItem(item)
            if siguiente is None and not visto:
                siguiente = cap
        siguiente = siguiente or (e["episodios"][0] if e["episodios"] else None)
        self._ruta = siguiente["ruta"] if siguiente else ""
        self.boton.setText(f"▶  T{siguiente['temporada']} · Cap. {siguiente['episodio']}" if siguiente else "▶  Reproducir")
        self.capitulos.show()

    def _reproducir(self):
        if self._ruta:
            self.reproducir.emit(self._ruta)
