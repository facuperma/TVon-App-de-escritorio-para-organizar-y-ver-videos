"""Tu BiriBiri (el muñequito 3D): editarlo, la cuenta (usuario y contraseña, sin correo) y los amigos con sus puntos."""
from __future__ import annotations

import base64
import json
import random

from PySide6.QtCore import QBuffer, QByteArray, QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider, QStackedWidget, QTabWidget,
    QVBoxLayout, QWidget,
)

from . import avatar3d, social, vista3d
from . import casa as modelo_casa
from . import mascotas
from .casa_ui import EscenaCasa
from .tareas import en_segundo_plano

PALETAS = {
    "piel": ("#f6d3b8", "#e8b896", "#d29b72", "#b07850", "#8d5a3b", "#5c3a24"),
    "pelo": ("#111111", "#3b2a1e", "#7a3b2e", "#d9a13b", "#e8e1d0", "#8a5cd1", "#2ec5d6"),
    "ojos": ("#2b1d14", "#3d6fb3", "#3f8a4f", "#111111"),
    "remera": ("#2f7fd1", "#d4513d", "#2e9f6b", "#8a5cd1", "#e0a21a", "#3a4a63", "#f2f2f2", "#1d1d1f"),
    "estampa_color": ("#f2f2f2", "#1d1d1f", "#e0a21a", "#d4513d", "#2ec5d6", "#e8707a"),
    "pantalon": ("#2b3a55", "#1d1d1f", "#5b4636", "#3c6e9e", "#7a7f87"),
    "zapatillas": ("#f2f2f2", "#1d1d1f", "#d4513d", "#2f7fd1"),
    "accesorio_color": ("#d4513d", "#2f7fd1", "#1d1d1f", "#e0a21a", "#2e9f6b", "#f2f2f2"),
    "mascota_color": tuple(mascotas.PALETA_PELAJE),
    "mascota_color2": tuple(mascotas.PALETA_SECUNDARIO),
    "lentes_color": ("#151515", "#f4f4f4", "#d4513d", "#2f7fd1", "#e0a21a", "#2e9f6b", "#8a5cd1", "#e8707a", "#7a7f87"),
}
NOMBRES = {"piel": "Piel", "pelo": "Pelo", "ojos": "Ojos", "remera": "Ropa", "estampa_color": "Detalles", "pantalon": "Pantalón",
           "zapatillas": "Zapatillas", "accesorio_color": "Color de los accesorios", "lentes_color": "Borde de los lentes",
           "mascota_color": "Pelaje", "mascota_color2": "Color secundario (orejas, manchas…)"}


class EstadoSocial(QObject):
    """La cuenta y el muñequito de esta PC. La comparten el botón de arriba a la derecha y la ventana."""
    cambio = Signal()

    def __init__(self, bib):
        super().__init__()
        self.bib = bib
        self.avatar = avatar3d.normalizar(bib.config("avatar") or "{}")
        self.perfil: dict | None = None
        self.error = ""
        self._ocupado = False
        self.cliente: social.Cliente | None = None
        base, token = bib.config("social_servidor"), bib.config("social_token")
        if base and token:
            try:
                self.cliente = social.Cliente(base, token)
            except social.ErrorSocial:
                self.cliente = None
        self._espera = QTimer(self, singleShot=True, interval=5000)
        self._espera.timeout.connect(self.sincronizar)
        self._cada = QTimer(self, interval=10 * 60 * 1000)
        self._cada.timeout.connect(self.sincronizar)
        self._cada.start()
        if self.cliente:
            QTimer.singleShot(3000, self.sincronizar)

    @property
    def usuario(self) -> str:
        return self.bib.config("social_usuario") or ""

    @property
    def conectado(self) -> bool:
        return self.cliente is not None

    @property
    def nombre(self) -> str:
        """El nombre que le puso a su BiriBiri (vacío si todavía no le puso)."""
        return (self.bib.config("protagonista_nombre") or "").strip()

    def guardar_nombre(self, nombre: str):
        nombre = " ".join(nombre.split())[:24]
        if nombre != self.nombre:
            self.bib.guardar_config("protagonista_nombre", nombre)
            self.cambio.emit()

    @property
    def en_logo(self) -> bool:
        """¿El Protagonista aparece apoyado en el logo cuando no hay nada seleccionado? (por defecto sí)"""
        return self.bib.config("protagonista_en_logo") != "0"

    def guardar_en_logo(self, activo: bool):
        self.bib.guardar_config("protagonista_en_logo", "1" if activo else "0")
        self.cambio.emit()

    @property
    def animacion(self) -> bool:
        """¿En la pantalla del logo, el Protagonista hace su escena (empuja al logo y sale volando)? (por defecto sí)"""
        return self.bib.config("protagonista_animacion") != "0"

    def guardar_animacion(self, activo: bool):
        self.bib.guardar_config("protagonista_animacion", "1" if activo else "0")
        self.cambio.emit()

    def nombre_visible(self) -> str:
        return self.nombre or (self.perfil["nombre"] if self.perfil else "") or self.usuario or "Tu BiriBiri"

    def puntos_texto(self) -> str:
        if self.perfil:
            return f"⭐ {self.perfil['puntos']} puntos"
        return "Sin cuenta: creá una para sumar puntos" if not self.conectado else "Contando tus puntos…"

    def resumen(self) -> str:
        if not self.conectado:
            return (f"{self.nombre} · sin cuenta, sin puntos" if self.nombre else
                    "🎬 Armá tu BiriBiri: la estrella de tu videoteca. Tocalo para empezar")
        if self.perfil:
            return f"{self.nombre_visible()} · {self.perfil['rango']} · {self.perfil['puntos']} puntos"
        return f"{self.nombre_visible()} · conectando…"

    def guardar_avatar(self, avatar: dict):
        self.avatar = avatar3d.normalizar(avatar)
        self.bib.guardar_config("avatar", json.dumps(self.avatar))
        self.cambio.emit()
        if self.cliente:
            cliente = self.cliente
            en_segundo_plano(lambda: cliente.guardar_avatar(self.avatar), self._perfil, self._fallo)

    def entrar(self, base: str, cliente: social.Cliente, nombre: str):
        self.bib.guardar_config("social_servidor", base)
        self.bib.guardar_config("social_token", cliente.token)
        self.bib.guardar_config("social_usuario", nombre)
        self.cliente = cliente
        self.error = ""
        # El muñequito de esta PC pasa a la cuenta
        en_segundo_plano(lambda: cliente.guardar_avatar(self.avatar), lambda p: (self._perfil(p), self.sincronizar()),
                         self._fallo)
        self.cambio.emit()

    def salir(self):
        cliente, self.cliente = self.cliente, None
        self.perfil = None
        self.bib.guardar_config("social_token", "")
        if cliente:
            en_segundo_plano(cliente.salir, lambda _r: None, lambda _m: None)
        self.cambio.emit()

    def avisar_visto(self):
        """Algo se terminó de ver: se manda en unos segundos (si se marcan varios, va todo junto)."""
        if self.cliente:
            self._espera.start()

    def sincronizar(self):
        if not self.cliente or self._ocupado:
            return
        self._ocupado = True
        items = social.vistas_de_biblioteca(self.bib)  # la base es del hilo de la interfaz: se lee acá
        cliente = self.cliente
        en_segundo_plano(lambda: cliente.enviar_vistas(items), self._perfil, self._fallo)

    def _perfil(self, perfil: dict):
        self._ocupado = False
        self.perfil = perfil
        self.error = ""
        self.cambio.emit()

    def _fallo(self, mensaje: str):
        self._ocupado = False
        self.error = mensaje
        if "venció" in mensaje or "Tenés que entrar" in mensaje:
            self.cliente = None
            self.bib.guardar_config("social_token", "")
        self.cambio.emit()


class _Muestras(QWidget):
    """Una fila de colores para elegir y un botón «Otro…»."""
    elegido = Signal(str)

    def __init__(self, colores, actual: str):
        super().__init__()
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(4)
        self._botones = []
        for c in colores:
            b = QPushButton(fixedSize=QSize(24, 24), checkable=True)
            b.setStyleSheet(f"QPushButton {{ background: {c}; border: 1px solid #555; border-radius: 12px; }}"
                            "QPushButton:checked { border: 3px solid palette(highlight); }")
            b.setToolTip(c)
            b.clicked.connect(lambda _=False, c=c: self._elegir(c))
            fila.addWidget(b)
            self._botones.append((c, b))
        otro = QPushButton("Otro…", objectName="chico")
        otro.clicked.connect(self._otro)
        fila.addWidget(otro)
        fila.addStretch()
        self._marcar(actual)

    def _marcar(self, color: str):
        for c, b in self._botones:
            b.setChecked(c == color)

    def _elegir(self, color: str):
        self._marcar(color)
        self.elegido.emit(color)

    def _otro(self):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self._elegir(color.name())


class _Encuadre(QWidget):
    """La foto con un círculo encima: se arrastra para centrar la cara y la rueda (o la barra) acerca."""
    LADO = 300

    def __init__(self, imagen: QImage):
        super().__init__()
        self.imagen = imagen
        self.setFixedSize(self.LADO, self.LADO)
        self.setCursor(Qt.OpenHandCursor)
        self.zoom = 1.0
        # Al empezar, el círculo toma el centro de la foto (el lado más corto entero)
        self.centro = QPointF(imagen.width() / 2, imagen.height() * 0.45)
        self._arrastre: QPointF | None = None

    def _escala(self) -> float:
        return self.LADO / min(self.imagen.width(), self.imagen.height()) * self.zoom

    def poner_zoom(self, zoom: float):
        self.zoom = max(1.0, min(6.0, zoom))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#111"))
        e = self._escala()
        p.translate(self.LADO / 2, self.LADO / 2)
        p.scale(e, e)
        p.translate(-self.centro)
        p.drawImage(0, 0, self.imagen)
        p.resetTransform()
        # Afuera del círculo, oscuro
        afuera = QPainterPath()
        afuera.addRect(QRectF(self.rect()))
        circulo = QPainterPath()
        circulo.addEllipse(QRectF(self.rect()).adjusted(8, 8, -8, -8))
        p.fillPath(afuera.subtracted(circulo), QColor(0, 0, 0, 150))
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.drawPath(circulo)
        p.end()

    def wheelEvent(self, e):
        self.poner_zoom(self.zoom * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1))
        self.zoom_cambio()

    def zoom_cambio(self):  # lo reemplaza el diálogo
        pass

    def mousePressEvent(self, e):
        self._arrastre = e.position()
        self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._arrastre is not None:
            d = (e.position() - self._arrastre) / self._escala()
            self.centro -= d
            self._arrastre = e.position()
            self.update()

    def mouseReleaseEvent(self, _e):
        self._arrastre = None
        self.setCursor(Qt.OpenHandCursor)

    def recorte(self, lado: int = 112) -> QImage:
        """Lo que se ve dentro del círculo, cuadrado y chico (va en la descripción del avatar)."""
        salida = QImage(lado, lado, QImage.Format_RGB32)
        salida.fill(QColor("#111"))
        p = QPainter(salida)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        util = self.LADO - 16
        e = self._escala() * lado / util
        p.translate(lado / 2, lado / 2)
        p.scale(e, e)
        p.translate(-self.centro)
        p.drawImage(0, 0, self.imagen)
        p.end()
        return salida


class _RecorteFoto(QDialog):
    def __init__(self, imagen: QImage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tu cara")
        # Fotos enormes (celulares): se achican antes, para que mover el círculo sea fluido
        if max(imagen.width(), imagen.height()) > 1600:
            imagen = imagen.scaled(1600, 1600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.encuadre = _Encuadre(imagen)
        barra = QSlider(Qt.Horizontal, minimum=100, maximum=600, value=100)
        barra.valueChanged.connect(lambda v: self.encuadre.poner_zoom(v / 100))
        self.encuadre.zoom_cambio = lambda: (barra.blockSignals(True), barra.setValue(int(self.encuadre.zoom * 100)),
                                             barra.blockSignals(False))
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Ok).setText("Usar esta foto")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        capa = QVBoxLayout(self)
        capa.addWidget(QLabel("Arrastrá la foto para que tu cara quede dentro del círculo.", objectName="pista"))
        capa.addWidget(self.encuadre, 0, Qt.AlignCenter)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Acercar"))
        fila.addWidget(barra, 1)
        capa.addLayout(fila)
        capa.addWidget(botones)

    def resultado(self) -> str:
        """La foto como data URL JPEG, achicando la calidad hasta que entre en el límite."""
        imagen = self.encuadre.recorte()
        for calidad in (82, 70, 58, 45, 32):
            datos = QByteArray()
            buffer = QBuffer(datos)
            buffer.open(QBuffer.WriteOnly)
            imagen.save(buffer, "JPG", calidad)
            url = "data:image/jpeg;base64," + base64.b64encode(bytes(datos)).decode()
            if len(url) <= avatar3d.FOTO_MAXIMO:
                return url
        return url


class VentanaAvatar(QWidget):
    def __init__(self, estado: EstadoSocial):
        super().__init__(None, Qt.Window)
        self.estado = estado
        self.spec = dict(estado.avatar)
        self.setWindowTitle("Mi videoteca — TorrentVision")
        self.resize(1500, 800)

        # La habitación (3 veces más ancha que el retrato de antes): BiriBiri y su mascota viven acá
        self.casa = modelo_casa.Casa(estado.bib)
        self.vista = vista3d.crear(self.spec, arrastrable=True, fondo=True, casa=True)
        self.vista.setMinimumSize(560, 430)
        self.escena = EscenaCasa(self.vista, self.casa)
        # Las caritas de los amigos (se arman de a una, en una vista escondida)
        self._miniaturas = vista3d.Miniaturas(96)
        self._miniaturas.lista.connect(self._miniatura_lista)
        izquierda = QVBoxLayout()
        izquierda.addWidget(self.vista, 1)
        self.lbl_ayuda_casa = QLabel("Arrastrá los muebles, a BiriBiri y a la mascota para acomodarlos · rueda: zoom · clic derecho y arrastrar: mover la vista · "
                                     "doble clic: vuelve · R: girar · Supr: guardar el mueble · Esc: cancelar", objectName="pista",
                                     alignment=Qt.AlignCenter, wordWrap=True)
        izquierda.addWidget(self.lbl_ayuda_casa)

        self.pestanas = QTabWidget()
        self.pestanas.addTab(self._armar_editor(), "🎬 BiriBiri")
        self.pestanas.addTab(self._armar_casa(), "🏠 Decorar")
        self.pestanas.addTab(self._armar_cuenta(), "🔑 Cuenta")
        self._pagina_amigos = self._armar_amigos()
        self.pestanas.addTab(self._pagina_amigos, "👥 Amigos")
        self.pestanas.currentChanged.connect(lambda i: self.pestanas.widget(i) is self._pagina_amigos and self._cargar_amigos())

        capa = QHBoxLayout(self)
        capa.addLayout(izquierda, 5)
        capa.addWidget(self.pestanas, 3)
        estado.cambio.connect(self._refrescar)
        self._refrescar()
        # Las monedas se ganan viendo películas y series: se cuentan al abrir la ventana y cada tanto
        QShortcut(QKeySequence("R"), self, activated=self.escena.girar)
        QShortcut(QKeySequence.Delete, self, activated=self.escena.guardar_seleccionado)
        QShortcut(QKeySequence("Escape"), self, activated=self.escena.cancelar)
        self._reloj_monedas = QTimer(self, interval=5 * 60 * 1000, timeout=self._cobrar)
        self._reloj_monedas.start()
        self.escena.cambio.connect(self._refrescar_casa)
        self._cobrar()

    # --- La casa: tienda, inventario, piso y paredes ----------------------------------------------------------

    def _cobrar(self):
        ganado = self.casa.cobrar(social.vistas_de_biblioteca(self.estado.bib))
        if ganado and hasattr(self, "lbl_monedas"):
            self.lbl_avisos.setText(f"🎉 ¡Ganaste {ganado} monedas por lo que viste!")
        self._refrescar_casa()

    def showEvent(self, e):
        super().showEvent(e)
        self._cobrar()

    def _armar_casa(self) -> QWidget:
        hoja = QWidget()
        capa = QVBoxLayout(hoja)
        self.lbl_monedas = QLabel(objectName="titulo")
        self.lbl_avisos = QLabel(objectName="pista", wordWrap=True)
        capa.addWidget(self.lbl_monedas)
        capa.addWidget(self.lbl_avisos)
        sub = QTabWidget()
        sub.setDocumentMode(True)

        # Tienda
        tienda = QWidget()
        c = QVBoxLayout(tienda)
        self.lista_tienda = QListWidget()
        for categoria in modelo_casa.CATEGORIAS:
            for clave, datos in modelo_casa.CATALOGO.items():
                if datos["categoria"] == categoria:
                    it = QListWidgetItem(f"{datos['nombre']}  ·  {datos['categoria']}  ·  🪙 {datos['precio']}")
                    it.setData(Qt.UserRole, clave)
                    self.lista_tienda.addItem(it)
        self.lista_tienda.itemDoubleClicked.connect(lambda _i: self._comprar_mueble())
        boton = QPushButton("Comprar", objectName="primario")
        boton.clicked.connect(self._comprar_mueble)
        c.addWidget(self.lista_tienda, 1)
        c.addWidget(boton)
        sub.addTab(tienda, "🛒 Tienda")

        # Inventario
        inventario = QWidget()
        c = QVBoxLayout(inventario)
        self.lista_inventario = QListWidget()
        self.lista_inventario.currentRowChanged.connect(lambda _r: self._color_inventario())
        self.combo_color_inv = QComboBox()
        poner = QPushButton("Poner en la casa", objectName="primario")
        poner.clicked.connect(self._poner_del_inventario)
        c.addWidget(QLabel("Lo que compraste y todavía no pusiste. Elegí uno, su color y hacé clic en el piso."))
        c.addWidget(self.lista_inventario, 1)
        c.addWidget(self.combo_color_inv)
        c.addWidget(poner)
        sub.addTab(inventario, "🎒 Inventario")

        # Piso y paredes
        acabados = QWidget()
        c = QVBoxLayout(acabados)
        self.lista_pisos, self.lista_paredes = QListWidget(), QListWidget()
        for lista, tabla, tipo in ((self.lista_pisos, modelo_casa.PISOS, "piso"), (self.lista_paredes, modelo_casa.PAREDES, "pared")):
            for clave in tabla:
                it = QListWidgetItem()
                it.setData(Qt.UserRole, clave)
                lista.addItem(it)
            lista.itemDoubleClicked.connect(lambda i, tipo=tipo: self._elegir_acabado(tipo, i.data(Qt.UserRole)))
        c.addWidget(QLabel("<b>Piso</b> (doble clic: comprarlo y ponerlo)"))
        c.addWidget(self.lista_pisos, 1)
        c.addWidget(QLabel("<b>Paredes</b> (doble clic: comprarlas y pintarlas)"))
        c.addWidget(self.lista_paredes, 1)
        sub.addTab(acabados, "🎨 Piso y paredes")

        # El mueble elegido
        elegido = QWidget()
        c = QVBoxLayout(elegido)
        self.lbl_elegido = QLabel(wordWrap=True)
        self.combo_color_mueble = QComboBox()
        self.combo_color_mueble.activated.connect(lambda _i: self.escena.pintar_seleccionado(self.combo_color_mueble.currentData()))
        girar = QPushButton("↻ Girar (R)")
        girar.clicked.connect(self.escena.girar)
        # Para sentarse (solo en sillones y sillas)
        self.caja_sentar = QWidget()
        cs = QVBoxLayout(self.caja_sentar)
        cs.setContentsMargins(0, 0, 0, 0)
        cs.addWidget(QLabel("<b>Sentarse</b> (o arrastrá a BiriBiri o a la mascota encima del mueble)"))
        for texto, accion in (("🧍 Sentar a BiriBiri", lambda: self.escena.sentar("bb")),
                              ("🐾 Sentar a la mascota", lambda: self.escena.sentar("mascota")),
                              ("🐾 BiriBiri sentado con la mascota en la falda", lambda: self.escena.falda()),
                              ("👫 Sentar a los dos", lambda: self.escena.sentar_los_dos()),
                              ("🚶 Pararlos", lambda: self.escena.parar_a_todos())):
            b = QPushButton(texto)
            b.clicked.connect(accion)
            cs.addWidget(b)
        guardar = QPushButton("🎒 Guardar en el inventario (Supr)")
        guardar.clicked.connect(self.escena.guardar_seleccionado)
        c.addWidget(self.lbl_elegido)
        c.addWidget(QLabel("Color"))
        c.addWidget(self.combo_color_mueble)
        c.addWidget(girar)
        c.addWidget(self.caja_sentar)
        c.addWidget(guardar)
        c.addStretch()
        sub.addTab(elegido, "🪑 Elegido")
        self._sub_casa = sub
        capa.addWidget(sub, 1)
        return hoja

    @staticmethod
    def _icono_color(hexa: str):
        from PySide6.QtGui import QPixmap
        pm = QPixmap(18, 18)
        pm.fill(QColor(hexa))
        return QIcon(pm)

    def _refrescar_casa(self):
        if not hasattr(self, "lbl_monedas"):
            return
        d = self.casa.datos
        self.lbl_monedas.setText(f"🪙 {d['monedas']} monedas")
        # Piso y paredes
        for lista, tabla, tenidos, puesto in ((self.lista_pisos, modelo_casa.PISOS, d["pisos"], d["piso"]),
                                              (self.lista_paredes, modelo_casa.PAREDES, d["paredes"], d["pared"])):
            for i in range(lista.count()):
                it = lista.item(i)
                clave = it.data(Qt.UserRole)
                nombre, precio, color, *_ = tabla[clave]
                estado = "puesto" if clave == puesto else ("tuyo" if clave in tenidos else f"🪙 {precio}")
                it.setText(f"{nombre}  ·  {estado}")
                it.setIcon(self._icono_color(color))
        # Inventario
        actual = self.lista_inventario.currentItem().data(Qt.UserRole) if self.lista_inventario.currentItem() else None
        self.lista_inventario.clear()
        for clave, cuantos in d["inventario"].items():
            it = QListWidgetItem(f"{modelo_casa.CATALOGO[clave]['nombre']}  ×{cuantos}")
            it.setData(Qt.UserRole, clave)
            self.lista_inventario.addItem(it)
            if clave == actual:
                self.lista_inventario.setCurrentItem(it)
        if self.lista_inventario.count() and not self.lista_inventario.currentItem():
            self.lista_inventario.setCurrentRow(0)
        self._color_inventario()
        # El mueble elegido
        m = self.escena.mueble_seleccionado()
        self.combo_color_mueble.blockSignals(True)
        self.combo_color_mueble.clear()
        if m:
            datos = modelo_casa.CATALOGO[m["id"]]
            self.lbl_elegido.setText(f"<b>{datos['nombre']}</b><br>Arrastralo para moverlo.")
            for color in datos["colores"]:
                self.combo_color_mueble.addItem(self._icono_color(color), color, color)
            self.combo_color_mueble.setCurrentIndex(max(0, self.combo_color_mueble.findData(m["color"])))
        else:
            self.lbl_elegido.setText("Hacé clic en un mueble de la casa para elegirlo.")
        self.combo_color_mueble.setEnabled(bool(m))
        self.combo_color_mueble.blockSignals(False)
        self.caja_sentar.setVisible(bool(m) and self.escena.puede_sentar() > 0)
        if m:
            self._sub_casa.setCurrentIndex(3)

    def _color_inventario(self):
        item = self.lista_inventario.currentItem()
        self.combo_color_inv.clear()
        if item:
            for color in modelo_casa.CATALOGO[item.data(Qt.UserRole)]["colores"]:
                self.combo_color_inv.addItem(self._icono_color(color), color, color)
        self.combo_color_inv.setEnabled(bool(item))

    def _comprar_mueble(self):
        item = self.lista_tienda.currentItem()
        if not item:
            return
        clave = item.data(Qt.UserRole)
        nombre = modelo_casa.CATALOGO[clave]["nombre"]
        if self.casa.comprar_mueble(clave):
            self.lbl_avisos.setText(f"✔ Compraste: {nombre}. Está en tu inventario.")
        else:
            self.lbl_avisos.setText(f"No te alcanzan las monedas para {nombre} (cuesta {modelo_casa.CATALOGO[clave]['precio']}). "
                                    "Se ganan viendo películas y series.")
        self._refrescar_casa()

    def _poner_del_inventario(self):
        item = self.lista_inventario.currentItem()
        if item:
            self.escena.empezar_colocar(item.data(Qt.UserRole), self.combo_color_inv.currentData())
            self.lbl_avisos.setText("Hacé clic en el piso para ponerlo (R: girarlo, Esc: cancelar).")

    def _elegir_acabado(self, tipo: str, clave: str):
        comprar, poner, tabla = ((self.casa.comprar_piso, self.casa.poner_piso, modelo_casa.PISOS) if tipo == "piso" else
                                 (self.casa.comprar_pared, self.casa.poner_pared, modelo_casa.PAREDES))
        if comprar(clave) and poner(clave):
            self.lbl_avisos.setText(f"✔ {tabla[clave][0]}.")
            self.escena.refrescar()
        else:
            self.lbl_avisos.setText(f"No te alcanzan las monedas para {tabla[clave][0]} (cuesta {tabla[clave][1]}).")
        self._refrescar_casa()

    # --- Editor ----------------------------------------------------------------------------------------------

    def _armar_editor(self) -> QWidget:
        hoja = QWidget()
        capa = QVBoxLayout(hoja)
        self._muestras = {}
        self._combos = {}
        self._deslizadores = {}
        fila_nombre = QHBoxLayout()
        self.nombre = QLineEdit(self.estado.nombre, maxLength=24, placeholderText="Ponele un nombre a tu BiriBiri")
        self.nombre.setToolTip("Este nombre reemplaza a «Armá tu BiriBiri» arriba a la derecha")
        self.nombre.textEdited.connect(lambda _t: self.lbl_guardado.setText("Sin guardar"))
        self.nombre.returnPressed.connect(lambda: self._guardar())
        fila_nombre.addWidget(QLabel("<b>Nombre</b>"))
        fila_nombre.addWidget(self.nombre, 1)
        capa.addLayout(fila_nombre)
        secciones = QTabWidget()
        secciones.setDocumentMode(True)
        secciones.tabBar().setUsesScrollButtons(True)
        secciones.tabBar().setExpanding(False)
        secciones.tabBar().setElideMode(Qt.ElideNone)
        secciones.tabBar().setStyleSheet("QTabBar::tab { padding: 7px 8px; margin: 0px 1px; }")

        # Cara: la foto (opcional), la piel y los gestos
        cara, form = self._seccion()
        fila_foto = QHBoxLayout()
        poner = QPushButton("📷 Tu cara con una foto…", objectName="primario")
        poner.clicked.connect(self._poner_foto)
        self.quitar_foto = QPushButton("Quitar la foto", objectName="chico")
        self.quitar_foto.clicked.connect(lambda: self._cambiar("foto", None))
        fila_foto.addWidget(poner)
        fila_foto.addWidget(self.quitar_foto)
        fila_foto.addStretch()
        form.addRow(fila_foto)
        form.addRow(QLabel("Una foto tuya de frente: se recorta en un círculo y se pega en la cara.",
                           objectName="pista", wordWrap=True))
        self._combo(form, "genero", "Género")
        self._fila_color(form, "piel")
        self._fila_color(form, "ojos")
        self._combo(form, "mirada", "Expresión de los ojos")
        self._combo(form, "cejas", "Cejas")
        self._combo(form, "boca", "Boca")
        self._combo(form, "barba", "Barba y bigote")
        form.addRow(QLabel("Con una foto puesta se ven solo la foto y lo que lleva encima (lentes, sombreros…): los ojos, "
                           "las cejas y la boca son para la cara sin foto.", objectName="pista", wordWrap=True))
        secciones.addTab(cara, "🙂 Cara")

        pelo, form = self._seccion()
        self._combo(form, "peinado", "Peinado")
        self._fila_color(form, "pelo")
        secciones.addTab(pelo, "💇 Pelo")

        ropa, form = self._seccion()
        self._combo(form, "cuerpo", "Cuerpo")
        self._combo(form, "ropa", "Ropa")
        self._filtrar_ropa()
        self._combo(form, "estampa", "Estampa")
        for clave in ("remera", "estampa_color", "pantalon", "zapatillas"):
            self._fila_color(form, clave)
        secciones.addTab(ropa, "👕 Ropa")

        extras, form = self._seccion()
        self._combo(form, "cabeza", "En la cabeza")
        self._combo(form, "lentes", "Lentes")
        self._fila_color(form, "lentes_color")
        self._combo(form, "extra", "Para la función")
        self._fila_color(form, "accesorio_color")
        secciones.addTab(extras, "🎩 Extras")

        fondo, form = self._seccion()
        self._combo(form, "bandera", "Bandera de fondo")
        form.addRow(QLabel("La bandera de tu país flamea detrás de tu BiriBiri (en esta ventana y en la tarjeta que aparece "
                           "al pasar el mouse por su botón).", objectName="pista", wordWrap=True))
        for clave, texto in (("bandera_x", "Izquierda ↔ derecha"), ("bandera_y", "Abajo ↔ arriba"), ("bandera_tam", "Tamaño"),
                             ("bandera_giro", "Inclinación"), ("bandera_costado", "Girada de costado")):
            minimo, maximo, _ = avatar3d.NUMEROS[clave]
            deslizador = QSlider(Qt.Horizontal)
            deslizador.setRange(minimo, maximo)
            deslizador.setValue(int(self.spec.get(clave, avatar3d.NUMEROS[clave][2])))
            deslizador.valueChanged.connect(lambda v, clave=clave: self._cambiar(clave, int(v)))
            self._deslizadores[clave] = deslizador
            form.addRow(texto, deslizador)
        restablecer = QPushButton("Dejar la bandera como estaba")
        restablecer.clicked.connect(self._restablecer_bandera)
        form.addRow(restablecer)
        secciones.addTab(fondo, "🏳 Fondo")

        poses_tab, form = self._seccion()
        self._combo(form, "pose", "Pose")
        self._combo(form, "lugar", "Otro lugar donde aparece")
        form.addRow(QLabel("Con la pose «Normal», en cada lugar toma la que le toca (sentado, acostado, nadando…). Si elegís "
                           "otra, la usa en todos lados. Podés girarlo arrastrándolo.", objectName="pista", wordWrap=True))
        secciones.addTab(poses_tab, "🧍 Pose")

        mascota_tab, form = self._seccion()
        self._combo(form, "mascota", "Mascota")
        self._fila_color(form, "mascota_color")
        self._fila_color(form, "mascota_color2")
        self._combo(form, "interaccion", "Qué hacen juntos")
        form.addRow(QLabel("Un perro o un gato (de distintas razas y colores) parado al lado de tu BiriBiri. Al cambiar de raza "
                           "se pone sus colores de siempre y después los podés cambiar. Con una interacción, tu BiriBiri deja la "
                           "pose elegida para hacerle mimos, darle un premio o llenarle el plato.", objectName="pista", wordWrap=True))
        secciones.addTab(mascota_tab, "🐾 Mascota")

        capa.addWidget(secciones, 1)
        self.en_logo = QCheckBox("Que aparezca apoyado en el logo cuando no hay ningún video elegido")
        self.en_logo.setChecked(self.estado.en_logo)
        self.con_animacion = QCheckBox("Con la animación: empuja al logo y sale volando (si no, queda apoyado quieto)")
        self.con_animacion.setChecked(self.estado.animacion)
        self.con_animacion.setEnabled(self.estado.en_logo)
        self.con_animacion.toggled.connect(self.estado.guardar_animacion)
        self.en_logo.toggled.connect(self.estado.guardar_en_logo)   # esto se aplica en el momento
        self.en_logo.toggled.connect(self.con_animacion.setEnabled)
        capa.addWidget(self.en_logo)
        capa.addWidget(self.con_animacion)
        botones = QHBoxLayout()
        azar = QPushButton("🎲 Sorprendeme")
        azar.clicked.connect(self._al_azar)
        guardar = QPushButton("Guardar", objectName="primario")
        guardar.clicked.connect(self._guardar)
        self.lbl_guardado = QLabel(objectName="pista")
        botones.addWidget(azar)
        botones.addStretch()
        botones.addWidget(self.lbl_guardado)
        botones.addWidget(guardar)
        capa.addLayout(botones)
        self._actualizar_foto()
        return hoja

    @staticmethod
    def _seccion() -> tuple[QWidget, QFormLayout]:
        hoja = QWidget()
        form = QFormLayout(hoja)
        form.setVerticalSpacing(10)
        return hoja, form

    def _combo(self, form: QFormLayout, clave: str, texto: str):
        combo = QComboBox()
        for k, v in avatar3d.OPCIONES[clave].items():
            combo.addItem(v, k)
        combo.setCurrentIndex(max(0, combo.findData(self.spec[clave])))
        combo.currentIndexChanged.connect(lambda _=0, clave=clave, combo=combo: self._cambiar(clave, combo.currentData()))
        self._combos[clave] = combo
        form.addRow(texto, combo)

    def _fila_color(self, form: QFormLayout, clave: str):
        m = _Muestras(PALETAS[clave], self.spec[clave])
        m.elegido.connect(lambda c, clave=clave: self._cambiar(clave, c))
        self._muestras[clave] = m
        form.addRow(NOMBRES[clave], m)

    def _filtrar_ropa(self):
        """Las prendas que se ofrecen según el género (vestidos y pollera para «mujer», traje para «hombre»; «no binario»
        ve todas). Si la que estaba puesta ya no se ofrece, vuelve a la remera."""
        genero = self.spec.get("genero", "nobinario")
        combo = self._combos["ropa"]
        combo.blockSignals(True)
        combo.clear()
        for k, v in avatar3d.OPCIONES["ropa"].items():
            para = avatar3d.ROPA_GENERO.get(k)
            if genero == "nobinario" or para is None or para == genero:
                combo.addItem(v, k)
        if combo.findData(self.spec.get("ropa")) < 0:
            self.spec["ropa"] = "remera"
        combo.setCurrentIndex(max(0, combo.findData(self.spec.get("ropa", "remera"))))
        combo.blockSignals(False)

    def _restablecer_bandera(self):
        for clave, deslizador in self._deslizadores.items():
            deslizador.setValue(avatar3d.NUMEROS[clave][2])     # cada uno avisa su cambio

    def _cambiar(self, clave: str, valor):
        if valor is None:
            self.spec.pop(clave, None)
        else:
            self.spec[clave] = valor
        if clave == "genero":
            self._filtrar_ropa()
        if clave == "mascota" and valor in mascotas.RAZAS:      # cada raza con sus colores de siempre
            for k, c in zip(("mascota_color", "mascota_color2"), mascotas.colores(valor)):
                self.spec[k] = c
                self._muestras[k]._marcar(c)
        self.vista.poner(self.spec)
        self.lbl_guardado.setText("Sin guardar")
        self._actualizar_foto()

    def _actualizar_foto(self):
        self.quitar_foto.setVisible(bool(self.spec.get("foto")))

    def _poner_foto(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegí una foto tuya", "", "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp)")
        if not ruta:
            return
        imagen = QImage(ruta)
        if imagen.isNull():
            return QMessageBox.warning(self, "Foto", "No se pudo abrir esa imagen.")
        dialogo = _RecorteFoto(imagen, self)
        if dialogo.exec():
            self._cambiar("foto", dialogo.resultado())

    def _al_azar(self):
        for clave, colores in PALETAS.items():
            if clave.startswith("mascota"):         # la mascota no se sortea
                continue
            self.spec[clave] = random.choice(colores)
            self._muestras[clave]._marcar(self.spec[clave])
        for clave, combo in self._combos.items():
            if clave in ("ropa", "bandera", "pose", "lugar", "mascota", "interaccion"):      # la ropa depende del género; bandera, pose y lugar no se sortean
                continue
            combo.blockSignals(True)
            combo.setCurrentIndex(random.randrange(combo.count()))
            combo.blockSignals(False)
            self.spec[clave] = combo.currentData()
        self._filtrar_ropa()
        combo = self._combos["ropa"]
        combo.blockSignals(True)
        combo.setCurrentIndex(random.randrange(combo.count()))
        combo.blockSignals(False)
        self.spec["ropa"] = combo.currentData()
        self.vista.poner(self.spec)
        self.lbl_guardado.setText("Sin guardar")

    def _guardar(self):
        self.estado.guardar_nombre(self.nombre.text())
        self.estado.guardar_avatar(self.spec)
        self.lbl_guardado.setText("✓ Guardado" + (" en tu cuenta" if self.estado.conectado else ""))

    # --- Cuenta ---------------------------------------------------------------------------------------------

    def _armar_cuenta(self) -> QWidget:
        self.paginas_cuenta = QStackedWidget()
        # Sin cuenta
        hoja = QWidget()
        form = QFormLayout(hoja)
        self.servidor = QLineEdit(self.estado.bib.config("social_servidor") or social.LOCAL,
                                  placeholderText="local")
        self.servidor.setToolTip("«local» guarda las cuentas en esta PC. Cuando haya un servidor en internet, "
                                 "va su dirección (https://…) para sumar amigos de otras casas.")
        self.usuario = QLineEdit(self.estado.usuario, placeholderText="3 a 20 letras, números o _", maxLength=20)
        self.clave = QLineEdit(echoMode=QLineEdit.Password, placeholderText="mínimo 8 caracteres")
        form.addRow("Servidor", self.servidor)
        form.addRow("Usuario", self.usuario)
        form.addRow("Contraseña", self.clave)
        fila = QHBoxLayout()
        crear = QPushButton("Crear cuenta", objectName="primario")
        crear.clicked.connect(lambda: self._cuenta("registrar"))
        entrar = QPushButton("Entrar")
        entrar.clicked.connect(lambda: self._cuenta("entrar"))
        olvide = QPushButton("Olvidé mi contraseña", objectName="chico")
        fila.addWidget(crear)
        fila.addWidget(entrar)
        fila.addStretch()
        fila.addWidget(olvide)
        form.addRow(fila)
        self.recuperacion = QFrame()
        rec = QFormLayout(self.recuperacion)
        self.codigo = QLineEdit(placeholderText="XXXX-XXXX-XXXX-XXXX")
        self.nueva = QLineEdit(echoMode=QLineEdit.Password, placeholderText="contraseña nueva")
        boton_rec = QPushButton("Cambiar la contraseña")
        boton_rec.clicked.connect(lambda: self._cuenta("recuperar"))
        rec.addRow("Código de recuperación", self.codigo)
        rec.addRow("Contraseña nueva", self.nueva)
        rec.addRow(boton_rec)
        self.recuperacion.hide()
        olvide.clicked.connect(lambda: self.recuperacion.setVisible(not self.recuperacion.isVisible()))
        form.addRow(self.recuperacion)
        form.addRow(QLabel("Con «local» las cuentas quedan guardadas en esta PC (los amigos tienen que ser otras "
                           "cuentas de esta misma PC hasta que haya un servidor en internet).",
                           objectName="pista", wordWrap=True))
        form.addRow(QLabel("No hace falta correo. Al crear la cuenta te damos un código de recuperación: "
                           "guardalo, es la única forma de cambiar la contraseña si te la olvidás.",
                           objectName="pista", wordWrap=True))
        self.msg_cuenta = QLabel(wordWrap=True)
        form.addRow(self.msg_cuenta)
        self.paginas_cuenta.addWidget(hoja)
        # Con cuenta
        hoja2 = QWidget()
        capa = QVBoxLayout(hoja2)
        self.lbl_conectado = QLabel(wordWrap=True, textFormat=Qt.RichText)
        sinc = QPushButton("🔄 Sumar lo que vi ahora")
        sinc.clicked.connect(self.estado.sincronizar)
        salir = QPushButton("Salir de la cuenta")
        salir.clicked.connect(self.estado.salir)
        capa.addWidget(self.lbl_conectado)
        capa.addWidget(QLabel("Cada película que terminás de ver suma 10 puntos y cada capítulo 2 (hasta 60 por día). "
                              "El servidor no sabe qué viste: TorrentVision manda una huella de cada una.",
                              objectName="pista", wordWrap=True))
        fila2 = QHBoxLayout()
        fila2.addWidget(sinc)
        fila2.addStretch()
        fila2.addWidget(salir)
        capa.addLayout(fila2)
        capa.addStretch()
        self.paginas_cuenta.addWidget(hoja2)
        return self.paginas_cuenta

    def _cuenta(self, accion: str):
        try:
            cliente = social.Cliente(self.servidor.text())
        except social.ErrorSocial as e:
            return self.msg_cuenta.setText(str(e))
        nombre, clave = self.usuario.text().strip(), self.clave.text()
        self.msg_cuenta.setText("Conectando…")
        if accion == "registrar":
            trabajo = lambda: cliente.registrar(nombre, clave)  # noqa: E731
        elif accion == "entrar":
            trabajo = lambda: cliente.entrar(nombre, clave)  # noqa: E731
        else:
            codigo, nueva = self.codigo.text(), self.nueva.text()
            trabajo = lambda: cliente.recuperar(nombre, codigo, nueva)  # noqa: E731

        def listo(r):
            self.clave.clear()
            self.nueva.clear()
            self.codigo.clear()
            self.msg_cuenta.clear()
            self.estado.entrar(cliente.origen, cliente, r["nombre"])
            if r.get("recuperacion"):
                self._mostrar_codigo(r["recuperacion"])

        en_segundo_plano(trabajo, listo, self.msg_cuenta.setText)

    def _mostrar_codigo(self, codigo: str):
        caja = QMessageBox(QMessageBox.Information, "Tu código de recuperación",
                           "Guardalo en un lugar seguro (anotalo o sacale una foto). Sin correo, es la única forma de "
                           "cambiar la contraseña si te la olvidás. No se vuelve a mostrar.<br><br>"
                           f"<span style='font-size: 18pt; font-family: Consolas, monospace;'>{codigo}</span>", parent=self)
        copiar = caja.addButton("Copiar", QMessageBox.ActionRole)
        caja.addButton("Ya lo guardé", QMessageBox.AcceptRole)
        copiar.clicked.connect(lambda: QGuiApplication.clipboard().setText(codigo))
        caja.exec()

    # --- Amigos ---------------------------------------------------------------------------------------------

    def _armar_amigos(self) -> QWidget:
        hoja = QWidget()
        capa = QVBoxLayout(hoja)
        fila = QHBoxLayout()
        self.nombre_amigo = QLineEdit(placeholderText="Usuario de tu amigo")
        self.nombre_amigo.returnPressed.connect(self._agregar_amigo)
        agregar = QPushButton("Agregar")
        agregar.clicked.connect(self._agregar_amigo)
        actualizar = QPushButton("🔄")
        actualizar.setToolTip("Actualizar")
        actualizar.clicked.connect(self._cargar_amigos)
        fila.addWidget(self.nombre_amigo, 1)
        fila.addWidget(agregar)
        fila.addWidget(actualizar)
        capa.addLayout(fila)
        self.pedidos = QWidget()
        self.capa_pedidos = QGridLayout(self.pedidos)
        self.capa_pedidos.setContentsMargins(0, 0, 0, 0)
        capa.addWidget(self.pedidos)
        self.lista_amigos = QListWidget()
        self.lista_amigos.setIconSize(QSize(54, 80))
        self.lista_amigos.setSpacing(4)
        capa.addWidget(self.lista_amigos, 1)
        abajo = QHBoxLayout()
        self.msg_amigos = QLabel(objectName="pista", wordWrap=True)
        quitar = QPushButton("Quitar amigo")
        quitar.clicked.connect(self._quitar_amigo)
        abajo.addWidget(self.msg_amigos, 1)
        abajo.addWidget(quitar)
        capa.addLayout(abajo)
        return hoja

    def _hacer_amigos(self, trabajo, texto: str = "Cargando…"):
        if not self.estado.cliente:
            return self.msg_amigos.setText("Creá tu cuenta o entrá (pestaña Cuenta) para agregar amigos.")
        self.msg_amigos.setText(texto)
        en_segundo_plano(trabajo, self._mostrar_amigos, self.msg_amigos.setText)

    def _cargar_amigos(self):
        c = self.estado.cliente
        self._hacer_amigos(lambda: c.amigos())

    def _agregar_amigo(self):
        nombre, c = self.nombre_amigo.text().strip(), self.estado.cliente
        if nombre:
            self._hacer_amigos(lambda: c.pedir_amistad(nombre), f"Mandando el pedido a {nombre}…")

    def _responder(self, nombre: str, aceptar: bool):
        c = self.estado.cliente
        self._hacer_amigos(lambda: c.responder(nombre, aceptar))

    def _quitar_amigo(self):
        item = self.lista_amigos.currentItem()
        if item and QMessageBox.question(self, "Quitar amigo", f"¿Quitar a {item.data(Qt.UserRole)} de tus amigos?") == QMessageBox.Yes:
            nombre, c = item.data(Qt.UserRole), self.estado.cliente
            self._hacer_amigos(lambda: c.quitar(nombre))

    def _miniatura_lista(self, nombre: str, pix):
        for i in range(self.lista_amigos.count()):
            item = self.lista_amigos.item(i)
            if item.data(Qt.UserRole) == nombre:
                item.setIcon(QIcon(pix))

    def _mostrar_amigos(self, datos: dict):
        self.nombre_amigo.clear()
        while self.capa_pedidos.count():
            self.capa_pedidos.takeAt(0).widget().deleteLater()
        for fila, nombre in enumerate(datos.get("recibidas", [])):
            self.capa_pedidos.addWidget(QLabel(f"<b>{nombre}</b> quiere ser tu amigo"), fila, 0)
            si, no = QPushButton("Aceptar", objectName="primario"), QPushButton("Rechazar")
            si.clicked.connect(lambda _=False, n=nombre: self._responder(n, True))
            no.clicked.connect(lambda _=False, n=nombre: self._responder(n, False))
            self.capa_pedidos.addWidget(si, fila, 1)
            self.capa_pedidos.addWidget(no, fila, 2)
        self.lista_amigos.clear()
        for a in datos.get("amigos", []):
            texto = (f"{a['nombre']}\n{a['rango']} · {a['puntos']} puntos · {a['peliculas']} películas"
                     + (f" · {a['capitulos']} capítulos" if a.get("capitulos") else ""))
            item = QListWidgetItem(texto)
            item.setData(Qt.UserRole, a["nombre"])
            self.lista_amigos.addItem(item)
            self._miniaturas.pedir(a["nombre"], a.get("avatar") or {})
        enviadas = datos.get("enviadas", [])
        partes = [f"{len(datos.get('amigos', []))} amigos"]
        if enviadas:
            partes.append("esperando respuesta de " + ", ".join(enviadas))
        self.msg_amigos.setText(" · ".join(partes))

    # --- Estado ---------------------------------------------------------------------------------------------

    def _refrescar(self):
        e = self.estado
        self.paginas_cuenta.setCurrentIndex(1 if e.conectado else 0)
        if e.conectado:
            p = e.perfil
            texto = (f"Conectado como <b>{p['nombre']}</b><br><span style='font-size: 16pt'>{p['rango']}</span>"
                     f" · {p['puntos']} puntos · {p['peliculas']} películas · {p['capitulos']} capítulos"
                     if p else f"Conectado como <b>{e.usuario}</b>…")
            if e.error:
                texto += f"<br><span style='color: #f87171'>{e.error}</span>"
            self.lbl_conectado.setText(texto)
        elif e.error:
            self.msg_cuenta.setText(e.error)
