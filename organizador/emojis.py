"""Emojis parejos en los menús.

Los textos de las opciones empiezan con un emoji («🗑 Borrar», «✔ Visto», «⛶ Pantalla completa»), pero cada
emoji tiene otro ancho y otro tamaño según la letra: las opciones quedaban desalineadas. Al abrirse un menú,
el emoji del principio se saca del texto y se dibuja como ícono, todos del mismo tamaño y centrados en la
columna de íconos, así el texto de todas las opciones arranca en el mismo lugar.
"""
from __future__ import annotations

import unicodedata

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidgetAction

_LADO = 64            # se dibuja grande y Qt lo achica: queda nítido con cualquier escala de Windows
_cache: dict[tuple[str, str], QIcon] = {}
color_texto: str | None = None   # lo pone la ventana al aplicar el tema (la hoja de estilo no cambia la paleta)


def _es_simbolo(c: str) -> bool:
    if c.isalnum() or c.isspace():
        return False
    return unicodedata.category(c) in ("So", "Sm", "Sk", "Mn", "Cf") or ord(c) >= 0x2000


def separar(texto: str) -> tuple[str, str] | None:
    """«🗑 Borrar» → («🗑», «Borrar»). None si el texto no empieza con un emoji seguido de un espacio."""
    principio, espacio, resto = texto.partition(" ")
    if not espacio or not resto.strip() or not principio or len(principio) > 8:
        return None
    if not _es_simbolo(principio[0]) or not all(_es_simbolo(c) for c in principio):
        return None
    return principio, resto.lstrip()


def icono(emoji: str, color: str) -> QIcon:
    clave = (emoji, color)
    if clave in _cache:
        return _cache[clave]
    pix = QPixmap(_LADO, _LADO)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
    fuente = QFont("Segoe UI Emoji")
    fuente.setPixelSize(int(_LADO * 0.78))
    p.setFont(fuente)
    # Que entre entero (algunos símbolos son más anchos o más altos que otros): se achica hasta que entra
    caja = p.fontMetrics().boundingRect(emoji)
    mayor = max(caja.width(), caja.height(), 1)
    if mayor > _LADO * 0.92:
        fuente.setPixelSize(max(8, int(fuente.pixelSize() * _LADO * 0.92 / mayor)))
        p.setFont(fuente)
    p.setPen(color)   # los símbolos de un color (✔ ⛶ ↺) toman el color del texto; los emojis traen el suyo
    p.drawText(QRectF(0, 0, _LADO, _LADO), Qt.AlignCenter, emoji)
    p.end()
    ic = QIcon(pix)
    _cache[clave] = ic
    return ic


def emparejar_menu(menu: QMenu):
    color = color_texto or menu.palette().color(menu.foregroundRole()).name()
    for accion in menu.actions():
        if isinstance(accion, QWidgetAction) or accion.isSeparator() or accion.isCheckable():
            continue
        if not accion.icon().isNull():
            continue
        # Solo si la acción vive en menús (en una barra se vería el ícono en vez del texto)
        if any(not isinstance(o, QMenu) for o in accion.associatedObjects()):
            continue
        partes = separar(accion.text())
        if partes is None:
            continue
        emoji, resto = partes
        accion.setIcon(icono(emoji, color))
        accion.setText(resto)
        accion.setIconVisibleInMenu(True)
    menu.adjustSize()


class _Filtro(QObject):
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and isinstance(obj, QMenu):
            try:
                emparejar_menu(obj)
            except Exception:   # nunca romper un menú por esto
                pass
        return False


_filtro: _Filtro | None = None


def instalar(app: QApplication):
    global _filtro
    if _filtro is None:
        _filtro = _Filtro(app)
        app.installEventFilter(_filtro)
