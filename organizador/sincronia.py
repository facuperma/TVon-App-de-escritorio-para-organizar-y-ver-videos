"""Sincronización automática de subtítulos: se compara CUÁNDO se habla en el audio del video con CUÁNDO
hay diálogos en el archivo de subtítulos, y se busca el desplazamiento en que más coinciden.

Cómo se hace fiable:
  * Del audio se toma el canal central (en 5.1 van ahí los diálogos; la música y los efectos quedan en los
    otros) y solo la banda de la voz (120 Hz a 3,8 kHz).
  * Qué es «voz» se decide con el nivel local (cada ~10 s), no con un umbral para toda la película: sirve
    igual en escenas calladas, con música o con mucho ruido.
  * De los subtítulos se descartan los que no son diálogo ([MÚSICA], (puerta), ♪…).
  * Se busca el mejor desfase en toda la película y después se comprueba por tramos de 8 minutos: si los tramos
    coinciden, el resultado es seguro; si no, no se aplica nada (peor sería dejarlos mal puestos).
  * Si el audio principal no da un resultado seguro se prueban las otras pistas de audio.
  * Si el desfase va cambiando a lo largo de la película (subtítulos de otra velocidad de cuadros) se avisa.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

import numpy as np

PASO_MS = 20                  # tamaño de cada tramo de análisis
HZ = 8000                     # audio mono a 8 kHz: de sobra para detectar voz
MUESTRAS = HZ * PASO_MS // 1000
MAX_DESFASE_MS = 300_000      # se busca hasta 5 minutos para cada lado
TRAMO = 24_000                # 8 minutos (en pasos de 20 ms)
SALTO = 12_000                # un tramo nuevo cada 4 minutos
RADIO_TRAMO = 500             # en cada tramo se mira ±10 s alrededor del desfase general
MIN_CONFIANZA = 4.0           # (se conserva por compatibilidad: el criterio real está en `_decidir`)


class ErrorSincronia(Exception):
    pass


@dataclass
class Resultado:
    retraso_ms: int
    confianza: float
    acuerdo: float = 1.0                 # fracción de tramos que coinciden con el desfase elegido
    deriva_ms: int = 0                   # cuánto cambia el desfase entre el principio y el final (0 si no hay datos)
    pista: int = 0                       # de qué pista de audio salió
    avisos: list[str] = field(default_factory=list)


# --- Audio ----------------------------------------------------------------------------------------------

def _filtro(canales: int) -> str:
    banda = "highpass=f=120,lowpass=f=3800"
    # 5.1 / 5.0: el canal central (el tercero) es donde van los diálogos
    return f"pan=mono|c0=c2,{banda}" if canales >= 5 else banda


def energia_del_audio(ffmpeg: str, ruta_video: str, indice_audio: int = 0, canales: int = 2, progreso=None) -> np.ndarray:
    """La energía (RMS) por tramo de 20 ms del audio, ya sin graves ni agudos."""
    orden = [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", ruta_video, "-map", f"0:a:{indice_audio}",
             "-vn", "-sn", "-dn", "-af", _filtro(canales), "-ac", "1", "-ar", str(HZ), "-f", "s16le", "-"]
    try:
        proceso = subprocess.Popen(orden, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        raise ErrorSincronia(f"No se pudo abrir ffmpeg: {e}") from e
    energias: list[np.ndarray] = []
    resto = b""
    vistos = 0
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
            vistos += len(energias[-1])
            if progreso:
                progreso(vistos * PASO_MS / 1000)
    finally:
        proceso.stdout.close()
        proceso.wait()
    if not energias:
        raise ErrorSincronia("No se pudo leer el audio del video")
    return np.concatenate(energias)


def puntaje_de_voz(energia: np.ndarray) -> np.ndarray:
    """0 a 1 por tramo: cuánto se parece a una voz hablando, según el nivel LOCAL (cada ~10 s)."""
    db = np.log10(energia + 1.0)
    n = len(db)
    if n < 500:
        raise ErrorSincronia("El video es demasiado corto para sincronizar")
    g_piso, g_techo = np.percentile(db, [10, 92])
    if g_techo - g_piso < 0.2:
        raise ErrorSincronia("El audio no tiene diferencias para detectar las voces")
    bloque = 500                                    # 10 s
    cantidad = int(np.ceil(n / bloque))
    pisos, techos = np.empty(cantidad), np.empty(cantidad)
    for i in range(cantidad):
        parte = db[i * bloque:(i + 1) * bloque]
        pisos[i], techos[i] = np.percentile(parte, [15, 92])
    # Entre bloques se suaviza; un bloque callado no puede inflar el ruido: se apoya en el piso y el rango globales
    suave = np.ones(5) / 5
    pisos = np.convolve(np.pad(pisos, 2, mode="edge"), suave, mode="valid")
    techos = np.convolve(np.pad(techos, 2, mode="edge"), suave, mode="valid")
    centros = (np.arange(cantidad) + 0.5) * bloque
    x = np.arange(n)
    piso = np.maximum(np.interp(x, centros, pisos), g_piso)
    techo = np.maximum(np.interp(x, centros, techos), piso + 0.6 * (g_techo - g_piso))
    puntaje = np.clip((db - piso) / (techo - piso), 0.0, 1.0)
    # Un poco de suavizado (100 ms) para que no titile
    return np.convolve(puntaje, np.ones(5) / 5, mode="same").astype(np.float32)


# --- Subtítulos -----------------------------------------------------------------------------------------

_ENTRE_CORCHETES = re.compile(r"[\[\(\{][^\]\)\}]*[\]\)\}]")
_CREDITOS = re.compile(r"(?i)subt[ií]tul|subtitled|traduc|sincroniz|\bsync\b|opensubtitles|www\.|\w\.(?:com|org|net)\b")


def cues_de_dialogo(cues: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Sin los carteles que no son voz: [MÚSICA], (puerta), ♪ letras ♪, «Subtitulado por…»."""
    limpios = []
    for a, b, texto in cues:
        t = texto.strip()
        if b - a < 250 or not t or "♪" in t or "♫" in t or _CREDITOS.search(t):
            continue
        hablado = re.sub(r"[\W_]+", "", _ENTRE_CORCHETES.sub("", t))
        if len(hablado) < 2:              # todo era un cartel entre corchetes o paréntesis
            continue
        limpios.append((a, b, t))
    return limpios


def actividad_de_subtitulos(cues: list[tuple[int, int, str]], largo: int) -> np.ndarray:
    """1 donde hay un diálogo en pantalla (sin ajuste)."""
    s = np.zeros(largo, dtype=np.float32)
    for a, b, _texto in cues:
        i, j = max(0, a // PASO_MS), min(largo, b // PASO_MS + 1)
        if i < j:
            s[i:j] = 1.0
    return s


# --- Búsqueda del desfase --------------------------------------------------------------------------------

def _cruzada(a: np.ndarray, s: np.ndarray) -> np.ndarray:
    """corr[u] = sum_t a[t] * s[t + u], para u = 0 .. len(s) - len(a) («valid»), por FFT."""
    tam = 1 << int(np.ceil(np.log2(len(a) + len(s))))
    c = np.fft.irfft(np.fft.rfft(s, tam) * np.conj(np.fft.rfft(a, tam)), tam)
    return c[:len(s) - len(a) + 1]


def _pico(valores: np.ndarray, ancho_exclusion: int) -> tuple[int, float, float]:
    """(índice del mejor, confianza z, relación con el segundo mejor lejano)."""
    k = int(np.argmax(valores))
    med = float(np.median(valores))
    sigma = float(np.std(valores)) or 1.0
    z = (float(valores[k]) - med) / sigma
    mascara = np.ones(len(valores), dtype=bool)
    mascara[max(0, k - ancho_exclusion):k + ancho_exclusion + 1] = False
    segundo = float(valores[mascara].max()) if mascara.any() else med
    relacion = (float(valores[k]) - med) / max(segundo - med, 1e-9)
    return k, z, relacion


def desfase_general(voz: np.ndarray, subs: np.ndarray) -> tuple[int, float, float]:
    """(desfase en pasos de 20 ms, z, relación). Positivo: los subtítulos tienen que salir más tarde."""
    n = len(voz)
    tope = min(MAX_DESFASE_MS // PASO_MS, n - 1)
    a = voz - voz.mean()
    s = subs[:n] - subs[:n].mean()
    if len(s) < n:
        s = np.concatenate([s, np.zeros(n - len(s), dtype=np.float32)])
    # Los subtítulos corridos d pasos: subs'[t] = subs[t - d]. Con relleno de ceros a ambos lados de s.
    relleno = np.zeros(tope, dtype=np.float32)
    s_largo = np.concatenate([relleno, s, relleno])
    corr = _cruzada(a, s_largo)[:2 * tope + 1]     # u = 0..2*tope  ->  d = tope - u
    k, z, relacion = _pico(corr, 50)
    return tope - k, z, relacion


def _por_tramos(voz: np.ndarray, subs: np.ndarray, d0: int) -> list[tuple[int, int, float]]:
    """Para cada tramo de la película: (inicio, mejor desfase local, z). Solo mira ±10 s alrededor de d0."""
    n = len(voz)
    R = RADIO_TRAMO
    resultados = []
    for t0 in range(0, max(1, n - TRAMO // 2), SALTO):
        a = voz[t0:t0 + TRAMO]
        if len(a) < TRAMO // 2:
            break
        # Los subtítulos de ese tramo: necesita subs[t0 - d0 - R + j], j = 0 .. len(a) + 2R - 1
        desde = t0 - d0 - R
        s_seg = np.zeros(len(a) + 2 * R, dtype=np.float32)
        i0, i1 = max(0, desde), min(len(subs), desde + len(s_seg))
        if i1 > i0:
            s_seg[i0 - desde:i1 - desde] = subs[i0:i1]
        if s_seg.sum() < 0.04 * len(s_seg):          # casi sin diálogos en este tramo: no sirve
            continue
        corr = _cruzada(a - a.mean(), s_seg - s_seg.mean())   # u = 0..2R ; d = d0 + R - u
        k, z, _rel = _pico(corr, 25)
        resultados.append((t0, d0 + R - k, z))
    return resultados


def _recta_robusta(puntos: list[tuple[int, int, float]]) -> tuple[float, float]:
    """(ordenada, pendiente) por Theil-Sen: la mediana de las pendientes entre pares, que no se deja engañar por
    unos pocos tramos erróneos. Con muy pocos puntos, una recta horizontal en su mediana."""
    if len(puntos) < 4:
        return float(np.median([d for _t, d, _z in puntos])) if puntos else 0.0, 0.0
    t = np.array([x[0] for x in puntos], dtype=np.float64)
    d = np.array([x[1] for x in puntos], dtype=np.float64)
    i, j = np.triu_indices(len(t), k=1)
    separados = (t[j] - t[i]) > SALTO / 2
    if not separados.any():
        return float(np.median(d)), 0.0
    pendiente = float(np.median((d[j] - d[i])[separados] / (t[j] - t[i])[separados]))
    return float(np.median(d - pendiente * t)), pendiente


def estimar(voz: np.ndarray, cues: list[tuple[int, int, str]], pista: int = 0) -> Resultado:
    """Calcula el desfase a partir de la voz del audio y los diálogos. Lanza ErrorSincronia si no es seguro."""
    dialogo = cues_de_dialogo(cues)
    if len(dialogo) < 20:
        raise ErrorSincronia("El subtítulo tiene muy pocos diálogos para compararlos con el audio")
    subs = actividad_de_subtitulos(dialogo, len(voz))
    if subs.sum() < 0.03 * len(voz):
        raise ErrorSincronia("Los diálogos del subtítulo no caen dentro de este video (¿es de otra película?)")
    d0, z, relacion = desfase_general(voz, subs)
    tramos = _por_tramos(voz, subs, d0)
    utiles = [x for x in tramos if x[2] >= 2.0]
    # El desfase puede ir corriéndose un poco (subtítulos de otra versión): se ajusta una recta a los tramos
    ordenada, pendiente = _recta_robusta(utiles)
    pasos_deriva = pendiente * len(voz)
    deriva_ms = int(pasos_deriva * PASO_MS)
    if abs(deriva_ms) < 400 or abs(deriva_ms) > 9000:
        pendiente, ordenada = 0.0, (float(np.median([d for _t, d, _z in utiles])) if utiles else float(d0))
        deriva_ms = 0
    coinciden = [(t, d, zi) for t, d, zi in utiles if abs(d - (ordenada + pendiente * t)) <= 15]    # ±300 ms
    n, k = len(tramos), len(coinciden)
    acuerdo = k / n if n else 0.0
    # Cuánto más de lo esperable por azar (un desfase cualquiera cae en esa franja el ~3 % de las veces)
    p0 = 31 / (2 * RADIO_TRAMO + 1)
    zb = (k - n * p0) / np.sqrt(n * p0 * (1 - p0)) if n else 0.0
    if coinciden:
        if pendiente:
            final = int(round(ordenada + pendiente * (len(voz) / 2)))     # al medio de la película
        else:
            final = int(np.median([d for _t, d, _z in coinciden]))
    else:
        final = d0
    avisos: list[str] = []
    if deriva_ms:
        avisos.append(f"Los subtítulos se van corriendo {abs(deriva_ms) / 1000:.1f} s a lo largo de la película (parece que "
                      "son de otra versión): quedan bien en el medio y algo corridos al principio y al final.")
    # Criterio: o un pico claro en toda la película que los tramos respaldan, o muchos tramos de acuerdo
    seguro = ((z >= 6.0 and relacion >= 1.2 and (n < 3 or acuerdo >= 0.3))
              or (zb >= 6.0 and k >= 4 and acuerdo >= 0.4)
              or (z >= 4.0 and relacion >= 1.15 and zb >= 4.5 and acuerdo >= 0.5))
    if not seguro:
        dura_subs = max(b for _a, b, _t in cues) / 60000
        dura_video = len(voz) * PASO_MS / 60000
        if dura_video > 20 and (dura_subs < 0.65 * dura_video or dura_subs > 1.25 * dura_video):
            raise ErrorSincronia(f"Este subtítulo no es de esta película\nEl subtítulo dura {dura_subs:.0f} min y la película "
                                 f"{dura_video:.0f} min: es de otra película o de otra versión. Buscá otro archivo de subtítulos.")
        raise ErrorSincronia("No se pudo sincronizar con seguridad (el audio no coincide con estos subtítulos, o casi "
                             "no hay diálogos). Probá con «🎯 Ahora» o con otro archivo de subtítulos")
    return Resultado(final * PASO_MS, float(z), acuerdo, deriva_ms, pista, avisos)


# --- Punto de entrada ------------------------------------------------------------------------------------

def _pistas_de_audio(ruta_video: str) -> list[tuple[int, int]]:
    """[(índice, canales)] de las pistas de audio, empezando por la principal."""
    try:
        from .roku import analizar
        info = analizar(ruta_video)
    except Exception:  # noqa: BLE001 - sin ffprobe se usa la primera pista
        info = {}
    audios = info.get("audios") or []
    if not audios:
        return [(0, 2)]
    principal = info.get("audio_idx", 0)
    orden = [principal] + [i for i in range(len(audios)) if i != principal]
    return [(i, audios[i]["canales"] or 2) for i in orden][:3]


def sincronizar_detallado(ffmpeg: str, ruta_video: str, cues: list[tuple[int, int, str]], progreso=None) -> Resultado:
    """Calcula el retraso (ms) que hay que aplicar a los subtítulos. Lanza ErrorSincronia si no se pudo
    o si el resultado no es confiable (para no dejar los subtítulos peor de lo que estaban)."""
    if len(cues) < 20:
        raise ErrorSincronia("El subtítulo tiene muy pocos diálogos para compararlos con el audio")
    ultimo: ErrorSincronia | None = None
    pistas = _pistas_de_audio(ruta_video)
    for n, (indice, canales) in enumerate(pistas):
        try:
            voz = puntaje_de_voz(energia_del_audio(ffmpeg, ruta_video, indice, canales, progreso))
            resultado = estimar(voz, cues, indice)
        except ErrorSincronia as e:
            ultimo = e
            continue
        if n:
            resultado.avisos.append(f"Se usó la pista de audio {indice + 1}.")
        return resultado
    raise ultimo or ErrorSincronia("No se pudo sincronizar")


def sincronizar(ffmpeg: str, ruta_video: str, cues: list[tuple[int, int, str]], progreso=None) -> tuple[int, float]:
    """(retraso en ms, confianza). Ver sincronizar_detallado."""
    r = sincronizar_detallado(ffmpeg, ruta_video, cues, progreso)
    return r.retraso_ms, r.confianza


def instalar_ffmpeg() -> None:
    """Con winget (viene con Windows 10/11), en una consola a la vista para seguir el progreso."""
    subprocess.Popen(["cmd", "/c", "winget install --id Gyan.FFmpeg -e --accept-source-agreements "
                      "--accept-package-agreements & echo. & echo Listo: ya podes cerrar esta ventana. & pause"],
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
