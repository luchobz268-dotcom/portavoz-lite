"""Las fotos de la página de una nota (Fase 5, Tanda B, etapa 1; plan `dale-valiant-planet.md`).

Baja la página por su cuenta y junta las fotos: la de redes (og:image), las del cuerpo de la nota con su pie, y las que
la página marca para los buscadores (JSON-LD). Tira lo que no sirve y guarda hasta 8 en
motor/cache/medios/<nota-id>/: NN.jpg en su tamaño real (hasta 2560 de lado largo) y NN-chica.jpg (1024 de lado largo)
para que la mire Claude. Si algo falla, devuelve [] y la nota sale igual, sin fotos: nunca frena la lectura.

Qué tira y cómo (cajón "se mide", salvo donde dice "se estima"):
- logos, íconos, publicidades y contadores de visitas: por la dirección y el formato (svg, gif);
- las de otras notas (se estima): las que están adentro de un link a otra página o en zonas con nombres de
  relacionadas, más leídas, publicidad, autor, menús;
- las ilustrativas o hechas con IA (decidido por el asistente el 2026-11-20, de la regla de Lucio de nunca usar
  imágenes hechas por IA): si el pie, la descripción o el crédito lo dicen;
- las de menos de 600 de ancho y las tiras muy angostas (banners), después de medirlas;
- las repetidas: por la dirección (la misma foto en otro tamaño) y por cómo se ven (una huella de 16x16 grises).

El crédito se lee de la página (se estima): un renglón marcado como crédito dentro del pie, "Foto: X", "(X)" o "| X"
al final del pie, "Fuente de la imagen, X", o el creditText de los buscadores. Si no hay, queda vacío: nunca se inventa.

Uso suelto (gasta internet, no gasta Claude):  python motor/medios_pagina.py <link>   -> imprime lo que juntó.
"""
import html as _html
import json
import re
import shutil
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import comun
import contrato
from comun import Falla, registro

CARPETA = comun.CACHE / "medios"
MAXIMO = contrato.MAXIMO_FOTOS   # fotos que se guardan por nota (decidido por el asistente, plan del 18/11)
ANCHO_MINIMO = 600          # más chicas se tiran (plan del 18/11)
LADO_GRANDE = 2560          # la foto para el video: su tamaño real, con este tope de lado largo
LADO_CHICO = 1024           # la copia que mira Claude
ESTIRADA = 3.5              # más angosta que 1 a 3,5 (de costado o parada) es una tira de publicidad, no una foto
TOPE_SEGUNDOS = 40          # todo junto: bajar la página, las fotos y convertirlas
A_BAJAR = 14                # candidatas que se intentan bajar como mucho
TOPE_BYTES_FOTO = 15_000_000
TOPE_BYTES_PAGINA = 6_000_000
PARECIDO = 12               # diferencia media de la huella (0 a 255) por debajo de la cual dos fotos son la misma

_VACIOS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_TAGS_MALOS = {"aside", "nav", "footer"}
# nombres de clase o id de zonas que no son la nota (relacionadas, publicidad, autor, menús, redes)
_ZONA_MALA = re.compile(
    r"related|relacionad|recomend|recommend|podcast|pv-carousel|video-carousel|mas-?leid|most-?read|trending|te-puede|mira-?tambien|tambien-te|feed-|promo|teaser|"
    r"outbrain|taboola|sidebar|newsletter|banner|publicidad|(^|[\s_-])ads?([\s_-]|$)|dfp|sponsor|share|social|"
    r"author|autor|byline|avatar|logo|comment|icon", re.I)
_DIRECCION_MALA = re.compile(
    r"logo|icon|sprite|avatar|placeholder|blank|pixel|spacer|scorecardresearch|facebook\.com/tr|doubleclick|"
    r"googlesyndication|/ads?/|tracking|xiti|arc-authors|/autor|/author|emoji|badge|\.svg(\?|$)|\.gif(\?|$)", re.I)
_CLASE_CREDITO = re.compile(r"credit|credito|crédito|copyright|autor|author|fuente|source|firma", re.I)
_IMAGEN_EN_LINK = re.compile(r"\.(jpe?g|png|webp|avif|gif)(\?|$)", re.I)
# "ilustrativa", "ilustración", "generada con IA" y parecidos: no entran (nunca imágenes hechas por IA)
_ILUSTRATIVA = re.compile(
    r"ilustrativ|ilustraci[oó]n|generad[ao]s? (con|por) (la )?(ia|inteligencia artificial)|"
    r"(cread|hech)[ao]s? con (la )?(ia|inteligencia artificial)|\(ia\)|imagen (de )?ia\b|midjourney|dall-?e\b|"
    r"stable diffusion|ai[- ]generated", re.I)
_TIPOS_NOTA = {"NewsArticle", "Article", "ReportageNewsArticle", "AnalysisNewsArticle", "BlogPosting",
               "LiveBlogPosting", "OpinionNewsArticle", "BackgroundNewsArticle"}


def _nombres(a):
    """Lo que dice qué es una zona: su clase, su id y las marcas que algunos diarios usan (BBC: data-e2e)."""
    return " ".join(a.get(k, "") for k in ("class", "id", "data-e2e", "data-testid", "data-component",
                                             "aria-labelledby")).strip()


def _limpio(texto, largo=300):
    t = " ".join(_html.unescape(str(texto or "")).split())
    return t[:largo].rstrip()


def _mejor_de_srcset(srcset, base):
    """(dirección, ancho) de la más grande de un srcset ("a.jpg 400w, b.jpg 1200w"). Sin "w", el ancho sale de la
    dirección (Infobae: ...&width=992). Si no se sabe ningún ancho, la primera con 0."""
    mejores = []
    for u, numero, letra in re.findall(r"([^\s,]\S*)(?:\s+(\d+)(?:\.\d+)?([wx]))?", _html.unescape(srcset or "")):
        u = u.rstrip(",")
        mejores.append((int(numero) if letra == "w" else ancho_en_url(u), len(mejores), u))
    if not mejores:
        return None, 0
    ancho, _, u = max(mejores, key=lambda m: (m[0], -m[1]))
    return urljoin(base, u), ancho


def _direccion_real(url, base):
    """Las imágenes de Next.js (/_next/image?url=...&w=980) apuntan a la original: se usa esa."""
    if not url:
        return None
    url = urljoin(base, _html.unescape(url.strip()))
    p = urlparse(url)
    if "/_next/image" in p.path:
        original = parse_qs(p.query).get("url")
        if original:
            url = urljoin(base, unquote(original[0]))
    return url if urlparse(url).scheme in ("http", "https") else None


# ------------------------------------------------------------------------------------------- Leer la página

class _Fotos(HTMLParser):
    """Recorre la página y anota cada <img> (y los <source> de su <picture>) con dónde está y el pie de su figura."""

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.ruta_pagina = urlparse(base).path.rstrip("/")
        self.pila = []          # [(tag, clases+id, href)]
        self.meta = {}
        self.ld = []
        self.en_ld = None
        self.imagenes = []      # en el orden de la página
        self.figuras = []       # figuras abiertas: {"imagenes": [...], "pie": [(texto, es_credito)], "otros": [...]}
        self.fuentes = []       # srcset de los <source> del <picture> abierto

    # --- dónde está
    def _zona_mala(self, extra=""):
        en_articulo = any(t == "article" for t, _, _ in self.pila)
        for tag, nombres, href in self.pila:
            if tag in _TAGS_MALOS or (tag == "header" and not en_articulo):
                return True
            if nombres and _ZONA_MALA.search(nombres):
                return True
        return bool(extra and _ZONA_MALA.search(extra))

    def _en_link_a_otra(self):
        for tag, _, href in self.pila:
            if tag != "a" or not href or href.startswith(("#", "javascript:")):
                continue
            destino = urljoin(self.base, href)
            if _IMAGEN_EN_LINK.search(destino):
                continue    # un link a la misma foto en grande (lupa): es de la nota
            if urlparse(destino).path.rstrip("/") != self.ruta_pagina:
                return True
        return False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            clave = (a.get("property") or a.get("name") or "").lower()
            if clave and a.get("content") and clave not in self.meta:
                self.meta[clave] = a["content"]
            return
        if tag == "script":
            self.en_ld = [] if "ld+json" in a.get("type", "").lower() else None
        if tag == "source":
            if any(t == "picture" for t, _, _ in self.pila):
                self.fuentes.append(a.get("srcset") or a.get("data-srcset") or "")
            return
        if tag == "img":
            self._imagen(a)
            return
        if tag in _VACIOS:
            return
        self.pila.append((tag, _nombres(a), a.get("href")))
        if tag == "picture":
            self.fuentes = []
        if tag == "figure":
            self.figuras.append({"imagenes": [], "pie": [], "otros": []})
        elif tag == "figcaption" and not any(t == "figure" for t, _, _ in self.pila[:-1]):
            # un pie sin <figure> (Infobae): es de la última foto, si todavía no tiene pie
            ultima = [self.imagenes[-1]] if self.imagenes and not self.imagenes[-1]["pie"] else []
            self.figuras.append({"imagenes": ultima, "pie": [], "otros": [], "suelta": True})

    def _imagen(self, a):
        srcset = a.get("srcset") or a.get("data-srcset") or ""
        candidatas = [_mejor_de_srcset(s, self.base) for s in [srcset, *self.fuentes] if s]
        candidatas = [c for c in candidatas if c[0]]
        directa = a.get("data-src") or a.get("data-original") or a.get("data-lazy-src") or a.get("src")
        if directa and not directa.startswith("data:"):
            candidatas.append((urljoin(self.base, _html.unescape(directa.strip())), ancho_en_url(directa)))
        # la más grande; una sin ancho conocido cuenta como 600 (Perfil: srcset de miniaturas y src de 900)
        url, ancho_dicho = (max(candidatas, key=lambda c: c[1] or 600) if candidatas else (None, 0))
        mostrada = urljoin(self.base, _html.unescape(url.strip())) if url else None
        url = _direccion_real(url, self.base)
        if not url:
            return
        foto = {"url": url, "alt": _limpio(a.get("alt")), "pie": "", "credito": "", "origen": "cuerpo",
                "orden": len(self.imagenes) + 1, "ancho_dicho": ancho_dicho, "descartada": None,
                # si la original no baja, la que muestra la página (La Voz: la de Next.js)
                "otras": [mostrada] if mostrada and mostrada != url else []}
        nombres = _nombres(a)
        if _DIRECCION_MALA.search(url):
            foto["descartada"] = "logo, ícono o publicidad"
        elif self._en_link_a_otra():
            foto["descartada"] = "de otra nota (está adentro de un link)"
        elif self._zona_mala(nombres):
            foto["descartada"] = "fuera de la nota (relacionadas, publicidad, autor o menú)"
        self.imagenes.append(foto)
        if self.figuras:
            self.figuras[-1]["imagenes"].append(foto)

    def handle_endtag(self, tag):
        if tag == "script" and self.en_ld is not None:
            self.ld.append("".join(self.en_ld))
            self.en_ld = None
        if tag == "picture":
            self.fuentes = []
        if self.figuras and ((tag == "figure" and not self.figuras[-1].get("suelta"))
                             or (tag == "figcaption" and self.figuras[-1].get("suelta"))):
            _pie_de_figura(self.figuras.pop())
        if tag in (t for t, _, _ in self.pila):
            while self.pila and self.pila.pop()[0] != tag:
                pass

    def handle_data(self, data):
        if self.en_ld is not None:
            self.en_ld.append(data)
            return
        if not self.figuras or not data.strip():
            return
        figura = self.figuras[-1]
        tags = [t for t, _, _ in self.pila]
        if "figcaption" in tags:
            desde = len(tags) - 1 - tags[::-1].index("figcaption")
            es_credito = any(_CLASE_CREDITO.search(n or "") for _, n, _ in self.pila[desde + 1:])
            figura["pie"].append((data, es_credito))
        elif not any(t in ("script", "style", "button", "noscript") for t in tags):
            figura["otros"].append(data)


_CREDITO_EN_TEXTO = [
    re.compile(r"\((?:fotos?|imagen|im[aá]genes|cr[eé]ditos?|fuente)\s*:\s*([^()]{2,80})\)\s*\.?\s*$", re.I),
    re.compile(r"(?:^|[\s.|,])(?:fotos?|cr[eé]ditos?|fuente)\s*:\s*\(?\s*(?:foto\s*:\s*)?([^()|]{2,80}?)\s*\)?\s*\.?\s*$",
               re.I),
    re.compile(r"\|\s*([^|]{2,60}?)\s*$"),
    re.compile(r"\(([^()]{2,60})\)\s*\.?\s*$"),
    # La Voz: "... Cumple prisión perpetua. José Gabriel Hernández / La Voz)": la última frase, corta y con barra
    re.compile(r"(?<=[.!?])\s+([^.()/]{2,40}/[^.()/]{2,30}?)\)?\s*\.?\s*$"),
]


def separar_credito(texto):
    """("pie sin el crédito", "crédito") de un texto de pie. Si no hay crédito, (texto, "")."""
    texto = _limpio(texto, 600)
    for patron in _CREDITO_EN_TEXTO:
        m = patron.search(texto)
        if m:
            credito = m.group(1).strip(" .,;:-")
            if credito and len(credito.split()) <= 9:
                pie = texto[:m.start()].strip(" .,;:|-")
                # "Fuente: (Foto: NA)" deja sólo la etiqueta: eso no es un pie
                if re.fullmatch(r"(?:fotos?|imagen|cr[eé]ditos?|fuente)?", pie, re.I):
                    pie = ""
                return pie, credito
    if re.fullmatch(r"(?:fotos?|imagen|cr[eé]ditos?|fuente)\s*:?", texto, re.I):   # la etiqueta sola, sin nada
        return "", ""
    return texto, ""


def _pie_de_figura(figura):
    """Reparte el texto de una figura entre el pie y el crédito de sus fotos."""
    credito = " ".join(_limpio(t) for t, es in figura["pie"] if es).strip(" |.,;:-")
    pie = " ".join(_limpio(t) for t, es in figura["pie"] if not es)
    otros = " ".join(_limpio(t) for t in figura["otros"])
    # BBC y parecidos: "Fuente de la imagen, X" fuera del pie y "Pie de foto, Y" adentro
    m = re.search(r"fuente de la imagen,\s*(.+?)(?=pie de foto|$)", f"{otros} {pie}", re.I)
    if m and not credito:
        credito = m.group(1).strip(" .,;:")
    pie = re.sub(r"^\s*pie de foto,\s*", "", re.sub(r"fuente de la imagen,.*?(?=pie de foto|$)", "", pie,
                                                     flags=re.I), flags=re.I)
    if not credito:
        pie, credito = separar_credito(pie)
    credito = re.sub(r"^(?:fotos?|cr[eé]ditos?|fuente)\s*:\s*", "", credito, flags=re.I).strip(" ()|.,;:-")
    for foto in figura["imagenes"]:
        foto["pie"] = _limpio(pie)
        foto["credito"] = _limpio(credito, 80)


def _objetos_ld(textos):
    """Todos los objetos de los JSON-LD de la página (con los de @graph)."""
    salida = []

    def recorrer(o):
        if isinstance(o, list):
            for x in o:
                recorrer(x)
        elif isinstance(o, dict):
            salida.append(o)
            if "@graph" in o:
                recorrer(o["@graph"])

    for t in textos:
        try:
            recorrer(json.loads(t.strip()))
        except (ValueError, TypeError):
            continue
    return salida


def _fotos_de_ld(objetos, base):
    """Las fotos que la nota marca para los buscadores: sólo el "image" del artículo (no la del autor ni el logo)."""
    salida = []
    for o in objetos:
        tipos = o.get("@type") or o.get("type")
        tipos = set(tipos if isinstance(tipos, list) else [tipos])
        if not tipos & _TIPOS_NOTA:
            continue
        imagenes = o.get("image")
        for im in (imagenes if isinstance(imagenes, list) else [imagenes]):
            if isinstance(im, str):
                im = {"url": im}
            if not isinstance(im, dict):
                continue
            url = _direccion_real(im.get("url") or im.get("contentUrl"), base)
            if not url:
                continue
            credito = im.get("creditText") or ""
            for campo in ("author", "copyrightHolder"):
                quien = im.get(campo)
                if not credito and isinstance(quien, dict) and quien.get("name"):
                    credito = quien["name"]
            pie = _limpio(im.get("caption") or im.get("description"))
            foto = {"url": url, "alt": "", "pie": pie, "credito": _limpio(credito, 80), "origen": "buscadores",
                    "orden": 10_000 + len(salida), "ancho_dicho": _entero(im.get("width")), "descartada": None,
                    "otras": []}
            if _DIRECCION_MALA.search(url) or re.search(r"logo|institucional", pie, re.I):
                foto["descartada"] = "logo, ícono o publicidad"
            salida.append(foto)
    return salida


def _entero(valor):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return 0


def clave(url):
    """La misma foto en otro tamaño da la misma clave: se le sacan los tamaños de la dirección."""
    p = urlparse(url)
    ruta = unquote(p.path).lower()
    ruta = re.sub(r"/(trim|crop|fit|resize|smart)/\d+/\d+/", "/", ruta)
    ruta = re.sub(r"/\d{1,4}x\d{1,4}/", "/", ruta)
    ruta = re.sub(r"(\.(jpe?g|png|webp|avif))+$", "", ruta)
    ruta = re.sub(r"_\d{1,4}x\d{1,4}(__\w+)?$", "", ruta)      # Clarín y La Voz: nombre_1256x620__2
    nombre = ruta.rsplit("/", 1)[-1]
    # Arc (Infobae, La Nación, Cronista, TN): "algunas-palabras-ID" y "ID" son la misma foto
    arc = re.search(r"(?:^|-)([a-z0-9]{24,})$", nombre)
    if arc:
        return arc.group(1)
    # un nombre largo (una huella o un nombre con palabras) identifica la foto aunque cambie la carpeta del tamaño
    return nombre if len(nombre) >= 12 else p.netloc.lower().removeprefix("www.") + ruta


_ARC = re.compile(r"https?://[a-z0-9.-]*images\.arcpublishing\.com/[a-z0-9_-]+/([A-Z0-9]{20,})\.(?:jpe?g|png|webp)",
                  re.I)


def originales_arc(pagina):
    """{clave: dirección} de las fotos originales que trae la página en sus datos (Arc, el sistema de Infobae,
    Página 12, TN y El Cronista): las mismas fotos en su tamaño real, sin achicar."""
    texto = pagina.replace(r"\u002F", "/").replace(r"\/", "/")
    return {m.group(1).lower(): m.group(0) for m in _ARC.finditer(texto)}


def original_en_pagina(url, texto):
    """La misma dirección sin la parte del tamaño (Perfil: /2026/11/20/900/0/foto.jpg -> /2026/11/20/foto.jpg), si la
    página la nombra en algún lado (su galería): es la foto en su tamaño real."""
    p = urlparse(url)
    ruta = re.sub(r"/(?:trim|crop|cropped|fit|resize)/\d+/\d+(?:/center)?/|/\d{2,4}/\d{1,4}/(?=[^/]+$)", "/", p.path)
    ruta = re.sub(r"/{2,}", "/", ruta)
    if ruta == re.sub(r"/{2,}", "/", p.path):
        return None
    sin_tamano = f"{p.scheme}://{p.netloc}{ruta}"
    return sin_tamano if sin_tamano in texto else None


def ancho_en_url(url):
    """El ancho que dice la dirección (/trim/137/137/, _340x340, /ws/512/, ?width=630), o 0 si no dice."""
    for patron in (r"/trim/(\d+)/\d+/", r"/(\d{2,4})x\d{2,4}/", r"_(\d{2,4})x\d{2,4}", r"/ws/(\d{2,4})/",
                   r"[?&](?:w|width)=(\d{2,4})\b"):
        m = re.search(patron, url, re.I)
        if m:
            return int(m.group(1))
    return 0


def _preferida(f):
    """Cuál de dos copias de la misma foto se usa: sin marca de agua (BBC: "branded") y la más grande. Una sin ancho
    conocido cuenta como 600."""
    return ("branded" not in f["url"].lower(), f["ancho_dicho"] or 600)


def candidatas(pagina, link):
    """Las fotos de la página en orden (la de redes primero), cada una con "descartada" = motivo o None.
    No baja nada: sólo lee el HTML. Las repetidas por la dirección se juntan en una."""
    lector = _Fotos(link)
    try:
        lector.feed(pagina)
        lector.close()
    except Exception:   # noqa: BLE001  (un HTML muy roto: se usa lo que se alcanzó a leer)
        pass
    while lector.figuras:
        _pie_de_figura(lector.figuras.pop())
    fotos = []
    og = lector.meta.get("og:image") or lector.meta.get("og:image:url") or lector.meta.get("twitter:image")
    og = _direccion_real(og, link)
    if og:
        fotos.append({"url": og, "alt": _limpio(lector.meta.get("og:image:alt")), "pie": "", "credito": "",
                      "origen": "redes", "orden": 0, "ancho_dicho": _entero(lector.meta.get("og:image:width")),
                      "otras": [],
                      "descartada": "logo, ícono o publicidad" if _DIRECCION_MALA.search(og) else None})
    fotos += lector.imagenes
    fotos += _fotos_de_ld(_objetos_ld(lector.ld), link)
    for f in fotos:
        if not f["descartada"] and _ILUSTRATIVA.search(" ".join([f["pie"], f["alt"], f["credito"]])):
            f["descartada"] = "ilustrativa o hecha con IA"
    # juntar las repetidas por la dirección: queda la de orden más temprano, con la dirección más grande que se
    # conozca y el pie y el crédito que haya
    juntas = {}
    for f in fotos:
        k = clave(f["url"])
        if k not in juntas:
            juntas[k] = dict(f)
            continue
        j = juntas[k]
        if _preferida(f) > _preferida(j):
            j["otras"] = [j["url"], *j["otras"]]
            j["url"], j["ancho_dicho"] = f["url"], f["ancho_dicho"]
        else:
            j["otras"] = [*j["otras"], f["url"]]
        j["otras"] = [u for i, u in enumerate([*j["otras"], *f["otras"]])
                      if u != j["url"] and u not in [*j["otras"], *f["otras"]][:i]]
        for campo in ("pie", "credito", "alt"):
            if not j[campo] and f[campo]:
                j[campo] = f[campo]
        if j["descartada"] and not f["descartada"] and j["descartada"] != "ilustrativa o hecha con IA":
            j["descartada"] = None   # la misma foto aparece también donde sí es de la nota
        if f["descartada"] == "ilustrativa o hecha con IA":
            j["descartada"] = f["descartada"]
    salida = sorted(juntas.values(), key=lambda f: f["orden"])
    originales = originales_arc(pagina)
    texto = pagina.replace(r"\/", "/")
    for f in salida:
        original = originales.get(clave(f["url"])) or original_en_pagina(f["url"], texto)
        if original and original != f["url"]:
            # la foto original que la propia página publica (Infobae, Página 12, TN, Cronista): primero esa
            f["otras"] = [f["url"], *[u for u in f["otras"] if u != f["url"]]]
            f["url"] = original
            f["ancho_dicho"] = 0   # el tamaño real no se sabe hasta bajarla (no es una miniatura)
        if not f["credito"] and f["alt"]:
            # sin pie con crédito: el que diga la descripción con una etiqueta ("Foto: X", "(Fuente: X)")
            for patron in _CREDITO_EN_TEXTO[:2]:
                m = patron.search(f["alt"])
                if m and len(m.group(1).split()) <= 9:
                    f["credito"] = _limpio(m.group(1).strip(" .,;:-()"), 80)
                    break
        if f["descartada"]:
            continue
        if _ILUSTRATIVA.search(" ".join([f["pie"], f["alt"], f["credito"]])):
            f["descartada"] = "ilustrativa o hecha con IA"
        elif 0 < (f["ancho_dicho"] or ancho_en_url(f["url"])) < 300:
            f["descartada"] = "miniatura"
    return salida


# ------------------------------------------------------------------------------------------- Bajar y convertir

def _medidas(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "json", str(ruta)], capture_output=True, timeout=20)
    try:
        s = json.loads(r.stdout or b"{}")["streams"][0]
        return int(s["width"]), int(s["height"])
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def _a_la_medida(ancho, alto, lado):
    """(ancho, alto) con el lado largo a `lado` como mucho, sin agrandar."""
    escala = min(1.0, lado / max(ancho, alto))
    return max(1, round(ancho * escala)), max(1, round(alto * escala))


def convertir(origen, grande, chica):
    """La foto en JPEG (tamaño real hasta 2560 de lado largo), la copia chica y su huella (256 bytes de grises).
    Devuelve (ancho, alto, huella) o None si FFmpeg no la pudo abrir."""
    medidas = _medidas(origen)
    if not medidas:
        return None
    ancho, alto = medidas
    g, c = _a_la_medida(ancho, alto, LADO_GRANDE), _a_la_medida(ancho, alto, LADO_CHICO)
    filtro = (f"[0:v]split=3[a][b][c];[a]scale={g[0]}:{g[1]}:flags=lanczos,format=yuvj444p[g];"
              f"[b]scale={c[0]}:{c[1]}:flags=lanczos,format=yuvj420p[ch];"
              "[c]crop='min(iw,ih)':'min(iw,ih)',scale=16:16:flags=area,format=gray[h]")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(origen), "-filter_complex",
                        filtro, "-map", "[g]", "-frames:v", "1", "-q:v", "2", str(grande),
                        "-map", "[ch]", "-frames:v", "1", "-q:v", "4", str(chica),
                        "-map", "[h]", "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True, timeout=60)
    if r.returncode != 0 or len(r.stdout) != 256 or not Path(grande).exists() or not Path(chica).exists():
        return None
    return g[0], g[1], r.stdout


def parecidas(h1, h2):
    return sum(abs(a - b) for a, b in zip(h1, h2)) / max(1, len(h1)) < PARECIDO


def _bajar_foto(direcciones, hasta, bajar):
    """Prueba las direcciones en orden (la original primero) hasta que una dé una imagen. (bytes, None) o
    (None, motivo)."""
    motivo = "no bajó"
    for url in direcciones[:3]:
        if time.monotonic() > hasta - 2:
            return None, "sin tiempo"
        try:
            codigo, cuerpo, enc = bajar(url, {"Accept": "image/avif,image/webp,image/jpeg,image/png,*/*"},
                                        timeout=max(3, min(12, int(hasta - time.monotonic()))),
                                        tope_bytes=TOPE_BYTES_FOTO)
        except Falla:
            codigo, cuerpo, enc = 0, b"", {}
        tipo = _encabezado(enc, "content-type").lower()
        if codigo != 200 or not cuerpo or (tipo and not tipo.startswith("image/") and "octet-stream" not in tipo):
            motivo = f"no bajó ({codigo or 'sin conexión'})"
        elif len(cuerpo) >= TOPE_BYTES_FOTO:
            motivo = "muy pesada"
        else:
            return cuerpo, None
    return None, motivo


def guardar(cands, carpeta, hasta, bajar=None):
    """Baja las candidatas sanas en orden, las convierte, tira chicas, tiras y repetidas, y guarda hasta MAXIMO.
    Devuelve (medios, registro de cada candidata) — el registro es lo que se mide."""
    bajar = bajar or comun.bajar
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    medios, huellas, anotado = [], [], []
    intentadas = 0
    for f in cands:
        nota = {"url": f["url"][:160], "origen": f["origen"], "motivo": f["descartada"]}
        anotado.append(nota)
        if f["descartada"]:
            continue
        if len(medios) >= MAXIMO:
            nota["motivo"] = "ya había 8"
            continue
        if intentadas >= A_BAJAR or time.monotonic() > hasta - 3:
            nota["motivo"] = "sin tiempo"
            continue
        intentadas += 1
        crudo = carpeta / "bajando.tmp"
        cuerpo, motivo = _bajar_foto([f["url"], *f.get("otras", [])], hasta, bajar)
        if not cuerpo:
            nota["motivo"] = motivo
            continue
        crudo.write_bytes(cuerpo)
        n = len(medios) + 1
        grande, chica = carpeta / f"{n:02d}.jpg", carpeta / f"{n:02d}-chica.jpg"
        hecho = convertir(crudo, grande, chica)
        crudo.unlink(missing_ok=True)
        if not hecho:
            nota["motivo"] = "no se pudo abrir"
            continue
        ancho, alto, huella = hecho
        nota["medidas"] = [ancho, alto]
        motivo = None
        if ancho < ANCHO_MINIMO:
            motivo = f"chica ({ancho} de ancho)"
        elif max(ancho, alto) / min(ancho, alto) > ESTIRADA:
            motivo = "tira angosta (publicidad)"
        else:
            for i, h in enumerate(huellas):
                if parecidas(h, huella):
                    motivo = f"repetida de la {i + 1}"
                    vieja = medios[i]
                    if ancho * alto > vieja["ancho"] * vieja["alto"]:
                        # la misma foto, más grande: se queda la grande, con el lugar y los textos de la primera
                        grande.replace(carpeta / vieja["archivo"])
                        chica.replace(carpeta / vieja["archivo"].replace(".jpg", "-chica.jpg"))
                        vieja["ancho"], vieja["alto"] = ancho, alto
                        motivo += " (más grande: la reemplaza)"
                    for campo in ("pie", "alt", "credito"):
                        if not vieja[campo] and f[campo]:
                            vieja[campo] = f[campo]
                    break
        if motivo:
            nota["motivo"] = motivo
            grande.unlink(missing_ok=True)
            chica.unlink(missing_ok=True)
            continue
        huellas.append(huella)
        medios.append({"n": n, "archivo": grande.name, "ancho": ancho, "alto": alto, "pie": f["pie"],
                       "alt": f["alt"], "credito": f["credito"]})
    return medios, anotado


def _encabezado(enc, nombre):
    for k, v in (enc or {}).items():
        if k.lower() == nombre:
            return v or ""
    return ""


def _bajar_pagina(link, hasta, bajar):
    codigo, cuerpo, enc = bajar(link, {"Accept": "text/html,application/xhtml+xml",
                                       "Accept-Language": "es-419,es;q=0.9"},
                                timeout=max(3, min(15, int(hasta - time.monotonic()))),
                                tope_bytes=TOPE_BYTES_PAGINA)
    if codigo != 200:
        registro(f"  fotos: la página contestó {codigo}")
        return None
    m = re.search(r"charset=([\w-]+)", _encabezado(enc, "content-type"))
    try:
        return cuerpo.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError:
        return cuerpo.decode("utf-8", errors="replace")


def juntar(nota, segundos=TOPE_SEGUNDOS, carpeta_base=None, bajar=None):
    """Las fotos de la nota: [{n, archivo, ancho, alto, pie, alt, credito}] o [] si no hay o algo falló.
    Si la nota ya se leyó antes (la misma carpeta con su medios.json y sus fotos), devuelve lo guardado sin bajar
    nada. `bajar` es para las pruebas (por defecto comun.bajar)."""
    link = nota.get("link")
    if not link or not nota.get("id") or segundos < 5:
        return []
    bajar = bajar or comun.bajar
    carpeta = Path(carpeta_base or CARPETA) / nota["id"]
    guardado = carpeta / "medios.json"
    if guardado.exists():
        try:
            medios = comun.leer_json(guardado)["medios"]
            if all((carpeta / m["archivo"]).exists() for m in medios):
                return medios
        except (OSError, ValueError, KeyError, TypeError):
            pass
    hasta = time.monotonic() + segundos
    try:
        pagina = _bajar_pagina(link, hasta, bajar)
        if not pagina:
            return []
        cands = candidatas(pagina, link)
        if carpeta.exists():
            shutil.rmtree(carpeta, ignore_errors=True)
        medios, anotado = guardar(cands, carpeta, hasta, bajar)
    except Exception as e:   # noqa: BLE001  (las fotos nunca frenan la nota)
        registro(f"  fotos: no se pudieron juntar ({type(e).__name__})")
        return []
    comun.escribir_json(guardado, {"link": link, "medios": medios, "candidatas": anotado})
    registro(f"  fotos de la página: {len(medios)} de {sum(1 for a in anotado if not a['motivo'])} sanas "
             f"({len(anotado)} vistas)")
    return medios


def carpeta_de(nota_id, carpeta_base=None):
    return Path(carpeta_base or CARPETA) / nota_id


def principal():
    if len(sys.argv) != 2:
        raise Falla("DESCONOCIDO", "uso: medios_pagina.py <link>")
    import hashlib
    link = sys.argv[1]
    nota = {"id": "nota-" + hashlib.md5(link.encode("utf-8")).hexdigest()[:10], "link": link}
    medios = juntar(nota)
    datos = comun.leer_json(carpeta_de(nota["id"]) / "medios.json") if medios else {"medios": []}
    return {"medios": medios, "candidatas": datos.get("candidatas", [])}


if __name__ == "__main__":
    sys.exit(comun.correr(principal))
