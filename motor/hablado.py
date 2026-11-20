"""Texto para decir en voz alta: números con letras, sin símbolos, sin emojis, sin links ni rayas.

Lo usan guiones.py (lo que sale de Google se limpia igual, por si se le escapa algo) y armar.py (para partir un guion
escrito a mano en tramos).
"""
import re

import contrato
from comun import numero_en_palabras, sin_emojis, sin_links, sin_rayas

_MILES = re.compile(r"\b\d{1,3}(?:\.\d{3})+\b")


def _entero(s):
    return int(s.replace(".", ""))


def _decir(entero, decimales=None):
    texto = numero_en_palabras(entero)
    if decimales:
        d = decimales.rstrip("0") or "0"
        texto += " coma " + (numero_en_palabras(int(d)) if not d.startswith("0") else
                             " ".join(numero_en_palabras(int(c)) for c in d))
    return texto


def decir_numeros(texto):
    """'20%' -> 'veinte por ciento', '1.500' -> 'mil quinientos', '3,5' -> 'tres coma cinco', 'US$ 10' -> 'diez
    dólares', '$ 300' -> 'trescientos pesos'. Lo que no reconoce lo deja como está."""
    t = str(texto)
    num = r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?"

    def a_palabras(m):
        return _decir(_entero(m.group(1)), m.group(2))

    t = re.sub(r"(?:US\$|U\$S|USD)\s*" + num, lambda m: a_palabras(m) + " dólares", t)
    t = re.sub(r"\$\s*" + num, lambda m: a_palabras(m) + " pesos", t)
    t = re.sub(num + r"\s*%", lambda m: a_palabras(m) + " por ciento", t)
    t = re.sub(r"(?<![\w,.])" + num + r"(?![\w])", a_palabras, t)
    return t


def limpiar_para_decir(texto):
    t = contrato.limpiar_invisibles(texto)
    t = sin_links(sin_emojis(t))
    t = re.sub(r"#(\w+)", r"\1", t)
    t = re.sub(r"[«»“”\"]", "", t)
    t = re.sub(r"\s*\(([^)]*)\)", r", \1,", t)
    t = sin_rayas(t)
    t = decir_numeros(t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r",\s*,", ",", t)
    t = re.sub(r",([.!?])", r"\1", t)
    return " ".join(t.split())


def oraciones(texto):
    """Parte un texto en oraciones (en el punto, el signo de pregunta o de exclamación que cierran)."""
    partes = re.split(r"(?<=[.!?…])\s+(?=[¿¡A-ZÁÉÍÓÚÑ0-9])", " ".join(str(texto).split()))
    return [p.strip() for p in partes if p.strip()]


def tramos_de(texto, max_palabras=22):
    """Tramos de una o dos oraciones seguidas (dos si la primera es corta)."""
    salida, actual = [], []
    for o in oraciones(texto):
        if actual and (len(" ".join(actual + [o]).split()) > max_palabras or len(actual) == 2):
            salida.append(" ".join(actual))
            actual = []
        actual.append(o)
        if len(" ".join(actual).split()) >= 12:
            salida.append(" ".join(actual))
            actual = []
    if actual:
        salida.append(" ".join(actual))
    return salida
