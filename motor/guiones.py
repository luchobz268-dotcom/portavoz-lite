"""Escribe los tres guiones de una nota (uno por enfoque) con UN pedido a gemini-3.8-flash.

Uso:  python motor/guiones.py <nota.json> [--duracion 15|30|60] [--enfoque dato|te-cambia|debate]
      python motor/guiones.py <nota.json> --duracion N --enfoque X --cambiar corto|simple --texto <archivo>
             [--tramos <archivo>]

<nota.json> es un archivo con la nota (la forma de revisarNota, o {"nota": {...}} como la imprime leer_nota.py).
Imprime {"guiones": [3 guiones con la forma de revisarGuion]} y sale con 0. Con --enfoque rehace sólo ese y imprime
{"guion": {...}} (su versión tiene origen "otro"). Cada versión lleva además "tramos": [{"texto", "buscar"}], los
pedazos del guion con las búsquedas en inglés para los clips (armar.py los usa).
Con --cambiar ("Más corto" o "Más simple" del Paso 2) reescribe el guion del archivo --texto con UN pedido a Google e
imprime {"version": {...}} con origen "corto" o "simple". "corto" queda con menos palabras que el original (si Google
se pasa, se recorta acá); "simple" nunca queda más largo. Si sale el mismo texto, DESCONOCIDO.
Si falla: {"error": {...}} y 1. Códigos: SIN_CONEXION, DESCONOCIDO (Google no contestó bien).

Las fotos de la nota (Tanda B, etapa 3, 2026-11-20): si la nota trae "medios" (las fotos que juntó leer_nota.py),
el pedido de los tres guiones lleva la lista numerada y las fotos mismas (las copias chicas: el pie de un diario no
dice lo que se ve), y cada tramo puede volver con "foto" (el número de la foto sugerida). Al mismo tiempo, en otro hilo, Claude mira las fotos (mirar_clips.mirar_fotos, 90 s como mucho): las que no
sirven se sacan, y si la mirada no llega a tiempo los guiones salen sin fotos. Después va el reparto de
fotos_del_guion.py. La salida suma "fotos": lo que vio Claude, [{"n", "sirve", "encuadre", "centro"}].
"Escribir otro" (--enfoque) no vuelve a mirar: usa nota.medios[].mirada, y sin eso sale sin fotos. "Más corto" y "Más
simple" tampoco miran: con --tramos (un archivo con los tramos de antes, [{"texto", "foto"?}]) cada foto pasa a la
parte nueva que dice lo mismo. Una nota sin fotos da exactamente lo de antes, con el mismo pedido.

Qué se mide y qué no: el largo en palabras se MIDE y se corrige acá (nunca sale un guion que no entra en el largo).
Que suene humano y no invente nada se ESTIMA: las reglas van en las instrucciones y se probó con notas reales, pero
Google se puede equivocar; la persona lo lee y lo puede cambiar antes de armar.

Antes de salir, cada versión pasa por revisar_guion.py y lleva "revision" (ver ese archivo y docs/contrato.md): los
tres guiones y "Otro" con el revisor (Claude Sonnet) y el arreglo (Claude Opus) si queda tiempo; "Más corto" y "Más
simple" sólo con lo que mide el código, y el arreglo si queda tiempo. El reloj cuenta desde que arranca el programa,
porque el Estudio corta el paso de los guiones a los 360 s y los cambios a los 240 s.
"""
import argparse
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import contrato  # noqa: E402
import fotos_del_guion as FG  # noqa: E402
import mirar_clips  # noqa: E402
import revisar_guion as RG  # noqa: E402
from comun import Falla, TopeDelDia, correr, leer_json, pedir_json, registro  # noqa: E402
from hablado import limpiar_para_decir, oraciones  # noqa: E402

INICIO = time.monotonic()
# Segundos que se usan como mucho (el Estudio corta a los 360 s los guiones y a los 240 s los cambios; queda margen)
TOPE_GUIONES = 330
TOPE_CAMBIO = 240


def reloj(tope, inicio=None):
    """quedan(): los segundos que faltan para `tope`, contados desde que arrancó el programa."""
    desde = INICIO if inicio is None else inicio
    return lambda: tope - (time.monotonic() - desde)

INSTRUCCIONES = """Eres guionista de videos verticales de noticias para redes sociales (TikTok, Reels, Shorts). Escribes
lo que dice en voz alta un locutor, en castellano neutro para toda Latinoamérica, tratando al público de tú.

Reglas que no se rompen nunca:
1. Sólo hechos que están en la nota. No agregues datos, cifras, nombres, causas, consecuencias ni opiniones que la
   nota no diga. Si la nota atribuye algo a alguien ("según el ministerio", "dijo el club"), mantén la atribución.
   Usa las mismas palabras de la nota para el estado de las cosas ("secuestrados" no es "recuperados", "detenido" no
   es "condenado", "previsto" no es "hecho"). Lo que la nota dice en futuro o como posible, sigue así ("está
   previsto", "podría", "funcionará"; si la nota dice "puede reclamar", no digas "hay penalización"). Los cálculos y estimaciones que hace el medio van atribuidos ("según Infobae"). Sin
   comentarios de quien escribe ("y encima", "por fin", "lamentablemente").
2. La primera oración es el gancho: lo más fuerte o lo más útil de la noticia, en menos de 12 palabras, dicho de
   forma directa. Prohibido arrancar con "Hola", "En este video", "Atención", "Última hora", "¿Sabías que" o con una
   pregunta retórica.
3. Oraciones cortas, de 5 a 15 palabras. Un dato concreto por oración: quién, cuánto, cuándo, dónde, qué cambia.
   Sin relleno: si una oración se puede borrar sin perder nada, no va.
4. Se escribe para el oído: números, fechas y horas con letras, como se dicen ("tres millones", "el veinte por
   ciento", "el martes catorce", "a las ocho de la noche"). Redondea las cifras largas como lo diría una persona
   ("casi dos millones") sólo si la nota da la cifra exacta y el redondeo no cambia el sentido. Nada de cifras con
   números, símbolos (%, $), abreviaturas, siglas sin explicar la primera vez, links, emojis, hashtags, comillas,
   paréntesis ni rayas.
5. Palabras comunes, como le contarías la noticia a un amigo. Sin palabras de propaganda ("increíble",
   "impactante", "histórico" si la nota no lo dice, "no vas a creer"). Sin modismos de un solo país ni voseo.
6. Si hay plata, di la moneda ("pesos argentinos", "dólares") si la nota la dice.
7. No cierres con "Síguenos", "Dale like", "Comenta" ni pidas que compartan, salvo la pregunta del enfoque debate.
8. La vuelta: en redes el video se repite solo, y al terminar vuelve a empezar sin pausa. La última oración empalma
   con la primera, para que la vuelta suene a una sola frase, o a una pregunta con su respuesta, y no se note el
   corte. Elige en cada guion la forma que suene más natural con lo que cuenta. Dos que funcionan (no copies sus
   palabras):
   - la última oración queda abierta, termina en "…", y la primera la completa. Por ejemplo, "Lo que ya se sabe es
     que…" y, al volver a empezar, el gancho;
   - la última hace una pregunta que la primera contesta.
   El cierre de cada enfoque (abajo) sigue siendo el suyo: la unión va en esa misma oración o en una muy corta
   después. La primera oración sigue sirviendo sola para el que empieza a ver el video: no arranca con "y", "pero",
   "porque" ni "que", y se entiende sin la última. Leídas seguidas, la última y la primera no pueden decir nada que
   la nota no diga: si la unión dice "por eso", "porque" o "así fue como", esa causa tiene que estar en la nota. La
   última oración no se despide ni da la historia por terminada ("eso es todo", "y así quedó todo", "hasta la
   próxima"). Los tres guiones de una nota usan uniones distintas, sin repetir la misma muletilla.
   En las notas sensibles la unión es sobria: sin preguntarle al que mira qué haría o qué siente, sin intriga y sin
   nada sobre las víctimas (por ejemplo, la última dice qué se sabe hasta ahora y la primera retoma el hecho).

Los tres enfoques (el pedido te dice cuáles escribir):
- "dato": cuenta la noticia y cierra con el dato más concreto o llamativo de la nota.
- "te-cambia": cuenta la noticia y cierra con qué le cambia al que mira en su vida diaria (su bolsillo, sus
  trámites, sus horarios, los servicios que usa). Sólo lo que la nota permite decir; si no le cambia nada directo,
  cierra con lo que conviene tener en cuenta.
- "debate": cuenta la noticia y cierra con UNA pregunta corta y abierta para que la gente opine en los comentarios,
  sin tomar partido y sin dejar mal al que piense distinto. La pregunta puede quedar abierta y completarse con la
  primera oración ("¿Tú qué piensas de que…" y el gancho).
Los tres cuentan la misma noticia con distinto cierre y distinto gancho: no copies las mismas oraciones.

Tramos: divide cada guion en tramos de una o dos oraciones seguidas. Los tramos, pegados en orden con un espacio,
son el guion entero, palabra por palabra.
Para cada tramo, "buscar": de 2 a 3 búsquedas EN INGLÉS para encontrar clips de video de archivo (stock) que
acompañen lo que se dice en ese tramo. Cada búsqueda tiene de 1 a 3 palabras y nombra algo que se pueda filmar
(objetos, lugares, acciones, ambientes), sin nombres propios, marcas, países, banderas ni gente famosa. Ordénalas
de la más precisa a la más general.

Si el pedido dice que la nota es sensible (política, crimen o tragedia): tono sobrio y respetuoso, sin dramatizar,
sin adjetivos de impacto y sin detalles morbosos. En "buscar" van SÓLO ambientes y objetos (edificios, calles,
cielo, papeles, luces, rutas), NUNCA personas, caras, manos, multitudes, policías, soldados, armas, sangre, heridos
ni niños."""

ESQUEMA_TRAMOS = {"type": "array", "items": {"type": "object", "properties": {
    "texto": {"type": "string"},
    "buscar": {"type": "array", "items": {"type": "string"}},
}, "required": ["texto", "buscar"]}}

ESQUEMA = {"type": "object", "properties": {"guiones": {"type": "array", "items": {"type": "object", "properties": {
    "enfoque": {"type": "string", "enum": contrato.ENFOQUES},
    "tramos": ESQUEMA_TRAMOS,
}, "required": ["enfoque", "tramos"]}}}, "required": ["guiones"]}

# Sólo cuando la nota trae fotos: cada tramo suma "foto" (0 si ninguna). Sin fotos, el pedido es el de siempre.
ESQUEMA_TRAMOS_CON_FOTO = {"type": "array", "items": {"type": "object", "properties": {
    **ESQUEMA_TRAMOS["items"]["properties"], "foto": {"type": "integer"},
}, "required": ["texto", "buscar", "foto"]}}
ESQUEMA_CON_FOTOS = {"type": "object", "properties": {"guiones": {"type": "array", "items": {"type": "object",
    "properties": {"enfoque": {"type": "string", "enum": contrato.ENFOQUES}, "tramos": ESQUEMA_TRAMOS_CON_FOTO},
    "required": ["enfoque", "tramos"]}}}, "required": ["guiones"]}

TEMAS_DICHOS = {"politica": "política", "crimen": "crimen", "tragedia": "tragedia"}


def rango_palabras(largo):
    """(mínimo, máximo) de palabras para pedir: el máximo es lo que entra justo en el largo."""
    tope = contrato.tope_palabras(largo)
    return max(10, int(contrato.objetivo_palabras(largo) * 0.85)), tope


def pedido(nota, largo, enfoques, evitar=None, fotos=None):
    minimo, maximo = rango_palabras(largo)
    sensible = nota.get("sensible") or nota.get("tema") in contrato.TEMAS_SENSIBLES
    renglones = [
        f"Escribe {len(enfoques)} guion{'es' if len(enfoques) > 1 else ''}, uno por enfoque, en este orden: "
        + ", ".join(enfoques) + ".",
        f"Largo: video de {largo} segundos. Cada guion tiene entre {minimo} y {maximo} palabras en total (cuenta "
        "las palabras antes de contestar; pasarse del máximo no está permitido).",
        ("La nota es SENSIBLE (" + TEMAS_DICHOS[nota.get('tema')] + "): sigue la regla de las notas sensibles."
         if sensible and nota.get("tema") in TEMAS_DICHOS else
         "La nota es SENSIBLE: sigue la regla de las notas sensibles." if sensible else "La nota no es sensible."),
    ]
    if evitar:
        renglones.append("Ya hay un guion con este enfoque; escribe otro distinto (otro gancho, otras oraciones):\n"
                         + evitar)
    if fotos:
        renglones.append(FG.lista_para_pedido(fotos, nota))
    renglones += ["", f"Titular: {nota.get('titular', '')}", f"Medio: {nota.get('medio') or 'sin dato'}",
                  f"Fecha: {nota.get('fecha') or 'sin dato'}", "", "Nota:", nota.get("texto", "")]
    return "\n".join(renglones)


def limpiar_tramos(tramos, fotos=None):
    """Los tramos como los quiere el contrato. Con `fotos` (los números de las fotos de la nota), cada tramo conserva
    su "foto" si es una de ésas y no se usó antes; un número inventado o repetido se tira."""
    salida = []
    usadas = set()
    for t in tramos or []:
        # los tres puntos seguidos pasan a un solo signo "…" (la unión de la vuelta, regla 8)
        texto = limpiar_para_decir(re.sub(r"\.{3,}", "…", str(t.get("texto", ""))))
        if not texto:
            continue
        buscar = []
        for b in t.get("buscar") or []:
            b = " ".join(str(b).lower().replace("#", "").split())
            if b and b not in buscar and len(b.split()) <= 4:
                buscar.append(b)
        tramo = {"texto": texto, "buscar": buscar[:3]}
        foto = t.get("foto")
        if fotos and foto and isinstance(foto, int) and not isinstance(foto, bool):
            if foto in fotos and foto not in usadas:
                tramo["foto"] = foto
                usadas.add(foto)
            else:
                registro(f"  una parte sugirió la foto {foto}, que no está o ya se usó: se tira")
        salida.append(tramo)
    return salida


def texto_de(tramos):
    return " ".join(t["texto"] for t in tramos)


def recortar(tramos, maximo):
    """Si se pasa del máximo: se sacan tramos del medio (nunca el gancho ni el cierre) hasta que entre. Si con dos
    tramos todavía se pasa, se sacan las oraciones de adentro, de a una y empezando por el primer tramo (cualquiera
    menos la primera del guion y la última). La primera oración y la última no se tocan, porque la última empalma con la primera cuando el video
    se repite (regla 8). Sólo si con esas dos todavía se pasa, se corta el final del último tramo."""
    tramos = list(tramos)
    while contrato.contar_palabras(texto_de(tramos)) > maximo and len(tramos) > 2:
        medio = sorted(range(1, len(tramos) - 1), key=lambda i: -contrato.contar_palabras(tramos[i]["texto"]))
        tramos.pop(medio[0] if len(tramos) > 3 else 1)
    while contrato.contar_palabras(texto_de(tramos)) > maximo and tramos:
        # una oración de adentro (ni la primera del guion ni la última), empezando por el primer tramo
        sacada = False
        for i, t in enumerate(tramos):
            partes = oraciones(t["texto"])
            adentro = [j for j in range(len(partes))
                       if not (i == 0 and j == 0) and not (i == len(tramos) - 1 and j == len(partes) - 1)]
            if len(partes) >= 2 and adentro:
                del partes[adentro[0]]
                tramos[i] = {**t, "texto": " ".join(partes)}
                sacada = True
                break
        if not sacada:
            break
    while contrato.contar_palabras(texto_de(tramos)) > maximo and tramos:
        ultimo = tramos[-1]["texto"].split()
        sobra = contrato.contar_palabras(texto_de(tramos)) - maximo
        if sobra >= len(ultimo):
            tramos.pop()
        else:
            tramos[-1] = {**tramos[-1], "texto": " ".join(ultimo[:len(ultimo) - sobra]).rstrip(",;:") + "."}
    return tramos


def guion_de(nota, enfoque, tramos, origen):
    texto = texto_de(tramos)
    return {"id": f"{nota['id']}-{enfoque}", "enfoque": enfoque,
            "versiones": [{"texto": texto, "palabras": contrato.contar_palabras(texto), "origen": origen,
                           "tramos": tramos}],
            "actual": 0}


def escribir(nota, largo, enfoques, origen="propuesta", evitar=None, fotos=None):
    """Los guiones de `enfoques` con UN pedido. Con `fotos` (las de fotos_del_guion.fotos_de_la_nota) cada tramo puede
    traer la foto sugerida; el reparto lo hace quien llama, después de la mirada."""
    _, maximo = rango_palabras(largo)
    # el que escribe VE las fotos: el pie de un diario suele contar la noticia y no lo que se ve (Tesla, 20/11)
    imagenes, fotos = FG.imagenes_para_pedido(nota, fotos or [])
    numeros = {f["n"] for f in fotos}
    try:
        r = pedir_json(INSTRUCCIONES, pedido(nota, largo, enfoques, evitar, fotos),
                       ESQUEMA_CON_FOTOS if numeros else ESQUEMA, temperatura=0.7, imagenes=imagenes or None)
    except TopeDelDia:
        raise Falla("DESCONOCIDO", "no se pueden escribir más guiones por ahora (tope del día)")
    por_enfoque = {}
    for g in r.get("guiones") or []:
        if g.get("enfoque") in enfoques and g.get("enfoque") not in por_enfoque:
            por_enfoque[g["enfoque"]] = limpiar_tramos(g.get("tramos"), numeros)
    faltan = [e for e in enfoques if not por_enfoque.get(e)]
    if faltan:
        # Google devolvió menos guiones o sin enfoque: se usan en orden los que vinieron
        sobrantes = [limpiar_tramos(g.get("tramos"), numeros) for g in r.get("guiones") or []]
        sobrantes = [s for s in sobrantes if s and s not in por_enfoque.values()]
        for e in faltan:
            if not sobrantes:
                raise Falla("DESCONOCIDO", f"no se pudo escribir el guion {e}")
            por_enfoque[e] = sobrantes.pop(0)
    salida = []
    for e in enfoques:
        tramos = por_enfoque[e]
        palabras = contrato.contar_palabras(texto_de(tramos))
        if palabras > maximo:
            registro(f"  el guion {e} se pasó ({palabras} palabras, entran {maximo}): se recorta")
            tramos = recortar(tramos, maximo)
        salida.append(guion_de(nota, e, tramos, origen))
    return salida


PEDIDO_CAMBIO = {
    "corto": ("Hazlo MÁS CORTO: entre {minimo} y {maximo} palabras. Quita lo menos importante; conserva el gancho, "
              "el dato principal, el cierre del enfoque y la unión de la vuelta (la última oración empalma con la "
              "primera, regla 8)."),
    "simple": ("Hazlo MÁS SIMPLE: palabras más comunes, oraciones más cortas, una idea por oración, los mismos "
               "hechos. Entre {minimo} y {maximo} palabras. Conserva la unión de la vuelta (la última oración "
               "empalma con la primera, regla 8)."),
}


def limites_cambio(texto, largo, accion):
    """(mínimo, máximo) de palabras para "Más corto" (menos que ahora) o "Más simple" (no más que ahora)."""
    actual = contrato.contar_palabras(texto)
    tope = contrato.tope_palabras(largo)
    if accion == "corto":
        maximo = max(1, min(tope, actual - 1, int(actual * 0.8)))
        return max(1, min(maximo, int(actual * 0.6))), maximo
    maximo = max(1, min(tope, actual))
    return max(1, min(maximo, int(actual * 0.7))), maximo


def cambiar(nota, largo, enfoque, texto, accion):
    """Más corto o más simple con UN pedido a Google. Devuelve la versión nueva (con sus tramos)."""
    texto = " ".join(str(texto or "").split())
    if accion not in PEDIDO_CAMBIO:
        raise Falla("DESCONOCIDO", "el cambio tiene que ser corto o simple")
    if not texto:
        raise Falla("DESCONOCIDO", "no hay texto para cambiar")
    if accion == "corto" and contrato.contar_palabras(texto) < 2:
        raise Falla("DESCONOCIDO", "ya no se puede acortar")
    minimo, maximo = limites_cambio(texto, largo, accion)
    # Del pedido de siempre quedan la regla de las notas sensibles y la nota (sin el largo, que acá es otro)
    base = pedido(nota, largo, [enfoque]).split("\n", 2)
    renglones = [f"Reescribe este guion del enfoque {enfoque}. " + PEDIDO_CAMBIO[accion].format(minimo=minimo,
                                                                                                maximo=maximo),
                 "Guion actual:", texto, base[2] if len(base) > 2 else ""]
    try:
        r = pedir_json(INSTRUCCIONES, "\n".join(renglones), ESQUEMA, temperatura=0.5)
    except TopeDelDia:
        raise Falla("DESCONOCIDO", "no se pueden escribir más guiones por ahora (tope del día)")
    lista = [limpiar_tramos(g.get("tramos")) for g in r.get("guiones") or []]
    tramos = next((t for t in lista if t), None)
    if not tramos:
        raise Falla("DESCONOCIDO", "no se pudo reescribir el guion")
    if contrato.contar_palabras(texto_de(tramos)) > maximo:
        registro(f"  el guion {accion} se pasó: se recorta a {maximo} palabras")
        tramos = recortar(tramos, maximo)
    nuevo = texto_de(tramos)
    if " ".join(nuevo.split()) == texto:
        raise Falla("DESCONOCIDO", "el cambio dio el mismo texto")
    return guion_de(nota, enfoque, tramos, accion)["versiones"][0]


MARGEN_MIRADA = 5   # segundos que se le esperan a la mirada después de su límite (el pedido corta solo)


class Mirada:
    """La mirada de las fotos en otro hilo, al mismo tiempo que se escriben los guiones. esperar() devuelve
    {n: {"sirve", "encuadre", "centro"}}, o None si no llegó a tiempo o falló (los guiones salen sin fotos)."""

    def __init__(self, nota, fotos, limite=None):
        self.limite = limite or mirar_clips.LIMITE_FOTOS
        self.desde = time.monotonic()
        self.resultado = None
        self.hilo = threading.Thread(target=self._mirar, args=(nota, fotos), daemon=True)
        self.hilo.start()

    def _mirar(self, nota, fotos):
        try:
            self.resultado = mirar_clips.mirar_fotos(nota, fotos, limite=self.limite)
        except Exception as e:   # noqa: BLE001  (la mirada nunca frena los guiones)
            registro(f"  las fotos no se pudieron mirar ({getattr(e, 'detalle', '') or type(e).__name__}): "
                     "los guiones salen sin fotos")

    def esperar(self):
        self.hilo.join(timeout=max(0.0, self.limite + MARGEN_MIRADA - (time.monotonic() - self.desde)))
        if self.hilo.is_alive():
            registro(f"  la mirada de las fotos pasó de {self.limite} s: los guiones salen sin fotos")
            return None
        return self.resultado


def miradas_guardadas(fotos):
    """Lo que ya se miró y guardó el Estudio en la nota (nota.medios[].mirada), para "Escribir otro"."""
    salida = {}
    for f in fotos:
        m = f.get("mirada")
        if (isinstance(m, dict) and isinstance(m.get("sirve"), bool) and m.get("encuadre") in contrato.ENCUADRES
                and isinstance(m.get("centro"), (int, float))):
            salida[f["n"]] = m
    return salida


def leer_tramos(ruta, fotos):
    """Los tramos de antes que manda el Estudio con --tramos: [{"texto", "foto"?}], sólo con fotos de la nota."""
    if not ruta:
        return []
    try:
        datos = leer_json(ruta)
    except (OSError, ValueError):
        registro("  no se pudieron leer los tramos de antes: el cambio sale sin fotos")
        return []
    numeros = {f["n"] for f in fotos}
    salida = []
    for t in datos if isinstance(datos, list) else []:
        if not isinstance(t, dict):
            continue
        tramo = {"texto": str(t.get("texto") or "")[:2000]}
        if t.get("foto") in numeros and not isinstance(t.get("foto"), bool):
            tramo["foto"] = t["foto"]
        salida.append(tramo)
    return salida


def principal():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("nota")
    p.add_argument("--duracion", type=int, default=contrato.LARGO_INICIAL)
    p.add_argument("--enfoque")
    p.add_argument("--evitar", help="archivo con el texto del guion anterior de ese enfoque (para no repetirlo)")
    p.add_argument("--cambiar", choices=["corto", "simple"])
    p.add_argument("--texto", help="archivo con el guion a cambiar (con --cambiar)")
    p.add_argument("--tramos", help="archivo con los tramos de antes, con sus fotos (con --cambiar)")
    try:
        a = p.parse_args(sys.argv[1:])
    except SystemExit:
        raise Falla("DESCONOCIDO", "uso: guiones.py <nota.json> [--duracion 15|30|60] [--enfoque X]")
    if a.duracion not in contrato.LARGOS:
        raise Falla("DESCONOCIDO", f"el largo tiene que ser uno de {contrato.LARGOS}")
    if a.enfoque and a.enfoque not in contrato.ENFOQUES:
        raise Falla("DESCONOCIDO", f"el enfoque tiene que ser uno de {contrato.ENFOQUES}")
    try:
        datos = leer_json(a.nota)
    except (OSError, ValueError):
        raise Falla("DESCONOCIDO", "no se pudo leer el archivo de la nota")
    nota = datos.get("nota", datos)
    if not nota.get("texto") or not nota.get("id"):
        raise Falla("DESCONOCIDO", "la nota no tiene texto o id")
    fotos = FG.fotos_de_la_nota(nota)
    if a.cambiar:
        if not a.enfoque or not a.texto:
            raise Falla("DESCONOCIDO", "--cambiar necesita --enfoque y --texto")
        try:
            texto = Path(a.texto).read_text(encoding="utf-8-sig")
        except OSError:
            raise Falla("DESCONOCIDO", "no se pudo leer el guion a cambiar")
        version = cambiar(nota, a.duracion, a.enfoque, texto, a.cambiar)
        no_sirven = {n for n, m in miradas_guardadas(fotos).items() if not m["sirve"]}
        viejos = [t for t in leer_tramos(a.tramos, fotos) if t.get("foto") not in no_sirven]
        version["tramos"] = FG.reubicar(viejos, version["tramos"])
        rango = limites_cambio(" ".join(texto.split()), a.duracion, a.cambiar)
        return {"version": RG.revisar_cambio(nota, a.enfoque, version, rango, reloj(TOPE_CAMBIO))}
    rango = rango_palabras(a.duracion)
    if a.enfoque:
        evitar = None
        if a.evitar:
            try:
                evitar = Path(a.evitar).read_text(encoding="utf-8-sig")[:2000]
            except OSError:
                evitar = None
        miradas = miradas_guardadas(fotos)
        sirven = [f for f in fotos if miradas.get(f["n"], {}).get("sirve")]
        guion = escribir(nota, a.duracion, [a.enfoque], origen="otro", evitar=evitar, fotos=sirven)
        FG.repartir(guion[0]["versiones"][0]["tramos"], {f["n"] for f in sirven})
        return {"guion": RG.revisar_guiones(nota, guion, rango, reloj(TOPE_GUIONES))[0]}
    mirada = Mirada(nota, fotos) if fotos else None
    guiones = escribir(nota, a.duracion, list(contrato.ENFOQUES), fotos=fotos)
    miradas = mirada.esperar() if mirada else None
    sirven = {n for n, m in (miradas or {}).items() if m["sirve"]}
    for g in guiones:
        FG.repartir(g["versiones"][0]["tramos"], sirven)
    salida = {"guiones": RG.revisar_guiones(nota, guiones, rango, reloj(TOPE_GUIONES))}
    if miradas:
        salida["fotos"] = [{"n": n, **miradas[n]} for n in sorted(miradas)]
    return salida


if __name__ == "__main__":
    sys.exit(correr(principal))
