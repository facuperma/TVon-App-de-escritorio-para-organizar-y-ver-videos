"""🛠 Modo desarrollador (Ctrl+2, 3): retocar la interfaz a gusto y verlo al instante. Colores, letra, tamaño y aire; el
orden, los nombres y cuáles se ven de los botones de la barra; qué controles del reproductor y qué secciones se ven; el
orden de las columnas; y presets con nombre (guardar, cargar, exportar, importar, volver a lo de fábrica)."""
from __future__ import annotations

import copy
import json

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QFileDialog, QFontComboBox, QFormLayout, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import diseno
from .temas import TEMAS

ROL = Qt.UserRole


class VentanaDesarrollador(QDialog):
    cambio = Signal(dict)      # el diseño nuevo, para aplicarlo en la ventana principal

    def __init__(self, d: dict, tema_actual, presets: dict, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("🛠 Modo desarrollador — TorrentVision")
        self.resize(760, 640)
        self.d = diseno.normalizar(d)
        self.tema = tema_actual
        self.presets = presets
        self._aplicar_luego = QTimer(self, singleShot=True, interval=120, timeout=lambda: self.cambio.emit(copy.deepcopy(self.d)))
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel("Todo lo que cambies acá se ve al instante y queda guardado. «Volver a lo de fábrica» lo "
                              "deshace todo.", objectName="pista", wordWrap=True))
        self.pestanas = QTabWidget()
        self.pestanas.addTab(self._armar_estilo(), "🎨 Colores y letra")
        self.pestanas.addTab(self._armar_botones(), "🔘 Botones")
        self.pestanas.addTab(self._armar_secciones(), "🧩 Secciones")
        self.pestanas.addTab(self._armar_presets(), "💾 Presets")
        capa.addWidget(self.pestanas, 1)
        fila = QHBoxLayout()
        fabrica = QPushButton("↺ Volver a lo de fábrica", objectName="peligro")
        fabrica.clicked.connect(self._fabrica)
        cerrar = QPushButton("Listo", objectName="primario")
        cerrar.clicked.connect(self.close)
        fila.addWidget(fabrica)
        fila.addStretch()
        fila.addWidget(cerrar)
        capa.addLayout(fila)

    def _cambio(self):
        self._aplicar_luego.start()

    # --- Colores y letra ----------------------------------------------------------------------------------
    def _armar_estilo(self) -> QWidget:
        hoja = QWidget()
        capa = QVBoxLayout(hoja)
        form = QFormLayout()
        self.letra = QFontComboBox()
        self.letra.setCurrentFont(QFont(self.d["letra"] or self.tema.letra))
        self.letra.currentFontChanged.connect(lambda f: (self.d.__setitem__("letra", f.family()), self._cambio()))
        form.addRow("Letra", self.letra)
        self.tam = QSpinBox(minimum=7, maximum=18, value=self.d["tam_letra"], suffix=" pt")
        self.tam.valueChanged.connect(lambda v: (self.d.__setitem__("tam_letra", v), self._cambio()))
        form.addRow("Tamaño de la letra", self.tam)
        self.radio = QSpinBox(minimum=0, maximum=24, value=self.d["radio"] if self.d["radio"] is not None else self.tema.radio, suffix=" px")
        self.radio.valueChanged.connect(lambda v: (self.d.__setitem__("radio", v), self._cambio()))
        form.addRow("Esquinas redondeadas", self.radio)
        self.aire = QSlider(Qt.Horizontal, minimum=50, maximum=180, value=self.d["aire"])
        self.lbl_aire = QLabel(f"{self.d['aire']} %")
        self.aire.valueChanged.connect(self._aire)
        fila_aire = QHBoxLayout()
        fila_aire.addWidget(self.aire, 1)
        fila_aire.addWidget(self.lbl_aire)
        form.addRow("Aire dentro de botones y filas", fila_aire)
        capa.addLayout(form)
        capa.addWidget(QLabel("<b>Colores</b> (tocá uno para cambiarlo; ↺ lo deja como el tema)"))
        grilla = QGridLayout()
        self._botones_color = {}
        for n, (campo, texto) in enumerate(diseno.COLORES):
            b = QPushButton()
            b.setFixedSize(46, 26)
            b.clicked.connect(lambda _=False, c=campo: self._elegir_color(c))
            deshacer = QPushButton("↺", objectName="chico", toolTip="Como el tema")
            deshacer.clicked.connect(lambda _=False, c=campo: self._color_tema(c))
            self._botones_color[campo] = b
            fila, col = divmod(n, 2)
            grilla.addWidget(QLabel(texto), fila, col * 3)
            grilla.addWidget(b, fila, col * 3 + 1)
            grilla.addWidget(deshacer, fila, col * 3 + 2)
        capa.addLayout(grilla)
        capa.addStretch()
        self._pintar_colores()
        return hoja

    def _aire(self, v):
        self.d["aire"] = v
        self.lbl_aire.setText(f"{v} %")
        self._cambio()

    def _color(self, campo) -> str:
        return self.d["colores"].get(campo) or getattr(self.tema, campo)

    def _pintar_colores(self):
        for campo, b in self._botones_color.items():
            c = self._color(campo)
            if not c.startswith("#"):
                c = "#808080"       # un degradé del tema: se muestra gris
            b.setStyleSheet(f"QPushButton {{ background: {c}; border: 2px solid {'#ffffff' if campo in self.d['colores'] else '#555'}; border-radius: 6px; }}")

    def _elegir_color(self, campo):
        actual = self._color(campo)
        color = QColorDialog.getColor(QColor(actual if actual.startswith("#") else "#808080"), self, "Elegí un color")
        if color.isValid():
            self.d["colores"][campo] = color.name()
            self._pintar_colores()
            self._cambio()

    def _color_tema(self, campo):
        self.d["colores"].pop(campo, None)
        self._pintar_colores()
        self._cambio()

    # --- Botones -------------------------------------------------------------------------------------------
    def _armar_botones(self) -> QWidget:
        hoja = QWidget()
        capa = QVBoxLayout(hoja)
        capa.addWidget(QLabel("<b>Barra de botones de arriba</b>: arrastralos para cambiar el orden, destildá los que no "
                              "quieras ver y cambiales el nombre abajo.", wordWrap=True))
        self.lista_barra = QListWidget()
        self.lista_barra.setDragDropMode(QListWidget.InternalMove)
        for clave in self.d["barra"]["orden"]:
            self._item_barra(clave)
        self.lista_barra.model().rowsMoved.connect(lambda *_: self._leer_barra())
        self.lista_barra.itemChanged.connect(lambda _i: self._leer_barra())
        self.lista_barra.currentItemChanged.connect(self._mostrar_nombre)
        capa.addWidget(self.lista_barra, 1)
        fila = QHBoxLayout()
        self.nombre_boton = QLineEdit(placeholderText="Nombre del botón elegido (vacío: el de siempre)")
        self.nombre_boton.editingFinished.connect(self._renombrar)
        sep = QPushButton("+ Separación")
        sep.clicked.connect(lambda: (self._item_barra("|"), self._leer_barra()))
        quitar = QPushButton("− Quitar separación")
        quitar.clicked.connect(self._quitar_separacion)
        fila.addWidget(self.nombre_boton, 1)
        fila.addWidget(sep)
        fila.addWidget(quitar)
        capa.addLayout(fila)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Cómo se ven:"))
        self.estilo_barra = QComboBox()
        for k, v in diseno.ESTILOS_BARRA.items():
            self.estilo_barra.addItem(v, k)
        self.estilo_barra.setCurrentIndex(max(0, self.estilo_barra.findData(self.d["barra"]["estilo"])))
        self.estilo_barra.currentIndexChanged.connect(lambda _i: (self.d["barra"].__setitem__("estilo", self.estilo_barra.currentData()), self._cambio()))
        fila.addWidget(self.estilo_barra, 1)
        capa.addLayout(fila)
        capa.addWidget(QLabel("<b>Controles del reproductor</b> (lo que no se vea sigue en el teclado y en el menú «⋯»)"))
        self.lista_controles = QListWidget()
        for clave, texto in diseno.CONTROLES.items():
            it = QListWidgetItem(texto)
            it.setData(ROL, clave)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if clave in self.d["controles_ocultos"] else Qt.Checked)
            self.lista_controles.addItem(it)
        self.lista_controles.itemChanged.connect(self._leer_controles)
        capa.addWidget(self.lista_controles, 1)
        return hoja

    def _item_barra(self, clave):
        if clave == "|":
            it = QListWidgetItem("──────── separación ────────")
            it.setFlags((it.flags() | Qt.ItemIsDragEnabled) & ~Qt.ItemIsUserCheckable)
        else:
            texto = self.d["barra"]["textos"].get(clave) or diseno.NOMBRES_BARRA[clave]
            it = QListWidgetItem(texto)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled)
            it.setCheckState(Qt.Unchecked if clave in self.d["barra"]["ocultos"] else Qt.Checked)
        it.setData(ROL, clave)
        self.lista_barra.addItem(it)

    def _leer_barra(self):
        orden, ocultos = [], []
        for i in range(self.lista_barra.count()):
            it = self.lista_barra.item(i)
            clave = it.data(ROL)
            orden.append(clave)
            if clave != "|" and it.checkState() == Qt.Unchecked:
                ocultos.append(clave)
        self.d["barra"]["orden"], self.d["barra"]["ocultos"] = orden, ocultos
        self._cambio()

    def _mostrar_nombre(self, it, _anterior=None):
        clave = it.data(ROL) if it else None
        self.nombre_boton.setEnabled(bool(clave) and clave != "|")
        self.nombre_boton.setText(self.d["barra"]["textos"].get(clave, "") if clave else "")

    def _renombrar(self):
        it = self.lista_barra.currentItem()
        if not it or it.data(ROL) == "|":
            return
        clave, texto = it.data(ROL), self.nombre_boton.text().strip()
        if texto:
            self.d["barra"]["textos"][clave] = texto
        else:
            self.d["barra"]["textos"].pop(clave, None)
        self.lista_barra.blockSignals(True)
        it.setText(texto or diseno.NOMBRES_BARRA[clave])
        self.lista_barra.blockSignals(False)
        self._cambio()

    def _quitar_separacion(self):
        it = self.lista_barra.currentItem()
        if it and it.data(ROL) == "|":
            self.lista_barra.takeItem(self.lista_barra.row(it))
            self._leer_barra()

    def _leer_controles(self, _it=None):
        self.d["controles_ocultos"] = [self.lista_controles.item(i).data(ROL) for i in range(self.lista_controles.count())
                                       if self.lista_controles.item(i).checkState() == Qt.Unchecked]
        self._cambio()

    # --- Secciones ----------------------------------------------------------------------------------------
    def _armar_secciones(self) -> QWidget:
        hoja = QWidget()
        capa = QVBoxLayout(hoja)
        capa.addWidget(QLabel("<b>Qué se ve</b>"))
        self._casillas = {}
        for clave, texto in diseno.SECCIONES.items():
            c = QCheckBox(texto)
            c.setChecked(clave not in self.d["secciones_ocultas"])
            c.toggled.connect(self._leer_secciones)
            self._casillas[clave] = c
            capa.addWidget(c)
        capa.addWidget(QLabel("<b>Orden de las columnas</b> (de izquierda a derecha)"))
        self.orden_columnas = QComboBox()
        from itertools import permutations
        for orden in permutations(diseno.COLUMNAS):
            self.orden_columnas.addItem("  ·  ".join(diseno.COLUMNAS[c] for c in orden), list(orden))
        for i in range(self.orden_columnas.count()):
            if self.orden_columnas.itemData(i) == self.d["columnas"]:
                self.orden_columnas.setCurrentIndex(i)
        self.orden_columnas.currentIndexChanged.connect(lambda _i: (self.d.__setitem__("columnas", list(self.orden_columnas.currentData())), self._cambio()))
        capa.addWidget(self.orden_columnas)
        capa.addStretch()
        return hoja

    def _leer_secciones(self):
        self.d["secciones_ocultas"] = [k for k, c in self._casillas.items() if not c.isChecked()]
        self._cambio()

    # --- Presets ------------------------------------------------------------------------------------------
    def _armar_presets(self) -> QWidget:
        hoja = QWidget()
        capa = QVBoxLayout(hoja)
        capa.addWidget(QLabel("Guardá cómo dejaste la interfaz con un nombre y volvé a él cuando quieras.", wordWrap=True))
        self.lista_presets = QListWidget()
        self._pintar_presets()
        capa.addWidget(self.lista_presets, 1)
        fila = QHBoxLayout()
        for texto, accion in (("💾 Guardar como…", self._guardar_preset), ("📂 Cargar", self._cargar_preset),
                              ("🗑 Borrar", self._borrar_preset)):
            b = QPushButton(texto)
            b.clicked.connect(accion)
            fila.addWidget(b)
        capa.addLayout(fila)
        fila = QHBoxLayout()
        exportar = QPushButton("⬆ Exportar a un archivo…")
        exportar.clicked.connect(self._exportar)
        importar = QPushButton("⬇ Importar de un archivo…")
        importar.clicked.connect(self._importar)
        fila.addWidget(exportar)
        fila.addWidget(importar)
        capa.addLayout(fila)
        capa.addWidget(QLabel("<b>Empezar desde un tema</b>: copia sus colores (después los retocás)."))
        fila = QHBoxLayout()
        self.combo_temas = QComboBox()
        for t in TEMAS:
            self.combo_temas.addItem(t.nombre, t.id)
        copiar = QPushButton("Copiar colores")
        copiar.clicked.connect(self._copiar_tema)
        fila.addWidget(self.combo_temas, 1)
        fila.addWidget(copiar)
        capa.addLayout(fila)
        return hoja

    def _pintar_presets(self):
        self.lista_presets.clear()
        for nombre in sorted(self.presets):
            self.lista_presets.addItem(nombre)

    def _guardar_preset(self):
        nombre, ok = QInputDialog.getText(self, "Guardar preset", "Nombre:")
        if ok and nombre.strip():
            self.presets[nombre.strip()[:40]] = copy.deepcopy(self.d)
            self._pintar_presets()
            self.cambio.emit(copy.deepcopy(self.d))

    def _cargar_preset(self):
        it = self.lista_presets.currentItem()
        if it:
            self._reemplazar(self.presets[it.text()])

    def _borrar_preset(self):
        it = self.lista_presets.currentItem()
        if it:
            self.presets.pop(it.text(), None)
            self._pintar_presets()
            self.cambio.emit(copy.deepcopy(self.d))

    def _exportar(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar diseño", "diseno_torrentvision.json", "JSON (*.json)")
        if ruta:
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False, indent=2)

    def _importar(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Importar diseño", "", "JSON (*.json)")
        if ruta:
            try:
                with open(ruta, encoding="utf-8") as f:
                    self._reemplazar(diseno.normalizar(json.load(f)))
            except (OSError, ValueError) as e:
                QMessageBox.warning(self, "Importar", f"No se pudo leer el archivo: {e}")

    def _copiar_tema(self):
        t = next(x for x in TEMAS if x.id == self.combo_temas.currentData())
        self.d["colores"] = {c: getattr(t, c) for c, _ in diseno.COLORES if getattr(t, c).startswith("#")}
        self._pintar_colores()
        self._cambio()

    def _fabrica(self):
        if QMessageBox.question(self, "Volver a lo de fábrica", "¿Deshacer todos los retoques de la interfaz?") == QMessageBox.Yes:
            self._reemplazar(diseno.normalizar({}))

    def _reemplazar(self, d: dict):
        """Pone otro diseño entero y rearma esta ventana para que lo muestre."""
        self.d = diseno.normalizar(d)
        actual = self.pestanas.currentIndex()
        for i, (armar, texto) in enumerate(((self._armar_estilo, "🎨 Colores y letra"), (self._armar_botones, "🔘 Botones"),
                                            (self._armar_secciones, "🧩 Secciones"))):
            vieja = self.pestanas.widget(i)
            self.pestanas.removeTab(i)
            self.pestanas.insertTab(i, armar(), texto)
            vieja.deleteLater()
        self.pestanas.setCurrentIndex(actual)
        self.cambio.emit(copy.deepcopy(self.d))
