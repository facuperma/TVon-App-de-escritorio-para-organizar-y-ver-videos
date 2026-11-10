import unittest

import numpy as np

from organizador import sincronia as S


def _escena(semilla=1, minutos=60):
    """Una «película» sintética: diálogos al azar (cues) y la voz que les corresponde en el audio."""
    r = np.random.default_rng(semilla)
    cues, t = [], 5_000
    while t < minutos * 60_000:
        largo = int(r.integers(1200, 4200))
        cues.append((t, t + largo, f"Diálogo número {len(cues)}"))
        t += largo + int(r.integers(900, 9000))
    n = minutos * 60 * 50
    voz = np.zeros(n, dtype=np.float32)
    for a, b, _t in cues:
        voz[a // 20:b // 20] = 1.0
    voz = np.clip(np.convolve(voz, np.ones(5) / 5, mode="same") + r.normal(0, 0.18, n), 0, 1).astype(np.float32)
    return cues, voz


def _corridos(cues, ms):
    return [(a + ms, b + ms, t) for a, b, t in cues if a + ms >= 0]


class PruebaSincronia(unittest.TestCase):
    def test_encuentra_el_desfase(self):
        cues, voz = _escena()
        for ms in (0, 3700, -12400, 58300, -140000):
            r = S.estimar(voz, _corridos(cues, ms))
            # los subtítulos llegaron `ms` corridos: hay que llevarlos `-ms` para volver a donde estaban
            self.assertLessEqual(abs(r.retraso_ms - (-ms)), 100, ms)

    def test_no_aplica_nada_si_no_coincide(self):
        _cues, voz = _escena(1)
        otras, _ = _escena(2)
        with self.assertRaises(S.ErrorSincronia):
            S.estimar(voz, otras)

    def test_avisa_si_es_de_otra_velocidad(self):
        cues, voz = _escena(3, minutos=90)
        # El subtítulo va corriéndose 3 s a lo largo de la película
        estirados = [(int(a * 1.00055), int(b * 1.00055), t) for a, b, t in cues]
        r = S.estimar(voz, estirados)
        self.assertTrue(r.avisos)
        self.assertGreater(abs(r.deriva_ms), 1500)

    def test_ignora_carteles_que_no_son_voz(self):
        cues = [(0, 2000, "[MÚSICA]"), (0, 2000, "(puerta)"), (0, 2000, "♪ la la ♪"), (0, 2000, "Hola, ¿cómo estás?"),
                (0, 2000, "Subtitulado por Fulano"), (0, 2000, "[RUIDO]\nQué tal")]
        self.assertEqual(len(S.cues_de_dialogo(cues)), 2)


if __name__ == "__main__":
    unittest.main()
