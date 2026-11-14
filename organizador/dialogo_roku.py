"""📡 Conectar un Roku: lo busca en la red, dice qué modelo es y qué versión de sistema tiene, explica cómo activar
el modo desarrollador si hace falta, instala el canal TorrentVision y lo vincula con la PC. Según el modelo, la PC
se adapta: a un Roku 4K le manda los videos HEVC de 10 bits y 2160p tal cual (sin convertir)."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from . import roku
from .tareas import en_segundo_plano

PASOS_DESARROLLADOR = (
    "Para poder instalarle el canal, el Roku necesita el <b>modo desarrollador</b> (una sola vez):<br>"
    "1. Con el control remoto apretá: <b>Inicio ×3, Arriba ×2, Derecha, Izquierda, Derecha, Izquierda, Derecha</b>.<br>"
    "2. En la pantalla que aparece, elegí <b>Enable installer and restart</b> y aceptá.<br>"
    "3. Elegí una <b>contraseña</b> (anotala) y dejá que el Roku se reinicie.<br>"
    "Después tocá <b>Revisar de nuevo</b>.")


class DialogoRoku(QDialog):
    def __init__(self, ventana, parent=None):
        super().__init__(parent or ventana)
        self.ventana = ventana
        self.bib = ventana.bib
        self.setWindowTitle("📡 Conectar un Roku — TorrentVision")
        self.resize(560, 520)
        capa = QVBoxLayout(self)
        capa.setSpacing(10)
        capa.addWidget(QLabel("Tu Roku y esta PC tienen que estar en la misma red (el mismo wifi o router).",
                              wordWrap=True, objectName="pista"))
        fila = QHBoxLayout()
        self.btn_buscar = QPushButton("🔎 Buscar Rokus", objectName="primario")
        self.btn_buscar.clicked.connect(self.buscar)
        fila.addWidget(self.btn_buscar)
        fila.addStretch(1)
        capa.addLayout(fila)
        self.lista = QListWidget()
        self.lista.setMinimumHeight(110)
        self.lista.currentItemChanged.connect(lambda *_: self._mostrar())
        capa.addWidget(self.lista)
        self.detalle = QLabel(wordWrap=True, textFormat=Qt.RichText)
        self.detalle.setMinimumHeight(90)
        capa.addWidget(self.detalle)
        fila_clave = QHBoxLayout()
        fila_clave.addWidget(QLabel("Contraseña del modo desarrollador:"))
        self.clave = QLineEdit(echoMode=QLineEdit.Password)
        fila_clave.addWidget(self.clave, 1)
        capa.addLayout(fila_clave)
        fila_botones = QHBoxLayout()
        self.btn_revisar = QPushButton("↻ Revisar de nuevo")
        self.btn_revisar.clicked.connect(self._revisar)
        self.btn_conectar = QPushButton("📺 Instalar y conectar", objectName="primario")
        self.btn_conectar.clicked.connect(self.conectar)
        fila_botones.addWidget(self.btn_revisar)
        fila_botones.addStretch(1)
        fila_botones.addWidget(self.btn_conectar)
        capa.addLayout(fila_botones)
        self.estado = QLabel(wordWrap=True, objectName="pista")
        capa.addWidget(self.estado)
        self._mostrar()
        self.buscar()

    # --- Buscar ---------------------------------------------------------------------------------------------
    def buscar(self):
        self.btn_buscar.setEnabled(False)
        self.estado.setText("Buscando Rokus en la red… (unos segundos)")
        conocido = (json.loads(self.bib.config("roku_perfil") or "{}") or {}).get("ip")

        def trabajo():
            return [p for r in roku.buscar_rokus(conocidas=[conocido] if conocido else []) if (p := roku.perfil_de(r["ip"]))]

        def listo(perfiles):
            self.btn_buscar.setEnabled(True)
            self.lista.clear()
            for p in perfiles:
                item = QListWidgetItem(f"📺 {p['nombre']}   ·   {p['modelo']}")
                item.setData(Qt.UserRole, p)
                self.lista.addItem(item)
            if perfiles:
                self.lista.setCurrentRow(0)
                self.estado.setText(f"Encontré {len(perfiles)} Roku." if len(perfiles) == 1 else f"Encontré {len(perfiles)} Rokus.")
            else:
                self.estado.setText("No encontré ningún Roku. Fijate que esté prendido y en la misma red, y buscá de nuevo.")
            self._mostrar()
        en_segundo_plano(trabajo, listo, lambda e: (self.btn_buscar.setEnabled(True), self.estado.setText(f"Error: {e}")))

    def _elegido(self) -> dict | None:
        item = self.lista.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _mostrar(self):
        p = self._elegido()
        self.btn_conectar.setEnabled(bool(p and p.get("desarrollador")))
        self.btn_revisar.setVisible(bool(p and not p.get("desarrollador")))
        self.clave.setEnabled(bool(p and p.get("desarrollador")))
        if not p:
            self.detalle.setText("")
            return
        video = ("<b>4K</b>: los videos HEVC (x265) de 10 bits y en 2160p se mandan tal cual, sin convertir."
                 if p["4k"] else "<b>Hasta 1080p</b>: los videos HEVC (x265) o más grandes que 1080p los convierte la PC.")
        texto = (f"<b>{p['modelo']}</b> · sistema {p['version'] or '?'} · {p['resolucion'] or '?'}<br>{video}<br><br>")
        texto += ("✅ Modo desarrollador activado: escribí su contraseña y tocá <b>Instalar y conectar</b>."
                  if p["desarrollador"] else PASOS_DESARROLLADOR)
        self.detalle.setText(texto)

    def _revisar(self):
        p = self._elegido()
        if not p:
            return
        self.estado.setText("Revisando…")

        def listo(nuevo):
            item = self.lista.currentItem()
            if item and nuevo:
                item.setData(Qt.UserRole, nuevo)
            self.estado.setText("")
            self._mostrar()
        en_segundo_plano(lambda: roku.perfil_de(p["ip"]), listo, lambda e: self.estado.setText(f"Error: {e}"))

    # --- Instalar y conectar ----------------------------------------------------------------------------------
    def conectar(self):
        p = self._elegido()
        if not p:
            return
        remoto = self.ventana.remoto
        if not remoto.servidor_roku:
            # El Roku le pide las películas a la PC por el servidor de ON: se enciende
            if not remoto.iniciar() or not remoto.servidor_roku:
                self.estado.setText("No se pudo encender ON (el servidor para el Roku). Probá desde 📱 Celular.")
                return
        paquete = roku.paquete_canal()
        if paquete is None:
            self.estado.setText("No encuentro el canal de Roku dentro de TorrentVision. Reinstalá la app.")
            return
        clave = self.clave.text()
        ip = p["ip"]
        pase = remoto.pase_roku(ip)
        puerto = remoto.puerto_roku
        self.btn_conectar.setEnabled(False)
        self.estado.setText("Instalando el canal en el Roku… (hasta un minuto)")

        def trabajo():
            error = roku.instalar_canal(ip, clave, paquete)
            if error:
                return error
            return "" if roku.vincular_por_ecp(ip, puerto, pase) else "El canal se instaló pero no abrió: abrilo desde el Roku."

        def listo(error):
            self.btn_conectar.setEnabled(True)
            if error:
                self.estado.setText("⚠ " + error)
                return
            self.bib.guardar_config("roku_perfil", json.dumps(p))
            roku.poner_perfil(p)
            extra = " Como es 4K, los videos HEVC van sin convertir." if p["4k"] else ""
            self.estado.setText(f"✅ Listo: TorrentVision se abrió en tu {p['nombre']}.{extra}")
        en_segundo_plano(trabajo, listo, lambda e: (self.btn_conectar.setEnabled(True), self.estado.setText(f"Error: {e}")))
