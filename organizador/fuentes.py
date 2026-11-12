"""Las tipografías que trae la app (Inter, con licencia libre OFL; ver fuentes/Inter-LICENCIA.txt)."""
from __future__ import annotations

import sys
from pathlib import Path

PESOS = ("Regular", "Medium", "SemiBold", "Bold")
_listas = False


def carpeta() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "organizador" / "fuentes"


def registrar() -> list[str]:
    """Le avisa a Qt de las fuentes de la app (una sola vez). Devuelve las familias que quedaron disponibles."""
    global _listas
    from PySide6.QtGui import QFontDatabase
    familias: list[str] = []
    for peso in PESOS:
        archivo = carpeta() / f"Inter-{peso}.ttf"
        if archivo.exists():
            if not _listas:
                QFontDatabase.addApplicationFont(str(archivo))
    _listas = True
    return [f for f in QFontDatabase.families() if f.startswith("Inter")]
