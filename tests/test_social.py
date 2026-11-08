"""Cuentas, puntos y amigos: el cliente de TorrentVision contra el servidor de verdad (en un puerto local)."""
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "servidor_social"))
import servidor  # noqa: E402

from organizador import social  # noqa: E402


class PruebaSocial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.carpeta = tempfile.mkdtemp()
        cls.srv = servidor.crear_servidor(0, os.path.join(cls.carpeta, "s.db"), "127.0.0.1")
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def cliente(self, nombre, clave="clave-segura"):
        c = social.Cliente(self.base)
        r = c.registrar(nombre, clave)
        return c, r

    def test_cuenta_sin_correo_y_recuperacion(self):
        c, r = self.cliente("ana_cine")
        self.assertRegex(r["recuperacion"], r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")
        with self.assertRaises(social.ErrorSocial):
            social.Cliente(self.base).registrar("ana_cine", "otra-clave-larga")
        with self.assertRaises(social.ErrorSocial):
            social.Cliente(self.base).entrar("ana_cine", "equivocada")
        self.assertEqual(social.Cliente(self.base).entrar("ANA_CINE", "clave-segura")["nombre"], "ana_cine")
        nuevo = social.Cliente(self.base).recuperar("ana_cine", r["recuperacion"], "clave-nueva-1")
        self.assertNotEqual(nuevo["recuperacion"], r["recuperacion"])
        with self.assertRaises(social.ErrorSocial):  # la sesión vieja se cerró al cambiar la contraseña
            c.yo()
        with self.assertRaises(social.ErrorSocial):  # el código viejo ya no sirve
            social.Cliente(self.base).recuperar("ana_cine", r["recuperacion"], "otra-clave-9")

    def test_puntos_sin_repetir_y_con_tope(self):
        c, _ = self.cliente("beto_series")
        pelis = [{"huella": social.huella(f"pelicula|p{i}|2000"), "tipo": "pelicula"} for i in range(8)]
        r = c.enviar_vistas(pelis[:3])
        self.assertEqual((r["puntos"], r["peliculas"], r["rango"]), (30, 3, "Espectador"))
        self.assertEqual(c.enviar_vistas(pelis[:3])["nuevas"], 0)  # repetidas no suman
        r = c.enviar_vistas(pelis)
        self.assertEqual(r["puntos"], servidor.TOPE_DIARIO)  # tope por día
        self.assertTrue(r["tope_hoy"])
        r = c.enviar_vistas([{"huella": "no-es-huella", "tipo": "pelicula"}, {"huella": "a" * 64, "tipo": "trampa"}])
        self.assertEqual(r["nuevas"], 0)

    def test_amigos_y_avatar(self):
        a, _ = self.cliente("carla_3d")
        b, _ = self.cliente("dani_pochoclo")
        b.guardar_avatar({"remera": "#123456", "peinado": "rulos", "accesorio": "hackear", "otro": "x"})
        b.enviar_vistas([{"huella": social.huella("pelicula|x|1999"), "tipo": "pelicula"}])
        a.pedir_amistad("dani_pochoclo")
        self.assertEqual(b.amigos()["recibidas"], ["carla_3d"])
        self.assertEqual(a.amigos()["amigos"], [])  # hasta que acepte, no ve nada
        b.responder("carla_3d", True)
        amigo = a.amigos()["amigos"][0]
        self.assertEqual((amigo["nombre"], amigo["puntos"], amigo["peliculas"]), ("dani_pochoclo", 10, 1))
        self.assertEqual(amigo["avatar"], {"remera": "#123456", "peinado": "rulos"})  # lo raro no se guarda
        a.quitar("dani_pochoclo")
        self.assertEqual(b.amigos()["amigos"], [])
        with self.assertRaises(social.ErrorSocial):
            a.pedir_amistad("no_existe_nadie")

    def test_sin_sesion_y_direcciones(self):
        with self.assertRaises(social.ErrorSocial) as e:
            social.Cliente(self.base).yo()
        self.assertEqual(e.exception.codigo, 401)
        with self.assertRaises(social.ErrorSocial):
            social.direccion_valida("http://cuentas.ejemplo.com")  # sin cifrar en internet: no
        self.assertEqual(social.direccion_valida("https://cuentas.ejemplo.com/"), "https://cuentas.ejemplo.com")
        self.assertEqual(social.direccion_valida("http://192.168.1.10:8780"), "http://192.168.1.10:8780")


if __name__ == "__main__":
    unittest.main()
