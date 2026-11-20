"""Lo del contrato (estudio/lib/contrato.js) que usa el motor, escrito de nuevo en Python para no depender de Node al
correr. probar_sin_gastar.py compara cada constante con contrato.js y algunas cuentas (palabras, largo para X): si
alguien cambia algo allá y no acá, esa prueba falla.

Regla de fondo, igual que allá: el motor devuelve CÓDIGOS y la pantalla pone las palabras (estudio/lib/textos.js).
"""
import math
import re
import unicodedata
from urllib.parse import urlparse

LARGOS = [15, 30, 60]
LARGO_INICIAL = 30
PALABRAS_POR_SEGUNDO = 3.3
MARGEN_LARGO = 0.1
ENFOQUES = ["dato", "te-cambia", "debate"]
ORIGENES = ["propuesta", "corto", "simple", "otro", "a-mano"]
PALABRAS_MINIMAS_NOTA = 60
TEMAS = ["general", "politica", "crimen", "tragedia"]
TEMAS_SENSIBLES = ["politica", "crimen", "tragedia"]
ETAPAS = ["clips", "voz", "tiempos", "armado", "textos"]
REDES = ["tiktok", "instagram", "youtube", "facebook", "x", "linkedin"]
TOPES_REDES = {
    "tiktok": {"texto": 2200},
    "instagram": {"texto": 2200, "hashtags": 30},
    "youtube": {"titulo": 100, "texto": 5000, "hashtags": 60},
    "facebook": {},
    "x": {"texto": 280},
    "linkedin": {"texto": 3000},
}
TOPE_ETIQUETAS_YOUTUBE = 500
CAMPOS_TEXTO = ["titulo", "descripcion", "hashtags", "etiquetasYoutube", "redes"]
# lo que puede marcar la revisión de un guion cuando no lo pudo arreglar sola (AVISOS_REVISION en contrato.js):
# DATO_NO_ESTA = el guion dice algo que no está en la nota; VERBO_CAMBIADO = cuenta como hecho algo que va a pasar
AVISOS_REVISION = ["DATO_NO_ESTA", "VERBO_CAMBIADO"]
# los campos de "revision" en cada versión del guion (CAMPOS_REVISION en contrato.js; revisarRevision los comprueba).
# "antes" y "arreglados" sólo vienen cuando "arreglado" es true: el texto de antes y los puntos que se arreglaron.
CAMPOS_REVISION = ["puntos", "arreglado", "aviso", "quien", "antes", "arreglados"]
# Las fotos de la página de la nota (desde el 2026-11-20; ver revisarMedios y revisarMirada en contrato.js)
MAXIMO_FOTOS = 8
ENCUADRES = ["acercamiento", "recorrido", "entera"]
CAMPOS_FOTO = ["n", "archivo", "ancho", "alto", "pie", "alt", "credito", "mirada"]
CAMPOS_MIRADA = ["sirve", "encuadre", "centro"]
CAMPOS_PIE = ["mostrar", "fuente", "ilustrativas"]
# cómo va cada foto aprobada (FORMAS en contrato.js): a pantalla completa o en un recuadro encima del clip.
# Una foto sin forma va a pantalla completa. Los campos de cada una (trabajo["imagenes"]) son CAMPOS_IMAGEN.
FORMAS = ["pantalla", "encima"]
CAMPOS_IMAGEN = ["tramo", "foto", "credito", "forma"]
AGRANDAR_HASTA = 2
# código -> qué camino le ofrece la pantalla (ERRORES en contrato.js)
ERRORES = {
    "LINK_INVALIDO": "corregir",
    "LINK_NO_ABRE": "pegar-texto",
    "NOTA_SIN_TEXTO": "pegar-texto",
    "MURO_DE_PAGO": "pegar-texto",
    "NOTA_MUY_CORTA": "corregir",
    "SIN_VOCES_HOY": "manana",
    "GUION_A_CORREGIR": "volver-al-guion",
    "SIN_CLIPS": "volver-al-guion",
    "FALLO_VOZ": "reintentar",
    "FALLO_ARMADO": "reintentar",
    "SIN_CONEXION": "reintentar",
    "DESCONOCIDO": "reintentar",
}


def js_round(x):
    """Math.round de JavaScript (redondea .5 para arriba; el round de Python redondea al par)."""
    return math.floor(x + 0.5)


def palabras_para(segundos):
    return js_round((segundos * PALABRAS_POR_SEGUNDO) / 5) * 5


def segundos_para(palabras):
    return js_round(palabras / PALABRAS_POR_SEGUNDO)


def entra_en_largo(palabras, largo):
    return segundos_para(palabras) <= largo * (1 + MARGEN_LARGO)


def entra_justo(palabras, largo):
    return segundos_para(palabras) <= largo


def tope_palabras(largo):
    """Lo más largo que entra SIN margen (topePalabras de lib/fuente/ejemplos.js)."""
    p = palabras_para(largo)
    while entra_justo(p + 1, largo):
        p += 1
    while p > 0 and not entra_justo(p, largo):
        p -= 1
    return p


def objetivo_palabras(largo):
    return min(palabras_para(largo), tope_palabras(largo))


# Lo que JavaScript y Python no cuentan igual como espacio, o que no se ve: se saca de todo texto que sale del motor.
_INVISIBLES = re.compile("[﻿​‌‍⁠\x00-\x08\x0b\x0e-\x1f\x7f-\x9f]")


def limpiar_invisibles(texto):
    return _INVISIBLES.sub("", unicodedata.normalize("NFC", str(texto or "")))


def contar_palabras(texto):
    return len(str(texto or "").split())


def crear_error(codigo, detalle=None):
    conocido = codigo if codigo in ERRORES else "DESCONOCIDO"
    e = {"codigo": conocido, "salida": ERRORES[conocido], "cuenta": False}
    if detalle:
        e["detalle"] = str(detalle)
    return {"error": e}


def link_valido(texto):
    try:
        u = urlparse(str(texto).strip())
        return u.scheme in ("http", "https") and "." in (u.hostname or "")
    except ValueError:
        return False


def _liviano(p):
    return p <= 0x10FF or 0x2000 <= p <= 0x200D or 0x2010 <= p <= 0x201F or 0x2032 <= p <= 0x2037


def largo_x(texto):
    """largoX de contrato.js: cada link vale 23, lo latino 1 y lo demás (emojis, otros alfabetos) 2. JavaScript
    recorre por letra entera (no por mitades), igual que Python."""
    n = 0
    texto = str(texto or "")
    links = re.findall(r"https?://\S+", texto, flags=re.I)
    n += 23 * len(links)
    sin_links = re.sub(r"https?://\S+", "", texto, flags=re.I)
    return n + sum(1 if _liviano(ord(c)) else 2 for c in sin_links)


def largo_js(texto):
    """.length de JavaScript: cuenta en unidades de 16 bits (un emoji vale 2)."""
    return len(str(texto or "").encode("utf-16-le")) // 2


def largo_para(red, texto):
    return largo_x(texto) if red == "x" else largo_js(texto)


HASHTAG_EN_TEXTO = re.compile(r"#[^\W]+", re.UNICODE)


def contar_hashtags(texto):
    return len(HASHTAG_EN_TEXTO.findall(str(texto or "")))


def largo_etiquetas(etiquetas):
    return largo_js(",".join(etiquetas or []))
