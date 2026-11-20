"""Lee una nota de un link (o de un texto pegado) y la devuelve con la forma de revisarNota (estudio/lib/contrato.js).

Uso:  python motor/leer_nota.py <link>
      python motor/leer_nota.py --texto <archivo .txt> [--link <link de donde salió>]

Imprime {"nota": {...}, "leida_con": "jina" | "gemini" | "pagina" | "texto"} y sale con 0.
Si la nota tiene link (también cuando se pega el texto con su link), junta las fotos de la página
(medios_pagina.py) y las suma en "medios"; si no hay o algo falla, la nota sale igual, sin ese campo.
Si falla, {"error": {...}} y sale con 1. Códigos: LINK_INVALIDO, LINK_NO_ABRE, NOTA_SIN_TEXTO, MURO_DE_PAGO,
NOTA_MUY_CORTA, SIN_CONEXION, DESCONOCIDO.

Por dónde lee, en orden (el primero que da texto gana):
  1. Jina Reader (https://r.jina.ai/<link>). Condiciones sin llave, leídas en su página oficial (https://jina.ai/reader/)
     el 2026-11-17: gratis para uso básico, hasta 20 pedidos por minuto, sólo páginas públicas, NO se saltea muros ni
     bloqueos de los sitios, y guarda lo leído 5 minutos (el mismo link en ese rato devuelve lo mismo).
  2. Gemini leyendo el link (herramienta url_context).
  3. Bajar la página y sacar el texto de sus párrafos.
Con lo leído, UN pedido a gemini-3.8-flash elige qué párrafos son la nota (devuelve sus números, así el texto queda
tal cual), y dice titular, medio, fecha, tema y si hay muro de pago. Si Google no contesta, se decide con reglas
simples (las de estudio/lib/sensible.js para el tema). Se ESTIMA: puede dejar un párrafo de más o de menos.
"""
import hashlib
import html
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contrato  # noqa: E402
import medios_pagina  # noqa: E402
from comun import (API, MODELO_TEXTO, Falla, TopeDelDia, bajar, correr, json_de_texto, pedir, pedir_json,  # noqa: E402
                   registro, sin_links, texto_de_respuesta)

ARRANQUE = time.monotonic()
TOPE_PROGRAMA = 225         # el Estudio corta leer la nota a los 240 s (TOPES.nota en lib/fuente/motor.js)
MAX_PARRAFOS = 160          # lo que se le manda a Google para elegir (una portada larga tiene cientos de renglones)
MAX_PALABRAS_ENVIO = 9000
PALABRAS_MURO = 200         # con muro de pago marcado y menos que esto, se pide pegar el texto

# Señales de muro de pago y de páginas que no son la nota (sólo se usan si Google no contesta).
_MURO = ["suscribite", "suscríbete", "suscribirse", "suscriptores", "contenido exclusivo", "para seguir leyendo",
         "ya sos suscriptor", "ya eres suscriptor", "hazte socio", "accedé ilimitado", "accede ilimitado",
         "nota exclusiva para"]
_BLOQUEO = ["just a moment", "attention required", "access denied", "are you a robot", "verify you are human",
            "enable javascript and cookies"]

# Copiado de estudio/lib/sensible.js (PALABRAS y estimarTema) el 2026-11-17: el tema, cuando Google no contesta.
_TEMAS_PALABRAS = {
    "tragedia": ["choque", "chocó", "accidente", "incendio", "inundación", "derrumbe", "víctima", "víctimas", "herido",
                 "heridos", "murió", "muerte", "fallec", "tragedia"],
    "crimen": ["asesin", "homicid", "robo", "robaron", "detenid", "policía", "delito", "crimen", "secuestr", "narco",
               "disparo", "baleado", "fiscal"],
    "politica": ["gobierno", "presidente", "presidenta", "diputad", "senador", "ministr", "elecci", "intendente",
                 "gobernador", "congreso", "partido", "campaña", "votación"],
}


def estimar_tema(texto):
    t = str(texto or "").lower()
    mejor, puntos = "general", 0
    for tema, lista in _TEMAS_PALABRAS.items():
        p = sum(t.count(raiz) for raiz in lista)
        if p > puntos:
            mejor, puntos = tema, p
    return mejor if puntos >= 2 else "general"


# ------------------------------------------------------------------------------------------- Párrafos

def limpiar_markdown(bloque):
    """Un bloque de markdown de Jina a texto: sin imágenes, links (queda su texto), negritas ni viñetas."""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", bloque)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^\s{0,3}(#{1,6}|[*+-]|\d+\.)\s+", "", t, flags=re.M)
    t = re.sub(r"(\*\*|__|`)", "", t)
    t = re.sub(r"(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)", "", t)
    t = sin_links(html.unescape(t))
    return " ".join(t.split())


def parrafos_de_markdown(md):
    """Los bloques que pueden ser parte de la nota: con al menos 6 palabras y que no sean casi todo links."""
    salida = []
    for bloque in re.split(r"\n\s*\n", md or ""):
        links = re.findall(r"\[([^\]]*)\]\([^)]*\)", bloque)
        limpio = limpiar_markdown(bloque)
        palabras = contrato.contar_palabras(limpio)
        if palabras < 6:
            continue
        en_links = sum(contrato.contar_palabras(x) for x in links)
        if en_links > 0.5 * palabras:
            continue
        salida.append(limpio)
    return salida


class _Pagina(HTMLParser):
    """Saca de un HTML el texto de los párrafos (fuera de menús, pies y scripts) y los datos de la cabecera."""
    SALTEAR = {"script", "style", "nav", "footer", "aside", "noscript", "form", "header", "svg", "figure"}
    BLOQUES = {"p", "h1", "h2", "li", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pila, self.parrafos, self.meta, self.actual, self.titulo = [], [], {}, None, ""
        self.en_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            clave = (a.get("property") or a.get("name") or "").lower()
            if clave and a.get("content"):
                self.meta.setdefault(clave, a["content"])
            return
        if tag in ("br", "img", "hr", "input", "link", "source"):
            return
        self.pila.append(tag)
        if tag == "title":
            self.en_title = True
        if tag in self.BLOQUES and not (self.SALTEAR & set(self.pila)):
            self.actual = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.en_title = False
        if tag in self.BLOQUES and self.actual is not None:
            texto = " ".join("".join(self.actual).split())
            if texto:
                self.parrafos.append(texto)
            self.actual = None
        if tag in self.pila:
            while self.pila and self.pila.pop() != tag:
                pass

    def handle_data(self, data):
        if self.en_title:
            self.titulo += data
        if self.actual is not None and not (self.SALTEAR & set(self.pila)):
            self.actual.append(data)


def leer_html(crudo):
    p = _Pagina()
    try:
        p.feed(crudo)
    except Exception:  # un HTML muy roto: se usa lo que se alcanzó a leer
        pass
    parrafos = [x for x in (sin_links(t) for t in p.parrafos) if contrato.contar_palabras(x) >= 6]
    return {
        "titulo": p.meta.get("og:title") or " ".join(p.titulo.split()),
        "medio": p.meta.get("og:site_name"),
        "fecha": p.meta.get("article:published_time") or p.meta.get("date") or p.meta.get("pubdate"),
        "parrafos": parrafos,
    }


# ------------------------------------------------------------------------------------------- Fuentes

def por_jina(link):
    """{titulo, fecha, parrafos} o None si Jina no pudo."""
    codigo, cuerpo, _ = bajar("https://r.jina.ai/" + link, {"Accept": "application/json", "X-Retain-Images": "none",
                                                            "X-Timeout": "25"}, timeout=45)
    if codigo != 200:
        registro(f"  Jina contestó {codigo}")
        return None
    try:
        datos = json.loads(cuerpo.decode("utf-8", errors="replace")).get("data") or {}
    except ValueError:
        return None
    contenido = datos.get("content") or ""
    if any(b in (datos.get("title", "") + contenido[:600]).lower() for b in _BLOQUEO):
        registro("  Jina se encontró con un bloqueo del sitio")
        return None
    parrafos = parrafos_de_markdown(contenido)
    if not parrafos:
        return {"titulo": datos.get("title"), "fecha": datos.get("publishedTime"), "parrafos": [], "vacia": True}
    return {"titulo": datos.get("title"), "fecha": datos.get("publishedTime"), "parrafos": parrafos}


ESQUEMA_ORDEN = {
    "type": "object",
    "properties": {
        "es_nota": {"type": "boolean"},
        "muro_de_pago": {"type": "boolean"},
        "titular": {"type": "string"},
        "medio": {"type": "string"},
        "fecha": {"type": "string"},
        "tema": {"type": "string", "enum": contrato.TEMAS},
        "parrafos": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["es_nota", "muro_de_pago", "titular", "medio", "fecha", "tema", "parrafos"],
}

INSTRUCCIONES_ORDEN = """Ordenas lo que se leyó de una página de un medio de noticias. Te paso el link, el título de la
página y sus párrafos numerados entre corchetes. Contesta en JSON:
- es_nota: true si la página tiene UNA nota periodística principal con texto (no una portada, una lista de notas, una
  página de video sin texto ni un error).
- muro_de_pago: true si el texto de la nota está cortado o tapado por un aviso para suscriptores.
- parrafos: los números de los párrafos que son el cuerpo de la nota principal, en orden. Incluye la bajada o copete
  si está. Deja afuera menús, títulos y resúmenes de otras notas, pies de foto, publicidad, avisos para suscribirse,
  firmas sueltas, fechas sueltas, botones para compartir y comentarios.
- titular: el título de la nota, tal como lo escribió el medio, sin el nombre del medio.
- medio: el nombre del medio como lo conoce la gente (por ejemplo "Infobae" o "El País"), no el dominio.
- fecha: la fecha de publicación como AAAA-MM-DD si aparece; si no, "".
- tema: "politica" si el centro de la nota es la disputa política (gobierno, elecciones, partidos, leyes, funcionarios,
  congreso); "crimen" si es un delito, un caso policial o un juicio penal; "tragedia" si hay muertos, heridos, un
  accidente, un incendio o una catástrofe; "general" para todo lo demás (economía, deportes, cultura, ciencia,
  servicios, clima sin víctimas). Si dudas entre "general" y otro, elige el otro."""


def ordenar(link, titulo, parrafos):
    """Pide a Google que elija los párrafos de la nota. Devuelve el dict del esquema, o None si Google no contesta."""
    numerados, total = [], 0
    for i, p in enumerate(parrafos[:MAX_PARRAFOS], 1):
        total += contrato.contar_palabras(p)
        if total > MAX_PALABRAS_ENVIO:
            break
        numerados.append(f"[{i}] {p}")
    contenido = f"Link: {link or '(texto pegado, sin link)'}\nTítulo de la página: {titulo or '(sin título)'}\n\n" + \
        "\n\n".join(numerados)
    try:
        return pedir_json(INSTRUCCIONES_ORDEN, contenido, ESQUEMA_ORDEN, intentos=2, timeout=90)
    except (Falla, TopeDelDia) as e:
        registro(f"  Google no ordenó la nota ({getattr(e, 'codigo', 'tope del día')}): sigo con reglas simples")
        return None


def por_gemini(link):
    """Gemini lee el link con url_context. {titulo, medio, fecha, tema, es_nota, muro, texto} o None."""
    pedido = (f"Lee esta página: {link}\n\nDevuelve SOLO un objeto JSON, sin nada más, con estas claves: es_nota "
              "(true si hay una nota periodística principal con texto), muro_de_pago (true si el texto está cortado "
              "para suscriptores), titular, medio (el nombre del medio, no el dominio), fecha (AAAA-MM-DD o \"\"), tema "
              "(politica, crimen, tragedia o general), texto (el cuerpo de la nota principal copiado TAL CUAL, "
              "párrafos separados por una línea en blanco, sin menús, sin títulos de otras notas, sin pies de foto ni "
              "publicidad).")
    cuerpo = {"contents": [{"role": "user", "parts": [{"text": pedido}]}], "tools": [{"url_context": {}}]}
    try:
        r = pedir(f"{API}/models/{MODELO_TEXTO}:generateContent", cuerpo, intentos=2, espera=10, timeout=180)
    except (Falla, TopeDelDia) as e:
        registro(f"  Gemini no pudo leer el link ({getattr(e, 'codigo', 'tope del día')})")
        return None
    estados = [m.get("urlRetrievalStatus", "") for m in
               ((r.get("candidates") or [{}])[0].get("urlContextMetadata") or {}).get("urlMetadata", [])]
    if any("PAYWALL" in s for s in estados):
        return {"muro": True, "es_nota": True, "texto": ""}
    if estados and not any("SUCCESS" in s for s in estados):
        registro(f"  Gemini no pudo abrir el link ({', '.join(estados)})")
        return None
    try:
        d = json_de_texto(texto_de_respuesta(r))
    except Falla:
        return None
    return {"titulo": d.get("titular"), "medio": d.get("medio"), "fecha": d.get("fecha"), "tema": d.get("tema"),
            "es_nota": bool(d.get("es_nota")), "muro": bool(d.get("muro_de_pago")), "texto": d.get("texto") or ""}


def por_pagina(link):
    """Baja la página y saca los párrafos. {titulo, medio, fecha, parrafos} o None."""
    codigo, cuerpo, enc = bajar(link, {"Accept": "text/html,application/xhtml+xml",
                                       "Accept-Language": "es-419,es;q=0.9"}, timeout=25, tope_bytes=6_000_000)
    if codigo != 200:
        registro(f"  la página contestó {codigo}")
        return None
    m = re.search(r"charset=([\w-]+)", enc.get("Content-Type", "") or enc.get("content-type", ""))
    crudo = cuerpo.decode(m.group(1) if m else "utf-8", errors="replace")
    if any(b in crudo[:5000].lower() for b in _BLOQUEO):
        return None
    return leer_html(crudo)


# ------------------------------------------------------------------------------------------- La nota

def fecha_corta(valor):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(valor or "").strip())
    return m.group(1) if m else None


def medio_de(link):
    """Sin otro dato, el nombre del medio sale del dominio: infobae.com -> Infobae (se ESTIMA)."""
    host = re.sub(r"^(www|m|amp)\.", "", (urlparse(link).hostname or "").lower())
    return host.split(".")[0].capitalize() if host else None


# Pies de foto con el crédito al final: "Las consultoras ... (REUTERS/Agustin Marcarian)"
_PIE_DE_FOTO = re.compile(r"\([^()]*(/|foto|archivo|captura|gentileza)[^()]*\)\s*$", re.I)


def texto_limpio(parrafos):
    texto = "\n\n".join(" ".join(contrato.limpiar_invisibles(p).split()) for p in parrafos if p and p.strip())
    return texto.strip()


def armar_nota(*, origen, link, titular, medio, fecha, tema, texto):
    texto = texto_limpio(re.split(r"\n\s*\n", texto))
    titular = " ".join(contrato.limpiar_invisibles(titular or "").split())
    if not titular:
        titular = (re.match(r"^.+?[.!?](\s|$)", texto) or [texto[:110]])[0].strip()
    if len(titular) > 120:
        titular = titular[:117].rstrip() + "..."
    tema = tema if tema in contrato.TEMAS else "general"
    base = link if origen == "link" else texto
    return {
        "id": ("nota-" if origen == "link" else "texto-") + hashlib.md5(base.encode("utf-8")).hexdigest()[:10],
        "origen": origen,
        "link": link if link and contrato.link_valido(link) else None,
        "medio": (" ".join(str(medio).split()) or None) if medio else None,
        "fecha": fecha_corta(fecha),
        "titular": titular,
        "tema": tema,
        "sensible": tema in contrato.TEMAS_SENSIBLES,
        "texto": texto,
        "palabras": contrato.contar_palabras(texto),
        "ejemplo": False,
    }


def tiene_muro(texto):
    t = (texto or "").lower()
    return any(m in t for m in _MURO)


def revisar_largo(nota, muro):
    if muro and nota["palabras"] < PALABRAS_MURO:
        raise Falla("MURO_DE_PAGO", f"la nota está para suscriptores ({nota['palabras']} palabras a la vista)")
    if nota["palabras"] < contrato.PALABRAS_MINIMAS_NOTA:
        raise Falla("NOTA_MUY_CORTA", f"la nota tiene {nota['palabras']} palabras")
    return nota


def de_parrafos(link, leida, origen="link"):
    """Con párrafos crudos (de Jina o de la página): Google elige y clasifica; si no, reglas simples."""
    parrafos = leida["parrafos"]
    orden = ordenar(link, leida.get("titulo"), parrafos)
    if orden:
        if not orden.get("es_nota"):
            raise Falla("NOTA_SIN_TEXTO", "la página no tiene una nota con texto")
        elegidos = [parrafos[i - 1] for i in orden.get("parrafos", []) if isinstance(i, int) and 1 <= i <= len(parrafos)]
        nota = armar_nota(origen=origen, link=link, titular=orden.get("titular") or leida.get("titulo"),
                          medio=orden.get("medio") or leida.get("medio") or medio_de(link),
                          fecha=fecha_corta(leida.get("fecha")) or orden.get("fecha"), tema=orden.get("tema"),
                          texto="\n\n".join(elegidos))
        return revisar_largo(nota, orden.get("muro_de_pago") or (not elegidos and tiene_muro(" ".join(parrafos))))
    # Sin Google: los párrafos de 12 palabras o más
    elegidos = [p for p in parrafos if contrato.contar_palabras(p) >= 12 and not _PIE_DE_FOTO.search(p)]
    texto = "\n\n".join(elegidos)
    nota = armar_nota(origen=origen, link=link, titular=leida.get("titulo"), medio=leida.get("medio") or medio_de(link),
                      fecha=leida.get("fecha"), tema=estimar_tema(f"{leida.get('titulo')} {texto}"), texto=texto)
    return revisar_largo(nota, tiene_muro(" ".join(parrafos)))


def nota_de_link(link):
    link = str(link or "").strip()
    if not contrato.link_valido(link):
        raise Falla("LINK_INVALIDO")
    sin_conexion = 0
    intentos = []
    # 1. Jina
    try:
        leida = por_jina(link)
    except Falla as e:
        sin_conexion += e.codigo == "SIN_CONEXION"
        leida = None
    if leida and leida["parrafos"]:
        registro(f"leída con Jina: {len(leida['parrafos'])} párrafos")
        return de_parrafos(link, leida), "jina"
    intentos.append("jina")
    # 2. Gemini con el link
    g = por_gemini(link)
    if g and g.get("muro") and contrato.contar_palabras(g.get("texto")) < PALABRAS_MURO:
        raise Falla("MURO_DE_PAGO", "Google ve un muro de pago")
    if g and g.get("es_nota") and contrato.contar_palabras(g.get("texto")) >= contrato.PALABRAS_MINIMAS_NOTA:
        registro("leída con Gemini")
        nota = armar_nota(origen="link", link=link, titular=g.get("titulo"), medio=g.get("medio") or medio_de(link),
                          fecha=g.get("fecha"), tema=g.get("tema"), texto=g["texto"])
        return revisar_largo(nota, g.get("muro")), "gemini"
    intentos.append("gemini")
    # 3. La página directo
    try:
        pagina = por_pagina(link)
    except Falla as e:
        sin_conexion += e.codigo == "SIN_CONEXION"
        pagina = None
    if pagina and pagina["parrafos"]:
        registro(f"leída de la página: {len(pagina['parrafos'])} párrafos")
        return de_parrafos(link, pagina), "pagina"
    if sin_conexion >= 2:
        raise Falla("SIN_CONEXION", "no hay conexión con internet")
    if (leida and leida.get("vacia")) or (g and not g.get("es_nota")):
        raise Falla("NOTA_SIN_TEXTO", "la página abre pero no tiene una nota con texto")
    raise Falla("LINK_NO_ABRE", "ninguna de las tres formas pudo abrir la página")


def nota_de_texto(texto, link=None):
    """Como notaDeTexto de lib/fuente/ejemplos.js: la primera línea es el título si hay más de una."""
    renglones = [r.strip() for r in contrato.limpiar_invisibles(texto).splitlines() if r.strip()]
    if not renglones:
        raise Falla("NOTA_MUY_CORTA", "el texto está vacío")
    titular = renglones[0] if len(renglones) > 1 else None
    cuerpo = "\n\n".join(renglones[1:] if len(renglones) > 1 else renglones)
    if contrato.contar_palabras(cuerpo) < contrato.PALABRAS_MINIMAS_NOTA:
        raise Falla("NOTA_MUY_CORTA", f"el texto tiene {contrato.contar_palabras(cuerpo)} palabras")
    orden = ordenar(link, titular, re.split(r"\n\s*\n", cuerpo))
    tema = (orden or {}).get("tema") or estimar_tema(f"{titular or ''} {cuerpo}")
    medio = medio_de(link) if link and contrato.link_valido(link) else None
    if medio and orden and orden.get("medio"):
        medio = orden["medio"]
    nota = armar_nota(origen="texto", link=link, titular=titular or (orden or {}).get("titular"), medio=medio,
                      fecha=(orden or {}).get("fecha"), tema=tema, texto=cuerpo)
    return nota


def principal():
    args = sys.argv[1:]
    if "--texto" in args:
        i = args.index("--texto")
        if i + 1 >= len(args):
            raise Falla("DESCONOCIDO", "falta el archivo del texto")
        link = args[args.index("--link") + 1] if "--link" in args and args.index("--link") + 1 < len(args) else None
        try:
            texto = Path(args[i + 1]).read_text(encoding="utf-8-sig")
        except OSError:
            raise Falla("DESCONOCIDO", "no se pudo leer el archivo del texto")
        return {"nota": con_fotos(nota_de_texto(texto, link)), "leida_con": "texto"}
    if len(args) != 1:
        raise Falla("DESCONOCIDO", "uso: leer_nota.py <link> | --texto <archivo> [--link <link>]")
    nota, como = nota_de_link(args[0])
    return {"nota": con_fotos(nota), "leida_con": como}


def con_fotos(nota):
    """Suma las fotos de la página (medios_pagina.py) si la nota tiene link. Con su propio tope (unos 40 s) y sin
    pasar el del programa; si no hay fotos o algo falla, la nota queda como estaba, sin "medios"."""
    if not nota.get("link"):
        return nota
    segundos = min(medios_pagina.TOPE_SEGUNDOS, TOPE_PROGRAMA - (time.monotonic() - ARRANQUE))
    try:
        medios = medios_pagina.juntar(nota, segundos=segundos)
    except Exception as e:   # noqa: BLE001  (las fotos nunca frenan la nota)
        registro(f"  fotos: no se pudieron juntar ({type(e).__name__})")
        medios = []
    if medios:
        nota["medios"] = medios
    return nota


if __name__ == "__main__":
    sys.exit(correr(principal))
