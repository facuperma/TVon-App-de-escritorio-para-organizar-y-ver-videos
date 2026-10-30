r"""Celulares vinculados al modo ON: se recuerdan entre arranques, vencen y se desvinculan.

Correr desde la carpeta del proyecto: .venv\Scripts\python -m unittest discover tests
"""
import json
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from organizador import remoto as modulo, seguridad  # noqa: E402
from organizador.db import Biblioteca  # noqa: E402

app = QApplication.instance() or QApplication([])


class _Gestor(QObject):
    progreso = Signal(str, int, int)


class _Ventana:
    def __init__(self, bib):
        self.bib = bib
        self.gestor = _Gestor()


class SesionesOn(unittest.TestCase):
    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.ruta = Path(self.carpeta.name) / "biblioteca.db"
        self.bib = Biblioteca(self.ruta)

    def tearDown(self):
        self.bib.con.close()
        self.carpeta.cleanup()

    def _reabrir(self) -> modulo.Remoto:
        """Como cerrar TVon y volver a abrirlo: base y Remoto nuevos."""
        self.bib.con.close()
        self.bib = Biblioteca(self.ruta)
        return modulo.Remoto(_Ventana(self.bib))

    def test_sigue_vinculado_despues_de_reiniciar(self):
        r = modulo.Remoto(_Ventana(self.bib))
        token = r.emparejar(r.codigo, "TVonON/1.1.2 (Linux; Android 14; SM-S918B)")
        self.assertTrue(r.sesion_valida(token))
        guardado = self.bib.config("on_sesiones")
        self.assertNotIn(token, guardado)  # solo la huella, nunca la sesión
        crudo = self.bib.con.execute("SELECT valor FROM config WHERE clave='on_sesiones'").fetchone()[0]
        if seguridad.DISPONIBLE:
            self.assertTrue(crudo.startswith(seguridad.PREFIJO))  # y cifrado con DPAPI
        r2 = self._reabrir()
        self.assertTrue(r2.sesion_valida(token))
        self.assertEqual(len(r2.celulares()), 1)
        self.assertTrue(r2.al_iniciar)  # con celulares vinculados, ON se enciende solo

    def test_sin_celulares_on_no_arranca_solo(self):
        self.assertFalse(modulo.Remoto(_Ventana(self.bib)).al_iniciar)

    def test_eleccion_del_usuario_manda(self):
        r = modulo.Remoto(_Ventana(self.bib))
        r.emparejar(r.codigo, "x")
        r.guardar_opcion("on_activo", False)
        self.assertFalse(self._reabrir().al_iniciar)

    def test_vence_sin_usar_y_se_renueva_al_usar(self):
        r = modulo.Remoto(_Ventana(self.bib))
        viejo = r.emparejar(r.codigo, "a")
        usado = r.emparejar(r.codigo, "b")
        hace_29_dias = time.time() - 29 * 24 * 3600
        for h in r._sesiones:
            r._sesiones[h]["usada"] = hace_29_dias
        r._guardar_sesiones()
        self.assertTrue(r.sesion_valida(usado))  # se usó: se renueva por 30 días más
        self.assertGreater(r._sesiones[seguridad.huella_sesion(usado)]["usada"], hace_29_dias)
        r2 = self._reabrir()
        r2._sesiones[seguridad.huella_sesion(viejo)]["usada"] = time.time() - 31 * 24 * 3600
        self.assertFalse(r2.sesion_valida(viejo))  # 31 días sin usarse: vencida
        self.assertTrue(r2.sesion_valida(usado))
        self.assertEqual(len(self._reabrir().celulares()), 1)

    def test_vencidas_se_borran_al_abrir(self):
        datos = [{"huella": "a" * 64, "nombre": "viejo", "creada": "01/01/2026 10:00",
                  "usada": time.time() - 40 * 24 * 3600},
                 {"huella": "b" * 64, "nombre": "sin fecha", "creada": "28/10/2026 10:00"}]
        self.bib.guardar_config("on_sesiones", json.dumps(datos))
        r = self._reabrir()
        self.assertEqual([c["nombre"] for c in r.celulares()], ["sin fecha"])  # las de antes arrancan hoy
        self.assertNotIn("viejo", self.bib.config("on_sesiones"))

    def test_desvincular(self):
        r = modulo.Remoto(_Ventana(self.bib))
        uno = r.emparejar(r.codigo, "uno")
        dos = r.emparejar(r.codigo, "dos")
        r.desvincular(seguridad.huella_sesion(uno))
        self.assertFalse(r.sesion_valida(uno))
        r2 = self._reabrir()
        self.assertFalse(r2.sesion_valida(uno))
        self.assertTrue(r2.sesion_valida(dos))

    def test_mismo_certificado_entre_arranques(self):
        r = modulo.Remoto(_Ventana(self.bib))
        r._contexto_tls()
        huella = r.huella_certificado
        r2 = self._reabrir()
        r2._contexto_tls()
        self.assertEqual(huella, r2.huella_certificado)

    def test_descubrimiento_contesta_puerto_y_huella(self):
        r = modulo.Remoto(_Ventana(self.bib))
        r.emparejar(r.codigo, "x")
        if not r.iniciar():
            self.skipTest(r.error)
        try:
            if r._udp is None:
                self.skipTest("el puerto UDP está ocupado")
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(3)
            s.sendto(b"TVON?", ("127.0.0.1", modulo.PUERTO))
            respuesta = json.loads(s.recvfrom(512)[0])
            s.close()
            self.assertEqual(respuesta["puerto"], r.puerto)
            self.assertEqual(respuesta["huella"], r.huella_certificado.replace(":", ""))
        finally:
            r.detener()
        self.assertIsNone(r._udp)


if __name__ == "__main__":
    unittest.main()
