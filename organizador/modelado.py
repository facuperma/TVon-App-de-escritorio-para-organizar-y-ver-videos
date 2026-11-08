"""Modelado suave para el Protagonista: cada pieza es un volumen (una «función de distancia») hecho de formas que
se funden entre sí con uniones suaves, y se convierte en una malla fina y lisa («surface nets»). Las normales salen
del mismo volumen, así la luz cae pareja, sin facetas ni costuras. El resultado se guarda como .glb (glTF) para
dibujarlo con Qt Quick 3D, en la placa de video.

Todo con numpy: no hace falta instalar nada más.
"""
from __future__ import annotations

import json
import struct

import numpy as np

# --- Formas (distancia con signo: negativa adentro) --------------------------------------------------------


def esfera(p, c, r):
    return np.linalg.norm(p - np.asarray(c, np.float32), axis=-1) - r


def elipsoide(p, c, radios):
    """Aproximación buena de la distancia a un elipsoide (la de Inigo Quilez)."""
    q = (p - np.asarray(c, np.float32))
    r = np.asarray(radios, np.float32)
    k0 = np.linalg.norm(q / r, axis=-1)
    k1 = np.linalg.norm(q / (r * r), axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def capsula(p, a, b, ra, rb=None):
    """Segmento de a a b, con radio ra en a y rb en b (un cono redondeado: mechones, brazos, piernas)."""
    rb = ra if rb is None else rb
    a = np.asarray(a, np.float32)
    b = np.asarray(b, np.float32)
    ba = b - a
    pa = p - a
    h = np.clip((pa @ ba) / float(ba @ ba), 0.0, 1.0)
    return np.linalg.norm(pa - h[..., None] * ba, axis=-1) - (ra + (rb - ra) * h)


def caja_redonda(p, c, medidas, r):
    q = np.abs(p - np.asarray(c, np.float32)) - (np.asarray(medidas, np.float32) / 2 - r)
    afuera = np.linalg.norm(np.maximum(q, 0.0), axis=-1)
    adentro = np.minimum(np.max(q, axis=-1), 0.0)
    return afuera + adentro - r


def curva(p, puntos, r0, r1, pasos=10):
    """Un mechón: tubo que sigue una curva de Bézier (por los puntos de control) y se afina de r0 a r1."""
    pts = np.asarray(puntos, np.float32)
    n = len(pts) - 1
    t = np.linspace(0, 1, pasos + 1)
    from math import comb
    curva_pts = sum(comb(n, i) * ((1 - t) ** (n - i) * t ** i)[:, None] * pts[i] for i in range(n + 1))
    d = None
    for i in range(pasos):
        ra = r0 + (r1 - r0) * t[i]
        rb = r0 + (r1 - r0) * t[i + 1]
        s = capsula(p, curva_pts[i], curva_pts[i + 1], ra, rb)
        d = s if d is None else np.minimum(d, s)
    return d


def unir(a, b, k=0.0):
    """Unión; con k > 0, suave (las formas se funden en vez de tocarse)."""
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def restar(a, b, k=0.0):
    """a menos b (con borde suave si k > 0)."""
    if k <= 0:
        return np.maximum(a, -b)
    h = np.clip(0.5 - 0.5 * (b + a) / k, 0.0, 1.0)
    return a + (-b - a) * h + k * h * (1.0 - h)


def cortar(a, b, k=0.0):
    """Intersección (lo que está en a y en b)."""
    if k <= 0:
        return np.maximum(a, b)
    h = np.clip(0.5 - 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h + k * h * (1.0 - h)


# --- De volumen a malla -------------------------------------------------------------------------------------

def _volumen(funcion, minimo, n, paso, grueso: int = 4):
    """La función en toda la grilla, pero calculada fina solo cerca de la superficie: primero una pasada gruesa
    (1 de cada `grueso` puntos por eje) y después, punto por punto, donde la gruesa dice que la superficie está cerca.
    Lejos, alcanza con el signo (y el valor aproximado) de la pasada gruesa. ~10 veces más rápido."""
    ng = (n - 1) // grueso + 2
    ejes_g = [minimo[i] + paso * grueso * np.arange(ng[i], dtype=np.float32) for i in range(3)]
    fg = funcion(np.stack(np.meshgrid(*ejes_g, indexing="ij"), axis=-1)).astype(np.float32)
    # Interpolación trilineal de la gruesa a la fina
    rel = [np.arange(n[i], dtype=np.float32) / grueso for i in range(3)]
    i0 = [np.minimum(np.floor(r).astype(int), ng[k] - 2) for k, r in enumerate(rel)]
    w = [r - i for r, i in zip(rel, i0)]
    f = np.zeros(tuple(n), np.float32)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                peso = ((w[0] if dx else 1 - w[0])[:, None, None] * (w[1] if dy else 1 - w[1])[None, :, None]
                        * (w[2] if dz else 1 - w[2])[None, None, :])
                f += peso * fg[np.ix_(i0[0] + dx, i0[1] + dy, i0[2] + dz)]
    banda = paso * grueso * 2.0
    cerca = np.argwhere(np.abs(f) < banda)
    if len(cerca):
        puntos = minimo + cerca.astype(np.float32) * paso
        for i in range(0, len(cerca), 400_000):
            trozo = cerca[i:i + 400_000]
            f[tuple(trozo.T)] = funcion(puntos[i:i + 400_000]).astype(np.float32)
    return f


def malla(funcion, minimo, maximo, paso: float = 0.006):
    """La superficie donde la función vale 0, como (vértices, normales, triángulos). «Surface nets»: un vértice por
    celda que corta la superficie (en el promedio de los cruces) y un cuadrilátero por arista que la atraviesa."""
    minimo = np.asarray(minimo, np.float32)
    maximo = np.asarray(maximo, np.float32)
    n = np.ceil((maximo - minimo) / paso).astype(int) + 1
    f = _volumen(funcion, minimo, n, paso)
    if not (f < 0).any():
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros((0, 3), np.uint32)
    s = f < 0
    # Las 8 esquinas de cada celda
    esq = [(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)]
    nx, ny, nz = n

    def tomar(arr, o):
        return arr[o[0]:nx - 1 + o[0], o[1]:ny - 1 + o[1], o[2]:nz - 1 + o[2]]

    alguno = np.zeros((nx - 1, ny - 1, nz - 1), bool)
    todos = np.ones((nx - 1, ny - 1, nz - 1), bool)
    for o in esq:
        alguno |= tomar(s, o)
        todos &= tomar(s, o)
    activa = alguno & ~todos
    celdas = np.argwhere(activa)
    indice = -np.ones(activa.shape, np.int64)
    indice[tuple(celdas.T)] = np.arange(len(celdas))
    # Posición de cada vértice: promedio de los cruces en las 12 aristas de la celda
    aristas = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    suma = np.zeros((len(celdas), 3), np.float32)
    cuenta = np.zeros(len(celdas), np.float32)
    ci, cj, ck = celdas.T
    for a, b in aristas:
        oa, ob = np.array(esq[a]), np.array(esq[b])
        fa = f[ci + oa[0], cj + oa[1], ck + oa[2]]
        fb = f[ci + ob[0], cj + ob[1], ck + ob[2]]
        cruza = (fa < 0) != (fb < 0)
        t = np.where(cruza, fa / np.where(cruza, fa - fb, 1.0), 0.0)
        punto = oa[None, :] + t[:, None] * (ob - oa)[None, :]
        suma += np.where(cruza[:, None], punto, 0.0)
        cuenta += cruza
    local = suma / np.maximum(cuenta, 1)[:, None]
    vert = minimo + (celdas + local) * paso
    # Caras: por cada arista de la grilla que atraviesa la superficie, las 4 celdas que la rodean
    caras = []
    for eje in range(3):
        o1, o2 = [(e) for e in range(3) if e != eje]
        corte = [slice(None)] * 3
        corte_sig = [slice(None)] * 3
        corte[eje] = slice(0, n[eje] - 1)
        corte_sig[eje] = slice(1, n[eje])
        a = s[tuple(corte)]
        b = s[tuple(corte_sig)]
        cambia = a != b
        pos = np.argwhere(cambia)
        # las celdas vecinas necesitan índice -1 en los otros dos ejes
        pos = pos[(pos[:, o1] >= 1) & (pos[:, o2] >= 1) & (pos[:, o1] <= n[o1] - 2) & (pos[:, o2] <= n[o2] - 2)]
        if not len(pos):
            continue
        adentro_primero = a[tuple(pos.T)]

        def celda(d1, d2):
            q = pos.copy()
            q[:, o1] -= d1
            q[:, o2] -= d2
            return indice[tuple(q.T)]

        v0, v1, v2, v3 = celda(1, 1), celda(0, 1), celda(0, 0), celda(1, 0)
        validos = (v0 >= 0) & (v1 >= 0) & (v2 >= 0) & (v3 >= 0)
        v0, v1, v2, v3, adentro_primero = v0[validos], v1[validos], v2[validos], v3[validos], adentro_primero[validos]
        t1 = np.stack([v0, v1, v2], axis=1)
        t2 = np.stack([v0, v2, v3], axis=1)
        # El sentido de los triángulos: hacia afuera
        dar_vuelta = adentro_primero if eje == 1 else ~adentro_primero
        t1[dar_vuelta] = t1[dar_vuelta][:, ::-1]
        t2[dar_vuelta] = t2[dar_vuelta][:, ::-1]
        caras += [t1, t2]
    tris = np.concatenate(caras).astype(np.uint32) if caras else np.zeros((0, 3), np.uint32)
    # Normales: el gradiente del volumen en cada vértice (luz pareja, sin facetas)
    gx, gy, gz = np.gradient(f, paso)
    rel = (vert - minimo) / paso
    i0 = np.clip(np.floor(rel).astype(int), 0, n - 2)
    w = rel - i0
    normal = np.zeros_like(vert)
    for o in esq:
        peso = np.prod(np.where(np.array(o)[None, :] == 1, w, 1 - w), axis=1)
        ii = (i0[:, 0] + o[0], i0[:, 1] + o[1], i0[:, 2] + o[2])
        normal += peso[:, None] * np.stack([gx[ii], gy[ii], gz[ii]], axis=1)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-9)
    return vert.astype(np.float32), normal.astype(np.float32), tris


# --- glTF (.glb) ------------------------------------------------------------------------------------------

def guardar_glb(ruta, partes: list[tuple[str, tuple, dict]]):
    """partes: [(nombre, (vértices, normales, triángulos[, uv]), material)]; material = {"color": (r,g,b),
    "rugosidad": 0..1, "metal": 0..1, "textura": bytes PNG/JPG opcional}. Cada parte es un nodo con su malla."""
    binario = bytearray()
    vistas, accesores, mallas, nodos, materiales, imagenes, texturas = [], [], [], [], [], [], []

    def agregar(datos: bytes, objetivo=None) -> int:
        while len(binario) % 4:
            binario.append(0)
        vista = {"buffer": 0, "byteOffset": len(binario), "byteLength": len(datos)}
        if objetivo:
            vista["target"] = objetivo
        binario.extend(datos)
        vistas.append(vista)
        return len(vistas) - 1

    for nombre, geo, mat in partes:
        v, nrm, t = geo[0], geo[1], geo[2]
        uv = geo[3] if len(geo) > 3 else None
        if not len(t):
            continue
        atributos = {}
        vi = agregar(np.ascontiguousarray(v, np.float32).tobytes(), 34962)
        accesores.append({"bufferView": vi, "componentType": 5126, "count": len(v), "type": "VEC3",
                          "min": v.min(axis=0).tolist(), "max": v.max(axis=0).tolist()})
        atributos["POSITION"] = len(accesores) - 1
        ni = agregar(np.ascontiguousarray(nrm, np.float32).tobytes(), 34962)
        accesores.append({"bufferView": ni, "componentType": 5126, "count": len(nrm), "type": "VEC3"})
        atributos["NORMAL"] = len(accesores) - 1
        if uv is not None:
            ui = agregar(np.ascontiguousarray(uv, np.float32).tobytes(), 34962)
            accesores.append({"bufferView": ui, "componentType": 5126, "count": len(uv), "type": "VEC2"})
            atributos["TEXCOORD_0"] = len(accesores) - 1
        ii = agregar(np.ascontiguousarray(t, np.uint32).tobytes(), 34963)
        accesores.append({"bufferView": ii, "componentType": 5125, "count": int(t.size), "type": "SCALAR"})
        material = {"name": nombre, "pbrMetallicRoughness": {
            "baseColorFactor": [*mat.get("color", (1, 1, 1)), 1.0],
            "metallicFactor": mat.get("metal", 0.0), "roughnessFactor": mat.get("rugosidad", 0.7)}}
        if mat.get("textura"):
            imagenes.append({"bufferView": agregar(mat["textura"]), "mimeType": mat.get("tipo", "image/jpeg")})
            texturas.append({"source": len(imagenes) - 1})
            material["pbrMetallicRoughness"]["baseColorTexture"] = {"index": len(texturas) - 1}
        if mat.get("dos_caras"):
            material["doubleSided"] = True
        materiales.append(material)
        mallas.append({"name": nombre, "primitives": [{"attributes": atributos, "indices": len(accesores) - 1,
                                                       "material": len(materiales) - 1}]})
        nodos.append({"name": nombre, "mesh": len(mallas) - 1})
    while len(binario) % 4:
        binario.append(0)
    gltf = {"asset": {"version": "2.0", "generator": "TorrentVision"}, "scene": 0,
            "scenes": [{"nodes": list(range(len(nodos)))}], "nodes": nodos, "meshes": mallas,
            "materials": materiales, "accessors": accesores, "bufferViews": vistas,
            "buffers": [{"byteLength": len(binario)}]}
    if imagenes:
        gltf["images"] = imagenes
        gltf["textures"] = texturas
    texto = json.dumps(gltf, separators=(",", ":")).encode()
    texto += b" " * ((4 - len(texto) % 4) % 4)
    total = 12 + 8 + len(texto) + 8 + len(binario)
    with open(ruta, "wb") as archivo:
        archivo.write(struct.pack("<III", 0x46546C67, 2, total))
        archivo.write(struct.pack("<II", len(texto), 0x4E4F534A) + texto)
        archivo.write(struct.pack("<II", len(binario), 0x004E4942) + bytes(binario))
