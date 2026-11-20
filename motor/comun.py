"""Piezas comunes del motor: pedidos a internet, pedidos a Google, salida en JSON y comparación de palabras.

Cada programa del motor imprime UN JSON en la salida (stdout) y sale con 0. Si falla, imprime
{"error": {"codigo", "salida", "cuenta", "detalle"}} con un código de ERRORES (contrato.py) y sale con 1.
El registro (lo que va pasando) va por stderr, sin llaves y sin rutas de la carpeta personal.
"""
import base64
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.dont_write_bytecode = True   # para no dejar archivos .pyc adentro de estudio/herramientas al importar de ahí

import contrato  # noqa: E402
import llaves  # noqa: E402

MOTOR = Path(__file__).resolve().parent
RAIZ = MOTOR.parent
ESTUDIO = RAIZ / "estudio"
HERRAMIENTAS = ESTUDIO / "herramientas"
CACHE = MOTOR / "cache"
API = "https://generativelanguage.googleapis.com/v1beta"
AGENTE = "portavoz-lite/0.1"          # el nombre con el que sale todo pedido: nunca datos de Lucio
MODELO_TEXTO = "gemini-3.8-flash"
# Quién escribe los textos (guiones, cambios, textos para redes, palabras de búsqueda, orden de la nota).
# Lucio, 2026-11-18: "prefiero que claude opus 5.5 escriba los guiones", con el cupo de su suscripción.
# En otra compu: Claude Code de la persona, si no su llave de Anthropic, si no Google (ver proveedor_texto).
# PORTAVOZ_TEXTO=google (o anthropic, o claude) lo fija. La voz y la transcripción siguen siempre en Google.
MODELO_CLAUDE = "claude-opus-5-5"


class Falla(Exception):
    """Un error con su código del contrato. `detalle` es corto y nunca lleva llaves ni rutas personales."""

    def __init__(self, codigo, detalle=""):
        super().__init__(detalle or codigo)
        self.codigo = codigo if codigo in contrato.ERRORES else "DESCONOCIDO"
        self.detalle = detalle


class TopeDelDia(Exception):
    """Google dice que TODAS las llaves gastaron lo del día."""


def sin_rutas(texto):
    """Saca las llaves y las rutas de la carpeta personal (C:/Users/<nombre>/...) de un texto."""
    texto = llaves.ocultar(texto)
    casa = str(Path.home())
    for forma in {casa, casa.replace("\\", "/"), casa.replace("\\", "\\\\")}:
        texto = re.sub(re.escape(forma), "~", texto, flags=re.I)
    texto = re.sub(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s'\"]+", "~", texto, flags=re.I)
    # También las de Linux y Mac (/home/<nombre>, /Users/<nombre>), por si el motor corre en otra máquina
    return re.sub(r"(?<![\w.])/(?:home|Users)/[^/\s'\"]+", "~", texto)


def registro(*partes):
    print(sin_rutas(" ".join(str(p) for p in partes)), file=sys.stderr, flush=True)


def _utf8():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def responder(datos):
    _utf8()
    sys.stdout.write(json.dumps(datos, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def correr(principal):
    """Corre principal() y traduce lo que pase a la salida acordada: JSON + 0, o error + 1."""
    _utf8()
    try:
        responder(principal())
        return 0
    except Falla as e:
        responder(contrato.crear_error(e.codigo, sin_rutas(e.detalle)[:300] if e.detalle else None))
        return 1
    except KeyboardInterrupt:
        responder(contrato.crear_error("DESCONOCIDO", "se cortó a mano"))
        return 1
    except Exception as e:  # cualquier otra cosa: código DESCONOCIDO con un detalle corto
        responder(contrato.crear_error("DESCONOCIDO", sin_rutas(f"{type(e).__name__}: {e}")[:300]))
        return 1


def leer_json(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8-sig"))


def escribir_json(ruta, datos):
    """Escribe con un nombre temporal y renombra: quien lo lea ve el viejo entero o el nuevo entero."""
    ruta = Path(ruta)
    parcial = ruta.with_name(f"{ruta.stem}.{os.getpid()}.parcial{ruta.suffix}")
    parcial.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    for vuelta in range(20):
        try:
            os.replace(parcial, ruta)
            return
        except PermissionError:   # en Windows, si otro lo está leyendo justo, el renombre falla un instante
            time.sleep(0.05 * (vuelta + 1))
    os.replace(parcial, ruta)


# ------------------------------------------------------------------------------------------- Pedidos a internet

def bajar(url, encabezados=None, timeout=30, tope_bytes=60_000_000):
    """GET con el nombre del programa. Devuelve (código, bytes, encabezados). Los errores HTTP no se tiran: vuelven
    con su código. Una conexión que no se puede hacer tira Falla SIN_CONEXION."""
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, **(encabezados or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(tope_bytes + 1)[:tope_bytes], dict(r.headers)
    except urllib.error.HTTPError as e:
        try:
            cuerpo = e.read()[:200_000]
        except Exception:
            cuerpo = b""
        return e.code, cuerpo, dict(e.headers or {})
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise Falla("SIN_CONEXION", f"no se pudo conectar con {urlparse(url).hostname}: "
                    f"{getattr(e, 'reason', e)}")


# Copiado de otro programa del autor (comun.py: llaves, tope_del_dia y pedir, líneas 9-58) el 2026-11-17. Cambios: las
# llaves salen de llaves.py; el nombre del programa es portavoz-lite/0.1; en vez de cortar el programa tira Falla
# (o TopeDelDia si todas las llaves llegaron al tope del día); una conexión caída es SIN_CONEXION.
_LLAVE_EN_USO = [0]   # cuál de las llaves se usa: pasa a la de repuesto cuando la de siempre llega al tope del día


def tope_del_dia(codigo, mensaje):
    """Google dice que esta llave ya gastó lo del día (no que está ocupado un rato). El "por día" viene en el detalle
    ("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), no siempre en el mensaje: se mira la respuesta entera."""
    return codigo == 429 and re.search(r"per ?day", mensaje.lower()) is not None


def pedir(url, cuerpo, intentos=4, espera=25, timeout=600, hasta=None):
    """POST a Google. Reintenta sólo cuando Google está saturado (503) o pide esperar (429). Si la llave llegó al tope
    del día y hay una de repuesto, sigue con esa sin gastar un intento. `hasta` (un time.monotonic()): cada intento
    espera como mucho lo que queda hasta ahí, también el de la llave de repuesto."""
    todas = llaves.gemini()
    # PORTAVOZ_INTENTOS_GOOGLE pone un techo a los intentos de cada pedido (para las pruebas con cupo contado: cada
    # intento puede gastar uno de los pedidos del día). Sin nada, los de cada llamada.
    techo = os.environ.get("PORTAVOZ_INTENTOS_GOOGLE", "")
    if techo.isdigit() and int(techo) >= 1:
        intentos = min(intentos, int(techo))
    if not todas:
        raise Falla("DESCONOCIDO", "falta la llave de Google (GEMINI_API_KEY)")
    i = 0
    while i < intentos:
        en_uso = todas[min(_LLAVE_EN_USO[0], len(todas) - 1)]
        req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers={
            "Content-Type": "application/json", "x-goog-api-key": en_uso, "User-Agent": AGENTE})
        i += 1
        if hasta is not None:
            timeout = min(timeout, max(1, int(hasta - time.monotonic())))
        try:
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:5000]
            if tope_del_dia(e.code, msg):
                if _LLAVE_EN_USO[0] + 1 < len(todas):
                    _LLAVE_EN_USO[0] += 1
                    i -= 1
                    registro("  la llave de siempre llegó al tope del día: sigo con la de repuesto")
                    continue
                raise TopeDelDia(sin_rutas(msg)[:200])
            if e.code in (429, 503) and i < intentos:
                registro(f"  Google ocupado ({e.code}), espero {espera} s y reintento")
                time.sleep(espera)
                continue
            if e.code in (429, 503):
                raise Falla("DESCONOCIDO", f"Google está saturado ({e.code}) después de {intentos} intentos")
            raise Falla("DESCONOCIDO", f"Google contestó {e.code}: {sin_rutas(msg)[:200]}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            # Que Google no conteste a tiempo no es falta de internet (medido el 2026-11-17 a la noche: con Google
            # saturado, un pedido de una palabra tardó más de 150 s). Se reintenta y, si sigue, es DESCONOCIDO.
            if isinstance(e, TimeoutError) or isinstance(getattr(e, "reason", None), TimeoutError):
                if i < intentos:
                    registro(f"  Google no contestó en {timeout} s: reintento")
                    continue
                raise Falla("DESCONOCIDO", f"Google no contestó a tiempo ({intentos} intentos de {timeout} s)")
            raise Falla("SIN_CONEXION", f"no se pudo conectar con Google: {getattr(e, 'reason', e)}")


def texto_de_respuesta(r):
    """El texto de una respuesta de generateContent (juntando sus partes; sin las de pensamiento)."""
    try:
        partes = r["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        motivo = (r.get("candidates") or [{}])[0].get("finishReason") if isinstance(r, dict) else None
        raise Falla("DESCONOCIDO", f"Google no devolvió texto ({motivo or 'sin motivo'})")
    return "".join(p.get("text", "") for p in partes if not p.get("thought"))


def json_de_texto(texto):
    """El primer objeto JSON de un texto (Google a veces lo envuelve en ```json ... ```)."""
    texto = texto.strip()
    try:
        return json.loads(texto)
    except ValueError:
        pass
    m = re.search(r"\{.*\}", texto, flags=re.S)
    if not m:
        raise Falla("DESCONOCIDO", "Google no devolvió un JSON")
    try:
        return json.loads(m.group(0))
    except ValueError:
        raise Falla("DESCONOCIDO", "Google devolvió un JSON roto")


PROVEEDORES = ("claude", "anthropic", "google")   # el orden en que se prueban si la persona no eligió


def proveedor_texto():
    """Quién escribe los textos: lo que eligió la persona (PORTAVOZ_TEXTO en el entorno o en el .env), o el primero
    que ande en esta compu: Claude Code (la suscripción), una llave de Anthropic, o Google."""
    elegido = llaves.quien_escribe_pedido()
    if elegido in PROVEEDORES:
        return elegido
    if programa_claude():
        return "claude"
    if llaves.anthropic():
        return "anthropic"
    return "google"


def _disponible(proveedor):
    if proveedor == "claude":
        return bool(programa_claude())
    if proveedor == "anthropic":
        return bool(llaves.anthropic())
    return bool(llaves.gemini())


def respaldos(primero):
    """Los que siguen a `primero` en el orden y están disponibles: a quién se pasa si `primero` falla."""
    return [p for p in PROVEEDORES[PROVEEDORES.index(primero) + 1:] if _disponible(p)]


def _version(ruta):
    m = re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", str(ruta))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def programa_claude():
    """El programa de Claude Code de esta PC: PORTAVOZ_CLAUDE, el que esté en el PATH, o el más nuevo de VS Code."""
    elegido = os.environ.get("PORTAVOZ_CLAUDE")
    if elegido and Path(elegido).is_file():
        return elegido
    en_path = shutil.which("claude")
    if en_path:
        return en_path
    base = Path.home() / ".vscode" / "extensions"
    candidatos = [*base.glob("anthropic.claude-code-*/resources/native-binary/claude.exe"),
                  *base.glob("anthropic.claude-code-*/resources/native-binary/claude")]
    if candidatos:
        return str(max(candidatos, key=_version))
    # Donde lo deja el instalador oficial (Mac, Linux y Windows) y donde lo deja Homebrew en Mac
    for fijo in (Path.home() / ".local" / "bin" / "claude", Path.home() / ".local" / "bin" / "claude.exe",
                 Path.home() / ".claude" / "local" / "claude", Path("/opt/homebrew/bin/claude"),
                 Path("/usr/local/bin/claude")):
        if fijo.is_file():
            return str(fijo)
    return None


_SOLO_JSON = "\n\nRespondé SOLO con el objeto JSON pedido, sin texto antes ni después y sin bloque de código."


def pedir_json_claude(instrucciones, contenido, esquema, timeout=240, intentos=2, imagenes=None, modelo=None):
    """Un pedido de texto a Claude Opus 5.5 (u otro `modelo`) por Claude Code, con el cupo de la suscripción de la PC.

    Sin herramientas, sin las reglas ni la configuración del usuario (--setting-sources vacío) y sin guardar la
    charla: sólo estas instrucciones y este contenido. Devuelve el objeto JSON.
    Con `imagenes` ([(rótulo, bytes de un JPEG)]) el pedido va con el formato de entrada "stream-json" de Claude Code,
    que acepta imágenes adentro del mensaje (medido el 2026-11-18: anda, unos 4 s con una imagen).
    """
    exe = programa_claude()
    if not exe:
        raise Falla("DESCONOCIDO", "no encuentro Claude Code en esta PC para escribir los textos")
    modelo = modelo or MODELO_CLAUDE
    ultimo = "Claude no contestó"
    for intento in range(1, max(1, intentos) + 1):
        with tempfile.TemporaryDirectory(prefix="portavoz-claude-") as carpeta:
            sistema = Path(carpeta) / "instrucciones.txt"
            sistema.write_text(instrucciones + _SOLO_JSON, encoding="utf-8")
            orden = [exe, "-p", "--model", modelo, "--system-prompt-file", str(sistema), "--tools", "",
                     "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
                     "--json-schema", json.dumps(esquema, ensure_ascii=False)]
            if imagenes:
                orden += ["--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]
                entrada = json.dumps({"type": "user", "message": {"role": "user", "content": bloques_anthropic(
                    contenido, imagenes)}}, ensure_ascii=False) + "\n"
            else:
                orden += ["--output-format", "json"]
                entrada = contenido
            t = time.time()
            try:
                r = subprocess.run(orden, input=entrada, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=timeout, cwd=carpeta,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired:
                # Sin segundo intento: el Estudio corta cada paso a los 4 o 6 minutos, y dos esperas largas no entran.
                registro(f"  Claude tardó más de {timeout} s (intento {intento})")
                raise Falla("SIN_CONEXION", f"Claude tardó más de {timeout} s en contestar")
        try:
            d = _resultado_de_claude(r.stdout)
        except ValueError:
            ultimo = "Claude no devolvió una respuesta legible"
            registro(f"  {ultimo} (salida {r.returncode}): {sin_rutas((r.stderr or r.stdout)[-300:])}")
            continue
        uso = d.get("usage") or {}
        registro(f"  Claude ({modelo}) contestó en {time.time() - t:.1f} s: "
                 f"{uso.get('input_tokens', 0) + uso.get('cache_creation_input_tokens', 0) + uso.get('cache_read_input_tokens', 0)}"
                 f" de entrada, {uso.get('output_tokens', 0)} de salida")
        if d.get("is_error"):
            mensaje = str(d.get("result") or d.get("subtype") or "error")
            if re.search(r"log ?in|not logged|authenticat|api key", mensaje, re.I):
                raise Falla("DESCONOCIDO", "Claude Code no tiene la sesión abierta en esta compu")
            if re.search(r"limit|tope|quota|usage", mensaje, re.I):
                raise Falla("DESCONOCIDO", "tu plan de Claude llegó a su tope por ahora; se renueva en unas horas")
            ultimo = f"Claude dio un error: {sin_rutas(mensaje[:200])}"
            registro(f"  {ultimo} (intento {intento})")
            continue
        if isinstance(d.get("structured_output"), dict):
            return d["structured_output"]
        try:
            return json_de_texto(str(d.get("result") or ""))
        except Falla as e:
            ultimo = f"Claude: {e.detalle}"
            registro(f"  {ultimo} (intento {intento})")
    raise Falla("DESCONOCIDO", ultimo)


def _resultado_de_claude(salida):
    """La respuesta final de Claude Code: la salida entera (formato json) o el último renglón "result" (stream-json)."""
    salida = salida.strip()
    try:
        d = json.loads(salida)
        if isinstance(d, dict):
            return d
    except ValueError:
        pass
    for renglon in reversed(salida.splitlines()):
        try:
            d = json.loads(renglon)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("type") == "result":
            return d
    raise ValueError("sin respuesta final")


def bloques_anthropic(contenido, imagenes):
    """El mensaje con imágenes en la forma de Anthropic (la misma que usa Claude Code): cada imagen precedida de su
    rótulo, y al final el texto del pedido."""
    bloques = []
    for rotulo, datos in imagenes or []:
        bloques.append({"type": "text", "text": rotulo})
        bloques.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                    "data": base64.b64encode(datos).decode("ascii")}})
    bloques.append({"type": "text", "text": contenido})
    return bloques


ULTIMO_PROVEEDOR = [None]   # quién contestó el último pedido de pedir_json (para dejarlo anotado)
_HILO = threading.local()   # lo mismo, pero de este hilo: con dos pedidos a la vez el de arriba se pisa


def proveedor_de_este_hilo():
    """Quién contestó el último pedido de pedir_json hecho desde este hilo (None si ninguno o si falló)."""
    return getattr(_HILO, "proveedor", None)


def pedir_json(instrucciones, contenido, esquema, temperatura=None, timeout=180, intentos=4, imagenes=None,
               modelo=None, limite=None):
    """Un pedido de texto con respuesta JSON de forma fija. Devuelve el objeto.

    Lo escribe el primero que ande (ver proveedor_texto): Claude Opus 5.5 por Claude Code, Claude Opus 5.5 con una llave
    de Anthropic, o gemini-3.8-flash. Si el elegido falla (tope del plan, sin sesión, sin internet), pasa al siguiente
    que esté disponible y lo deja anotado en el registro. `imagenes` ([(rótulo, bytes de un JPEG)]) van con el pedido
    (los tres las aceptan).
    `modelo`: otro modelo de Claude (por ejemplo Sonnet para el revisor del guion); va a Claude Code y a la llave de
    Claude, Google sigue con el suyo. `limite`: segundos para toda la cadena de respaldo, con un solo intento por
    proveedor y cada espera recortada a lo que queda (lo usa el reloj de guiones.py). Sin los dos, todo como siempre.
    """
    primero = proveedor_texto()
    ULTIMO_PROVEEDOR[0] = None
    _HILO.proveedor = None
    hasta = time.monotonic() + limite if limite else None

    def espera(normal):
        if hasta is None:
            return normal
        return min(normal, max(1, int(hasta - time.monotonic())))

    for proveedor in [primero, *respaldos(primero)]:
        try:
            if proveedor == "claude":
                r = pedir_json_claude(instrucciones, contenido, esquema, timeout=espera(200),
                                      intentos=1 if limite else min(intentos, 2), imagenes=imagenes, modelo=modelo)
            elif proveedor == "anthropic":
                r = pedir_json_anthropic(instrucciones, contenido, esquema, timeout=espera(max(timeout, 200)),
                                         imagenes=imagenes, modelo=modelo)
            else:
                r = pedir_json_google(instrucciones, contenido, esquema, temperatura, espera(timeout),
                                      1 if limite else intentos, imagenes=imagenes, hasta=hasta)
            ULTIMO_PROVEEDOR[0] = proveedor
            _HILO.proveedor = proveedor
            return r
        except Falla as e:
            siguientes = respaldos(proveedor)
            if not siguientes:
                raise
            if hasta is not None and hasta - time.monotonic() < 5:
                registro(f"  {NOMBRES_PROVEEDOR[proveedor]} no pudo y no queda tiempo para otro")
                raise
            registro(f"  {NOMBRES_PROVEEDOR[proveedor]} no pudo ({e.detalle or e.codigo}): "
                     f"sigo con {NOMBRES_PROVEEDOR[siguientes[0]]}")

NOMBRES_PROVEEDOR = {"claude": "Claude Code", "anthropic": "la llave de Claude", "google": "Google"}


def pedir_json_google(instrucciones, contenido, esquema, temperatura=None, timeout=180, intentos=4, imagenes=None,
                      hasta=None):
    config = {"responseMimeType": "application/json", "responseSchema": esquema}
    if temperatura is not None:
        config["temperature"] = temperatura
    partes = []
    for rotulo, datos in imagenes or []:
        partes += [{"text": rotulo}, {"inline_data": {"mime_type": "image/jpeg",
                                                      "data": base64.b64encode(datos).decode("ascii")}}]
    cuerpo = {"systemInstruction": {"parts": [{"text": instrucciones}]},
              "contents": [{"role": "user", "parts": [*partes, {"text": contenido}]}],
              "generationConfig": config}
    r = pedir(f"{API}/models/{MODELO_TEXTO}:generateContent", cuerpo, intentos=intentos, espera=15, timeout=timeout,
              hasta=hasta)
    return json_de_texto(texto_de_respuesta(r))


API_ANTHROPIC = "https://api.anthropic.com/v1/messages"
_NO_SOPORTADO = ("minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum", "multipleOf", "pattern",
                 "propertyOrdering", "nullable")


def esquema_para_anthropic(esquema):
    """El esquema del motor (pensado para Google) con lo que pide la salida de forma fija de Anthropic: todo objeto
    con additionalProperties false y todos sus campos pedidos, y sin topes de largo o de número, que ahí no van."""
    if isinstance(esquema, list):
        return [esquema_para_anthropic(x) for x in esquema]
    if not isinstance(esquema, dict):
        return esquema
    limpio = {k: esquema_para_anthropic(v) for k, v in esquema.items() if k not in _NO_SOPORTADO}
    if limpio.get("type") == "object":
        limpio["additionalProperties"] = False
        limpio.setdefault("required", list(limpio.get("properties", {})))
    return limpio


def pedir_json_anthropic(instrucciones, contenido, esquema, timeout=240, imagenes=None, modelo=None):
    """Un pedido de texto a Claude Opus 5.5 con la llave de Anthropic de la persona (ANTHROPIC_API_KEY), directo y con
    lo que ya trae Python (sin instalar nada). Devuelve el objeto JSON."""
    llave = llaves.anthropic()
    if not llave:
        raise Falla("DESCONOCIDO", "falta la llave de Claude (ANTHROPIC_API_KEY)")
    modelo = modelo or MODELO_CLAUDE
    cuerpo = {"model": modelo, "max_tokens": 16000, "system": instrucciones,
              "messages": [{"role": "user", "content": bloques_anthropic(contenido, imagenes) if imagenes
                            else contenido}],
              "output_config": {"effort": "medium",
                                "format": {"type": "json_schema", "schema": esquema_para_anthropic(esquema)}},
              "fallbacks": "default"}
    req = urllib.request.Request(API_ANTHROPIC, data=json.dumps(cuerpo).encode(), headers={
        "Content-Type": "application/json", "x-api-key": llave, "anthropic-version": "2026-10-21",
        "anthropic-beta": "server-side-fallback-2026-07-01", "User-Agent": AGENTE})
    t = time.time()
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except urllib.error.HTTPError as e:
        msg = sin_rutas(e.read().decode(errors="replace")[:400])
        if e.code == 401:
            raise Falla("DESCONOCIDO", "la llave de Claude no anda: revisala en Ajustes")
        if e.code in (402, 403) or re.search(r"credit|billing", msg, re.I):
            raise Falla("DESCONOCIDO", "la cuenta de la llave de Claude no tiene saldo")
        if e.code in (429, 503, 529):
            raise Falla("DESCONOCIDO", f"Claude está ocupado ({e.code}); probá de nuevo en un rato")
        raise Falla("DESCONOCIDO", f"Claude contestó {e.code}: {msg[:200]}")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise Falla("SIN_CONEXION", f"no se pudo conectar con Claude: {getattr(e, 'reason', e)}")
    uso = r.get("usage") or {}
    registro(f"  Claude ({modelo}, con llave) contestó en {time.time() - t:.1f} s: "
             f"{uso.get('input_tokens', 0)} de entrada, {uso.get('output_tokens', 0)} de salida")
    if r.get("stop_reason") == "refusal":
        raise Falla("DESCONOCIDO", "Claude no quiso escribir sobre esta nota")
    if r.get("stop_reason") == "max_tokens":
        raise Falla("DESCONOCIDO", "Claude se quedó sin lugar para contestar")
    texto = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
    return json_de_texto(texto)


# ------------------------------------------------------------------------------------------- Palabras

# Copiado de otro programa del autor (comun.py: comparar palabras, líneas 145-197) el 2026-11-17, sin cambios.
_U = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
      "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
      "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"]
_D = {3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta", 8: "ochenta", 9: "noventa"}
_C = {1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos",
      7: "setecientos", 8: "ochocientos", 9: "novecientos"}


def _menos_de_mil(n):
    if n < 30:
        return _U[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _D[d] + ("" if u == 0 else " y " + _U[u])
    if n == 100:
        return "cien"
    c, r = divmod(n, 100)
    return _C[c] + ("" if r == 0 else " " + _menos_de_mil(r))


def numero_en_palabras(n):
    if n < 1000:
        return _menos_de_mil(n)
    if n < 1_000_000:
        m, r = divmod(n, 1000)
        return ("mil" if m == 1 else _menos_de_mil(m) + " mil") + ("" if r == 0 else " " + _menos_de_mil(r))
    mi, r = divmod(n, 1_000_000)
    base = "un millón" if mi == 1 else _menos_de_mil(mi) + " millones"
    return base + ("" if r == 0 else " " + numero_en_palabras(r))


def normalizar(palabra):
    """Minúsculas, sin signos y sin tildes; cuatrocientas = cuatrocientos."""
    p = unicodedata.normalize("NFD", palabra.lower())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    p = re.sub(r"[^a-z0-9ñ]", "", p)
    p = re.sub(r"ientas$", "ientos", p)
    return p


def palabras_normalizadas(texto):
    """Lista de (palabra normalizada) pasando los números escritos con cifras a palabras."""
    from hablado import decir_numeros  # acá adentro: hablado usa comun
    # Agregado el 2026-11-18 (no está en el otro programa): la transcripción escribe las cifras a la inglesa ("$30,000",
    # "$29,990") o con un espacio ("29 990"). Sin esto se leían "treinta coma cero" o "veintinueve novecientos
    # noventa", parecía que faltaba el "mil" y se gastaba otra voz en cada nota con dólares. Una coma seguida de
    # exactamente tres cifras es miles; un decimal de tres cifras ("2,345") se leería mal, y lo peor que pasa es otra voz.
    texto = re.sub(r"(?<![\d.,])(\d{1,3})((?:,\d{3})+)(?![\d,]|\.\d)", lambda m: m.group(1) + m.group(2).replace(",", "."),
                   texto)
    texto = re.sub(r"(?<![\d.,])(\d{1,3}) (\d{3})(?![\d,]|\.\d)", r"\1.\2", texto)
    texto = re.sub(r"(US\$|U\$S|\$)\s+(?=\d)", r"\1", texto)   # "$ 300": el signo pegado a la cifra, o se perdía "pesos"
    salida = []
    for crudo in texto.split():
        # Agregado el 2026-11-18 (no está en el otro programa): la transcripción escribe "2,2%" o "$ 300" donde la voz dijo
        # "dos coma dos por ciento"; sin esto contaba como palabras que faltan y se gastaba otra voz.
        if re.search(r"\d,\d{1,2}(?!\d)|\d\s*%|\$\s*\d", crudo):
            salida += [n for n in (normalizar(x) for x in decir_numeros(crudo).split()) if n]
            continue
        limpio = re.sub(r"[.,](?=\d{3}\b)", "", crudo)  # 20.000 o 20,000 -> 20000
        m = re.fullmatch(r"\W*(\d+)(?::00)?\W*", limpio)
        if m:
            salida += [normalizar(x) for x in numero_en_palabras(int(m.group(1))).split()]
        else:
            n = normalizar(crudo)
            if n:
                salida.append(n)
    return salida
# ---- fin de lo copiado de comun.py


def diferencias(texto_guion, palabras_transcriptas):
    """Copiado de otro programa del autor (voz.py: diferencias) el 2026-11-17. Devuelve (lista de diferencias,
    parecido de 0 a 1) y además las operaciones, para saber si falta o sobra algo (no sólo una palabra mal escrita)."""
    # Agregado el 2026-11-18: la transcripción escribe "$" tanto para pesos como para dólares, así que al comparar las
    # dos cuentan como la misma palabra (una palabra cambiada por otra igual no hacía pedir otra voz).
    def _moneda(ps):
        return ["moneda" if p in ("pesos", "dolares") else p for p in ps]
    a = _moneda(palabras_normalizadas(texto_guion))
    b = _moneda(palabras_normalizadas(" ".join(w["word"] for w in palabras_transcriptas)))
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    difs = [f"guion: '{' '.join(a[i1:i2])}'  audio: '{' '.join(b[j1:j2])}'" for op, i1, i2, j1, j2 in ops]
    return difs, sm.ratio(), ops


def es_mejor(parecido, difs, parecido_mejor, difs_mejor):
    """Copiado de otro programa del autor (voz.py: es_mejor) el 2026-11-17, sin cambios.
    Entre dos intentos gana el que más se parece al guion; el número de diferencias sólo desempata."""
    if round(parecido, 3) != round(parecido_mejor, 3):
        return parecido > parecido_mejor
    return len(difs) < len(difs_mejor)


# ------------------------------------------------------------------------------------------- Textos que salen

_EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2B00-\u2BFF\uFE0F\u200D\u20E3]")
_LINK = re.compile(r"(https?://\S+|www\.\S+)", re.I)


def sin_emojis(texto):
    return re.sub(r"[ \t]{2,}", " ", _EMOJI.sub("", texto))


def sin_rayas(texto):
    """La raya larga y la media no van nunca en lo que ve la gente (reglas de Lucio, 1.2): se cambian por una coma."""
    texto = re.sub(r"\s*[—–]\s*", ", ", texto)
    texto = re.sub(r"^,\s*", "", texto, flags=re.M)
    return re.sub(r",\s*([.,;:!?])", r"\1", texto)


def sin_links(texto):
    return _LINK.sub("", texto)
