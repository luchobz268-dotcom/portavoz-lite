"""La vuelta del sonido (Fase 5, plan del 2026-11-20): en redes el video se repite solo, y al volver a empezar la última
palabra tiene que pegar con la primera, sin un hueco mudo ni un salto de volumen.

Medido el 2026-11-20 en los videos de Tesla y de Tenaris: entre la última palabra y la primera había medio segundo
mudo (la voz de Google trae unos 0,26 s mudos al principio y 0,15 a 0,3 al final), y el final sonaba 13 a 15 dB más
bajo que el arranque.

Qué hace, sin tocar voz.mp3 (sirve para rearmar sin gastar otra voz):
  1. preparar: mide dónde empieza y dónde termina la voz y recorta lo mudo de los bordes. Quedan ANTES segundos antes
     de la primera palabra y DESPUES después de la última. Nunca corta voz: si un borde mudo ya es más corto, queda
     como está. También calcula cuánto sube (o baja) la última frase para acercarse a la primera.
  2. filtro: el pedazo de FFmpeg que hace el recorte y el volumen adentro del armado (armar.py).
  3. correr: corre los tiempos de cada palabra lo mismo que el recorte, así subtítulos y cortes caen en su palabra.
  4. medir_vuelta: en el video terminado, el silencio y el salto de volumen de la vuelta. Avisa, no frena.
Los números (ANTES, DESPUES, los avisos) los puso el asistente el 2026-11-20; Lucio los confirma de oído.
"""
import math
import re
import subprocess

import numpy as np

import contrato
from hablado import oraciones

ANTES = 0.05          # segundos mudos que quedan antes de la primera palabra
DESPUES = 0.12        # y después de la última: la vuelta queda en unos 0,17 s
UMBRAL = -45.0        # dB por debajo de la ventana más fuerte: de ahí para abajo cuenta como mudo
VENTANA = 0.01        # segundos de cada ventana al medir
TOPE_SUBIDA = 7.0     # lo más que se mueve la última frase (otro programa del autor, decidido allá el 2026-11-01)
PICO_MAXIMO = -1.0    # dB: la subida nunca lleva un pico de la última frase más arriba que esto
AVISO_SILENCIO = 0.4  # segundos: más que esto en la vuelta, se avisa
AVISO_SALTO = 3.0     # dB: un salto de volumen mayor en la vuelta, se avisa
FUNDIDO = 0.02        # segundos de fundido en cada punta del sonido (sólo evita un chasquido; cae en lo mudo)


# ----------------------------------------------------------------------------- Copiado de otro programa
# Del armado de cortos de otro programa del autor (leído el 2026-11-20, sin tocarlo), igual que la voz y los subtítulos.
# Sus pruebas: las mismas cuentas que allá, en probar_sin_gastar.py.

def ganancia_de_la_vuelta(arranque, cierre, margen=1.5, tope=4.0, frases=None):
    """Cuántos dB sube (o baja) la última frase para que la vuelta del bucle no salte: si el primer medio segundo de la
    voz y el último se separan más que el margen, se acerca el final hasta el margen, nunca más de tope.
    frases = (nivel de la primera frase entera, nivel de la última entera): si se dan, la subida nunca deja la última
    frase más fuerte que la primera."""
    diferencia = arranque - cierre
    if abs(diferencia) <= margen:
        return 0.0
    ajuste = max(-tope, min(tope, diferencia - math.copysign(margen, diferencia)))
    if frases and ajuste > 0:
        ajuste = min(ajuste, max(frases[0] - frases[1], 0.0))
    return round(ajuste, 2) + 0.0


def nivel_medio(ruta, desde=0.0, largo=0.0):
    """Volumen promedio (dB) de un pedazo de audio. (Allá guarda lo medido por ruta; acá no, porque un rearmado puede
    medir otra voz con el mismo nombre en el mismo programa.)"""
    return _volumen(ruta, desde, largo)[0]


# ------------------------------------------------------------------------------- Lo propio

def _volumen(ruta, desde, largo):
    """(promedio, pico) en dB de un pedazo de audio, con volumedetect de FFmpeg."""
    args = ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{max(desde, 0.0):.3f}"] + (
        ["-t", f"{largo:.3f}"] if largo else [])
    r = subprocess.run(args + ["-i", str(ruta), "-af", "volumedetect", "-f", "null", "-"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    medio = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    pico = re.search(r"max_volume:\s*(-?[\d.]+) dB", r.stderr)
    if not (medio and pico):
        raise RuntimeError("FFmpeg no pudo medir el volumen")
    return float(medio.group(1)), float(pico.group(1))


def bordes_de_voz(ruta):
    """(desde, hasta, largo) en segundos: dónde empieza y dónde termina lo que suena, y lo que dura el archivo.
    Se decodifica con el mismo FFmpeg que arma el video, así los segundos son los mismos."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ruta), "-vn", "-ac", "1", "-ar", "16000",
                        "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.float32)
    if r.returncode != 0 or not len(x):
        raise RuntimeError("FFmpeg no pudo leer el sonido")
    largo = len(x) / 16000
    paso = int(16000 * VENTANA)
    n = len(x) // paso
    if not n:
        return 0.0, largo, largo
    db = 20 * np.log10(np.sqrt((x[:n * paso].reshape(n, paso).astype(np.float64) ** 2).mean(axis=1)) + 1e-9)
    suena = np.where(db > db.max() + UMBRAL)[0]
    if not len(suena):
        return 0.0, largo, largo
    return (round(float(suena[0]) * VENTANA, 3), round(min(largo, (float(suena[-1]) + 1) * VENTANA), 3),
            round(largo, 3))


def _frases(texto, palabras_tiempos):
    """(inicio y fin de la primera oración, inicio de la última, dónde se enciende el volumen de la última) según los
    tiempos de cada palabra, o None si el guion tiene una sola oración o los tiempos no coinciden con el texto."""
    partes = oraciones(texto)
    cuentas = [contrato.contar_palabras(p) for p in partes]
    if len(partes) < 2 or sum(cuentas) != len(palabras_tiempos) or not cuentas[0] or not cuentas[-1]:
        return None
    primera = (palabras_tiempos[0][1], palabras_tiempos[cuentas[0] - 1][2])
    k = len(palabras_tiempos) - cuentas[-1]
    ultima = palabras_tiempos[k][1]
    # el volumen cambia en el medio de la pausa de antes, no justo en la palabra: la marca de tiempo de la
    # transcripción puede llegar unas centésimas tarde, y el arranque de la frase quedaría sin subir
    enciende = (palabras_tiempos[k - 1][2] + ultima) / 2
    return primera, ultima, enciende


def preparar(ruta_voz, texto, palabras_tiempos):
    """El recorte y el volumen de la vuelta, para filtro() y correr(). Devuelve
    {"desde", "hasta", "duracion", "ganancia", "enciende", "medido": {...}}, en segundos del archivo de la voz salvo
    "enciende" (segundos del video, ya recortado). Si algo no se puede medir, la voz queda como está (sin recorte ni
    volumen) y "fallo" dice por qué: la vuelta nunca frena el video."""
    try:
        voz_desde, voz_hasta, largo = bordes_de_voz(ruta_voz)
    except (RuntimeError, OSError) as e:
        return {"desde": 0.0, "hasta": None, "duracion": None, "ganancia": 0.0, "enciende": 0.0, "medido": {},
                "fallo": str(e)}
    desde = round(max(0.0, voz_desde - ANTES), 3)
    hasta = round(min(largo, voz_hasta + DESPUES), 3)
    salida = {"desde": desde, "hasta": hasta, "duracion": round(hasta - desde, 3), "ganancia": 0.0, "enciende": 0.0,
              "medido": {"voz_desde": voz_desde, "voz_hasta": voz_hasta, "largo_voz": largo}}
    frases = _frases(texto, palabras_tiempos)
    if not frases or voz_hasta - voz_desde < 1.0:
        return salida
    (p_ini, p_fin), u_ini, enciende = frases
    try:
        ruta = str(ruta_voz)
        arranque = nivel_medio(ruta, voz_desde, 0.5)
        cierre = nivel_medio(ruta, max(voz_hasta - 0.5, voz_desde), 0.5)
        nivel_primera = nivel_medio(ruta, p_ini, max(p_fin - p_ini, 0.5))
        nivel_ultima, pico_ultima = _volumen(ruta, u_ini, max(voz_hasta - u_ini, 0.5))
    except (RuntimeError, OSError) as e:
        salida["fallo"] = str(e)
        return salida
    ganancia = ganancia_de_la_vuelta(arranque, cierre, tope=TOPE_SUBIDA, frases=(nivel_primera, nivel_ultima))
    if ganancia > 0:
        # que la subida no lleve ningún pico al tope (se oiría roto)
        ganancia = round(max(0.0, min(ganancia, PICO_MAXIMO - pico_ultima)), 2) + 0.0
    salida.update({"ganancia": ganancia, "enciende": round(max(0.0, enciende - desde), 3)})
    salida["medido"].update({"arranque": arranque, "cierre": cierre, "primera_frase": nivel_primera,
                             "ultima_frase": nivel_ultima, "pico_ultima": pico_ultima})
    return salida


def filtro(vuelta, entrada, salida="a"):
    """El pedazo de FFmpeg (filter_complex) que toma el sonido de la entrada número `entrada`, lo recorta, sube la
    última frase y deja la etiqueta [salida]."""
    partes = [f"[{entrada}:a]"]
    cadena = []
    if vuelta.get("hasta") is not None:
        cadena.append(f"atrim=start={vuelta['desde']:.3f}:end={vuelta['hasta']:.3f}")
        cadena.append("asetpts=PTS-STARTPTS")
    if vuelta.get("ganancia"):
        cadena.append(f"volume={vuelta['ganancia']:.2f}dB:enable='gte(t,{vuelta['enciende']:.3f})'")
    if vuelta.get("duracion"):
        cadena.append(f"afade=t=in:d={FUNDIDO}")
        cadena.append(f"afade=t=out:st={max(vuelta['duracion'] - FUNDIDO, 0):.3f}:d={FUNDIDO}")
    return partes[0] + (",".join(cadena) or "anull") + f"[{salida}]"


def correr(palabras_tiempos, vuelta):
    """Los tiempos de cada palabra [(palabra, inicio, fin)] en segundos del video ya recortado."""
    d, total = vuelta.get("desde") or 0.0, vuelta.get("duracion")

    def ajustar(t):
        t = max(0.0, t - d)
        return round(min(t, total), 3) if total else round(t, 3)
    return [(w, ajustar(i), ajustar(f)) for w, i, f in palabras_tiempos]


def medir_vuelta(video):
    """Cómo queda la vuelta en el video terminado: {"silencio": s, "salto": dB, "avisos": [...]}.
    silencio: lo mudo del final más lo mudo del principio (lo que se oye entre la última palabra y la primera).
    salto: la diferencia de volumen entre el último medio segundo con voz y el primero (como mide el otro programa, pero sin
    contar lo mudo de las puntas, que bajaría el promedio sin que se oiga)."""
    voz_desde, voz_hasta, largo = bordes_de_voz(video)
    silencio = round(float(voz_desde + (largo - voz_hasta)), 3)
    ruta = str(video)
    salto = round(abs(_volumen(ruta, max(voz_hasta - 0.5, voz_desde), 0.5)[0] - _volumen(ruta, voz_desde, 0.5)[0]), 1)
    avisos = []
    if silencio > AVISO_SILENCIO:
        avisos.append(f"la vuelta tiene {silencio:.2f} s mudos (tope {AVISO_SILENCIO})")
    if salto > AVISO_SALTO:
        avisos.append(f"el volumen salta {salto:.1f} dB en la vuelta (tope {AVISO_SALTO:.0f})")
    return {"silencio": silencio, "salto": salto, "avisos": avisos}
