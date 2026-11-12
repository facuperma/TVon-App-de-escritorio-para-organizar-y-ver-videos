"""El menú de desarrollador: lo guardado se revisa y se aplica encima del tema."""
import unittest

from organizador import diseno, temas


class PruebaDiseno(unittest.TestCase):
    def test_normalizar(self):
        d = diseno.normalizar({"colores": {"fondo": "#123456", "texto": "rojo", "inventado": "#000000"}, "tam_letra": 99,
                               "aire": 10, "barra": {"orden": ["on", "archivos", "trucho"], "ocultos": ["peliculas", "x"]},
                               "columnas": ["der", "izq", "centro"], "controles_ocultos": ["stop", "nada"]})
        self.assertEqual(d["colores"], {"fondo": "#123456"})
        self.assertEqual((d["tam_letra"], d["aire"]), (18, 50))
        self.assertEqual(d["barra"]["orden"][:2], ["on", "archivos"])
        self.assertEqual(set(x for x in d["barra"]["orden"] if x != "|"), set(diseno.BARRA) - {"|"})   # no se pierde ninguno
        self.assertEqual(d["barra"]["ocultos"], ["peliculas"])
        self.assertEqual(d["columnas"], ["der", "izq", "centro"])
        self.assertEqual(d["controles_ocultos"], ["stop"])
        self.assertEqual(diseno.normalizar("no es json"), diseno.normalizar({}))

    def test_se_aplica_sobre_el_tema(self):
        t = temas.TEMAS[0]
        d = diseno.normalizar({"colores": {"acento": "#ff0000"}, "letra": "Arial", "radio": 3, "tam_letra": 12, "aire": 140})
        nuevo = diseno.tema_con(t, d)
        self.assertEqual((nuevo.acento, nuevo.letra, nuevo.radio), ("#ff0000", "Arial", 3))
        hoja = temas.estilo(nuevo) + diseno.qss(d)
        self.assertIn("#ff0000", hoja)
        self.assertIn("font-size: 12pt", hoja)
        self.assertIs(diseno.tema_con(t, diseno.normalizar({})), t)       # sin retoques, el mismo tema


if __name__ == "__main__":
    unittest.main()
