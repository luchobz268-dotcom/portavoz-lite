"""Arma el video de un trabajo: clips, voz, tiempos de cada palabra, armado con FFmpeg y textos para publicar.

Uso:  python motor/armar.py <carpeta del trabajo> [--rapida]

Lee <carpeta>/trabajo.json (la forma de revisarTrabajo). Orden: primero los CLIPS (si no hay, SIN_CLIPS antes de gastar
la voz), después la VOZ, los TIEMPOS, el ARMADO y los TEXTOS. En cada cambio de etapa escribe avance.json (la forma de
revisarAvance, con nombre temporal y renombre). Deja en la carpeta: avance.json, voz.mp3, transcripcion.json,
control-voz.json, subtitulos.ass, video.mp4, portada.jpg, textos-variantes.json, resultado.json y armado.json (qué
clips se usaron y cuánto tardó cada etapa). En trabajo.json sólo anota vocesGastadas (no toca el estado: eso lo hace
el Estudio).
Antes de usar los clips, Claude los mira (mirar_clips.py); qué sacó y por qué queda en armado.json, en "mirada".
El sonido pasa por vuelta.py: se recortan los bordes mudos de la voz y la última frase se empareja con la primera, para
que el video se repita en redes sin que se note el corte (voz.mp3 no se toca). Cómo quedó, en armado.json, en "vuelta".
Imprime {"resultado": {...}, "segundos": {etapa: s}, "vocesGastadas": n} y sale con 0. Si falla: {"error": {...}},
armado-error.txt con una línea corta, avance.json con la etapa en "fallo", y sale con 1. Códigos: GUION_A_CORREGIR,
SIN_CLIPS, SIN_VOCES_HOY, FALLO_VOZ, FALLO_ARMADO, SIN_CONEXION, DESCONOCIDO.

--rapida: 540x960, 15 cuadros por segundo y el preset más rápido (para probar). Sin --rapida: 1080x1920 y 30.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contrato  # noqa: E402
from comun import (HERRAMIENTAS, MOTOR, Falla, TopeDelDia, correr, escribir_json, leer_json, normalizar,  # noqa: E402
                   pedir_json, registro, sin_emojis, sin_links, sin_rutas)
import clips as C  # noqa: E402
from cifras import juntar_cifras  # noqa: E402
import mirar_clips as MC  # noqa: E402
import textos as TX  # noqa: E402
from hablado import tramos_de  # noqa: E402
from tiempos import tiempos_del_guion  # noqa: E402
from voz import guardar_control, voz_para  # noqa: E402
import vuelta as VU  # noqa: E402

sys.path.insert(0, str(HERRAMIENTAS))
import medir  # noqa: E402  (estudio/herramientas/medir.py: se importa, no se copia)
import subtitulos as S  # noqa: E402  (estudio/herramientas/subtitulos.py: se importa, no se copia)

ORDEN = ["clips", "voz", "tiempos", "armado", "textos"]   # el orden en que se hacen
MEDIDAS = MOTOR / "medidas.json"
# Segundos de trabajo por cada segundo de video, hasta que haya medidas de verdad (salen de motor/medidas.json, que se
# actualiza solo después de cada armado). Son una ESTIMACIÓN.
POR_SEGUNDO_INICIAL = {"clips": 0.8, "voz": 0.9, "tiempos": 0.05, "armado": 1.2, "armado_rapida": 0.3, "textos": 0.5}


# ------------------------------------------------------------------------------------------- Avance

def leer_medidas():
    try:
        m = leer_json(MEDIDAS)
    except (OSError, ValueError):
        m = {}
    por = {**POR_SEGUNDO_INICIAL, **(m.get("por_segundo") or {})}
    return {"por_segundo": por, "palabras_por_segundo": m.get("palabras_por_segundo") or contrato.PALABRAS_POR_SEGUNDO,
            "muestras": m.get("muestras", 0)}


def guardar_medidas(medidas, tardanza, segundos_video, palabras, rapida, reales):
    """Promedio que se mueve: la mitad de lo viejo y la mitad de lo nuevo. Sólo las etapas que trabajaron de verdad
    (una voz que salió de lo guardado no mide nada)."""
    por = dict(medidas["por_segundo"])
    if segundos_video <= 0:
        return
    for etapa, s in tardanza.items():
        if etapa not in reales:
            continue
        clave = "armado_rapida" if etapa == "armado" and rapida else etapa
        nuevo = s / segundos_video
        por[clave] = round(nuevo if medidas["muestras"] == 0 else (por[clave] + nuevo) / 2, 3)
    pps = palabras / segundos_video
    viejo = medidas["palabras_por_segundo"]
    try:
        escribir_json(MEDIDAS, {"por_segundo": por, "palabras_por_segundo": round((viejo + pps) / 2, 3),
                                "muestras": medidas["muestras"] + 1,
                                "nota": "lo escribe armar.py solo; sirve para estimar cuánto falta"})
    except OSError:
        pass


class Avance:
    def __init__(self, carpeta, segundos_video, rapida, medidas):
        self.ruta = Path(carpeta) / "avance.json"
        self.estado = {e: "espera" for e in contrato.ETAPAS}
        self.rapida = rapida
        self.medidas = medidas
        self.segundos_video = segundos_video
        self.inicio_etapa = None
        self.actual = None
        self.tardanza = {}

    def estimado(self, etapa):
        clave = "armado_rapida" if etapa == "armado" and self.rapida else etapa
        return self.medidas["por_segundo"][clave] * self.segundos_video

    def escribir(self, error=None):
        total = sum(self.estimado(e) for e in ORDEN) or 1
        hecho, restante = 0.0, 0.0
        for e in ORDEN:
            est = self.estimado(e)
            if self.estado[e] == "listo":
                hecho += est
            elif self.estado[e] == "haciendo":
                pasado = time.time() - self.inicio_etapa
                hecho += min(pasado, est * 0.9)
                restante += max(est - pasado, est * 0.1)
            elif self.estado[e] == "espera":
                restante += est
        listo = all(self.estado[e] == "listo" for e in ORDEN)
        datos = {"etapas": [{"id": e, "estado": self.estado[e]} for e in contrato.ETAPAS],
                 "porcentaje": 100 if listo else min(99, int(100 * hecho / total)),
                 "restante": 0 if listo or error else max(1, int(round(restante))),
                 "actual": self.actual, "hechas": [e for e in ORDEN if self.estado[e] == "listo"],
                 "actualizado": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if error:
            datos["error"] = error
        escribir_json(self.ruta, datos)

    def empezar(self, etapa):
        self.actual = etapa
        self.estado[etapa] = "haciendo"
        self.inicio_etapa = time.time()
        self.escribir()
        registro(f"[{etapa}]")

    def terminar(self, etapa):
        self.tardanza[etapa] = round(time.time() - self.inicio_etapa, 2)
        self.estado[etapa] = "listo"
        self.actual = None
        self.escribir()

    def fallar(self, error):
        etapa = self.actual or next((e for e in ORDEN if self.estado[e] != "listo"), ORDEN[0])
        self.estado[etapa] = "fallo"
        self.escribir(error)


# ------------------------------------------------------------------------------------------- Guion y tramos

def guion_del_trabajo(trabajo):
    g = trabajo.get("guion") or {}
    texto = " ".join(sin_links(sin_emojis(contrato.limpiar_invisibles(g.get("texto", "")))).split())
    if not texto:
        raise Falla("GUION_A_CORREGIR", "el guion está vacío")
    if trabajo.get("largo") not in contrato.LARGOS:
        raise Falla("DESCONOCIDO", "el largo del trabajo no es 15, 30 ni 60")
    if not contrato.entra_en_largo(contrato.contar_palabras(texto), trabajo["largo"]):
        raise Falla("GUION_A_CORREGIR", "el guion se pasa del largo")
    return texto


def tramos_guardados(trabajo, texto):
    """Los tramos que escribió guiones.py, si el guion elegido sigue siendo el mismo palabra por palabra."""
    gs = trabajo.get("guiones") or {}
    for g in gs.get("lista") or []:
        if g.get("id") != gs.get("elegido"):
            continue
        try:
            v = g["versiones"][g.get("actual", 0)]
        except (KeyError, IndexError, TypeError):
            return None
        tramos = v.get("tramos")
        if tramos and " ".join(t["texto"] for t in tramos).split() == texto.split():
            return tramos
    return None


ESQUEMA_BUSCAR = {"type": "object", "properties": {"tramos": {"type": "array", "items": {
    "type": "object", "properties": {"buscar": {"type": "array", "items": {"type": "string"}}},
    "required": ["buscar"]}}}, "required": ["tramos"]}


def buscar_para(tramos_texto, nota):
    """Para un guion escrito o cambiado a mano: UN pedido a Google con las búsquedas de clips de cada tramo. Si Google
    no contesta, las búsquedas genéricas del tema."""
    from guiones import INSTRUCCIONES   # las mismas reglas de búsqueda (y de notas sensibles) que los guiones
    pedido = ("Para cada tramo, en el mismo orden, da de 2 a 3 búsquedas en inglés para clips de archivo, siguiendo "
              "las reglas de 'buscar'. " + ("La nota es SENSIBLE: sólo ambientes y objetos, nunca personas.\n\n"
                                            if nota.get("sensible") else "\n\n")
              + "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(tramos_texto)))
    try:
        r = pedir_json(INSTRUCCIONES, pedido, ESQUEMA_BUSCAR, intentos=2)
        listas = [t.get("buscar") or [] for t in r.get("tramos") or []]
    except (Falla, TopeDelDia) as e:
        if getattr(e, "codigo", "") == "SIN_CONEXION":
            raise
        listas = []
    genericos = C.GENERICOS.get(nota.get("tema"), C.GENERICOS["general"])
    return [{"texto": t, "buscar": (listas[i] if i < len(listas) and listas[i] else genericos[:2])}
            for i, t in enumerate(tramos_texto)]


# ------------------------------------------------------------------------------------------- Armado

def ffmpeg(args, cwd):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        ultima = (r.stderr.strip().splitlines() or ["sin detalle"])[-1]
        raise Falla("FALLO_ARMADO", "FFmpeg: " + sin_rutas(ultima)[:200])


def plan_de_tomas(eleccion, limites):
    """Las tomas del video: [(ruta, inicio, fin)] para FFmpeg y el plan para armado.json, una por toma:
    {"tramo", "clip", "desde", "hasta", "buscado", "mirado", "origen", "prestado_de"?}. "tramo" y "prestado_de" (de
    qué tramo sale un clip prestado) cuentan desde 1, como se ven en el video; en "mirada" los tramos van desde 0.
    "mirado": lo que dijo Claude de ese clip ("sirve", "no tiene que ver"...) o None si no lo miró; "origen": "propio",
    "prestado" o "rechazado_ultimo_recurso" (uno "no tiene que ver" que entró porque no quedaba ningún otro).
    "clip_desde": en qué segundo del clip arranca la toma (0 si el clip va entero); "cortado": lo que medir_clip.py le
    sacó al clip y por qué ([{"desde", "hasta", "motivo"}], segundos del clip), sólo si se le sacó algo.
    Cada toma para FFmpeg es (ruta, inicio, fin, desde, hasta): desde y hasta son el pedazo bueno del clip, o None."""
    usados = {c["id"] for e in eleccion for c in e["usados"]}
    lista_tomas, plan = [], []
    for e, (ini, fin) in zip(eleccion, limites):
        clips_tramo = C.completar(e, fin - ini, usados)
        t0 = ini
        for clip, s in C.tomas(clips_tramo, fin - ini):
            lista_tomas.append((clip["ruta"], t0, t0 + s, clip.get("desde"), clip.get("hasta")))
            toma = {"tramo": e["tramo"] + 1, "clip": clip["id"], "desde": round(t0, 2), "hasta": round(t0 + s, 2),
                    "buscado": e["buscado"], "mirado": clip.get("mirado"), "origen": clip.get("origen", "propio"),
                    "clip_desde": clip.get("desde", 0.0)}
            if clip.get("cortado"):
                toma["cortado"] = clip["cortado"]
            if clip["id"] in (e.get("prestado_de") or {}):
                toma["prestado_de"] = e["prestado_de"][clip["id"]] + 1
            plan.append(toma)
            t0 += s
    return lista_tomas, plan


def limites_de_tramos(tramos, tiempos, total):
    """Dónde empieza cada tramo: en el arranque de su primera palabra (el primero en 0, el último termina con la voz)."""
    cuentas = [len([w for w in t["texto"].split() if normalizar(w)]) for t in tramos]
    inicios, k = [], 0
    for n in cuentas:
        inicios.append(tiempos[k][0] if k < len(tiempos) else total)
        k += n
    inicios[0] = 0.0
    return [(inicios[i], inicios[i + 1] if i + 1 < len(inicios) else total) for i in range(len(tramos))]


# Colores: el video sale marcado como alta definición (bt709), igual que estudio/herramientas/armar_video_ejemplo.py,
# y la portada JPEG con la receta común en rango completo (si no, los colores salen corridos en algunos programas).
MARCAS_ALTA_DEFINICION = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
PORTADA_ESCALA = "scale=540:960:in_color_matrix=bt709:in_range=tv:out_color_matrix=bt601:out_range=full"
_DEFINICION_COMUN = {"smpte170m", "bt470bg", "bt601"}


def matriz_del_clip(ruta):
    """bt601 si el clip dice que es de definición común; si no dice nada, bt709 (los de Pexels son de alta)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_space",
                        "-of", "csv=p=0", str(ruta)], capture_output=True, text=True)
    return "bt601" if r.stdout.strip() in _DEFINICION_COMUN else "bt709"


def pedazo_aparte(carpeta, ruta, desde, hasta):
    """El pedazo bueno del clip en un archivo aparte (adentro de `carpeta`), para repetirlo en bucle: repetir el clip
    entero volvería a pasar por la parte cortada."""
    destino = Path(carpeta) / f"pedazo-{len(list(Path(carpeta).glob('pedazo-*.mp4')))}.mp4"
    ffmpeg(["-ss", f"{desde:.3f}", "-t", f"{hasta - desde:.3f}", "-i", str(ruta), "-an", "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "14", str(destino)], cwd=carpeta)
    return destino


def armar_video(carpeta, tomas, total, ancho, alto, cuadros, preset, sonido=None):
    """tomas: [(ruta del clip, inicio, fin)] o [(ruta, inicio, fin, desde, hasta)] seguidas; desde y hasta, el pedazo
    bueno del clip (None si va entero). Un solo FFmpeg: cada toma arranca en su pedazo, recortada al centro, escalada y
    cortada a su cantidad exacta de cuadros; los subtítulos encima; la voz en AAC. Si una toma dura más que su pedazo,
    el pedazo se pasa antes a un archivo aparte (en una carpeta temporal) y se repite ése.
    sonido: lo que preparó vuelta.preparar (recorte de los bordes mudos y volumen de la última frase); None, la voz
    entera como está. Al final no hay fundido ni portada: la imagen sigue hasta el último cuadro, para la vuelta."""
    with tempfile.TemporaryDirectory(prefix="portavoz-pedazos-") as aparte:
        _armar_video(carpeta, tomas, total, ancho, alto, cuadros, preset, aparte, sonido)


def _armar_video(carpeta, tomas, total, ancho, alto, cuadros, preset, aparte, sonido=None):
    args, filtros, etiquetas, matrices = [], [], [], {}
    tomas = [(*t, None, None)[:5] for t in tomas]
    limites = [round(ini * cuadros) for _, ini, _, _, _ in tomas] + [round(total * cuadros)]
    for i, (ruta, ini, fin, desde, hasta) in enumerate(tomas):
        n = max(1, limites[i + 1] - limites[i])
        matriz = matrices.setdefault(str(ruta), matriz_del_clip(ruta))
        largo = n / cuadros + 0.5
        if desde is None:
            args += ["-stream_loop", "-1", "-t", f"{largo:.3f}", "-i", str(ruta)]
        elif hasta - desde >= largo:
            args += ["-ss", f"{desde:.3f}", "-t", f"{largo:.3f}", "-i", str(ruta)]
        else:
            args += ["-stream_loop", "-1", "-t", f"{largo:.3f}", "-i", str(pedazo_aparte(aparte, ruta, desde, hasta))]
        filtros.append(f"[{i}:v]fps={cuadros},scale={ancho}:{alto}:force_original_aspect_ratio=increase:"
                       f"in_color_matrix={matriz}:out_color_matrix=bt709,crop={ancho}:{alto},setsar=1,format=yuv420p,"
                       f"setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709,"
                       f"trim=end_frame={n},setpts=PTS-STARTPTS[v{i}]")
        etiquetas.append(f"[v{i}]")
    voz = len(tomas)
    args += ["-i", "voz.mp3"]
    filtros.append("".join(etiquetas) + f"concat=n={len(tomas)}:v=1:a=0[base]")
    # El .ass va con su nombre corto porque FFmpeg corre adentro de la carpeta del trabajo (la ruta puede tener espacios).
    # Va con el filtro "ass" y no con "subtitles": "subtitles" lee el archivo con otro lector y, si alguna palabra dura
    # cero (la transcripción a veces las da), pierde el primer renglón (medido el 2026-11-20 con el video de Tesla:
    # faltaba la caja oscura del arranque). Lo vigila estudio/herramientas/probar_subtitulos.py.
    filtros.append(f"[base]ass=subtitulos.ass:fontsdir='{S.FONTSDIR}'[v]")
    if sonido:
        filtros.append(VU.filtro(sonido, voz, "a"))
    pid = os.getpid()
    video_parcial, portada_parcial = f"video.{pid}.parcial.mp4", f"portada.{pid}.parcial.jpg"
    ffmpeg([*args, "-filter_complex", ";".join(filtros), "-map", "[v]", "-map", "[a]" if sonido else f"{voz}:a:0",
            "-t", f"{total:.3f}", "-r", str(cuadros), "-c:v", "libx264", "-preset", preset, "-crf", "21",
            "-pix_fmt", "yuv420p", *MARCAS_ALTA_DEFINICION, "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            video_parcial],
           cwd=carpeta)
    ffmpeg(["-ss", f"{min(1.0, total / 2):.2f}", "-i", video_parcial, "-frames:v", "1", "-vf", PORTADA_ESCALA,
            "-q:v", "3", portada_parcial], cwd=carpeta)
    # Primero la portada y después el video: si el video está, la portada también.
    os.replace(Path(carpeta) / portada_parcial, Path(carpeta) / "portada.jpg")
    os.replace(Path(carpeta) / video_parcial, Path(carpeta) / "video.mp4")


def escribir_subtitulos(carpeta, palabras_tiempos, nota, total):
    vt = TX.textos_video()
    renglones = ([vt["fuente"].replace("{medio}", nota["medio"])] if nota.get("medio") else []) + [vt["ilustrativas"]]
    # las cifras se ven en números, en una sola pantalla (la voz las dice en palabras): cifras.py
    en_pantalla = juntar_cifras(palabras_tiempos)
    palabras = [S.limpiar(w) for w, _, _ in en_pantalla]
    tiempos = [(ini, fin) for _, ini, fin in en_pantalla]
    variante = "Sobria" if nota.get("sensible") else "Principal"
    eventos = S.dialogos(palabras, tiempos, variante) + [S.pie(renglones, total)]
    (Path(carpeta) / "subtitulos.ass").write_text(S.cabecera() + "\n".join(eventos) + "\n", encoding="utf-8")
    return variante


def anotar_voces(carpeta, n):
    """Suma n a vocesGastadas en trabajo.json (leer, cambiar y guardar sin esperas en el medio)."""
    ruta = Path(carpeta) / "trabajo.json"
    t = leer_json(ruta)
    t["vocesGastadas"] = int(t.get("vocesGastadas") or 0) + n
    escribir_json(ruta, t)


# ------------------------------------------------------------------------------------------- Todo junto

def armar(carpeta, rapida):
    carpeta = Path(carpeta).resolve()
    try:
        trabajo = leer_json(carpeta / "trabajo.json")
    except (OSError, ValueError):
        raise Falla("DESCONOCIDO", "no se pudo leer trabajo.json")
    nota = trabajo.get("nota") or {}
    sensible = bool(nota.get("sensible")) or nota.get("tema") in contrato.TEMAS_SENSIBLES
    medidas = leer_medidas()
    texto = guion_del_trabajo(trabajo)
    palabras = contrato.contar_palabras(texto)
    ancho, alto, cuadros, preset = (540, 960, 15, "ultrafast") if rapida else (1080, 1920, 30, "veryfast")
    av = Avance(carpeta, palabras / medidas["palabras_por_segundo"], rapida, medidas)
    voces = [0]
    reales = set()
    try:
        for archivo in S.ARCHIVOS_LETRAS:
            if not (medir.LETRAS / archivo).exists():
                raise Falla("FALLO_ARMADO", f"falta la letra {archivo} en marca/letras")

        # CLIPS (antes que la voz: si no hay clips no se gasta una voz)
        av.empezar("clips")
        tramos = tramos_guardados(trabajo, texto) or buscar_para(tramos_de(texto), nota)
        pedidos_antes = C.contados()
        mirada = {}
        pedidas = {}   # las búsquedas nuevas que escribe Claude al mirar, para los tramos sin ningún clip que sirva
        eleccion = C.elegir_clips(tramos, sensible, nota.get("tema", "general"), ancho, alto,
                                  1 / medidas["palabras_por_segundo"],
                                  mirar=lambda grupos: MC.mirar(grupos, nota, sensible, busquedas=pedidas),
                                  mirada=mirada, busquedas=pedidas)
        if C.contados() != pedidos_antes:
            reales.add("clips")
        av.terminar("clips")

        # VOZ
        av.empezar("voz")

        def al_gastar():
            voces[0] += 1
            anotar_voces(carpeta, 1)

        info_voz = voz_para(texto, sensible, carpeta, al_gastar=al_gastar)
        guardar_control(carpeta, info_voz)
        if info_voz["gastadas"]:
            reales.add("voz")
        total = info_voz["duracion"]
        av.segundos_video = total
        av.terminar("voz")

        # TIEMPOS
        av.empezar("tiempos")
        palabras_tiempos = tiempos_del_guion(texto, leer_json(carpeta / "transcripcion.json"), total)
        # la vuelta: se recortan los bordes mudos (y los tiempos se corren lo mismo) y se empareja la última frase
        sonido = VU.preparar(carpeta / "voz.mp3", texto, palabras_tiempos)
        if sonido.get("fallo"):
            registro(f"  la vuelta no se pudo medir ({sonido['fallo']}): la voz va entera, como está")
        elif sonido["duracion"]:
            palabras_tiempos = VU.correr(palabras_tiempos, sonido)
            total = sonido["duracion"]
        reales.add("tiempos")
        av.terminar("tiempos")

        # ARMADO
        av.empezar("armado")
        variante = escribir_subtitulos(carpeta, palabras_tiempos, nota, total)
        limites = limites_de_tramos(tramos, [(i, f) for _, i, f in palabras_tiempos], total)
        lista_tomas, plan = plan_de_tomas(eleccion, limites)
        for e in eleccion:   # los repuestos que quedaron afuera al medirlos (clips.completar)
            mirada.setdefault("sin_pedazos", []).extend(e.get("sin_pedazos") or [])
        armar_video(carpeta, lista_tomas, total, ancho, alto, cuadros, preset, sonido)
        vuelta = {"recorte": [sonido["desde"], sonido["hasta"]], "ganancia_ultima": sonido["ganancia"]}
        try:
            vuelta.update(VU.medir_vuelta(carpeta / "video.mp4"))
            for aviso in vuelta["avisos"]:
                registro(f"  ojo con la vuelta: {aviso}")
        except (RuntimeError, OSError) as e:
            vuelta["fallo"] = f"no se pudo medir en el video: {e}"
        reales.add("armado")
        av.terminar("armado")

        def anotar_armado():
            """armado.json: qué clip va en cada momento, la voz y los segundos de cada etapa. Se escribe apenas
            está el video (si después fallan los textos, queda igual) y otra vez al final."""
            escribir_json(carpeta / "armado.json", {
                "segundos": av.tardanza, "duracion": round(total, 3), "estilo": variante,
                "medida": f"{ancho}x{alto}", "cuadros": cuadros, "tomas": plan, "mirada": mirada, "vuelta": vuelta,
                "voz": {k: info_voz[k] for k in ("parecido", "gastadas", "de_guardada", "estilo")},
                "vocesGastadas": voces[0]})

        anotar_armado()

        # TEXTOS
        av.empezar("textos")
        resultado = TX.generar(carpeta, trabajo)
        reales.add("textos")
        av.terminar("textos")
    except Falla as f:
        error = contrato.crear_error(f.codigo, sin_rutas(f.detalle)[:300] if f.detalle else None)["error"]
        av.fallar(error)
        (carpeta / "armado-error.txt").write_text(f"{f.codigo}: {sin_rutas(f.detalle or '')[:300]}\n", encoding="utf-8")
        raise
    except Exception as e:
        error = contrato.crear_error("DESCONOCIDO", sin_rutas(f"{type(e).__name__}: {e}")[:300])["error"]
        av.fallar(error)
        (carpeta / "armado-error.txt").write_text(f"DESCONOCIDO: {error.get('detalle', '')}\n", encoding="utf-8")
        raise

    guardar_medidas(medidas, av.tardanza, total, palabras, rapida, reales)
    anotar_armado()
    return {"resultado": resultado, "segundos": av.tardanza, "vocesGastadas": voces[0]}


def principal():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise Falla("DESCONOCIDO", "uso: armar.py <carpeta del trabajo> [--rapida]")
    carpeta = Path(args[0])
    if not carpeta.is_dir():
        raise Falla("DESCONOCIDO", "no existe la carpeta del trabajo")
    return armar(carpeta, "--rapida" in sys.argv[1:])


if __name__ == "__main__":
    sys.exit(correr(principal))
