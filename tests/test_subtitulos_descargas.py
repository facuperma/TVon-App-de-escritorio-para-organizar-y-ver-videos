"""Subtítulos bajados a Descargas (sueltos, en .zip o ya descomprimidos) que se ponen solos junto a su video."""
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from organizador.db import Biblioteca  # noqa: E402
from organizador.subtitulos import video_del_subtitulo  # noqa: E402
from organizador.vigilancia import Vigilante  # noqa: E402

SRT = "1\n00:00:01,000 --> 00:00:02,000\nHola\n"


class EmparejarNombres(unittest.TestCase):
    videos = [r"C:\V\Before.Sunrise.1995.1080p.BluRay.x264-[YTS.AM].mp4",
              r"C:\V\Before.Sunset.2004.1080p.BluRay.x264.AAC5.1-[YTS.MX].mp4",
              r"C:\V\Twin.Peaks.S03E01.720p.mkv", r"C:\V\Twin.Peaks.S03E02.720p.mkv"]

    def test_subdivx(self):
        self.assertEqual(video_del_subtitulo(["Before Sunrise (1995) - [francox88] [339191]"], self.videos),
                         self.videos[0])
        self.assertEqual(video_del_subtitulo(["Before.Sunset.2004.720p.BrRip.x264.YIFY.srt"], self.videos),
                         self.videos[1])

    def test_capitulo(self):
        self.assertEqual(video_del_subtitulo(["Twin Peaks 3x02 - [x] [1]"], self.videos), self.videos[3])
        self.assertIsNone(video_del_subtitulo(["Twin Peaks - [x] [1]"], self.videos))  # ¿cuál capítulo?

    def test_otro_anio_u_otra_pelicula(self):
        self.assertIsNone(video_del_subtitulo(["Before Sunrise (1985)"], self.videos))
        self.assertIsNone(video_del_subtitulo(["Matrix (1999)"], self.videos))


class UbicarEnDescargas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.descargas, videos = raiz / "Descargas", raiz / "Videos"
        self.descargas.mkdir()
        (videos / "Before Sunrise (1995)").mkdir(parents=True)
        self.video = videos / "Before Sunrise (1995)" / "Before.Sunrise.1995.1080p.BluRay.x264-[YTS.AM].mp4"
        self.video2 = videos / "Before.Sunset.2004.1080p.BluRay.mp4"
        for v in (self.video, self.video2):
            v.write_bytes(b"0")
        self.bib = Biblioteca(raiz / "biblioteca.db")
        self.bib.guardar_config("carpeta_descargas_sistema", str(self.descargas))
        self.bib.agregar_archivos([self.video, self.video2])
        self.vig = Vigilante(raiz / "biblioteca.db")
        self.listos = []
        self.vig.subtitulo_listo.connect(lambda v, s: self.listos.append((v, s)))

    def tearDown(self):
        self.bib.con.close()
        self.tmp.cleanup()

    def _viejo(self, ruta: Path, segundos: int = 10):
        t = time.time() - segundos
        os.utime(ruta, (t, t))

    def test_zip_y_carpeta_descomprimida(self):
        archivo = self.descargas / "Before Sunset (2004) - [ripper77] [336574].zip"
        with zipfile.ZipFile(archivo, "w") as z:
            z.writestr("Before.Sunset.2004.720p.BrRip.x264.YIFY.srt", SRT)
        carpeta = self.descargas / "Before Sunrise (1995) - [francox88] [339191]"
        carpeta.mkdir()
        (carpeta / "Before.Sunrise.1995.DVDRip.DivX.srt").write_text(SRT, encoding="utf-8")
        otro = self.descargas / "TP-Excel.zip"
        with zipfile.ZipFile(otro, "w") as z:
            z.writestr("planilla.xlsx", "x")
        for p in (archivo, carpeta, otro):
            self._viejo(p)
        self.vig._ubicar_subtitulos(self.vig_bib())
        self.assertTrue(self.video.with_name(self.video.stem + ".es.srt").exists())
        self.assertTrue(self.video2.with_name(self.video2.stem + ".es.srt").exists())
        self.assertFalse(archivo.exists())
        self.assertFalse(carpeta.exists())
        self.assertTrue(otro.exists())  # lo que no es un subtítulo no se toca
        self.assertEqual(len(self.listos), 2)
        # Otro subtítulo para un video que ya tiene: no se agrega ni se borra
        repetido = self.descargas / "Before.Sunrise.1995.srt"
        repetido.write_text(SRT, encoding="utf-8")
        self._viejo(repetido)
        self.vig._ubicar_subtitulos(self.vig_bib())
        self.assertTrue(repetido.exists())

    def test_viejos_no_se_tocan(self):
        sub = self.descargas / "Before.Sunrise.1995.srt"
        sub.write_text(SRT, encoding="utf-8")
        self._viejo(sub, 3 * 24 * 3600)
        self.vig._ubicar_subtitulos(self.vig_bib())
        self.assertTrue(sub.exists())

    def vig_bib(self):
        return self.bib


if __name__ == "__main__":
    unittest.main()
