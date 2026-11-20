"""Mide cada clip en la PC, sin gastar nada, para cortar lo que no va (pedido de Lucio del 2026-11-18, mirando los
videos de Tesla: "no incluyas videos con celular y pantalla blanca o verde. Tampoco videos en blanco y negro, además
si hay partes blancas o que no se muestra nada, cortalas").

FFmpeg decodifica el clip a CUADROS_POR_SEGUNDO cuadros por segundo en tamaño chico (90 x 160) y de cada cuadro se
mide:
  - color: qué parte del cuadro tiene color de verdad. Casi nada = blanco y negro. (No el promedio: una ruta gris o una
    pared blanca filmadas en color tienen el promedio bajo, pero algún punto con color siempre aparece.)
  - bordes: cuánto cambia la luz de un punto al de al lado. Casi nada = pared o pantalla lisa, un cuadro donde no se ve
    nada. (No la variación total de la luz: una pared lisa con una sombra suave la tiene alta y está igual de vacía.)
  - verde: qué parte del cuadro es el verde chillón y liso de los fondos para recortar (pantalla verde). Un pasto
    o un árbol no cuentan: tienen textura.
Con eso salen los PEDAZOS QUE SIRVEN del clip: los tramos sin cuadros malos, con un margen a cada lado del cuadro malo
y de al menos LARGO_MINIMO segundos. Qué se mide y qué no: el blanco y negro, lo liso y el verde se MIDEN; un celular
con la pantalla blanca chiquito en un rincón no cambia estas medidas: ese lo mira Claude (motivo "pantalla" en
mirar_clips.py), y eso se ESTIMA.

Dónde está el límite entre "liso" y "pared con poca textura" es gusto de Lucio: los números de abajo los eligió el
asistente el 2026-11-18 midiendo los clips bajados y los dos casos de Tesla (ver docs/decisiones.md), y se cambian acá.

La medida se guarda al lado del clip (mismo nombre, .medida.json) para no medirlo dos veces.
"""
import json
import subprocess
from pathlib import Path

import numpy as np

VERSION = 1                 # si cambian los límites, sube y las medidas guardadas se rehacen
CUADROS_POR_SEGUNDO = 4
ANCHO, ALTO = 90, 160
COLOR_MINIMO = 0.004        # parte del cuadro con color de verdad por debajo de esto: blanco y negro
BORDES_MINIMOS = 1.0        # cuánto cambia la luz de un punto al de al lado, en promedio: menos es liso, sin nada
VERDE_MAXIMO = 0.15         # parte del cuadro con verde de pantalla para recortar
MARGEN = 0.25               # segundos que se sacan a cada lado de un cuadro malo
LARGO_MINIMO = 1.0          # un pedazo bueno más corto que esto no se usa

MOTIVOS = {"blanco_y_negro": "blanco y negro", "liso": "liso, sin nada", "verde": "pantalla verde"}


def medidas_de_cuadros(cuadros):
    """cuadros: arreglo (n, alto, ancho, 3) de 0 a 255. Devuelve (color, bordes, verde), uno por cuadro."""
    c = cuadros.astype(np.float32)
    maximo, minimo = c.max(axis=3), c.min(axis=3)
    sat = np.where(maximo > 40, (maximo - minimo) / np.maximum(maximo, 1), 0)
    color = (sat > 0.2).mean(axis=(1, 2))
    luz = c @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    bordes = (np.abs(np.diff(luz, axis=1)).mean(axis=(1, 2)) + np.abs(np.diff(luz, axis=2)).mean(axis=(1, 2))) / 2
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    # el verde chillón y liso de los fondos para recortar: casi sin rojo, y sin textura (un pasto tiene textura)
    cambio = np.zeros_like(luz)
    cambio[:, :, 1:] += np.abs(np.diff(luz, axis=2))
    cambio[:, 1:, :] += np.abs(np.diff(luz, axis=1))
    verde = ((g > 100) & (g > r * 2.2) & (g > b * 1.5) & (cambio < 6)).mean(axis=(1, 2))
    return color, bordes, verde


def motivo_de(color, bordes, verde):
    """Por qué un cuadro no va, o None si va."""
    if bordes < BORDES_MINIMOS:
        return "liso"
    if verde > VERDE_MAXIMO:
        return "verde"
    if color < COLOR_MINIMO:
        return "blanco_y_negro"
    return None


def decodificar(ruta):
    """Los cuadros chicos del clip, como arreglo (n, ALTO, ANCHO, 3). Recorta al centro como el armado (vertical)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(ruta), "-vf",
                        f"fps={CUADROS_POR_SEGUNDO},scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,"
                        f"crop={ANCHO}:{ALTO}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=180)
    if r.returncode != 0 or not r.stdout:
        return None
    return np.frombuffer(r.stdout, dtype=np.uint8).reshape(-1, ALTO, ANCHO, 3)


def pedazos(motivos, duracion):
    """motivos: el motivo de cada cuadro (None = va), a CUADROS_POR_SEGUNDO. Devuelve [[desde, hasta]] en segundos."""
    paso = 1 / CUADROS_POR_SEGUNDO
    malos = [k * paso for k, m in enumerate(motivos) if m]
    buenos, desde = [], 0.0
    for t in malos:
        hasta = t - MARGEN
        if hasta - desde >= LARGO_MINIMO:
            buenos.append([round(desde, 2), round(hasta, 2)])
        desde = max(desde, t + paso + MARGEN)   # el cuadro malo cubre de t a t + paso
    if duracion - desde >= LARGO_MINIMO:
        buenos.append([round(desde, 2), round(duracion, 2)])
    return buenos


def medir(ruta, duracion=None):
    """{"version", "duracion", "pedazos": [[desde, hasta]], "cortado": [{"desde", "hasta", "motivo"}]}, o None si FFmpeg
    no pudo abrir el clip (quien llama lo usa entero, como antes). Guarda la medida al lado del clip."""
    ruta = Path(ruta)
    if not ruta.is_file():
        return None
    guardada = ruta.with_suffix(".medida.json")
    if guardada.exists():
        try:
            m = json.loads(guardada.read_text(encoding="utf-8"))
            if m.get("version") == VERSION:
                return m
        except (OSError, ValueError):
            pass
    cuadros = decodificar(ruta)
    if cuadros is None or not len(cuadros):
        return None
    total = duracion or len(cuadros) / CUADROS_POR_SEGUNDO
    motivos = [motivo_de(*x) for x in zip(*medidas_de_cuadros(cuadros))]
    cortado, paso = [], 1 / CUADROS_POR_SEGUNDO
    for k, m in enumerate(motivos):   # los tramos malos seguidos, juntos, para el registro
        if not m:
            continue
        if cortado and cortado[-1]["motivo"] == MOTIVOS[m] and abs(cortado[-1]["hasta"] - k * paso) < paso / 2:
            cortado[-1]["hasta"] = round((k + 1) * paso, 2)
        else:
            cortado.append({"desde": round(k * paso, 2), "hasta": round((k + 1) * paso, 2), "motivo": MOTIVOS[m]})
    m = {"version": VERSION, "duracion": round(total, 2), "pedazos": pedazos(motivos, total), "cortado": cortado}
    try:
        guardada.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return m


def util(medida):
    """Los segundos que sirven del clip según su medida."""
    return round(sum(h - d for d, h in medida["pedazos"]), 2)
