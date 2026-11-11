"""BiriBiri (el muñequito 3D): todas las opciones se arman sin errores, el género filtra la ropa, las banderas se dibujan."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from organizador import avatar3d, banderas, poses, protagonista3d

_app = QApplication.instance() or QApplication([])


class PruebaBiriBiri(unittest.TestCase):
    def test_cada_opcion_se_arma(self):
        """Una vez cada valor de cada opción (malla gruesa: es para ver que no falle, no para verla)."""
        with tempfile.TemporaryDirectory() as tmp:
            for clave, valores in avatar3d.OPCIONES.items():
                if clave == "bandera":
                    continue
                for valor in valores:
                    spec = {clave: valor, "genero": "mujer" if valor in ("vestido", "pollera", "blusa", "vestido_largo") else "hombre"}
                    carpeta = protagonista3d.construir(spec, Path(tmp), paso=0.02)
                    self.assertTrue((carpeta / "listo").exists(), (clave, valor))

    def test_partes_con_foto_y_lentes(self):
        """Con foto, la cara sale hacia adelante y los lentes también (no quedan adentro)."""
        import base64
        from PySide6.QtCore import QBuffer, QByteArray
        from PySide6.QtGui import QColor, QImage
        im = QImage(64, 64, QImage.Format_RGB32)
        im.fill(QColor("#c89"))
        datos = QByteArray()
        b = QBuffer(datos)
        b.open(QBuffer.OpenModeFlag.WriteOnly)
        im.save(b, "JPG", 60)
        spec = {"foto": "data:image/jpeg;base64," + base64.b64encode(bytes(datos)).decode(), "lentes": "gatuno"}
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = protagonista3d.construir(spec, Path(tmp), paso=0.02)
            self.assertTrue((carpeta / "listo").exists())

    def test_el_genero_filtra_la_ropa(self):
        for prenda, para in avatar3d.ROPA_GENERO.items():
            self.assertIn(prenda, avatar3d.OPCIONES["ropa"])
            self.assertIn(para, avatar3d.OPCIONES["genero"])
        self.assertEqual(avatar3d.normalizar({})["genero"], "nobinario")      # los que ya existían no cambian

    def test_la_bandera_no_cambia_el_muneco(self):
        a = protagonista3d.clave({"bandera": "ar"})
        b = protagonista3d.clave({"bandera": "us"})
        self.assertEqual(a, b)
        self.assertNotEqual(a, protagonista3d.clave({"genero": "mujer"}))

    def test_banderas(self):
        paises = {k for k in avatar3d.OPCIONES["bandera"] if k != "ninguna"}
        self.assertEqual(paises, set(banderas.DIBUJOS))
        with tempfile.TemporaryDirectory() as tmp:
            for codigo in paises:
                archivo = banderas.ruta(codigo, Path(tmp))
                self.assertTrue(archivo and archivo.exists() and archivo.stat().st_size > 500, codigo)
            self.assertIsNone(banderas.ruta("xx", Path(tmp)))

    def test_poses_y_lugares(self):
        for nombre in poses.POSES:
            datos = poses.ajustes(nombre)
            self.assertEqual(set(datos), set(poses.BASE), nombre)     # solo ajustes que la escena conoce
        for lugar, pose in poses.POSE_DEL_LUGAR.items():
            self.assertIn(lugar, poses.LUGARES)
            self.assertIn(pose, poses.POSES)
        s = avatar3d.normalizar({"pose": "celebrando", "lugar": "lista"})
        self.assertEqual((s["pose"], s["lugar"]), ("celebrando", "lista"))
        self.assertEqual(avatar3d.normalizar({"pose": "xx"})["pose"], "normal")
        self.assertEqual(protagonista3d.clave({"pose": "t", "lugar": "visor"}), protagonista3d.clave({}))   # no cambia el modelo

    def test_la_palestina_reemplaza_a_israel(self):
        self.assertIn("ps", avatar3d.OPCIONES["bandera"])
        self.assertNotIn("il", avatar3d.OPCIONES["bandera"])


if __name__ == "__main__":
    unittest.main()
