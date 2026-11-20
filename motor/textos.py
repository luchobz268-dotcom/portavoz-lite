"""Los textos para publicar: título, descripción, hashtags, etiquetas de YouTube y un texto por red.

Lo usan armar.py (al final del armado) y otro_texto.py ("Pedir otro"). UN pedido a gemini-3.8-flash trae tres
variantes de cada texto; se guardan en textos-variantes.json, en la carpeta del trabajo, y resultado.json lleva la
primera. Los topes de cada red (TOPES_REDES de contrato.js) se MIDEN y se corrigen acá: nunca sale un texto que una
red no acepta. Que el texto esté bien escrito se ESTIMA (lo escribe Google).
Lo que la nota dice en futuro y una variante cuenta como hecho ("funcionará" en la nota, "funciona" en el texto) se
MIDE con los verbos regulares (revisar_guion.py): esa variante va última, y si las tres lo tienen, Claude Opus arregla
la primera con un pedido más (sólo el verbo; si no sale, queda como estaba).
"""
import json
import re
import unicodedata
from pathlib import Path

import contrato
import revisar_guion as RG
from comun import ESTUDIO, Falla, TopeDelDia, escribir_json, leer_json, pedir_json, registro, sin_emojis, sin_links, sin_rayas

TEXTOS_VIDEO = ESTUDIO / "datos" / "ejemplos" / "textos.json"
CAMPOS_RED = ["tiktok", "instagram", "youtube", "facebook", "x", "linkedin"]

INSTRUCCIONES = """Escribes los textos para publicar un video corto de noticias en redes sociales. Castellano neutro
para toda Latinoamérica, tratando de tú, sin voseo. Sólo hechos que están en la nota o en el guion del video: no
inventes datos, cifras ni opiniones. Sin rayas largas ni medias, sin links, sin palabras de propaganda
("increíble", "impactante", "no te lo pierdas").

Cuidado con los hechos (reglas que no se rompen):
- Usa las mismas palabras de la nota para el estado de las cosas. Si la nota dice "secuestrados", no escribas
  "recuperados"; "detenido" o "acusado" no es "condenado" ni "culpable"; "previsto" no es "hecho".
- Lo que la nota dice en futuro o como posible, sigue en futuro o como posible ("está previsto", "podría",
  "funcionará"). Si la nota dice "puede reclamar", no escribas "hay penalización" ni "cobra": escribe "puede
  reclamar". Esto vale también para el título.
- Los cálculos, estimaciones y comparaciones que hace el medio van atribuidos ("según Infobae, ..."), nunca como
  dato propio.
- Sin opinión ni comentario de quien escribe: nada de "y encima", "central para", "clave para", "por fin",
  "lamentablemente", "por suerte" ni adjetivos que juzgan. Tampoco interpretes qué significa la noticia ("esto
  muestra un modelo nuevo", "plantea cómo cambia..."): si la nota no lo dice, no va. Vale también para linkedin.
- Siglas: en cada texto, la primera vez que aparece una sigla va escrita completa o explicada al lado (por ejemplo
  "la DDI, la oficina de investigaciones de la policía"). Si no hace falta la sigla, mejor no usarla.

Escribe 3 variantes distintas de cada texto (cada una con otro ángulo u otras palabras). Cada variante tiene:
- titulo: para YouTube, de 40 a 90 letras, claro y concreto, sin hashtags ni emojis. Si separa dos partes, con
  dos puntos (por ejemplo "Lomas de Zamora: detienen a un ex gendarme por un robo"), nunca con barra ni raya.
- descripcion: 2 o 3 oraciones que resumen la noticia, sin hashtags ni emojis.
- hashtags: de 3 a 6, en minúsculas, sin tildes ni espacios, empezando con #, sobre el tema concreto (no sólo
  #noticias).
- etiquetasYoutube: de 5 a 10 frases cortas de búsqueda, sin comas y sin #.
- tiktok: 1 o 2 oraciones cortas que enganchan, sin hashtags (se agregan después).
- instagram: 2 o 3 párrafos muy cortos separados por una línea en blanco, sin hashtags.
- youtube: 2 o 3 oraciones para la descripción del video, sin hashtags.
- facebook: 2 o 3 oraciones, tono de conversación; puede cerrar con una pregunta.
- x: una o dos oraciones, de 200 letras como mucho, sin hashtags.
- linkedin: 2 o 3 oraciones, tono más formal, sobre por qué importa la noticia.
EMOJIS: si el pedido dice que la nota es sensible, ninguno en ningún texto. Si no, como mucho uno en tiktok, uno en
instagram y uno en x; en el resto, ninguno."""

_TEXTO = {"type": "string"}
_LISTA = {"type": "array", "items": {"type": "string"}}
ESQUEMA = {"type": "object", "properties": {"variantes": {"type": "array", "items": {"type": "object", "properties": {
    "titulo": _TEXTO, "descripcion": _TEXTO, "hashtags": _LISTA, "etiquetasYoutube": _LISTA,
    **{red: _TEXTO for red in CAMPOS_RED},
}, "required": ["titulo", "descripcion", "hashtags", "etiquetasYoutube", *CAMPOS_RED]}}}, "required": ["variantes"]}


def textos_video():
    """Los textos fijos que se imprimen en el video y la fuente (estudio/datos/ejemplos/textos.json, clave video)."""
    try:
        return leer_json(TEXTOS_VIDEO)["video"]
    except (OSError, ValueError, KeyError):
        raise Falla("FALLO_ARMADO", "faltan los textos del video en estudio/datos/ejemplos/textos.json")


def linea_fuente(nota):
    medio = (nota or {}).get("medio")
    return textos_video()["fuente"].replace("{medio}", medio) if medio else ""


# ------------------------------------------------------------------------------------------- Topes

def _limpio(texto, sensible, emojis=True):
    t = contrato.limpiar_invisibles(texto)
    t = sin_rayas(sin_links(t))
    if sensible or not emojis:
        t = sin_emojis(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def cortar(texto, tope, medir=contrato.largo_js):
    """Corta en la última oración (o palabra) que entra en el tope."""
    if medir(texto) <= tope:
        return texto
    oraciones = re.split(r"(?<=[.!?])\s+", texto)
    while len(oraciones) > 1 and medir(" ".join(oraciones)) > tope:
        oraciones.pop()
    t = " ".join(oraciones)
    while medir(t) > tope and " " in t:
        t = t.rsplit(" ", 1)[0].rstrip(",;:")
    while medir(t) > tope:
        t = t[:-1]
    return t


def hashtag(h):
    h = unicodedata.normalize("NFD", str(h).strip().lower())
    h = "".join(c for c in h if unicodedata.category(c) != "Mn")
    h = re.sub(r"[^\w]", "", h.replace("#", ""))
    return "#" + h if h else None


def ajustar_hashtags(lista):
    salida = []
    for h in lista or []:
        h = hashtag(h)
        if h and h not in salida and len(h) <= 40:
            salida.append(h)
    salida = salida[: contrato.TOPES_REDES["instagram"]["hashtags"]]
    return salida or ["#noticias"]


def ajustar_etiquetas(lista):
    salida = []
    for e in lista or []:
        e = " ".join(sin_emojis(str(e)).replace(",", " ").replace("#", " ").split())
        if e and e.lower() not in [x.lower() for x in salida]:
            salida.append(e)
    while salida and contrato.largo_etiquetas(salida) > contrato.TOPE_ETIQUETAS_YOUTUBE:
        salida.pop()
    return salida or ["noticias"]


def con_hashtags(texto, hashtags, red):
    """El texto de una red con sus hashtags al final, sin pasar el tope (si no entran todos, se sacan del final)."""
    tope = contrato.TOPES_REDES[red].get("texto")
    tope_h = contrato.TOPES_REDES[red].get("hashtags")
    hs = list(hashtags)[:tope_h] if tope_h else list(hashtags)
    if red == "x":
        hs = hs[:3]
    separador = "\n\n" if red in ("instagram", "youtube", "linkedin") else " "
    while True:
        completo = texto + (separador + " ".join(hs) if hs else "")
        if not tope or contrato.largo_para(red, completo) <= tope or not hs:
            break
        hs.pop()
    if tope and contrato.largo_para(red, completo) > tope:
        completo = cortar(texto, tope, lambda t: contrato.largo_para(red, t))
    return completo


# ------------------------------------------------------------------------------------------- Lo que se cuenta

# Palabras con las que quien escribe opina o comenta (18/11: "y encima", "central para la causa"). Se cuentan para
# ordenar las variantes; no se borran del texto, porque sacarlas a ciegas puede romper la oración.
OPINION = ["y encima", "central para", "clave para", "por fin", "lamentablemente", "afortunadamente", "por suerte",
           "sin duda", "escandalos", "vergonzos", "insólit", "indignante", "polémic"]
_SIGLA = re.compile(r"(?<![\w(])([A-ZÁÉÍÓÚÑ]{2,6})(?![\w)])")
_EXPLICADA = re.compile(r"\s*[,(:]")


def siglas_sin_explicar(texto):
    """Siglas cuya primera aparición no va explicada al lado: ni seguida de coma, dos puntos o paréntesis, ni entre
    paréntesis después del nombre completo. Es una cuenta aproximada: sirve para ordenar, no para prohibir."""
    vistas, malas = set(), []
    for m in _SIGLA.finditer(texto or ""):
        sigla = m.group(1)
        if sigla in vistas:
            continue
        vistas.add(sigla)
        if not _EXPLICADA.match(texto, m.end()):
            malas.append(sigla)
    return malas


def _textos_de(variante):
    return [variante.get("titulo", ""), variante.get("descripcion", ""), *(variante.get("redes") or {}).values()]


def verbos_cambiados(variante, nota):
    """[(presente, futuro)] de lo que la variante cuenta como hecho y la nota dice que va a pasar (C5)."""
    if not nota:
        return []
    return RG.verbos_cambiados(" ".join(t or "" for t in _textos_de(variante)), nota.get("texto", ""))


def problemas(variante, nota=None):
    """Cuántos problemas que se pueden contar tiene una variante: siglas sin explicar y palabras de opinión, en cada
    texto por separado (cada uno se publica solo). Con la nota, también cada verbo que cuenta como hecho algo que la
    nota dice en futuro."""
    total = 0
    for t in _textos_de(variante):
        bajo = (t or "").lower()
        total += len(siglas_sin_explicar(t)) + sum(bajo.count(p) for p in OPINION)
    return total + len(verbos_cambiados(variante, nota))


def titulo_con_dos_puntos(titulo):
    """El título separa sus partes con dos puntos (Lucio, 2026-11-18): la primera barra o raya pasa a ser ':'."""
    return re.sub(r"\s*[|—–]\s*", ": ", titulo or "", count=1).replace("|", ",")


def armar_variante(v, nota, sensible):
    """Una variante de Google -> los textos con la forma de resultado.textos, dentro de los topes."""
    fuente = linea_fuente(nota)
    hashtags = ajustar_hashtags(v.get("hashtags"))
    titulo = _limpio(titulo_con_dos_puntos(v.get("titulo", "")), sensible, emojis=False)
    titulo = titulo.replace("#", "").replace("\n", " ")
    titulo = cortar(titulo or nota.get("titular", ""), contrato.TOPES_REDES["youtube"]["titulo"])
    descripcion = _limpio(v.get("descripcion", ""), sensible, emojis=False).replace("#", "")
    descripcion = (descripcion + ("\n\n" + fuente if fuente else "")).strip()
    descripcion = cortar(descripcion, contrato.TOPES_REDES["youtube"]["texto"])
    redes = {}
    for red in CAMPOS_RED:
        base = _limpio(v.get(red, ""), sensible, emojis=red in ("tiktok", "instagram", "x"))
        base = re.sub(r"(?<!\w)#\w+", "", base).strip()
        if not base:
            base = nota.get("titular", "")
        if red == "youtube" and fuente:
            base = base + "\n\n" + fuente
        redes[red] = base if red == "facebook" else con_hashtags(base, hashtags, red)
    return {"titulo": titulo, "descripcion": descripcion, "hashtags": hashtags,
            "etiquetasYoutube": ajustar_etiquetas(v.get("etiquetasYoutube")), "redes": redes}


# ------------------------------------------------------------------------------------------- Pedido

# El arreglo del verbo tiene un tope de 120 s; con menos de esto por delante no se pide (el Estudio corta "Pedir otro"
# a los 240 s y, si se pasa, se pierde todo, también lo que ya estaba bien).
MINIMO_PARA_ARREGLO_VERBO = 140


def pedir_variantes(nota, guion_texto, quedan=None):
    """Las tres variantes de los textos para publicar. `quedan()` (opcional) = segundos que faltan para que el Estudio
    corte el paso ("Pedir otro"): si quedan menos de MINIMO_PARA_ARREGLO_VERBO, el arreglo del verbo no se pide. Sin
    reloj (al armar el video, que tiene tiempo de sobra), como siempre."""
    sensible = bool(nota.get("sensible"))
    contenido = "\n".join([
        "La nota es SENSIBLE (" + nota.get("tema", "") + "): ningún emoji y tono sobrio." if sensible
        else "La nota no es sensible.",
        f"Titular: {nota.get('titular', '')}", f"Medio: {nota.get('medio') or 'sin dato'}", "",
        "Guion del video:", guion_texto, "", "Nota:", " ".join(str(nota.get("texto", "")).split()[:1500])])
    try:
        r = pedir_json(INSTRUCCIONES, contenido, ESQUEMA, temperatura=0.8)
    except TopeDelDia:
        raise Falla("DESCONOCIDO", "no se pueden escribir más textos por ahora (tope del día)")
    crudas = [v for v in (r.get("variantes") or [])[:3] if isinstance(v, dict)]
    variantes = [armar_variante(v, nota, sensible) for v in crudas]
    if not variantes:
        raise Falla("DESCONOCIDO", "no se pudieron escribir los textos")
    # va primero la que tiene menos problemas que se pueden contar, y última la que cambia un verbo de la nota;
    # ninguna se tira (la persona elige las otras)
    cuentas = [problemas(v, nota) for v in variantes]
    verbos = [verbos_cambiados(v, nota) for v in variantes]
    if any(cuentas):
        registro(f"  problemas contados por variante: {cuentas}")
    orden = sorted(range(len(variantes)), key=lambda i: (bool(verbos[i]), cuentas[i]))
    variantes = [variantes[i] for i in orden]
    if all(verbos[i] for i in orden):
        primera = orden[0]
        hay = None if quedan is None else quedan()
        if hay is not None and hay < MINIMO_PARA_ARREGLO_VERBO:
            registro(f"  no queda tiempo para arreglar el verbo ({int(hay)} s): van como salieron")
        else:
            limite = 120 if hay is None else min(120, int(hay) - 20)
            arreglada = arreglar_verbo(nota, sensible, crudas[primera], verbos[primera], limite)
            if arreglada is not None:
                variantes[0] = arreglada
    return variantes


ARREGLO_VERBO = """

Ahora no escribes de cero: arreglas UNA variante que ya existe. Cambia SÓLO los verbos que te marco, para que digan lo
mismo que la nota (si la nota lo dice en futuro, va en futuro), y deja el resto de cada texto palabra por palabra.
Devuelve una sola variante."""


def arreglar_verbo(nota, sensible, cruda, verbos, limite=120):
    """Las tres variantes cuentan como hecho algo que va a pasar: UN pedido a Claude Opus arregla la primera, sólo el
    verbo. Devuelve la variante arreglada, o None si no salió (y queda como estaba)."""
    marcados = "; ".join(f'"{presente}" tiene que decir "{futuro}" como la nota' for presente, futuro in verbos)
    contenido = "\n".join([
        "La nota es SENSIBLE: ningún emoji." if sensible else "La nota no es sensible.",
        f"Titular: {nota.get('titular', '')}", "", "Verbos a arreglar: " + marcados, "",
        "Variante:", json.dumps(cruda, ensure_ascii=False), "", "Nota:",
        " ".join(str(nota.get("texto", "")).split()[:1500])])
    try:
        r = pedir_json(INSTRUCCIONES + ARREGLO_VERBO, contenido, ESQUEMA, temperatura=0.3, limite=limite)
        nueva = next((v for v in (r.get("variantes") or []) if isinstance(v, dict)), None)
        if nueva is None:
            raise Falla("DESCONOCIDO", "no vino la variante")
        armada = armar_variante(nueva, nota, sensible)
    except (Falla, TopeDelDia) as e:
        registro(f"  el arreglo del verbo no salió ({getattr(e, 'detalle', '') or e}): queda como estaba")
        return None
    except Exception as e:   # noqa: BLE001  (el arreglo nunca frena los textos)
        registro(f"  el arreglo del verbo no salió ({type(e).__name__}): queda como estaba")
        return None
    if verbos_cambiados(armada, nota):
        registro("  el arreglo del verbo no cambió el verbo: queda como estaba")
        return None
    registro(f"  verbo arreglado en la primera variante: {marcados}")
    return armada


def por_campo(variantes):
    """[3 variantes enteras] -> {titulo: [..], ..., redes: {red: [..]}} (la forma de las variantes de ejemplo)."""
    salida = {c: [v[c] for v in variantes] for c in ["titulo", "descripcion", "hashtags", "etiquetasYoutube"]}
    salida["redes"] = {red: [v["redes"][red] for v in variantes] for red in CAMPOS_RED}
    return salida


def resultado_de(trabajo_id, variantes_campo, elegidos=None):
    elegidos = elegidos or {}
    textos = {c: variantes_campo[c][elegidos.get(c, 0)] for c in ["titulo", "descripcion", "hashtags",
                                                                  "etiquetasYoutube"]}
    textos["redes"] = {red: variantes_campo["redes"][red][elegidos.get(f"redes.{red}", 0)] for red in CAMPOS_RED}
    return {"video": f"/api/trabajos/{trabajo_id}/video", "portada": f"/api/trabajos/{trabajo_id}/portada",
            "textos": textos}


def generar(carpeta, trabajo):
    """Pide los textos, guarda textos-variantes.json y resultado.json. Devuelve el resultado."""
    carpeta = Path(carpeta)
    variantes = pedir_variantes(trabajo["nota"], trabajo["guion"]["texto"])
    campo = por_campo(variantes)
    escribir_json(carpeta / "textos-variantes.json", {"variantes": campo, "pedidos": 1})
    resultado = resultado_de(trabajo["id"], campo)
    escribir_json(carpeta / "resultado.json", resultado)
    registro(f"  textos listos: {len(variantes)} variantes de cada uno")
    return resultado
