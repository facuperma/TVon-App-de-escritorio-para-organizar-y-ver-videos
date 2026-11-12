"""La casa de BiriBiri: monedas, compras, muebles en la grilla y guardado."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from organizador import casa, muebles
from organizador.db import Biblioteca

_app = QApplication.instance() or QApplication([])


class PruebaCasa(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.bib = Biblioteca(Path(self.tmp.name) / "b.db")
        self.casa = casa.Casa(self.bib)

    def tearDown(self):
        self.tmp.cleanup()

    def test_monedas_por_lo_que_se_ve(self):
        antes = self.casa.monedas
        vistas = [{"huella": "a", "tipo": "pelicula"}, {"huella": "b", "tipo": "episodio"}]
        self.assertEqual(self.casa.cobrar(vistas), casa.RECOMPENSA["pelicula"] + casa.RECOMPENSA["episodio"])
        self.assertEqual(self.casa.cobrar(vistas), 0)          # cada una se cobra una sola vez
        self.assertEqual(self.casa.monedas, antes + 60)

    def test_comprar_y_poner(self):
        self.assertFalse(self.casa.comprar_mueble("heladera") and self.casa.monedas < 0)
        self.casa.datos["monedas"] = 1000
        self.assertTrue(self.casa.comprar_mueble("sillon"))
        self.assertEqual(self.casa.monedas, 1000 - casa.CATALOGO["sillon"]["precio"])
        self.assertIsNone(self.casa.poner_mueble("mesa", 0, 0))           # no lo compró
        i = self.casa.poner_mueble("sillon", 2, 2, 0)
        self.assertEqual(i, 0)
        self.assertNotIn("sillon", self.casa.datos["inventario"])
        self.casa.guardar_mueble(0)
        self.assertEqual(self.casa.datos["inventario"]["sillon"], 1)

    def test_no_se_pisan_ni_se_salen(self):
        self.casa.datos["monedas"] = 2000
        for item in ("sillon", "sillon", "alfombra", "mesa"):
            self.casa.comprar_mueble(item)
        self.assertEqual(self.casa.poner_mueble("sillon", 0, 0), 0)
        self.assertIsNone(self.casa.poner_mueble("sillon", 1, 1))                     # se pisa con el primero
        self.assertIsNone(self.casa.poner_mueble("sillon", casa.COLUMNAS - 1, 0))     # se sale por la derecha
        self.assertIsNotNone(self.casa.poner_mueble("alfombra", 0, 0))                # la alfombra se pone abajo de todo
        self.assertIsNotNone(self.casa.poner_mueble("mesa", 6, 4))
        self.assertTrue(self.casa.girar_mueble(0))
        self.assertEqual(self.casa.datos["muebles"][0]["rot"], 90)

    def test_acabados_y_guardado(self):
        self.casa.datos["monedas"] = 500
        self.assertTrue(self.casa.comprar_piso("marmol") and self.casa.poner_piso("marmol"))
        self.assertFalse(self.casa.poner_pared("ladrillo"))             # todavía no es suya
        self.casa.comprar_pared("ladrillo")
        self.casa.poner_pared("ladrillo")
        otra = casa.Casa(self.bib)                                      # se vuelve a leer lo guardado
        self.assertEqual((otra.datos["piso"], otra.datos["pared"]), ("marmol", "ladrillo"))

    def test_lo_guardado_mal_se_corrige(self):
        self.bib.guardar_config("casa", '{"piso": "xx", "monedas": -5, "muebles": [{"id": "sillon", "cx": 99, "cz": -4, "rot": 45, "color": "#123456"}, {"id": "dragon"}]}')
        c = casa.Casa(self.bib)
        self.assertEqual((c.datos["piso"], c.datos["monedas"]), ("madera", 0))
        self.assertEqual(len(c.datos["muebles"]), 1)
        m = c.datos["muebles"][0]
        self.assertTrue(c.cabe("sillon", m["cx"], m["cz"], m["rot"], sin=0))
        self.assertEqual(m["color"], casa.CATALOGO["sillon"]["colores"][0])

    def test_cada_mueble_y_textura_se_arma(self):
        with tempfile.TemporaryDirectory() as tmp:
            for item, datos in casa.CATALOGO.items():
                glb = muebles.construir(item, datos["colores"][0], tmp)
                self.assertTrue(glb.exists() and glb.stat().st_size > 500, item)
            for clave, (_n, _p, c1, dibujo, c2) in {**casa.PISOS, **casa.PAREDES}.items():
                if dibujo != "liso":
                    self.assertTrue(muebles.textura(clave, dibujo, c1, c2, tmp).exists(), clave)

    def test_sentarse(self):
        self.casa.datos["monedas"] = 2000
        for item in ("sillon", "silla_gamer", "mesa"):
            self.casa.comprar_mueble(item)
        self.casa.poner_mueble("mesa", 8, 6, 0)
        self.casa.poner_mueble("sillon", 0, 0, 0)
        self.casa.poner_mueble("silla_gamer", 6, 0, 0)
        self.assertFalse(self.casa.sentar("bb", 0))                       # en una mesa no se sienta nadie
        self.assertTrue(self.casa.sentar("bb", 1, 0))
        self.assertTrue(self.casa.sentar("mascota", 1, 0))                # el lugar estaba ocupado: se corre al libre
        self.assertEqual(self.casa.datos["sentado"]["mascota"], [1, 1])
        self.assertTrue(self.casa.sentar("bb", 2, 0))
        self.assertFalse(self.casa.sentar("mascota", 2, 0) and self.casa.datos["sentado"]["mascota"] == [2, 0])   # la silla es de uno
        self.casa.guardar_mueble(0)                                       # sacar la mesa: los muebles cambian de número
        self.assertEqual(self.casa.datos["sentado"]["bb"], [1, 0])
        self.casa.guardar_mueble(0)                                       # sacar el sillón: la mascota se levanta
        self.assertIsNone(self.casa.datos["sentado"]["mascota"])
        self.casa.parar()
        self.assertEqual(self.casa.datos["sentado"], {"bb": None, "mascota": None, "falda": False})


if __name__ == "__main__":
    unittest.main()
