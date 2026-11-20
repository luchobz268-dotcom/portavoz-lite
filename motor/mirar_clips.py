"""Claude mira cada clip candidato antes de usarlo (plan woolly-locket, Parte A, 2026-11-18).

Lo usa clips.py (elegir_clips). De cada clip saca tres cuadros (principio, medio y final) del archivo mediano de
Pexels, sin bajarlo entero: FFmpeg pide sólo el pedacito de cada momento. Las miniaturas que Pexels da con la búsqueda
(180 por 320) quedaron chicas: en la primera prueba real no se leía la marca de un reloj ni se veía una cara reflejada
en una vidriera (2026-11-18). Esas miniaturas quedan de respaldo si el video no se puede abrir. Los tres cuadros van
uno al lado del otro en una sola imagen, y manda UN pedido con todas las imágenes
del video, la nota y lo que dice cada tramo. Claude contesta, clip por clip, si sirve o por qué no.

Qué se mide y qué no: que cada clip que entra fue mirado se MIDE (queda en armado.json). Que Claude acierte con la
gente, las marcas y los lugares se ESTIMA: tres fotitos no ven lo que pasa entre una y otra, y una marca chiquita
puede pasar.

Si Claude no puede mirar (sin internet, tope del plan, tarda demasiado), quien llama sigue como antes, con el filtro
de palabras de clips.py, y lo deja anotado (Lucio, 2026-11-18: "sigue igual que hoy").

Si a un tramo no le sirve ninguno de sus clips, Claude escribe en la misma respuesta 2 búsquedas nuevas de ambiente
para esa frase ("busquedas"); clips.py las prueba antes que las de siempre, para no tener que prestar un clip de otro
tramo. En el pedido van las búsquedas ya probadas de cada tramo, para que no las repita (18/11: la tercera vuelta
repetía las cuatro de la segunda y no podía traer nada nuevo).
"""
import hashlib
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from comun import CACHE, Falla, bajar, pedir_json, registro

CARPETA = CACHE / "fotitos"
ALTO_FOTITO = 640          # alto de cada cuadro: a 320 no se leían marcas ni se veían reflejos (medido el 18/11)
ANCHO_MAXIMO = 480         # un clip apaisado se achica a este ancho, para que la tira no quede enorme
MOMENTOS = (0.1, 0.5, 0.9)  # en qué parte del clip se saca cada cuadro
SIRVE = "sirve"
SIN_MIRAR = "sin mirar"     # sin fotitos, o Claude no lo contestó
DE_CLAUDE = ("gente", "marca", "lugar", "pantalla", "dibujo", "contradice")   # los graves que decide Claude
# "dibujo": Lucio, 2026-11-20, con botón: los dibujos animados quedan afuera (el de una factura "BILLS" en el video
# de Tesla rearmado mostraba cifras que no eran de la nota).
# Lo decide la PC midiendo la tira, antes de mandársela a Claude (no gasta cupo): los tres cuadros sin color
# (Lucio, 2026-11-18: "tampoco videos en blanco y negro"). El blanco y negro de un pedazo se corta en medir_clip.py.
BLANCO_Y_NEGRO = "blanco y negro"
GRAVES = (*DE_CLAUDE, BLANCO_Y_NEGRO)               # nunca entran
FLOJO = "no tiene que ver"                          # entra sólo si no queda otra
MOTIVOS = [SIRVE, *DE_CLAUDE, FLOJO]                # lo que puede contestar Claude

INSTRUCCIONES = """Miras clips de video de archivo (Pexels) que van de fondo en un video corto de noticias, mientras
una voz lee el guion. De cada clip ves tres cuadros, uno al lado del otro: principio, medio y final.

Para cada clip decides si sirve para el tramo del guion que acompaña. "motivo" es UNO de estos, del más grave al menos:
- "gente": SÓLO si la nota es DELICADA (política, crimen o tragedia) y en algún cuadro se distingue una persona: una
  cara, un cuerpo entero, o una persona como protagonista de la imagen, aunque esté de espaldas. También cuenta una
  cara reflejada en un vidrio o un espejo, o en un cartel. Las fotos de bancos
  como Pexels no se pueden usar con gente reconocible en esos temas. Sólo sirven multitudes muy lejanas donde no se
  distingue a nadie, o manos sueltas sin cara. En una nota que NO es delicada, la gente no es motivo.
- "marca": se lee o se reconoce una marca, un logo o un nombre comercial que no es el de la nota, aunque sea chico o
  se lea a medias: el nombre en la esfera de un reloj, el logo de un auto, el cartel de un negocio, un envase, la
  pantalla de una app o un servicio que la nota no nombra.
- "lugar": muestra un lugar que contradice la nota: la bandera o un cartel de otro país, un monumento famoso de otra
  ciudad, arquitectura típica de otro país (por ejemplo los edificios de ladrillo con escaleras de incendio por fuera,
  típicos de Nueva York), o un paisaje imposible para el lugar que nombra la nota: mar, bahía o costa si ese lugar no
  tiene costa, montañas, nieve. Cuenta también lo que se ve reflejado en un vidrio. Una calle, un edificio o una
  ruta sin señas de dónde son sirven.
- "pantalla": se ve un celular, una tableta, un monitor o una tele con la pantalla en blanco, en verde, apagada o de
  un solo color, sin nada adentro, aunque sea en un solo cuadro o en un rincón. En el video queda un hueco vacío.
  Una pantalla con una imagen adentro (sin marca) no es motivo.
- "dibujo": no es una filmación de verdad sino un dibujo animado, una ilustración, un gráfico animado o una animación
  hecha en computadora (por ejemplo una factura dibujada sobre un fondo de color, íconos o personajes dibujados),
  aunque sea en un solo cuadro. Los números o textos dibujados no son de la nota y confunden.
- "contradice": la imagen contradice lo que dice la voz en ese tramo (por ejemplo, alguien manejando con las manos en
  el volante cuando la voz dice que el auto no tiene volante), o muestra otro tipo de lugar u objeto que el que
  nombra (una tienda de ropa cuando la voz dice "relojería"). Si la nota trata de un producto, modelo, edificio o
  lugar concreto (un auto de cierta marca, un teléfono, un estadio), un clip con OTRO de su tipo como protagonista
  contradice: parece que ese es el de la nota (un auto común cuando la voz dice "el Cybercab"). Para eso sirven
  ambientes sin protagonista: calles, rutas, una ciudad, pantallas sin marca. También contradice un símbolo que
  sugiere otra cosa (una caja de regalo o un cartel de oferta cuando la voz habla de pagar).
- "no tiene que ver": no tiene relación con lo que dice el tramo ni con la nota (por ejemplo un baile para una nota
  de economía).
- "sirve": nada de lo anterior.
Ante la duda entre "sirve" y un motivo grave, elige el motivo grave. Los clips del tramo 1 van también de portada
del video: míralos con más cuidado todavía. "detalle": en pocas palabras y en castellano,
qué se ve que te hizo decidir. Contesta todos los clips, con su número.

"busquedas": si a un tramo no le sirve ninguno de sus clips, escribe 2 búsquedas nuevas de ambiente para esa frase:
en inglés, de 1 a 3 palabras, sin protagonista, sin marcas ni lugares con nombre, y sin gente si la nota es delicada.
Nunca repitas una de las que ya se buscaron para ese tramo (van después de "Ya se buscó"): esas no traen nada nuevo.
"tramo" es el número de tramo que te paso. Si todos los tramos tienen algún clip que sirve, deja la lista vacía."""

ESQUEMA = {"type": "object", "properties": {
    "clips": {"type": "array", "items": {"type": "object", "properties": {
        "numero": {"type": "integer"}, "motivo": {"type": "string", "enum": MOTIVOS}, "detalle": {"type": "string"},
    }, "required": ["numero", "motivo", "detalle"]}},
    # opcional: búsquedas nuevas para los tramos sin ningún clip que sirva
    "busquedas": {"type": "array", "items": {"type": "object", "properties": {
        "tramo": {"type": "integer"}, "consultas": {"type": "array", "items": {"type": "string"}},
    }, "required": ["tramo", "consultas"]}},
}, "required": ["clips"]}
BUSQUEDAS_POR_TRAMO = 2


def cuadros_de(video):
    """Hasta tres links de fotitos del clip (principio, medio y final). Vacío si Pexels no dio ninguna."""
    lista = [c for c in video.get("cuadros") or [] if c]
    if not lista:
        return [video["imagen"]] if video.get("imagen") else []
    if len(lista) <= 3:
        return lista
    return [lista[0], lista[len(lista) // 2], lista[-1]]


def _bajar_foto(link):
    codigo, cuerpo, _ = bajar(link, {"Accept": "image/jpeg,image/*"}, timeout=30, tope_bytes=5_000_000)
    if codigo != 200 or len(cuerpo) < 500:
        raise Falla("DESCONOCIDO", f"no se pudo bajar una fotito de Pexels ({codigo})")
    return cuerpo


def archivo_para_mirar(video):
    """El archivo de Pexels del que se sacan los cuadros: el más chico que tenga al menos 540 de lado corto (alcanza
    para leer una marca en un reloj) o, si no hay, el más grande que haya."""
    archivos = [a for a in video.get("archivos") or [] if a.get("link") and a.get("ancho") and a.get("alto")]
    if not archivos:
        return None
    lado = lambda a: min(a["ancho"], a["alto"])   # noqa: E731
    buenos = [a for a in archivos if lado(a) >= 540]
    return min(buenos, key=lado) if buenos else max(archivos, key=lado)


def _cuadro(link, segundo, destino):
    """Un cuadro del video en `segundo`, pedido por internet sin bajar el archivo entero."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-user_agent", "portavoz-lite/0.1",
                        "-ss", f"{segundo:.2f}", "-i", link, "-frames:v", "1", "-q:v", "4", str(destino)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
    if r.returncode != 0 or not destino.exists() or destino.stat().st_size < 500:
        raise Falla("DESCONOCIDO", "no se pudo sacar un cuadro del clip")
    return destino.read_bytes()


def _cuadros_del_video(video):
    """Tres cuadros (principio, medio y final) del archivo mediano del clip. None si no se pudo."""
    archivo = archivo_para_mirar(video)
    duracion = float(video.get("duracion") or 0)
    if not archivo or duracion <= 0:
        return None
    with tempfile.TemporaryDirectory(prefix="portavoz-cuadros-") as carpeta:
        try:
            return [_cuadro(archivo["link"], max(0.0, min(duracion * m, duracion - 0.5)), Path(carpeta) / f"{i}.jpg")
                    for i, m in enumerate(MOMENTOS)]
        except (Falla, subprocess.TimeoutExpired, OSError):
            return None


def tira(video):
    """Una imagen JPEG con tres cuadros del clip uno al lado del otro (guardada en motor/cache/fotitos). Los cuadros
    salen del video; si no se puede, de las miniaturas de Pexels. None si no hay nada que mirar."""
    archivo = archivo_para_mirar(video)
    links = cuadros_de(video)
    if not archivo and not links:
        return None
    clave = hashlib.md5(f"v2|{archivo and archivo['link']}|{'|'.join(links)}".encode("utf-8")).hexdigest()[:12]
    destino = CARPETA / f"{video['id']}-{clave}.jpg"
    if destino.exists() and destino.stat().st_size > 500:
        return destino.read_bytes()
    fotos = _cuadros_del_video(video)
    if not fotos:
        if not links:
            return None
        try:
            fotos = [_bajar_foto(l) for l in links]
        except Falla:
            return None
    CARPETA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="portavoz-fotitos-") as carpeta:
        entradas = []
        for i, datos in enumerate(fotos):
            ruta = Path(carpeta) / f"{i}.jpg"
            ruta.write_bytes(datos)
            entradas += ["-i", str(ruta)]
        n = len(fotos)
        escalas = ";".join(f"[{i}:v]scale=w={ANCHO_MAXIMO}:h={ALTO_FOTITO}:force_original_aspect_ratio=decrease,"
                           f"scale=-2:{ALTO_FOTITO},format=yuvj420p[f{i}]" for i in range(n))
        union = ("".join(f"[f{i}]" for i in range(n)) + f"hstack=inputs={n}[t]") if n > 1 else "[f0]copy[t]"
        salida = Path(carpeta) / "tira.jpg"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *entradas, "-filter_complex",
                            f"{escalas};{union}", "-map", "[t]", "-frames:v", "1", "-q:v", "5", str(salida)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not salida.exists():
            return None
        datos = salida.read_bytes()
    destino.write_bytes(datos)
    return datos


def sin_color(datos):
    """True si la tira (los tres cuadros) es blanco y negro, medido con la misma regla que medir_clip.py. Si no se
    puede medir, False: el clip se le muestra a Claude como siempre."""
    import medir_clip as MC
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "-", "-vf", "scale=270:160",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], input=datos, capture_output=True, timeout=30)
        cuadro = MC.np.frombuffer(r.stdout, dtype=MC.np.uint8).reshape(1, 160, 270, 3)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return False
    return bool(MC.medidas_de_cuadros(cuadro)[0][0] < MC.COLOR_MINIMO)


def pedido(grupos, nota, sensible, numeros):
    """El texto del pedido: la nota, si es delicada, y cada tramo con los números de sus clips."""
    renglones = [
        ("La nota es DELICADA (" + str(nota.get("tema") or "") + "): rige el motivo 'gente'." if sensible
         else "La nota NO es delicada: la gente no es motivo."),
        f"Titular: {nota.get('titular', '')}",
        "Comienzo de la nota: " + " ".join(str(nota.get("texto", "")).split()[:250]),
        "",
        "Tramos del guion (lo que dice la voz) y los clips de cada uno:",
    ]
    for g in grupos:
        nums = [str(numeros[v["id"]]) for v in g["candidatos"] if v["id"] in numeros]
        if nums:
            ya = "; ".join(g.get("probadas") or [])
            renglones.append(f"Tramo {g['tramo'] + 1}: \"{g['texto']}\". Clips: {', '.join(nums)}."
                             + (f" Ya se buscó: {ya}." if ya else ""))
    return "\n".join(renglones)


def busquedas_de(respuesta, grupos):
    """{tramo (desde 0): [consultas]} con las búsquedas nuevas que escribió Claude, limpias: en minúscula, de 1 a 3
    palabras, sin repetir, 2 por tramo, y sólo de tramos que se le pasaron. Las que ya se buscaron para ese tramo
    ("probadas" del grupo) no van: clips.py igual las vuelve a sacar."""
    tramos = {g["tramo"] for g in grupos}
    ya = {g["tramo"]: set(g.get("probadas") or []) for g in grupos}
    salida = {}
    for b in (respuesta or {}).get("busquedas") or []:
        if not isinstance(b, dict) or not isinstance(b.get("tramo"), int):
            continue
        tramo = b["tramo"] - 1   # Claude ve los tramos desde 1
        if tramo not in tramos:
            continue
        lista = salida.setdefault(tramo, [])
        for c in b.get("consultas") or []:
            c = " ".join(str(c).lower().replace("#", "").split())
            if (c and len(c.split()) <= 3 and c not in lista and c not in ya[tramo]
                    and len(lista) < BUSQUEDAS_POR_TRAMO):
                lista.append(c)
    return {t: l for t, l in salida.items() if l}


def mirar(grupos, nota, sensible, busquedas=None):
    """grupos: [{"tramo": i, "texto": "...", "candidatos": [video, ...], "probadas"?: [búsquedas ya hechas]}].
    Devuelve {id del clip: {"motivo",
    "detalle"}} para todos los candidatos: los que no tienen fotitos van con motivo "sin mirar".
    Si se le pasa `busquedas` (un diccionario), deja ahí las búsquedas nuevas que escribió Claude para los tramos sin
    ningún clip que sirva: {tramo (desde 0): [consultas]}.
    Tira Falla o TopeDelDia si Claude (o quien lo reemplace) no pudo mirar."""
    todos = []
    for g in grupos:
        for v in g["candidatos"]:
            if v["id"] not in [x["id"] for x in todos]:
                todos.append(v)
    with ThreadPoolExecutor(max_workers=8) as ex:
        tiras = list(ex.map(tira, todos))
    veredictos, imagenes, numeros, por_numero = {}, [], {}, {}
    for v, datos in zip(todos, tiras):
        if datos is None:
            veredictos[v["id"]] = {"motivo": SIN_MIRAR, "detalle": "Pexels no dio fotitos"}
            continue
        if sin_color(datos):
            veredictos[v["id"]] = {"motivo": BLANCO_Y_NEGRO, "detalle": "los tres cuadros, medidos en la PC"}
            continue
        n = len(imagenes) + 1
        numeros[v["id"]], por_numero[n] = n, v["id"]
        imagenes.append((f"Clip {n}:", datos))
    if not imagenes:
        return veredictos
    registro(f"  mirando {len(imagenes)} clips")
    r = pedir_json(INSTRUCCIONES, pedido(grupos, nota, sensible, numeros), ESQUEMA, intentos=2, imagenes=imagenes)
    for c in r.get("clips") or []:
        id_ = por_numero.get(c.get("numero"))
        motivo = c.get("motivo")
        if id_ is None or motivo not in MOTIVOS:
            continue
        if motivo == "gente" and not sensible:
            motivo = SIRVE   # la gente sólo es motivo en las notas delicadas
        veredictos[id_] = {"motivo": motivo, "detalle": str(c.get("detalle") or "")[:200]}
    for id_ in numeros:   # uno que Claude no contestó se trata como no mirado
        veredictos.setdefault(id_, {"motivo": SIN_MIRAR, "detalle": "Claude no lo contestó"})
    if busquedas is not None:
        busquedas.update(busquedas_de(r, grupos))
    return veredictos


# ------------------------------------------------------------------------------------------- Las fotos de la nota
# Tanda B, etapa 3 (2026-11-20): Claude mira las fotos que trajo la página de la nota (medios_pagina.py) mientras
# guiones.py escribe los guiones, y dice de cada una si tiene que ver y cómo se encuadra en la pantalla vertical.

INSTRUCCIONES_FOTOS = """Miras las fotos que trae la página de una noticia. Van de fondo en un video vertical corto
(9:16, angosto y alto) de esa misma noticia, mientras una voz lee el guion.

Para cada foto contestas:
- "sirve": true sólo si es una foto de verdad que muestra algo de ESTA noticia: la gente, el lugar, el objeto o el
  hecho del que habla. false si:
  - no tiene que ver con esta noticia (la foto de otra nota, de una publicidad o de otro tema);
  - es un logo, un ícono o una marca sola sobre un fondo liso;
  - no es una foto: un dibujo, una ilustración, una caricatura, una imagen hecha en computadora o con inteligencia
    artificial, un gráfico, un cuadro con números, un mapa o una infografía;
  - es una imagen diseñada con letras grandes encima (una placa con texto, una tapa, un afiche, la captura de una
    página, de una red social o de un documento): esas letras no son las de la voz y confunden.
  Ante la duda, false.
- "encuadre": cómo se mueve la foto en la pantalla vertical:
  - "acercamiento": acercamiento lento hacia lo importante. Para fotos con un protagonista claro (una persona, un
    objeto) que entra en una franja vertical angosta.
  - "recorrido": recorrido lento de costado. Para fotos anchas donde lo importante está repartido a lo largo (una
    fila de gente, una calle, un paisaje, un auto visto de costado).
  - "entera": la foto entera, sin recortar, con franjas arriba y abajo. Sólo si recortarla a una franja vertical
    dejaría afuera algo importante que tampoco se puede recorrer.
- "centro": dónde está lo más importante de la foto, de izquierda a derecha: 0 es el borde izquierdo, 0.5 el medio y
  1 el borde derecho.
- "detalle": en pocas palabras y en castellano, qué se ve que te hizo decidir.
Contesta todas las fotos, con su número."""

ESQUEMA_FOTOS = {"type": "object", "properties": {"fotos": {"type": "array", "items": {"type": "object", "properties": {
    "numero": {"type": "integer"}, "sirve": {"type": "boolean"},
    "encuadre": {"type": "string", "enum": ["acercamiento", "recorrido", "entera"]},
    "centro": {"type": "number"}, "detalle": {"type": "string"},
}, "required": ["numero", "sirve", "encuadre", "centro", "detalle"]}}}, "required": ["fotos"]}

LIMITE_FOTOS = 90   # segundos: si la mirada tarda más, el guion sale sin fotos (plan del 18/11)


def pedido_fotos(nota, fotos):
    import fotos_del_guion as FG
    renglones = [f"Titular: {nota.get('titular', '')}",
                 "Comienzo de la nota: " + " ".join(str(nota.get("texto", "")).split()[:250]), "",
                 "Las fotos, con lo que dice la página de cada una:"]
    renglones += [f"Foto {f['n']}: {FG.que_muestra(f, nota)}" for f in fotos]
    return "\n".join(renglones)


def mirar_fotos(nota, fotos, carpeta_base=None, limite=LIMITE_FOTOS):
    """fotos: las de fotos_del_guion.fotos_de_la_nota. Devuelve {n: {"sirve", "encuadre", "centro"}} de las que
    Claude contestó (las que no contestó no están: no se usan). Deja anotado qué vio en cada una.
    Tira Falla o TopeDelDia si no pudo mirar; quien llama sigue sin fotos."""
    import contrato
    import fotos_del_guion as FG
    imagenes, leidas = FG.imagenes_para_pedido(nota, fotos, carpeta_base)
    por_numero = {f["n"]: f for f in leidas}
    if not imagenes:
        return {}
    registro(f"  mirando {len(imagenes)} fotos de la nota")
    r = pedir_json(INSTRUCCIONES_FOTOS, pedido_fotos(nota, [por_numero[n] for n in por_numero]), ESQUEMA_FOTOS,
                   intentos=1, imagenes=imagenes, limite=limite)
    salida = {}
    for c in (r or {}).get("fotos") or []:
        n = c.get("numero")
        if n not in por_numero or n in salida or not isinstance(c.get("sirve"), bool):
            continue
        centro = c.get("centro")
        if (c.get("encuadre") not in contrato.ENCUADRES or not isinstance(centro, (int, float))
                or isinstance(centro, bool)):
            continue
        salida[n] = {"sirve": c["sirve"], "encuadre": c["encuadre"],
                     "centro": round(min(1.0, max(0.0, float(c["centro"]))), 2)}
        registro(f"    foto {n}: {'sirve' if c['sirve'] else 'no sirve'}, {c['encuadre']} "
                 f"({str(c.get('detalle') or '')[:120]})")
    return salida
