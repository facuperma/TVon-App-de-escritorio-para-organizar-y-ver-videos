"""Sonidos chiquitos de la videoteca, hechos acá mismo (sin archivos de afuera): el de las moneditas al comprar."""
from __future__ import annotations

import math
import os
import struct
import wave
from pathlib import Path

HZ = 44100
_efectos: dict[str, object] = {}


def _carpeta() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TVon" / "sonidos"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _monedas(destino: Path):
    """Tres moneditas que caen una atrás de otra: un «cling» brillante (dos tonos metálicos que se apagan rápido)."""
    muestras = [0.0] * int(HZ * 0.75)
    for k, (inicio, tono) in enumerate(((0.0, 1975.5), (0.11, 2637.0), (0.23, 3135.9))):
        i0 = int(inicio * HZ)
        for n in range(int(HZ * 0.45)):
            t = n / HZ
            env = math.exp(-t * 11) * min(1.0, t * 400)
            v = (math.sin(2 * math.pi * tono * t) * 0.55 + math.sin(2 * math.pi * tono * 2.76 * t) * 0.25
                 + math.sin(2 * math.pi * tono * 5.4 * t) * 0.12 * math.exp(-t * 30))
            if i0 + n < len(muestras):
                muestras[i0 + n] += v * env * (0.75 - 0.12 * k)
    pico = max(abs(m) for m in muestras) or 1.0
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(HZ)
        w.writeframes(b"".join(struct.pack("<h", int(m / pico * 0.8 * 32767)) for m in muestras))


GENERADORES = {"monedas": _monedas}


def ruta(nombre: str) -> Path:
    archivo = _carpeta() / f"{nombre}_v1.wav"
    if not archivo.exists():
        GENERADORES[nombre](archivo)
    return archivo


def sonar(nombre: str, volumen: float = 0.6):
    """Lo hace sonar (si no hay audio en la PC, no pasa nada)."""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QSoundEffect
        efecto = _efectos.get(nombre)
        if efecto is None:
            efecto = QSoundEffect()
            efecto.setSource(QUrl.fromLocalFile(str(ruta(nombre))))
            _efectos[nombre] = efecto
        efecto.setVolume(volumen)
        efecto.play()
    except Exception:  # noqa: BLE001 - sin sonido no es un error
        pass
