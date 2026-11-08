"""Detectar la introducción de una serie, para ofrecer «⏭ Saltar intro».

La intro es el mismo pedazo de audio (la canción y los efectos) en todos los capítulos. Se sacan con ffmpeg los
primeros minutos de dos capítulos de la misma serie, se calcula una huella del sonido cada 0,1 s (como hace
Chromaprint: cómo cambia la energía entre bandas de frecuencia) y se busca el tramo largo que se repite en los dos.
Es la idea del plugin «Intro Skipper» de Jellyfin, con numpy y sin dependencias nuevas.
"""
from __future__ import annotations

import subprocess

import numpy as np

HZ = 8000
PASO = 800                 # 0,1 s por cuadro de huella
VENTANA = 2048
MAX_SEGUNDOS = 600         # se mira el comienzo de cada capítulo (la intro casi siempre está en los primeros 10 min)
MIN_INTRO_S, MAX_INTRO_S = 12, 150
BANDAS = np.geomspace(150, 3800, 34)


class ErrorIntro(Exception):
    pass


def audio(ffmpeg: str, ruta: str, segundos: int = MAX_SEGUNDOS) -> np.ndarray:
    orden = [ffmpeg, "-hide_banner", "-loglevel", "error", "-t", str(segundos), "-i", ruta, "-vn", "-sn", "-dn",
             "-ac", "1", "-ar", str(HZ), "-f", "s16le", "-"]
    try:
        r = subprocess.run(orden, capture_output=True, timeout=240,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ErrorIntro(f"No se pudo leer el audio: {e}") from e
    datos = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32)
    if len(datos) < HZ * 60:
        raise ErrorIntro("El audio es demasiado corto")
    return datos


def huella(muestras: np.ndarray) -> np.ndarray:
    """Cómo suena cada 0,1 s: la energía en 33 bandas de frecuencia (en escala logarítmica), normalizada por
    capítulo y por cuadro. Se compara por parecido (correlación), no por igualdad: así sirve aunque los capítulos
    tengan el audio un poco distinto (otra grabación, otro volumen, otra compresión)."""
    n = (len(muestras) - VENTANA) // PASO
    indices = np.arange(VENTANA)[None, :] + PASO * np.arange(n)[:, None]
    cuadros = muestras[indices] * np.hanning(VENTANA)[None, :]
    espectro = np.abs(np.fft.rfft(cuadros, axis=1)) ** 2
    frecs = np.fft.rfftfreq(VENTANA, 1 / HZ)
    lugar = np.searchsorted(frecs, BANDAS)
    bandas = np.stack([espectro[:, a:b].sum(axis=1) for a, b in zip(lugar[:-1], lugar[1:])], axis=1)
    e = np.log(bandas + 1.0)
    e = (e - e.mean(axis=0)) / (e.std(axis=0) + 1e-6)          # por banda, en todo el capítulo
    e = e - e.mean(axis=1, keepdims=True)                      # por cuadro: la forma, no el volumen
    e /= np.linalg.norm(e, axis=1, keepdims=True) + 1e-6
    return e.astype(np.float32)


def _corrimientos(a: np.ndarray, b: np.ndarray, cuantos: int = 12) -> list[int]:
    """Los corrimientos (en cuadros) en que los dos audios más se parecen, por correlación con FFT."""
    n = len(a) + len(b)
    largo = 1 << (n - 1).bit_length()
    fa = np.fft.rfft(a, largo, axis=0)
    fb = np.fft.rfft(b, largo, axis=0)
    corr = np.fft.irfft((np.conj(fa) * fb).sum(axis=1), largo)   # corr[d] = sum_i a[i]·b[i+d]
    corr = np.concatenate([corr[-(len(a) - 1):], corr[:len(b)]])  # d de -(len(a)-1) a len(b)-1
    desde = -(len(a) - 1)
    orden = np.argsort(corr)[::-1]
    elegidos: list[int] = []
    for k in orden:
        d = int(k) + desde
        if all(abs(d - x) > 30 for x in elegidos):
            elegidos.append(d)
        if len(elegidos) >= cuantos:
            break
    return elegidos


def _tramo_largo(parecido: np.ndarray, umbral: float = 0.55, hueco: int = 15) -> tuple[int, int] | None:
    """El tramo más largo en que los dos audios se parecen (tolera huecos cortos de hasta 1,5 s)."""
    suave = np.convolve(parecido, np.ones(10) / 10, mode="same") > umbral
    mejor, inicio, ultimo = None, None, -10 ** 9
    for i in np.nonzero(suave)[0]:
        if inicio is None or i - ultimo > hueco:
            inicio = i
        ultimo = i
        if mejor is None or (i - inicio) > (mejor[1] - mejor[0]):
            mejor = (inicio, i)
    return mejor


def comparar(a: np.ndarray, b: np.ndarray) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """La parte que se repite en dos capítulos: ((inicio, fin) en a, (inicio, fin) en b), en segundos."""
    resultado, largo_mejor = None, 0
    for d in _corrimientos(a, b):
        i0, i1 = max(0, -d), min(len(a), len(b) - d)
        if i1 - i0 < MIN_INTRO_S * 10:
            continue
        parecido = np.einsum("ij,ij->i", a[i0:i1], b[i0 + d:i1 + d])
        tramo = _tramo_largo(parecido)
        if tramo is None:
            continue
        largo = tramo[1] - tramo[0]
        if largo > largo_mejor:
            largo_mejor = largo
            resultado = ((i0 + tramo[0]) / 10, (i0 + tramo[1]) / 10), ((i0 + tramo[0] + d) / 10, (i0 + tramo[1] + d) / 10)
    if resultado is None or not MIN_INTRO_S <= largo_mejor / 10 <= MAX_INTRO_S:
        return None
    return resultado


# --- El detector, en segundo plano ---------------------------------------------------------------------------

import threading  # noqa: E402

from PySide6.QtCore import QObject, Signal  # noqa: E402

TOLERANCIA_S = 5.0   # dos comparaciones «coinciden» si la intro empieza y termina a menos de esto


def combinar(resultados: list[tuple[float, float] | None]) -> tuple[float, float] | None:
    """La intro del capítulo según sus comparaciones con otros: con dos o más, tienen que coincidir."""
    validos = [r for r in resultados if r]
    if not validos:
        return None
    if len(resultados) == 1:
        return validos[0]
    for i, a in enumerate(validos):
        for b in validos[i + 1:]:
            if abs(a[0] - b[0]) <= TOLERANCIA_S and abs(a[1] - b[1]) <= TOLERANCIA_S:
                return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    return None


class DetectorIntro(QObject):
    """Detecta intros de a una, en un hilo propio. `listo(ruta, inicio_ms, fin_ms)`: (0, 0) si no se encontró."""
    listo = Signal(str, int, int)

    def __init__(self, ffmpeg_ruta):
        super().__init__()
        self._ffmpeg = ffmpeg_ruta          # función que devuelve la ruta de ffmpeg (o None)
        self._cola: list[tuple[str, list[str]]] = []
        self._huellas: dict[str, np.ndarray] = {}
        self._cerrojo = threading.Condition()
        self._en_curso: set[str] = set()
        threading.Thread(target=self._bucle, daemon=True, name="intro").start()

    def pedir(self, ruta: str, companeros: list[str], primero: bool = True):
        """Buscar la intro de `ruta` comparándola con otros capítulos de la misma temporada."""
        if not companeros:
            return
        with self._cerrojo:
            if ruta in self._en_curso or any(r == ruta for r, _c in self._cola):
                return
            self._cola.insert(0, (ruta, companeros)) if primero else self._cola.append((ruta, companeros))
            self._cerrojo.notify()

    def _huella(self, ffmpeg: str, ruta: str) -> np.ndarray:
        if ruta not in self._huellas:
            if len(self._huellas) > 8:
                self._huellas.pop(next(iter(self._huellas)))
            self._huellas[ruta] = huella(audio(ffmpeg, ruta))
        return self._huellas[ruta]

    def _bucle(self):
        while True:
            with self._cerrojo:
                while not self._cola:
                    self._cerrojo.wait()
                ruta, companeros = self._cola.pop(0)
                self._en_curso.add(ruta)
            try:
                ffmpeg = self._ffmpeg()
                if not ffmpeg:
                    continue
                propia = self._huella(ffmpeg, ruta)
                resultados = []
                for otro in companeros[:2]:
                    try:
                        r = comparar(propia, self._huella(ffmpeg, otro))
                    except ErrorIntro:
                        continue
                    resultados.append(r[0] if r else None)
                if not resultados:
                    continue
                intro = combinar(resultados)
                inicio, fin = (int(intro[0] * 1000), int(intro[1] * 1000)) if intro else (0, 0)
                self.listo.emit(ruta, inicio, fin)
            except (ErrorIntro, OSError, ValueError, MemoryError):
                pass
            finally:
                with self._cerrojo:
                    self._en_curso.discard(ruta)
