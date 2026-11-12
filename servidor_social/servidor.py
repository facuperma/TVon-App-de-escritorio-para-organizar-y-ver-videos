"""Servidor de cuentas de TorrentVision: usuario y contraseña (sin correo), el muñequito, los puntos por lo que
se vio y los amigos. Solo usa la biblioteca estándar de Python.

    python servidor_social/servidor.py --puerto 8780 --base social.db

En internet tiene que ir detrás de HTTPS (un proxy como Caddy o el del hosting): las contraseñas viajan en el pedido.

Privacidad: el servidor no sabe QUÉ películas viste. TorrentVision manda una huella (SHA-256) de cada una, que sirve
para no contarla dos veces pero no dice cuál es. A los amigos solo se les muestra el muñequito, los puntos y cuántas
películas y capítulos viste.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

NOMBRE = re.compile(r"[A-Za-z0-9_]{3,20}")
HUELLA = re.compile(r"[0-9a-f]{64}")
CLAVE_MIN = 8
PUNTOS = {"pelicula": 10, "episodio": 2}
TOPE_DIARIO = 60
MAX_AMIGOS = 200
MAX_VISTAS_POR_PEDIDO = 5000
VIGENCIA_SESION = 365 * 24 * 3600
RANGOS = [(0, "Espectador"), (50, "Cinéfilo"), (150, "Crítico"), (400, "Programador"), (1000, "Archivista")]
COLORES_AVATAR = ("piel", "pelo", "ojos", "remera", "estampa_color", "pantalon", "zapatillas", "accesorio_color", "lentes_color",
                  "mascota_color", "mascota_color2")
# Las opciones de BiriBiri: el servidor guarda cualquier valor corto (TorrentVision revisa que exista al mostrarlo), así
# las opciones nuevas no necesitan actualizar el servidor
CLAVES_AVATAR = ("peinado", "boca", "barba", "cuerpo", "ropa", "estampa", "cabeza", "lentes", "extra", "genero", "mirada", "cejas",
                 "bandera", "pose", "lugar", "mascota", "interaccion")
NUMEROS_AVATAR = ("bandera_x", "bandera_y", "bandera_tam", "bandera_giro", "bandera_costado")
# Las mismas opciones que organizador/avatar3d.py (OPCIONES)
OPCIONES_AVATAR = {
    "peinado": ("corto", "flequillo", "largo", "colita", "trenzas", "rulos", "afro", "cresta", "rodete", "pelado"),
    "boca": ("sonrisa", "seria", "sorpresa", "lengua"),
    "barba": ("ninguna", "bigote", "candado", "barba"),
    "cuerpo": ("normal", "flaco", "robusto"),
    "ropa": ("remera", "boca", "buzo", "campera", "vestido"),
    "estampa": ("lisa", "rayas", "logo"),
    "cabeza": ("ninguno", "gorra", "gorro", "sombrero", "galera", "corona"),
    "lentes": ("ninguno", "anteojos", "lentes3d", "sol", "antifaz"),
    "extra": ("ninguno", "pochoclos", "gaseosa", "claqueta", "auriculares", "bufanda", "capa"),
}
ACCESORIOS = ("ninguno", "gorra", "anteojos", "lentes3d", "auriculares", "pochoclos")  # versión anterior
FOTO_MAXIMO = 24_000

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
    clave TEXT NOT NULL, recuperacion TEXT NOT NULL, avatar TEXT NOT NULL DEFAULT '{}', creado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sesiones (
    huella TEXT PRIMARY KEY, usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE, usada REAL NOT NULL);
CREATE TABLE IF NOT EXISTS vistas (
    usuario INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE, huella TEXT NOT NULL, tipo TEXT NOT NULL,
    puntos INTEGER NOT NULL, dia TEXT NOT NULL, PRIMARY KEY (usuario, huella));
CREATE TABLE IF NOT EXISTS casas (
    usuario INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE, datos TEXT NOT NULL, actualizada REAL NOT NULL);
CREATE TABLE IF NOT EXISTS amistades (
    de INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE, a INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    estado TEXT NOT NULL, PRIMARY KEY (de, a));
"""


class Error(Exception):
    def __init__(self, mensaje: str, codigo: int = 400):
        super().__init__(mensaje)
        self.codigo = codigo


# --- Contraseñas: scrypt (lenta a propósito) con sal propia ---------------------------------------------------

def cifrar(clave: str) -> str:
    sal = secrets.token_bytes(16)
    hecho = hashlib.scrypt(clave.encode(), salt=sal, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${sal.hex()}${hecho.hex()}"


def coincide(clave: str, guardada: str) -> bool:
    try:
        _, sal, hecho = guardada.split("$")
        nuevo = hashlib.scrypt(clave.encode(), salt=bytes.fromhex(sal), n=2 ** 14, r=8, p=1, dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(nuevo.hex(), hecho)


def rango(puntos: int) -> str:
    return [n for minimo, n in RANGOS if puntos >= minimo][-1]


def avatar_valido(datos) -> dict:
    if not isinstance(datos, dict):
        return {}
    limpio = {k: v.lower() for k, v in datos.items()
              if k in COLORES_AVATAR and isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v)}
    for clave in CLAVES_AVATAR:
        valor = datos.get(clave)
        if isinstance(valor, str) and re.fullmatch(r"[a-z0-9_]{1,30}", valor):
            limpio[clave] = valor
    for clave in NUMEROS_AVATAR:
        valor = datos.get(clave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool) and -1000 <= valor <= 1000:
            limpio[clave] = int(valor)
    if datos.get("accesorio") in ACCESORIOS:
        limpio["accesorio"] = datos["accesorio"]
    # La foto de la cara: solo un JPEG chico en base64 (se comprueba que sea de verdad un JPEG)
    foto = datos.get("foto")
    if isinstance(foto, str) and len(foto) <= FOTO_MAXIMO and re.fullmatch(r"data:image/jpeg;base64,[A-Za-z0-9+/=]+", foto):
        try:
            if base64.b64decode(foto.split(",", 1)[1], validate=True)[:3] == b"\xff\xd8\xff":
                limpio["foto"] = foto
        except ValueError:
            pass
    return limpio


class Social:
    """Toda la lógica, sin HTTP (así se prueba directo)."""

    def __init__(self, ruta_base: str):
        self.ruta = ruta_base
        self._local = threading.local()
        self._cerrojo = threading.Lock()
        self._intentos: dict[str, list[float]] = {}
        with self._con() as con:
            con.executescript(ESQUEMA)

    def _con(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.ruta, timeout=10)
            con.execute("PRAGMA foreign_keys = ON")
            con.execute("PRAGMA journal_mode = WAL")
            self._local.con = con
        return con

    # Freno a la fuerza bruta: 10 intentos fallidos (o 5 cuentas nuevas) por IP cada 10 minutos
    def _frenar(self, clave: str, limite: int):
        ahora = time.time()
        with self._cerrojo:
            lista = [t for t in self._intentos.get(clave, []) if ahora - t < 600]
            self._intentos[clave] = lista
            if len(lista) >= limite:
                raise Error("Demasiados intentos: esperá unos minutos", 429)

    def _anotar(self, clave: str):
        with self._cerrojo:
            self._intentos.setdefault(clave, []).append(time.time())

    def _sesion_nueva(self, usuario: int) -> str:
        token = secrets.token_urlsafe(32)
        with self._con() as con:
            con.execute("INSERT INTO sesiones VALUES (?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), usuario, time.time()))
        return token

    def usuario_de(self, token: str | None) -> int:
        if not token:
            raise Error("Tenés que entrar con tu cuenta", 401)
        huella = hashlib.sha256(token.encode()).hexdigest()
        con = self._con()
        fila = con.execute("SELECT usuario, usada FROM sesiones WHERE huella = ?", (huella,)).fetchone()
        if not fila or time.time() - fila[1] > VIGENCIA_SESION:
            raise Error("La sesión venció: entrá de nuevo", 401)
        if time.time() - fila[1] > 24 * 3600:
            with con:
                con.execute("UPDATE sesiones SET usada = ? WHERE huella = ?", (time.time(), huella))
        return fila[0]

    # --- Cuentas ---------------------------------------------------------------------------------------

    def registrar(self, nombre: str, clave: str, ip: str) -> dict:
        self._frenar("registro:" + ip, 5)
        if not NOMBRE.fullmatch(nombre or ""):
            raise Error("El usuario va de 3 a 20 letras, números o guiones bajos")
        if len(clave or "") < CLAVE_MIN or len(clave) > 200:
            raise Error(f"La contraseña necesita al menos {CLAVE_MIN} caracteres")
        # Sin correo, la única forma de recuperar la cuenta: un código que se muestra una sola vez
        codigo = "-".join(secrets.token_hex(2).upper() for _ in range(4))
        try:
            with self._con() as con:
                cur = con.execute("INSERT INTO usuarios (nombre, clave, recuperacion, creado) VALUES (?, ?, ?, ?)",
                                  (nombre, cifrar(clave), cifrar(codigo), time.time()))
        except sqlite3.IntegrityError:
            raise Error("Ese usuario ya existe: elegí otro", 409) from None
        self._anotar("registro:" + ip)
        return {"token": self._sesion_nueva(cur.lastrowid), "recuperacion": codigo, "nombre": nombre}

    def entrar(self, nombre: str, clave: str, ip: str) -> dict:
        self._frenar("entrar:" + ip, 10)
        fila = self._con().execute("SELECT id, nombre, clave FROM usuarios WHERE nombre = ?", (nombre or "",)).fetchone()
        if not fila or not coincide(clave or "", fila[2]):
            self._anotar("entrar:" + ip)
            raise Error("Usuario o contraseña incorrectos", 403)
        return {"token": self._sesion_nueva(fila[0]), "nombre": fila[1]}

    def recuperar(self, nombre: str, codigo: str, nueva: str, ip: str) -> dict:
        self._frenar("entrar:" + ip, 10)
        fila = self._con().execute("SELECT id, nombre, recuperacion FROM usuarios WHERE nombre = ?", (nombre or "",)).fetchone()
        if not fila or not coincide((codigo or "").strip().upper(), fila[2]):
            self._anotar("entrar:" + ip)
            raise Error("Usuario o código de recuperación incorrectos", 403)
        if len(nueva or "") < CLAVE_MIN:
            raise Error(f"La contraseña necesita al menos {CLAVE_MIN} caracteres")
        codigo_nuevo = "-".join(secrets.token_hex(2).upper() for _ in range(4))
        with self._con() as con:
            con.execute("UPDATE usuarios SET clave = ?, recuperacion = ? WHERE id = ?", (cifrar(nueva), cifrar(codigo_nuevo), fila[0]))
            con.execute("DELETE FROM sesiones WHERE usuario = ?", (fila[0],))  # se cierran las otras sesiones
        return {"token": self._sesion_nueva(fila[0]), "recuperacion": codigo_nuevo, "nombre": fila[1]}

    def salir(self, token: str):
        with self._con() as con:
            con.execute("DELETE FROM sesiones WHERE huella = ?", (hashlib.sha256(token.encode()).hexdigest(),))

    def borrar_cuenta(self, usuario: int, clave: str):
        fila = self._con().execute("SELECT clave FROM usuarios WHERE id = ?", (usuario,)).fetchone()
        if not fila or not coincide(clave or "", fila[0]):
            raise Error("Contraseña incorrecta", 403)
        with self._con() as con:
            con.execute("DELETE FROM usuarios WHERE id = ?", (usuario,))

    # --- Perfil y puntos -----------------------------------------------------------------------------------

    def perfil(self, usuario: int) -> dict:
        con = self._con()
        nombre, avatar = con.execute("SELECT nombre, avatar FROM usuarios WHERE id = ?", (usuario,)).fetchone()
        puntos, pelis, caps = con.execute(
            "SELECT COALESCE(SUM(puntos), 0), SUM(tipo = 'pelicula'), SUM(tipo = 'episodio') FROM vistas WHERE usuario = ?",
            (usuario,)).fetchone()
        return {"nombre": nombre, "avatar": json.loads(avatar or "{}"), "puntos": puntos, "peliculas": pelis or 0,
                "capitulos": caps or 0, "rango": rango(puntos)}

    def guardar_avatar(self, usuario: int, avatar) -> dict:
        with self._con() as con:
            con.execute("UPDATE usuarios SET avatar = ? WHERE id = ?", (json.dumps(avatar_valido(avatar)), usuario))
        return self.perfil(usuario)

    def sumar_vistas(self, usuario: int, items) -> dict:
        """Lo que se vio (huellas): cada una cuenta una sola vez, con un tope de puntos por día. Lo que no entra
        hoy se cuenta otro día (TorrentVision vuelve a mandar todo)."""
        if not isinstance(items, list) or len(items) > MAX_VISTAS_POR_PEDIDO:
            raise Error("Lista de vistas inválida")
        hoy = date.today().isoformat()
        con = self._con()
        ya = {h for (h,) in con.execute("SELECT huella FROM vistas WHERE usuario = ?", (usuario,))}
        sumados_hoy = con.execute("SELECT COALESCE(SUM(puntos), 0) FROM vistas WHERE usuario = ? AND dia = ?",
                                  (usuario, hoy)).fetchone()[0]
        nuevos = 0
        with con:
            for it in items:
                if not isinstance(it, dict):
                    continue
                huella, tipo = str(it.get("huella", "")), it.get("tipo")
                if not HUELLA.fullmatch(huella) or tipo not in PUNTOS or huella in ya:
                    continue
                if sumados_hoy + PUNTOS[tipo] > TOPE_DIARIO:
                    break
                con.execute("INSERT INTO vistas VALUES (?, ?, ?, ?, ?)", (usuario, huella, tipo, PUNTOS[tipo], hoy))
                ya.add(huella)
                sumados_hoy += PUNTOS[tipo]
                nuevos += 1
        return {**self.perfil(usuario), "nuevas": nuevos, "tope_hoy": sumados_hoy >= TOPE_DIARIO}

    # --- Amigos -----------------------------------------------------------------------------------------------

    # --- La videoteca (la habitación) ----------------------------------------------------------------------
    CLAVES_CASA = ("piso", "pared", "muebles", "adornos", "bandera", "bb", "mascota", "sentado")

    def guardar_casa(self, usuario: int, casa) -> dict:
        """Lo que se ve de la habitación (sin monedas ni inventario). La revisa TorrentVision al mostrarla."""
        if not isinstance(casa, dict):
            raise Error("Casa inválida")
        publica = {k: casa[k] for k in self.CLAVES_CASA if k in casa}
        texto = json.dumps(publica)
        if len(texto) > 64 * 1024:
            raise Error("La casa es demasiado grande", 413)
        with self._con() as con:
            con.execute("INSERT OR REPLACE INTO casas VALUES (?, ?, ?)", (usuario, texto, time.time()))
        return {"ok": True}

    def casa_de(self, usuario: int, nombre: str) -> dict:
        """La videoteca de un amigo (solo si son amigos)."""
        otro = self._id(nombre)
        con = self._con()
        amigos = con.execute("SELECT 1 FROM amistades WHERE de = ? AND a = ? AND estado = 'aceptada'", (usuario, otro)).fetchone()
        if not amigos and otro != usuario:
            raise Error("Solo podés visitar la videoteca de tus amigos", 403)
        fila = con.execute("SELECT datos FROM casas WHERE usuario = ?", (otro,)).fetchone()
        if not fila:
            raise Error(f"{nombre} todavía no armó su videoteca", 404)
        perfil = self.perfil(otro)
        return {"nombre": perfil["nombre"], "avatar": perfil["avatar"], "casa": json.loads(fila[0])}

    def _id(self, nombre: str) -> int:
        fila = self._con().execute("SELECT id FROM usuarios WHERE nombre = ?", (nombre or "",)).fetchone()
        if not fila:
            raise Error("No existe ese usuario", 404)
        return fila[0]

    def amigos(self, usuario: int) -> dict:
        con = self._con()
        aceptados = [a for (a,) in con.execute(
            "SELECT a FROM amistades WHERE de = ? AND estado = 'aceptada'", (usuario,))]
        recibidas = [n for (n,) in con.execute(
            "SELECT u.nombre FROM amistades x JOIN usuarios u ON u.id = x.de WHERE x.a = ? AND x.estado = 'pendiente'", (usuario,))]
        enviadas = [n for (n,) in con.execute(
            "SELECT u.nombre FROM amistades x JOIN usuarios u ON u.id = x.a WHERE x.de = ? AND x.estado = 'pendiente'", (usuario,))]
        lista = sorted((self.perfil(a) for a in aceptados), key=lambda p: -p["puntos"])
        return {"amigos": lista, "recibidas": recibidas, "enviadas": enviadas}

    def pedir_amistad(self, usuario: int, nombre: str) -> dict:
        otro = self._id(nombre)
        if otro == usuario:
            raise Error("No podés agregarte a vos mismo")
        con = self._con()
        if con.execute("SELECT COUNT(*) FROM amistades WHERE de = ?", (usuario,)).fetchone()[0] >= MAX_AMIGOS:
            raise Error("Llegaste al máximo de amigos")
        with con:
            inversa = con.execute("SELECT estado FROM amistades WHERE de = ? AND a = ?", (otro, usuario)).fetchone()
            if inversa and inversa[0] == "pendiente":  # el otro ya me había pedido: quedan amigos
                con.execute("UPDATE amistades SET estado = 'aceptada' WHERE de = ? AND a = ?", (otro, usuario))
                con.execute("INSERT OR REPLACE INTO amistades VALUES (?, ?, 'aceptada')", (usuario, otro))
            else:
                con.execute("INSERT OR IGNORE INTO amistades VALUES (?, ?, 'pendiente')", (usuario, otro))
        return self.amigos(usuario)

    def responder(self, usuario: int, nombre: str, aceptar: bool) -> dict:
        otro = self._id(nombre)
        con = self._con()
        with con:
            if not con.execute("SELECT 1 FROM amistades WHERE de = ? AND a = ? AND estado = 'pendiente'", (otro, usuario)).fetchone():
                raise Error("No hay un pedido de ese usuario", 404)
            if aceptar:
                con.execute("UPDATE amistades SET estado = 'aceptada' WHERE de = ? AND a = ?", (otro, usuario))
                con.execute("INSERT OR REPLACE INTO amistades VALUES (?, ?, 'aceptada')", (usuario, otro))
            else:
                con.execute("DELETE FROM amistades WHERE de = ? AND a = ?", (otro, usuario))
        return self.amigos(usuario)

    def quitar(self, usuario: int, nombre: str) -> dict:
        otro = self._id(nombre)
        with self._con() as con:
            con.execute("DELETE FROM amistades WHERE (de = ? AND a = ?) OR (de = ? AND a = ?)", (usuario, otro, otro, usuario))
        return self.amigos(usuario)


# --- HTTP ---------------------------------------------------------------------------------------------------------

class _Manejador(BaseHTTPRequestHandler):
    server_version = "TorrentVision-Social"
    sys_version = ""
    timeout = 30

    def log_message(self, *args):
        pass

    @property
    def social(self) -> Social:
        return self.server.social  # type: ignore[attr-defined]

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _cuerpo(self) -> dict:
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > 512 * 1024:
            raise Error("Pedido demasiado grande", 413)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            raise Error("JSON inválido") from None
        if not isinstance(datos, dict):
            raise Error("JSON inválido")
        return datos

    def _token(self) -> str | None:
        valor = self.headers.get("Authorization", "")
        return valor[7:].strip() if valor.startswith("Bearer ") else None

    def _ip(self) -> str:
        # Detrás de un proxy propio, la IP real viene en X-Forwarded-For (solo si se lo configuró)
        if self.server.confiar_proxy and (reenviada := self.headers.get("X-Forwarded-For")):  # type: ignore[attr-defined]
            return reenviada.split(",")[0].strip()
        return self.client_address[0]

    def do_GET(self):
        self._atender("GET")

    def do_POST(self):
        self._atender("POST")

    def _atender(self, metodo: str):
        ruta = urlparse(self.path).path.rstrip("/")
        try:
            s = self.social
            if metodo == "GET" and ruta == "/salud":
                return self._json({"ok": True, "servicio": "torrentvision-social"})
            if metodo == "POST" and ruta in ("/registro", "/entrar", "/recuperar"):
                d = self._cuerpo()
                if ruta == "/registro":
                    return self._json(s.registrar(str(d.get("nombre", "")), str(d.get("clave", "")), self._ip()))
                if ruta == "/entrar":
                    return self._json(s.entrar(str(d.get("nombre", "")), str(d.get("clave", "")), self._ip()))
                return self._json(s.recuperar(str(d.get("nombre", "")), str(d.get("codigo", "")),
                                              str(d.get("nueva", "")), self._ip()))
            token = self._token()
            usuario = s.usuario_de(token)
            if metodo == "GET" and ruta == "/yo":
                return self._json(s.perfil(usuario))
            if metodo == "GET" and ruta == "/amigos":
                return self._json(s.amigos(usuario))
            if metodo != "POST":
                raise Error("No existe", 404)
            d = self._cuerpo()
            if ruta == "/avatar":
                return self._json(s.guardar_avatar(usuario, d.get("avatar")))
            if ruta == "/vistas":
                return self._json(s.sumar_vistas(usuario, d.get("items")))
            if ruta == "/amigos/pedir":
                return self._json(s.pedir_amistad(usuario, str(d.get("nombre", ""))))
            if ruta == "/amigos/responder":
                return self._json(s.responder(usuario, str(d.get("nombre", "")), bool(d.get("aceptar"))))
            if ruta == "/casa":
                return self._json(s.guardar_casa(usuario, d.get("casa")))
            if ruta == "/casa/ver":
                return self._json(s.casa_de(usuario, str(d.get("nombre", ""))))
            if ruta == "/amigos/quitar":
                return self._json(s.quitar(usuario, str(d.get("nombre", ""))))
            if ruta == "/salir":
                s.salir(token or "")
                return self._json({"ok": True})
            if ruta == "/borrar_cuenta":
                s.borrar_cuenta(usuario, str(d.get("clave", "")))
                return self._json({"ok": True})
            raise Error("No existe", 404)
        except Error as e:
            self._json({"error": str(e)}, e.codigo)
        except (ConnectionError, TimeoutError):
            pass
        except Exception:  # noqa: BLE001 - sin detalles internos en la respuesta
            try:
                self._json({"error": "Error interno del servidor"}, 500)
            except OSError:
                pass


def crear_servidor(puerto: int, ruta_base: str, direccion: str = "0.0.0.0", confiar_proxy: bool = False):
    servidor = ThreadingHTTPServer((direccion, puerto), _Manejador)
    servidor.daemon_threads = True
    servidor.social = Social(ruta_base)  # type: ignore[attr-defined]
    servidor.confiar_proxy = confiar_proxy  # type: ignore[attr-defined]
    return servidor


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Servidor de cuentas y amigos de TorrentVision")
    a.add_argument("--puerto", type=int, default=8780)
    a.add_argument("--direccion", default="0.0.0.0")
    a.add_argument("--base", default=str(Path(__file__).with_name("social.db")))
    a.add_argument("--detras-de-proxy", action="store_true", help="usar X-Forwarded-For (solo detrás de tu proxy HTTPS)")
    args = a.parse_args()
    srv = crear_servidor(args.puerto, args.base, args.direccion, args.detras_de_proxy)
    print(f"TorrentVision Social en http://{args.direccion}:{args.puerto} (base: {args.base})")
    srv.serve_forever()
