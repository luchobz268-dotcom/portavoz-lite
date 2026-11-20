"""Revisa que la instalación esté entera. Lo usan la skill portavoz-instalar y la pantalla Ajustes del Estudio.

Imprime UNA línea de JSON (como todo programa del motor):
  python chequeo.py              -> qué hay: Python, sus piezas (numpy y fontTools), ffmpeg y ffprobe, Claude Code, quién escribe, qué llaves
                                    hay (sólo los últimos 4 caracteres, nunca la llave entera).
  python chequeo.py --llaves     -> lo mismo, y además prueba cada llave con un pedido que no gasta nada.
  python chequeo.py --probar google|pexels|anthropic
                                 -> prueba UNA llave nueva que llega por la entrada (no por los argumentos, así no queda
                                    en la lista de programas de la compu). Ajustes la prueba antes de guardarla.
Las pruebas de llaves: Google lista sus modelos, Anthropic lista sus modelos y Pexels busca un clip. Ninguna gasta voces
ni pedidos pagos. Nunca se imprime una llave: sólo "anda", "mala" o "sin internet".
"""
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun  # noqa: E402
import llaves  # noqa: E402

NOMBRES = ("google", "pexels", "anthropic")


def final(llave):
    """Los últimos 4 caracteres, para reconocerla sin mostrarla."""
    return f"…{llave[-4:]}" if llave and len(llave) >= 8 else ("…" if llave else None)


def _pedido(nombre, llave):
    if nombre == "google":
        return urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
                                      headers={"x-goog-api-key": llave, "User-Agent": comun.AGENTE})
    if nombre == "pexels":
        return urllib.request.Request("https://api.pexels.com/v1/search?query=city&per_page=1",
                                      headers={"Authorization": llave, "User-Agent": comun.AGENTE})
    return urllib.request.Request("https://api.anthropic.com/v1/models?limit=1",
                                  headers={"x-api-key": llave, "anthropic-version": "2023-06-01",
                                           "User-Agent": comun.AGENTE})


def probar(nombre, llave):
    """"anda", "mala", "sin-internet" o "falta"."""
    if not llave:
        return "falta"
    try:
        with urllib.request.urlopen(_pedido(nombre, llave.strip()), timeout=15) as r:
            return "anda" if r.status == 200 else "mala"
    except urllib.error.HTTPError as e:
        return "mala" if e.code in (400, 401, 403) else "sin-internet"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "sin-internet"


def _contesta(programa, args):
    ruta = shutil.which(programa)
    if not ruta:
        return False
    try:
        return subprocess.run([ruta, *args], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def revisar(con_llaves=False):
    try:
        import numpy  # noqa: F401
        import fontTools  # noqa: F401
        hay_piezas = True
    except ImportError:
        hay_piezas = False
    actuales = {"google": (llaves.gemini() or [None])[0], "pexels": llaves.pexels(), "anthropic": llaves.anthropic()}
    datos = {
        "python": ".".join(map(str, sys.version_info[:3])),
        "python_sirve": sys.version_info >= (3, 10),
        "piezas_python": hay_piezas,
        "ffmpeg": _contesta("ffmpeg", ["-version"]),
        "ffprobe": _contesta("ffprobe", ["-version"]),
        "claude_code": bool(comun.programa_claude()),
        "elegido": llaves.quien_escribe_pedido() or "",
        "escribe": comun.proveedor_texto(),
        "llaves": {n: final(v) for n, v in actuales.items()},
        "prestadas": llaves.prestadas(),
    }
    if con_llaves:
        datos["pruebas"] = {n: probar(n, v) for n, v in actuales.items()}
    return datos


def principal():
    args = sys.argv[1:]
    if args[:1] == ["--probar"]:
        nombre = args[1] if len(args) > 1 else ""
        if nombre not in NOMBRES:
            raise comun.Falla("DESCONOCIDO", "llave desconocida")
        return {"llave": nombre, "resultado": probar(nombre, sys.stdin.readline().strip())}
    return revisar(con_llaves="--llaves" in args)


if __name__ == "__main__":
    sys.exit(comun.correr(principal))
