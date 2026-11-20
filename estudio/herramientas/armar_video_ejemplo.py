"""Arma el video de EJEMPLO de un trabajo del Estudio: el guion como subtítulo sobre un fondo de prueba en movimiento.

Uso:  python armar_video_ejemplo.py <carpeta del trabajo> --palabras-por-segundo=2.5 [--rapida]

Lee <carpeta>/trabajo.json y deja ahí:
  - video.mp4: 1080x1920 a 30 cuadros (con --rapida, 540x960 a 10), con una pista de audio muda, preparado para que
    el celular lo empiece a mostrar antes de terminar de bajarlo;
  - portada.jpg: un cuadro del segundo 1, a 540x960;
  - subtitulos.ass: los subtítulos que se imprimieron (sirve para revisar qué estilo salió);
  - armado.json: el registro del armado (segundos, palabras, estilo, fondo y, en letras_reemplazadas, las letras del
    guion o del pie que la letra de la marca no tiene y libass dibujó con otra).
Video y portada se escriben con un nombre temporal y se renombran al final: si existen, están completos (y el
registro ya está escrito).
Si algo falla, sale con un código distinto de 0 y deja un texto corto del error en armado-error.txt.

Las palabras se reparten a la velocidad que le pasa el Estudio (--palabras-por-segundo, que sale de
PALABRAS_POR_SEGUNDO en lib/contrato.js: acá no hay copia que se pueda quedar vieja) y el video dura eso más medio
segundo. Los emojis no se dibujan ni cuentan como palabra. Los temas delicados salen con el estilo sobrio. Las
palabras que ve la gente (el cartel y el pie) salen de datos/ejemplos/textos.json, campo "video".

El color: libass pinta con la receta de color de los videos comunes, y los navegadores leen un video alto (como el de
1080x1920) con la de alta definición. Por eso, después de imprimir los subtítulos, el video se pasa a la de alta
definición y queda marcado así: el celeste del resaltado se ve igual en el navegador y en el celular.

Los fondos son tres, de 60 segundos, en tonos petróleo y celeste, y se hacen UNA sola vez en
datos/fondos-de-ejemplo/ (si falta alguno, se rehace solo). Un candado evita que dos armados hagan el mismo a la vez:
vale mientras el programa que lo tomó siga vivo y por CANDADO_VENCE segundos como mucho (hacer un fondo tarda unos
22 s). Si ese programa se murió (lo cortó el Estudio, se apagó la PC), el que llega no espera: lo pisa y lo hace. Un
corte a la mitad deja un fondo-*.parcial.mp4 que no se borra (no molesta: se pisa con el nombre del próximo).
Por cada video sólo se imprimen los subtítulos encima, con la compresión más rápida (medido en esta PC: es lo que
hace que un video de un minuto salga en segundos y no en minutos).
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import medir  # noqa: E402
import subtitulos as S  # noqa: E402

ESTUDIO = AQUI.parent
FONDOS = ESTUDIO / "datos" / "fondos-de-ejemplo"
TEXTOS = ESTUDIO / "datos" / "ejemplos" / "textos.json"

COLA = 0.5                   # medio segundo más al final, para que la última palabra no se corte en seco
DURACION_FONDO = 60
CANDADO_VENCE = 120          # segundos: un candado más viejo que esto es de un armado que se murió
ESPERA_CANDADO = 150         # segundos que se espera a que otro armado termine el mismo fondo (el Estudio corta a 480)
# libass pinta con la receta de los videos comunes (bt601) y el navegador lee este video con la de alta definición
# (bt709): se pasa de una a la otra sin tocar los colores (fast=1) y el archivo queda marcado con la nueva.
A_ALTA_DEFINICION = "colorspace=all=bt709:iall=bt601-6-525:fast=1"
MARCAS_ALTA_DEFINICION = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
# La portada es un JPEG, que todos leen con la receta común y en rango completo: se le escribe así.
PORTADA_ESCALA = "scale=540:960:in_color_matrix=bt709:in_range=tv:out_color_matrix=bt601:out_range=full"
USO = "Uso: python armar_video_ejemplo.py <carpeta del trabajo> --palabras-por-segundo=2.5 [--rapida]"

# Tres fondos en movimiento con los colores de la marca (estudio/app/globals.css): petróleo #0d181c, #153a3b,
# #263e50 y #0a2530; celeste #5cc4d6 y #7dd3df. Las coordenadas son para 1080x1920; en rápido se achican.
FONDOS_DEF = [
    ("petroleo", "linear", (0, 0, 1080, 1920), ("0d181c", "153a3b", "263e50", "5cc4d6")),
    ("celeste", "radial", (540, 700, 1080, 1920), ("5cc4d6", "263e50", "153a3b", "0d181c")),
    ("mezcla", "circular", (300, 500, 900, 1600), ("0a2530", "153a3b", "7dd3df", "263e50")),
]


class Falla(Exception):
    """Un error con un texto corto, el que queda en armado-error.txt."""


def ffmpeg(args, cwd=None):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise Falla(f"FFmpeg falló: {r.stderr.strip()[-300:]}")


# ------------------------------------------------------------------------------------------- Fondos

def medidas(rapida):
    return (540, 960, 10) if rapida else (1080, 1920, 30)


def leer_candado(ruta):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def pid_vivo(pid):
    """True si ese programa sigue andando. En Windows se pregunta sin tocarlo (os.kill ahí lo terminaría)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if not 0 < pid <= 0xFFFFFFFF:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        h = k.OpenProcess(0x1000, False, pid)   # 0x1000: sólo preguntar cómo está
        if not h:
            return ctypes.get_last_error() == 5   # acceso negado: existe, pero es de otro usuario
        try:
            codigo = wintypes.DWORD()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(codigo))) and codigo.value == 259   # 259: sigue andando
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def candado_vivo(info):
    """Lo tiene alguien de verdad: no está libre, no se venció y el programa que lo tomó sigue vivo."""
    try:
        edad = time.time() - float(info.get("hora", 0))
    except (TypeError, ValueError, AttributeError):
        return False
    return bool(info) and not info.get("libre") and edad < CANDADO_VENCE and pid_vivo(info.get("pid"))


def tomar_candado(ruta):
    """True si lo tomó. Un candado libre o vencido se pisa (nunca se borra nada)."""
    yo = json.dumps({"pid": os.getpid(), "hora": time.time()})
    try:
        fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(yo)
        return True
    except FileExistsError:
        if candado_vivo(leer_candado(ruta)):
            return False
        ruta.write_text(yo, encoding="utf-8")
        return True


def soltar_candado(ruta):
    ruta.write_text(json.dumps({"libre": True, "hora": time.time()}), encoding="utf-8")


def hacer_fondo(nombre, tipo, puntos, colores, rapida):
    ancho, alto, cuadros = medidas(rapida)
    # El degradé se calcula a un cuarto del tamaño y se agranda: es liso, así que no se nota, y tarda mucho menos
    # (medido en esta PC: el circular a tamaño completo llevaba más de 4 minutos).
    chico_a, chico_h = ancho // 4, alto // 4
    escala = chico_a / 1080
    x0, y0, x1, y1 = (round(p * escala) for p in puntos)
    c = ":".join(f"c{i}=0x{col}" for i, col in enumerate(colores))
    fuente = (f"gradients=s={chico_a}x{chico_h}:r={cuadros}:d={DURACION_FONDO}:nb_colors={len(colores)}:speed=0.01:"
              f"type={tipo}:x0={x0}:y0={y0}:x1={x1}:y1={y1}:{c}")
    final = FONDOS / f"fondo-{nombre}{'-rapida' if rapida else ''}.mp4"
    parcial = final.with_name(f"{final.stem}.{os.getpid()}.parcial.mp4")
    ffmpeg(["-f", "lavfi", "-i", fuente, "-vf", f"scale={ancho}:{alto}:flags=bicubic", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-g", str(cuadros * 2), "-movflags", "+faststart",
            str(parcial)])
    os.replace(parcial, final)


def fondo(indice, rapida):
    """La ruta del fondo; si falta, lo hace (una sola vez, con candado)."""
    nombre, tipo, puntos, colores = FONDOS_DEF[indice]
    final = FONDOS / f"fondo-{nombre}{'-rapida' if rapida else ''}.mp4"
    candado = final.with_suffix(".lock")
    FONDOS.mkdir(parents=True, exist_ok=True)
    limite = time.time() + ESPERA_CANDADO
    while not (final.exists() and final.stat().st_size > 0):
        if tomar_candado(candado):
            try:
                if not (final.exists() and final.stat().st_size > 0):
                    hacer_fondo(nombre, tipo, puntos, colores, rapida)
            finally:
                soltar_candado(candado)
        elif time.time() > limite:
            raise Falla("Otro armado se quedó trabado haciendo el fondo de prueba.")
        else:
            time.sleep(0.5)
    return final


# ------------------------------------------------------------------------------------------- Video

def textos_video():
    try:
        return json.loads(TEXTOS.read_text(encoding="utf-8"))["video"]
    except (OSError, ValueError, KeyError) as e:
        raise Falla(f"No se pudieron leer los textos del video: {e}")


def tiempos_de(cuantas, por_segundo):
    """Cada palabra dura lo mismo: 1 / por_segundo segundos. La última se queda en pantalla hasta el final."""
    paso = 1 / por_segundo
    total = cuantas * paso + COLA
    tiempos = [(i * paso, (i + 1) * paso) for i in range(cuantas)]
    tiempos[-1] = (tiempos[-1][0], total)
    return tiempos, total


def armar(carpeta, rapida, por_segundo):
    try:
        trabajo = json.loads((carpeta / "trabajo.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Falla(f"No se pudo leer el trabajo: {e}")
    nota = trabajo.get("nota") or {}
    palabras = S.limpiar((trabajo.get("guion") or {}).get("texto", "")).split()
    if not palabras:
        raise Falla("El guion está vacío.")
    for archivo in S.ARCHIVOS_LETRAS:
        if not (medir.LETRAS / archivo).exists():
            raise Falla(f"Falta la letra {archivo} en marca/letras.")

    tiempos, total = tiempos_de(len(palabras), por_segundo)
    variante = "Sobria" if nota.get("sensible") else "Principal"
    vt = textos_video()
    renglones = ([vt["fuente"].replace("{medio}", nota["medio"])] if nota.get("medio") else []) + [vt["ilustrativas"]]
    # El cartel va arriba, dentro de la zona que no tapan los botones de las apps (y 260 en adelante).
    cartel = (f"Style: Cartel,{S.PIE['letra']},40,{S.ass(S.PAPEL)},{S.ass(S.PAPEL)},{S.ass(S.TINTA)},{S.ass(S.TINTA)},"
              f"0,0,0,0,100,100,2,0,3,12,0,8,140,140,300,1")
    eventos = (S.dialogos(palabras, tiempos, variante)
               + [S.pie(renglones, total), f"Dialogue: 2,{S.t(0)},{S.t(total)},Cartel,,0,0,0,,{S.limpiar(vt['cartel'])}"])
    (carpeta / "subtitulos.ass").write_text(S.cabecera([cartel]) + "\n".join(eventos) + "\n", encoding="utf-8")
    # Las letras que la letra de la marca no tiene: no se cambian, pero quedan anotadas en el registro.
    dichas = " ".join(p.upper() for p in palabras) if variante == "Principal" else " ".join(palabras)
    archivo_guion = (S.PRINCIPAL if variante == "Principal" else S.SOBRIA)["archivo"]
    abajo = " ".join([*renglones, S.limpiar(vt["cartel"])])
    reemplazadas = sorted(set(S.letras_que_faltan(dichas, archivo_guion)) | set(S.letras_que_faltan(abajo, S.PIE["archivo"])))

    _, _, cuadros = medidas(rapida)
    id_ = str(trabajo.get("id", carpeta.name))
    elegido = fondo(int(hashlib.md5(id_.encode("utf-8")).hexdigest(), 16) % len(FONDOS_DEF), rapida)
    pid = os.getpid()
    video_parcial = f"video.{pid}.parcial.mp4"
    portada_parcial = f"portada.{pid}.parcial.jpg"
    # El .ass va con su nombre corto porque FFmpeg corre adentro de la carpeta del trabajo (la ruta tiene espacios).
    # Filtro "ass" y no "subtitles": "subtitles" pierde el primer renglón si alguna palabra dura cero (2026-11-20).
    ffmpeg(["-stream_loop", "-1", "-i", str(elegido), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-t", f"{total:.2f}", "-vf", f"ass=subtitulos.ass:fontsdir='{S.FONTSDIR}',{A_ALTA_DEFINICION}",
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", *MARCAS_ALTA_DEFINICION, "-r", str(cuadros), "-c:a", "aac", "-b:a", "64k",
            "-movflags", "+faststart", video_parcial], cwd=carpeta)
    ffmpeg(["-ss", f"{min(1.0, total / 2):.2f}", "-i", video_parcial, "-frames:v", "1", "-vf", PORTADA_ESCALA,
            "-q:v", "3", portada_parcial], cwd=carpeta)
    # Primero la portada y después el video: si el video está, la portada también.
    registro = {"segundos": round(total, 2), "palabras": len(palabras), "estilo": variante, "fondo": elegido.name,
                "letras_reemplazadas": reemplazadas}
    (carpeta / "armado.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(carpeta / portada_parcial, carpeta / "portada.jpg")
    os.replace(carpeta / video_parcial, carpeta / "video.mp4")
    return registro


def velocidad(argv):
    """El número de --palabras-por-segundo=X, o None si falta o no sirve."""
    for a in argv:
        if a.startswith("--palabras-por-segundo="):
            try:
                v = float(a.split("=", 1)[1])
            except ValueError:
                return None
            return v if 0 < v < 100 else None
    return None


def main(argv):
    # En Windows la salida no es UTF-8: una letra de otro alfabeto en el registro o en un error (日, Ж) rompía el
    # armado con el video ya hecho. Se escribe siempre en UTF-8, que es como lo lee el Estudio.
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = [a for a in argv if not a.startswith("--")]
    rapida = "--rapida" in argv
    por_segundo = velocidad(argv)
    if len(args) != 1 or por_segundo is None:
        print(USO, file=sys.stderr)
        return 2
    carpeta = Path(args[0]).resolve()
    if not carpeta.is_dir():
        print(f"No existe la carpeta {carpeta}", file=sys.stderr)
        return 2
    try:
        print(json.dumps(armar(carpeta, rapida, por_segundo), ensure_ascii=False))
        return 0
    except Exception as e:  # cualquier falla deja su texto corto, para que el Estudio sepa qué pasó
        texto = str(e) if isinstance(e, Falla) else f"{type(e).__name__}: {e}"
        try:
            (carpeta / "armado-error.txt").write_text(texto[:500] + "\n", encoding="utf-8")
        except OSError:
            pass
        print(texto, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
