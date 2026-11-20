"""Las llaves del motor. NUNCA se imprimen: ni en el registro, ni en errores, ni en archivos.

- PEXELS_API_KEY: del entorno o del .env propio.
- GEMINI_API_KEY y GEMINI_API_KEY_REPUESTO: primero del entorno, después del .env propio y, si no están en ninguno,
  del .env que diga PORTAVOZ_LLAVES_PRESTADAS (en la PC de Lucio, las prestadas de otro programa suyo, de forma
  temporal). Se leen en su lugar y no se copian a ningún otro archivo. El registro avisa "uso llaves prestadas".
  Para pasar a llaves propias alcanza con escribirlas en el .env propio: no se toca código.
  La dirección de ese otro .env vive en el .env de Lucio (desde el 2026-11-20), así no viaja con el programa.
- ANTHROPIC_API_KEY: opcional. Si la persona no tiene Claude Code, los guiones los escribe Claude con esta llave.
- PORTAVOZ_TEXTO: quién escribe los guiones ("claude", "anthropic", "google" o vacío = el primero que ande). Se lee
  del entorno o del .env propio (lo escribe la pantalla Ajustes).
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENV_PROPIO = Path(os.environ.get("PORTAVOZ_ENV") or RAIZ / ".env")   # PORTAVOZ_ENV: las pruebas usan uno temporal
NOMBRES_GEMINI = ("GEMINI_API_KEY", "GEMINI_API_KEY_REPUESTO")

_cache = {}
_aviso_dado = [False]


def leer_env(ruta):
    """Las líneas NOMBRE=valor de un .env. Las que no tienen "=" o empiezan con # se saltean."""
    datos = {}
    try:
        texto = Path(ruta).read_text(encoding="utf-8-sig")
    except OSError:
        return datos
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v:
            datos[k.strip()] = v
    return datos


def _todas():
    if "todas" not in _cache:
        propio = leer_env(ENV_PROPIO)
        gemini = [os.environ.get(n) or propio.get(n) for n in NOMBRES_GEMINI]
        prestadas = False
        otro_env = os.environ.get("PORTAVOZ_LLAVES_PRESTADAS") or propio.get("PORTAVOZ_LLAVES_PRESTADAS")
        if not any(gemini) and otro_env and Path(otro_env).is_file():
            otro = leer_env(otro_env)
            gemini = [otro.get(n) for n in NOMBRES_GEMINI]
            prestadas = any(gemini)
        _cache["todas"] = {
            "gemini": [g for g in gemini if g],
            "pexels": os.environ.get("PEXELS_API_KEY") or propio.get("PEXELS_API_KEY"),
            "anthropic": os.environ.get("ANTHROPIC_API_KEY") or propio.get("ANTHROPIC_API_KEY"),
            "texto": (os.environ.get("PORTAVOZ_TEXTO") or propio.get("PORTAVOZ_TEXTO") or "").strip().lower(),
            "prestadas": prestadas,
        }
    return _cache["todas"]


def gemini():
    """[la de siempre, la de repuesto] (la de repuesto sólo si está). Lista vacía si no hay ninguna."""
    t = _todas()
    if t["prestadas"] and not _aviso_dado[0]:
        _aviso_dado[0] = True
        print("uso llaves prestadas", file=sys.stderr, flush=True)
    return list(t["gemini"])


def pexels():
    return _todas()["pexels"]


def anthropic():
    return _todas()["anthropic"]


def quien_escribe_pedido():
    """Lo que eligió la persona: "claude", "anthropic", "google" o "" (el primero que ande)."""
    return _todas()["texto"]


def prestadas():
    return _todas()["prestadas"]


def ocultar(texto):
    """Saca cualquier llave conocida de un texto antes de mostrarlo o guardarlo."""
    texto = str(texto)
    t = _todas()
    for llave in [*t["gemini"], t["pexels"], t["anthropic"]]:
        if llave and len(llave) > 6:
            texto = texto.replace(llave, "<llave>")
    return texto
