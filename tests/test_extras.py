import unittest
from pathlib import Path

from organizador.titulos import es_extra


class PruebaExtras(unittest.TestCase):
    def test_carpetas_de_extras(self):
        for ruta in (
            r"C:\Videos\Stalker.1979.CC.Bluray.1080p.DTS-HD-1.0.x264-Grym\Stalker.Extras-Grym\Rashit.Safiullin-Grym.mkv",
            r"C:\Videos\Stalker.1979.CC.Bluray.1080p.DTS-HD-1.0.x264-Grym\Stalker.Extras-Grym\Geoff.Dryer-Grym.mkv",
            r"C:\Videos\Pelicula (2020)\Extras\Entrevista.mkv",
            r"C:\Videos\Pelicula (2020)\Featurettes\Detras de escena.mp4",
            r"C:\Videos\Movie - Behind The Scenes\clip.mkv",
            r"C:\Videos\Movie.2020.1080p\Movie.Deleted.Scenes\scene1.mkv",
        ):
            self.assertTrue(es_extra(Path(ruta), 10 * 1024 ** 3), ruta)

    def test_no_son_extras(self):
        for ruta in (
            r"C:\Videos\Extras (2005)\Extras.S01E01.mkv",
            r"C:\Videos\Extras.S01.1080p.BluRay\Extras.S01E02.mkv",
            r"C:\Videos\The Interview (2014)\The.Interview.2014.1080p.mkv",
            r"C:\Videos\Stalker.1979.CC.Bluray.1080p.DTS-HD-1.0.x264-Grym\Stalker.1979.CC.Bluray.1080p.DTS-HD-1.0.x264-Grym.mkv",
            r"C:\Videos\Trailer Park Boys\Trailer.Park.Boys.S01E01.mkv",
        ):
            self.assertFalse(es_extra(Path(ruta), 3 * 1024 ** 3), ruta)


if __name__ == "__main__":
    unittest.main()
