"""Sincronización automática de subtítulos: se compara CUÁNDO se habla en el audio del video con CUÁNDO
hay diálogos en el archivo de subtítulos, y se busca el desplazamiento en que más coinciden.

Es la misma idea de ffsubsync, sin sus dependencias pesadas: ffmpeg saca el audio (mono, 8 kHz), la
energía por tramos de 20 ms dice dónde hay voz, y una correlación por FFT (numpy) encuentra el desfase.
No corrige que el subtítulo vaya "estirándose" (otra velocidad de cuadros): solo un corrimiento fijo,
que es lo habitual cuando el archivo es de otra versión del video.
"""
import subprocess

import numpy as np

PASO_MS = 20                  # tamaño de cada tramo de análisis
HZ = 8000                     # audio mono a 8 kHz: de sobra para detectar voz
MUESTRAS = HZ * PASO_MS // 1000
MAX_DESFASE_MS = 300_000      # se busca hasta 5 minutos para cada lado
MIN_CONFIANZA = 4.0           # cuánto más fuerte que el ruido tiene que ser el mejor desfase


class ErrorSincronia(Exception):
    pass


def actividad_del_audio(ffmpeg: str, ruta_video: str, progreso=None) -> np.ndarray:
    """Un valor 0/1 por tramo de 20 ms: 1 donde hay voz (o algo parecido) en el audio del video."""
    orden = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", ruta_video, "-vn", "-sn", "-dn",
             "-ac", "1", "-ar", str(HZ), "-f", "s16le", "-"]
    try:
        proceso = subprocess.Popen(orden, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        raise ErrorSincronia(f"No se pudo abrir ffmpeg: {e}") from e
    energias: list[np.ndarray] = []
    resto = b""
    try:
        while True:
            bloque = proceso.stdout.read(MUESTRAS * 2 * 5000)  # ~100 s de audio por vez
            if not bloque:
                break
            datos = resto + bloque
            util = len(datos) // (MUESTRAS * 2) * (MUESTRAS * 2)
            resto = datos[util:]
            if not util:
                continue
            m = np.frombuffer(datos[:util], dtype=np.int16).astype(np.float32).reshape(-1, MUESTRAS)
            energias.append(np.sqrt((m * m).mean(axis=1)))
            if progreso:
                progreso(sum(len(e) for e in energias) * PASO_MS / 1000)
    finally:
        proceso.stdout.close()
        proceso.wait()
    if not energias:
        raise ErrorSincronia("No se pudo leer el audio del video")
    energia = np.concatenate(energias)
    # Umbral entre el piso de ruido y el nivel de la voz (en escala logarítmica, que es como se oye)
    db = np.log10(energia + 1.0)
    bajo, alto = np.percentile(db, [20, 90])
    if alto - bajo < 0.2:
        raise ErrorSincronia("El audio no tiene diferencias para detectar las voces")
    voz = (db > (bajo + alto) / 2).astype(np.float32)
    # Tragos cortos de silencio dentro de una frase no cuentan: se unen (~0,3 s)
    nucleo = np.ones(15, dtype=np.float32)
    # (solo hacia adelante: el comienzo de cada frase tiene que quedar donde está, es lo que se compara)
    return (np.convolve(voz, nucleo, mode="full")[:len(voz)] > 0).astype(np.float32)


def actividad_de_subtitulos(cues: list[tuple[int, int, str]], largo: int) -> np.ndarray:
    """Lo mismo para el archivo de subtítulos: 1 donde hay un diálogo en pantalla (sin ajuste)."""
    s = np.zeros(largo, dtype=np.float32)
    for a, b, _texto in cues:
        i, j = max(0, a // PASO_MS), min(largo, b // PASO_MS + 1)
        if i < j:
            s[i:j] = 1.0
    return s


def mejor_desfase(audio: np.ndarray, subs: np.ndarray) -> tuple[int, float]:
    """(desfase en ms, confianza). Positivo: los subtítulos tienen que salir más tarde."""
    n = len(audio)
    a = audio * 2 - 1  # +1 hay voz, -1 silencio: coincidir suma y discrepar resta
    s = subs[:n] * 2 - 1
    if len(s) < n:
        s = np.concatenate([s, -np.ones(n - len(s), dtype=np.float32)])
    tam = 1 << int(np.ceil(np.log2(2 * n)))
    corr = np.fft.irfft(np.fft.rfft(a, tam) * np.conj(np.fft.rfft(s, tam)), tam)
    # corr[d] = sum a[t] * s[t - d]: el índice d (o d - tam, si es negativo) es el desfase en tramos
    tope = min(MAX_DESFASE_MS // PASO_MS, n - 1)
    candidatos = np.concatenate([corr[:tope + 1], corr[tam - tope:]])
    desfases = np.concatenate([np.arange(0, tope + 1), np.arange(-tope, 0)])
    k = int(np.argmax(candidatos))
    # Confianza: cuánto sobresale el pico respecto de lo que da un desfase cualquiera
    ruido = float(np.std(candidatos)) or 1.0
    confianza = float((candidatos[k] - np.median(candidatos)) / ruido)
    return int(desfases[k]) * PASO_MS, confianza


def sincronizar(ffmpeg: str, ruta_video: str, cues: list[tuple[int, int, str]], progreso=None) -> tuple[int, float]:
    """Calcula el retraso (ms) que hay que aplicar a los subtítulos. Lanza ErrorSincronia si no se pudo
    o si el resultado no es confiable (para no dejar los subtítulos peor de lo que estaban)."""
    if len(cues) < 20:
        raise ErrorSincronia("El subtítulo tiene muy pocos diálogos para compararlos con el audio")
    audio = actividad_del_audio(ffmpeg, ruta_video, progreso)
    subs = actividad_de_subtitulos(cues, len(audio))
    retraso, confianza = mejor_desfase(audio, subs)
    if confianza < MIN_CONFIANZA:
        raise ErrorSincronia("No se pudo sincronizar con seguridad (el audio no coincide con estos subtítulos). "
                             "Probá con «🎯 Ahora» o con otro archivo de subtítulos")
    return retraso, confianza


def instalar_ffmpeg() -> None:
    """Con winget (viene con Windows 10/11), en una consola a la vista para seguir el progreso."""
    subprocess.Popen(["cmd", "/c", "winget install --id Gyan.FFmpeg -e --accept-source-agreements "
                      "--accept-package-agreements & echo. & echo Listo: ya podes cerrar esta ventana. & pause"],
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
