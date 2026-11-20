"""La voz del guion: la genera con Google, la pasa a texto para controlarla y deja el momento de cada palabra.

No se llama solo: lo usa armar.py. Lo que gasta cupo es generar_voz (una voz de las del día, compartidas con
otro programa mientras las llaves sean prestadas). Transcribir no gasta voces.

Guarda cada voz en motor/cache/voces/<huella del estilo y el texto>/: si el mismo guion se vuelve a armar (un
reintento, o el mismo video otra vez) no se pide de nuevo.
"""
import base64
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import wave
from pathlib import Path

from comun import API, CACHE, Falla, TopeDelDia, diferencias, es_mejor, escribir_json, leer_json, pedir, registro

# Copiado de otro programa del autor (voz.py: VOZ, MODELO_VOZ, MODELO_TEXTO, MAX_LETRAS_TONO, generar_voz, a_mp3,
# duracion, transcribir; líneas 21-78) el 2026-11-17. Cambios: el estilo es de locutor de noticias para redes en
# castellano neutro (docs/decisiones.md: "Castellano neutro para toda Latinoamérica"), no el narrador del otro programa; los
# errores son Falla con su código en vez de cortar el programa.
VOZ = "Orus"
MODELO_VOZ = "gemini-3.8-flash-tts"
MODELO_TRANSCRIBIR = "gemini-3.5-transcribe"
MAX_LETRAS_TONO = 60         # Google advierte que las notas de tono largas hacen que la voz se corra
ESTILO = "locutor de noticias, castellano neutro, ágil y claro"
ESTILO_SOBRIO = "locutor de noticias, castellano neutro, sobrio y claro"   # política, crímenes y tragedias
VOCES = CACHE / "voces"
CUENTA_DEL_DIA = CACHE / "voces-gastadas.json"

assert len(ESTILO) <= MAX_LETRAS_TONO and len(ESTILO_SOBRIO) <= MAX_LETRAS_TONO


def generar_voz(texto, destino_wav, estilo=ESTILO):
    cuerpo = {"model": MODELO_VOZ,
              "input": [{"type": "user_input", "content": [{"type": "text", "text": texto,
                         "annotations": [{"type": "speech_metadata", "style": estilo}]}]}],
              "response_format": {"type": "audio"},
              "generation_config": {"speech_config": [{"voice": VOZ}]}}
    r = pedir(f"{API}/interactions", cuerpo, intentos=3)

    def buscar(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("data", "audio") and isinstance(v, str) and len(v) > 1000:
                    return v
                x = buscar(v)
                if x:
                    return x
        if isinstance(o, list):
            for v in o:
                x = buscar(v)
                if x:
                    return x

    datos = buscar(r)
    if not datos:
        raise Falla("FALLO_VOZ", "Google no devolvió audio")
    crudo = base64.b64decode(datos)
    if crudo[:4] == b"RIFF":
        Path(destino_wav).write_bytes(crudo)
    else:
        with wave.open(str(destino_wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(crudo)


def a_mp3(origen, destino):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(origen), "-ac", "1", "-ar", "44100",
                    "-b:a", "192k", str(destino)], check=True)


def duracion(archivo):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                 "csv=p=0", str(archivo)], capture_output=True, text=True, check=True).stdout)


def transcribir(mp3):
    cuerpo = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/mp3",
              "data": base64.b64encode(Path(mp3).read_bytes()).decode()}}]}],
              "generationConfig": {"audioTranscriptionConfig": {"wordTimestamp": True}}}
    r = pedir(f"{API}/models/{MODELO_TRANSCRIBIR}:generateContent", cuerpo, intentos=3)
    try:
        return r["candidates"][0]["content"]["parts"][0]["audioTranscription"]
    except (KeyError, IndexError, TypeError):
        raise Falla("FALLO_VOZ", "Google no devolvió la transcripción con tiempos")
# ---- fin de lo copiado de voz.py


def coincide(texto, transcripcion):
    """¿La voz dice el guion? Se ESTIMA con la transcripción, que también se equivoca.
    Cuenta como que NO coincide si falta o sobra alguna palabra (una diferencia de distinto largo) o si el parecido
    baja de 0,9. Una palabra cambiada por otra del mismo largo (un nombre escrito distinto por la transcripción) no
    alcanza para gastar otra voz: casi siempre es la transcripción la que se equivoca, no la voz."""
    difs, parecido, ops = diferencias(texto, transcripcion.get("words", []))
    faltan_o_sobran = any((i2 - i1) != (j2 - j1) for _, i1, i2, j1, j2 in ops)
    return (not faltan_o_sobran and parecido >= 0.9), difs, parecido


def contar_del_dia():
    """Cuántas voces gastó el motor hoy (sólo informativo: el tope de verdad lo pone Google)."""
    try:
        d = leer_json(CUENTA_DEL_DIA)
    except (OSError, ValueError):
        d = {}
    return d.get(datetime.date.today().isoformat(), 0)


def _sumar_del_dia():
    try:
        d = leer_json(CUENTA_DEL_DIA)
    except (OSError, ValueError):
        d = {}
    hoy = datetime.date.today().isoformat()
    d[hoy] = d.get(hoy, 0) + 1
    CUENTA_DEL_DIA.parent.mkdir(parents=True, exist_ok=True)
    escribir_json(CUENTA_DEL_DIA, d)


def voz_para(texto, sensible, destino, al_gastar=lambda: None, max_voces=2):
    """Deja en `destino` voz.mp3 y transcripcion.json del texto. Devuelve un dict con duracion, parecido, diferencias,
    gastadas (voces nuevas pedidas a Google) y de_guardada (True si salió de motor/cache/voces).

    Regla de gasto: un intento; el segundo SÓLO si la transcripción no coincide con el guion (ver coincide). Si el
    segundo tampoco, queda el que más se parece. `al_gastar` se llama apenas Google devuelve cada voz, para que
    armar.py la anote en trabajo.json aunque después algo falle. `max_voces` (o PORTAVOZ_VOCES_MAX) pone un techo."""
    estilo = ESTILO_SOBRIO if sensible else ESTILO
    huella = hashlib.md5(f"{VOZ}\n{estilo}\n{texto}".encode("utf-8")).hexdigest()[:16]
    guardada = VOCES / huella
    guardada.mkdir(parents=True, exist_ok=True)
    destino = Path(destino)
    final, final_tr = guardada / "voz.mp3", guardada / "transcripcion.json"
    techo = int(os.environ.get("PORTAVOZ_VOCES_MAX") or max_voces)
    gastadas = 0

    if final.exists() and final_tr.exists():
        tr = leer_json(final_tr)
        ok, difs, parecido = coincide(texto, tr)
        registro(f"  la voz de este guion ya estaba guardada: no se pide de nuevo (parecido {parecido:.3f})")
        de_guardada = True
    else:
        de_guardada = False
        mejor = None
        for intento in (1, 2):
            mp3 = guardada / f"intento{intento}.mp3"
            if not mp3.exists():
                if gastadas >= techo:
                    break
                registro(f"  pidiendo la voz a Google (intento {intento})")
                wav = guardada / f"intento{intento}.{os.getpid()}.wav"
                try:
                    generar_voz(texto, wav, estilo)
                except TopeDelDia:
                    raise Falla("SIN_VOCES_HOY", "Google dice que se gastaron las voces del día")
                except Falla as e:
                    raise Falla("SIN_CONEXION" if e.codigo == "SIN_CONEXION" else "FALLO_VOZ", e.detalle)
                gastadas += 1
                _sumar_del_dia()
                al_gastar()
                a_mp3(wav, mp3)
                try:
                    os.replace(wav, guardada / f"intento{intento}.wav")   # se sobrescribe la próxima vez; no se borra
                except OSError:
                    pass
            else:
                registro(f"  el intento {intento} ya estaba grabado: sólo se controla")
            guardado_tr = guardada / f"transcripcion{intento}.json"
            if guardado_tr.exists():
                tr = leer_json(guardado_tr)
            else:
                try:
                    tr = transcribir(mp3)
                except TopeDelDia:
                    raise Falla("FALLO_VOZ", "Google no transcribió la voz (tope del día)")
                except Falla as e:
                    raise Falla("SIN_CONEXION" if e.codigo == "SIN_CONEXION" else "FALLO_VOZ", e.detalle)
                escribir_json(guardado_tr, tr)
            ok, difs, parecido = coincide(texto, tr)
            registro(f"  parecido con el guion: {parecido:.3f}, diferencias: {len(difs)}")
            if mejor is None or es_mejor(parecido, difs, mejor[3], mejor[1]):
                mejor = (mp3, difs, tr, parecido)
            if ok:
                break
        if mejor is None:
            raise Falla("FALLO_VOZ", "no se pudo grabar la voz")
        mp3, difs, tr, parecido = mejor
        shutil.copyfile(mp3, final)
        escribir_json(final_tr, tr)

    destino.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(final, destino / "voz.mp3")
    escribir_json(destino / "transcripcion.json", tr)
    return {"duracion": duracion(destino / "voz.mp3"), "parecido": round(parecido, 3), "diferencias": difs,
            "gastadas": gastadas, "de_guardada": de_guardada, "estilo": estilo}


def guardar_control(destino, info):
    (Path(destino) / "control-voz.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
