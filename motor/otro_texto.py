"""Cambia un texto para publicar por la variante siguiente ("Pedir otro").

Uso:  python motor/otro_texto.py <carpeta del trabajo> <campo> [red]
      campo: titulo, descripcion, hashtags, etiquetasYoutube o redes (con red: tiktok, instagram, youtube, facebook,
      x o linkedin).

Usa las variantes guardadas en textos-variantes.json; cuando se acaban, hace UN pedido nuevo a Google (tres variantes
más de todo, se suman las de ese campo). Guarda resultado.json e imprime {"resultado": {...}} con 0. Si falla,
{"error": {...}} y 1. Códigos: DESCONOCIDO, SIN_CONEXION.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contrato  # noqa: E402
from comun import Falla, correr, escribir_json, leer_json, registro  # noqa: E402
import textos as TX  # noqa: E402

INICIO = time.monotonic()
TOPE = 240   # el Estudio corta "Pedir otro" a los 4 minutos (TOPES.otro en estudio/lib/fuente/motor.js)


def quedan():
    """Los segundos que faltan para que el Estudio corte este paso, contados desde que arrancó el programa."""
    return TOPE - (time.monotonic() - INICIO)


def siguiente(lista, actual):
    """Índice de la variante que sigue a la actual; None si la actual es la última."""
    clave = json.dumps(actual, ensure_ascii=False, sort_keys=True)
    i = next((k for k, x in enumerate(lista) if json.dumps(x, ensure_ascii=False, sort_keys=True) == clave), -1)
    return i + 1 if i + 1 < len(lista) else None


def principal():
    args = sys.argv[1:]
    if len(args) not in (2, 3):
        raise Falla("DESCONOCIDO", "uso: otro_texto.py <carpeta> <campo> [red]")
    carpeta, campo = Path(args[0]), args[1]
    red = args[2] if len(args) == 3 else None
    if campo not in contrato.CAMPOS_TEXTO:
        raise Falla("DESCONOCIDO", "ese texto no se puede pedir de nuevo")
    if campo == "redes" and red not in contrato.REDES:
        raise Falla("DESCONOCIDO", "falta decir de qué red")
    try:
        trabajo = leer_json(carpeta / "trabajo.json")
        resultado = leer_json(carpeta / "resultado.json")
        guardadas = leer_json(carpeta / "textos-variantes.json")
    except (OSError, ValueError):
        raise Falla("DESCONOCIDO", "el video todavía no tiene textos")
    variantes = guardadas["variantes"]
    lista = variantes["redes"][red] if campo == "redes" else variantes[campo]
    actual = resultado["textos"]["redes"][red] if campo == "redes" else resultado["textos"][campo]
    i = siguiente(lista, actual)
    if i is None:
        registro("  se acabaron las variantes guardadas: pido tres más")
        nuevas = TX.por_campo(TX.pedir_variantes(trabajo["nota"], trabajo["guion"]["texto"], quedan))
        sumar = nuevas["redes"][red] if campo == "redes" else nuevas[campo]
        vistos = {json.dumps(x, ensure_ascii=False, sort_keys=True) for x in lista}
        sumar = [x for x in sumar if json.dumps(x, ensure_ascii=False, sort_keys=True) not in vistos] or sumar
        i = len(lista)
        lista.extend(sumar)
        guardadas["pedidos"] = int(guardadas.get("pedidos", 1)) + 1
        escribir_json(carpeta / "textos-variantes.json", guardadas)
    nuevo = lista[i]
    if campo == "redes":
        resultado["textos"]["redes"][red] = nuevo
    else:
        resultado["textos"][campo] = nuevo
    escribir_json(carpeta / "resultado.json", resultado)
    return {"resultado": resultado}


if __name__ == "__main__":
    sys.exit(correr(principal))
