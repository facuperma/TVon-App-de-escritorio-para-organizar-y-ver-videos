"""BiriBiri en otros lugares del reproductor: sentado debajo de la lista, acostado arriba del buscador, saludando en la
esquina del video o parado sobre la barra de abajo. Es una vista 3D transparente que flota encima de la ventana (no
agarra el mouse) y se acomoda sola cuando se mueve o cambia de tamaño lo que tiene al lado."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt

from . import avatar3d, poses, vista3d

# Tamaño de la vista de cada lugar (ancho, alto)
TAMANOS = {"lista": (170, 150), "buscador": (240, 120), "visor": (150, 200), "estado": (120, 160)}


class LugaresBiriBiri(QObject):
    def __init__(self, ventana):
        super().__init__(ventana)
        self.v = ventana
        self._vista = None
        self._lugar = "ninguno"
        self._spec: dict | None = None
        self._pendiente = QTimer(self, singleShot=True, interval=0, timeout=self.reposicionar)
        for w in (ventana, *self._anclas().values()):
            if w is not None:
                w.installEventFilter(self)

    def _anclas(self) -> dict:
        v = self.v
        return {"lista": getattr(v, "centro", None), "buscador": getattr(v, "fila_buscar", None),
                "visor": getattr(v, "visor", None), "estado": v.statusBar()}

    def poner(self, spec: dict | None):
        """spec = cómo es BiriBiri (con su lugar elegido). None = que no aparezca."""
        s = avatar3d.normalizar(spec) if spec is not None else None
        lugar = s["lugar"] if s else "ninguno"
        if lugar not in TAMANOS:
            lugar = "ninguno"
        self._spec = s
        if lugar == "ninguno":
            self._lugar = lugar
            if self._vista is not None:
                self._vista.hide()
            return
        if self._vista is None or lugar != self._lugar:
            if self._vista is not None:
                self._vista.deleteLater()
            self._vista = vista3d.crear(s, "cuerpo", parent=self.v, con_pose=True, lugar=lugar)
            self._vista.setAttribute(Qt.WA_TransparentForMouseEvents)
            self._vista.setFixedSize(*TAMANOS[lugar])
            self._vista.pose(liviano=False, vaiven=0.0, sombra=False)
        else:
            self._vista.poner(s)
        self._lugar = lugar
        self.reposicionar()

    def eventFilter(self, obj, e):
        if self._vista is not None and e.type() in (QEvent.Resize, QEvent.Move, QEvent.Show, QEvent.Hide):
            self._pendiente.start()
        return False

    def reposicionar(self):
        vista, lugar = self._vista, self._lugar
        if vista is None or lugar not in TAMANOS:
            return
        v = self.v
        ancla = self._anclas().get(lugar)
        w, h = TAMANOS[lugar]
        visible = (ancla is not None and ancla.isVisible() and not getattr(v, "_video_completo", False)
                   and v.isVisible() and not v.isMinimized())
        if not visible:
            vista.hide()
            return
        r = ancla.rect()
        origen = ancla.mapTo(v, r.topLeft())
        if lugar == "lista":          # sentado sobre el borde de abajo de la lista, del lado derecho
            x, y = origen.x() + r.width() - w - 4, origen.y() + r.height() - h + 12
        elif lugar == "buscador":     # acostado encima del buscador
            x, y = origen.x() + r.width() - w - 90, origen.y() - h + 22
        elif lugar == "visor":        # en la esquina de abajo a la derecha del reproductor
            x, y = origen.x() + r.width() - w - 10, origen.y() + r.height() - h - 6
        else:                         # parado sobre la barra de abajo
            x, y = origen.x() + r.width() - w - 40, origen.y() - h + 14
        # Si el lugar es muy chico, no aparece (taparía todo)
        if r.width() < w + 20 or (lugar in ("lista", "visor") and r.height() < 150):
            vista.hide()
            return
        vista.move(max(0, x), max(0, y))
        vista.show()
        vista.raise_()
