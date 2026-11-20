"""Revisa los guiones contra la nota antes de mostrarlos, y arregla una vez lo que no puede salir así.

No es un programa aparte: lo llama guiones.py (los tres guiones, "Otro" y "Más corto" / "Más simple").

Cómo va:
1. El código mira cada guion (gratis, se MIDE): C1 el largo, C2 que cada número y cada nombre propio esté en la nota,
   C3 sin links, emojis, rayas ni numerales, C4 la primera frase corta, C5 que no cuente como hecho algo que la nota
   dice que va a pasar ("funcionará" en la nota, "funciona" en el guion), C6 la vuelta (la última frase no se despide
   y la primera no arranca colgada con "Y…") y C7 que las tres uniones no usen la misma muletilla.
2. Como en otro programa del autor (Lucio, 2026-11-20), salen AL
   MISMO TIEMPO dos pedidos a Claude Sonnet (se ESTIMA):
   - el panel, que lee la nota y los tres guiones juntos (R1 a R13): fidelidad, gancho, lo que se entiende a los 3
     segundos, qué suma cada frase, cierre según el enfoque, tono, la vuelta, que suene a persona y que las uniones
     no se repitan. Cada duda dice si es una pregunta buscada (se deja) o una confusión.
   - los espectadores de prueba, que NO ven la nota (el que revisa no sabe más que el que mira): tres perfiles que
     dicen qué entendieron, qué no, dónde se irían y si se nota el corte en la vuelta. La junta la hace el código.
   Si alguno falla o tarda, sigue el otro; si fallan los dos, los guiones salen igual, con lo que vio el código.
3. Si un guion quedó marcado (un dato que no está en la nota, un verbo cambiado o un gancho de relleno), Claude Opus lo
   arregla con UN pedido para todos los marcados, una sola vuelta, junto con los puntos "importante" del panel, de
   los espectadores y de la vuelta. Un guion que sólo tiene puntos "importante" entra en ese mismo pedido si sobra
   tiempo (Lucio, 2026-11-18). El código vuelve a medir el arreglo: si se pasa del largo, trae un dato o un verbo que
   el original no tenía, rompe la vuelta, o tiene menos futuros que el original ("funcionará" que pasó a "circula"),
   queda el original.
4. Lo que no se pudo arreglar queda como aviso: DATO_NO_ESTA o VERBO_CAMBIADO (AVISOS_REVISION del contrato).

Cada versión revisada lleva "revision": {"puntos": [textos], "arreglado", "aviso", "quien", "antes"?, "arreglados"?}.
Después de un arreglo, "arreglados" son los puntos que se mandaron a arreglar, y los puntos del revisor que quedan
empiezan con "Antes del arreglo: " (hablan del texto de antes y de sus tramos).
"""
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun  # noqa: E402
import contrato  # noqa: E402
from comun import Falla, TopeDelDia, pedir_json, registro, sin_emojis  # noqa: E402
from hablado import decir_numeros, oraciones  # noqa: E402

MODELO_REVISOR = "claude-sonnet-5-5"
TOPE_PRIMERA_FRASE = 14
TOPE_PUNTOS = 8   # como cada revisor del otro programa del autor
GRAVEDADES = ["marca", "importante", "menor"]
CRITERIOS_REVISOR = [f"R{i}" for i in range(1, 14)]

# ------------------------------------------------------------------------------------------- Números (C2)

_UNIDADES = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
    "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100,
    "doscientos": 200, "doscientas": 200, "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
    "cuatrocientas": 400, "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600,
    "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800, "novecientos": 900,
    "novecientas": 900,
}
_ESCALAS = {"mil": 1_000, "millon": 1_000_000, "millones": 1_000_000, "billon": 10 ** 12, "billones": 10 ** 12}
_ARTICULOS = {"un", "uno", "una"}
# "casi dos millones" por 1.950.000: con estas palabras delante, el número puede estar redondeado
_APROXIMA = ("casi", "unos", "unas", "mas de", "menos de", "cerca de", "alrededor de", "aproximadamente",
             "poco mas de", "poco menos de", "hasta")
_MONEDAS = r"(dólares|pesos|euros|reales)"


def sin_tildes(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _palabras(texto, cortes=False):
    """Las palabras sin signos (los signos se cambian por espacios), en minúscula y sin tildes. Con `cortes`, una coma
    o un punto quedan como "|", para que "treinta mil, dos mil" no se lea como un solo número."""
    t = sin_tildes(texto)
    if cortes:
        t = re.sub(r"[,.;:!?¿¡()]", " | ", t)
    return re.sub(r"[^\w|]+", " ", t).split()


def _valor(fichas):
    """El valor de una tira de palabras de número ya separada ('dos millones trescientos mil' -> 2300000)."""
    total = actual = 0
    for f in fichas:
        if f in _UNIDADES:
            actual += _UNIDADES[f]
        elif f == "mil":
            actual = max(actual, 1) * 1000
        elif f in _ESCALAS:
            total += max(actual, 1) * _ESCALAS[f]
            actual = 0
    return total + actual


def numeros_dichos(texto):
    """[(valor, palabras que lo dicen, posición)] de cada número dicho en palabras ('tres coma cinco millones',
    'un millón y medio', 'medio millón'). Un 'un' o 'una' solos son artículos y no cuentan. La posición cuenta las
    comas y los puntos como una palabra más ("|")."""
    p = _palabras(texto, cortes=True)
    salida, i = [], 0
    while i < len(p):
        es_numero = p[i] in _UNIDADES or p[i] in _ESCALAS
        if p[i] in ("cien", "ciento") and i > 0 and p[i - 1] == "por":   # "por ciento" no es un número
            es_numero = False
        medio = p[i] == "medio" and i + 1 < len(p) and p[i + 1] in _ESCALAS
        if not es_numero and not medio:
            i += 1
            continue
        inicio, fichas, decimales, escala_final = i, [], [], 1
        if medio:
            salida.append((0.5 * _ESCALAS[p[i + 1]], " ".join(p[i:i + 2]), i))
            i += 2
            continue
        while i < len(p):
            f = p[i]
            if f in ("cien", "ciento") and i > 0 and p[i - 1] == "por":
                break
            if f in _UNIDADES or f in _ESCALAS:
                fichas.append(f)
                i += 1
            elif f == "y" and i + 1 < len(p) and p[i + 1] in _UNIDADES and fichas and fichas[-1] not in _ESCALAS:
                i += 1   # "treinta y cinco"
            elif f == "coma" and i + 1 < len(p) and p[i + 1] in _UNIDADES:
                i += 1
                while i < len(p) and p[i] in _UNIDADES:
                    decimales.append(p[i])
                    i += 1
                while i < len(p) and p[i] in _ESCALAS:   # "dos coma cinco millones"
                    escala_final *= _ESCALAS[p[i]]
                    i += 1
                break
            else:
                break
        valor = _valor(fichas)
        if decimales:
            cifras = ("".join(str(_UNIDADES[d]) for d in decimales) if decimales[0] == "cero"
                      else str(_valor(decimales)))
            valor = (valor + float("0." + cifras)) * escala_final
        # "un millón y medio", "dos horas y media" no (ahí "horas" corta la tira)
        if i + 1 < len(p) and p[i] == "y" and p[i + 1] in ("medio", "media"):
            ultima = next((_ESCALAS[f] for f in reversed(fichas) if f in _ESCALAS), 1) * escala_final
            valor += 0.5 * ultima
            i += 2
        dicho = " ".join(p[inicio:i])
        if fichas and all(f in _ARTICULOS for f in fichas) and not decimales:
            continue   # "un hombre", "una medida"
        salida.append((valor, dicho, inicio))
    return salida


def numeros_de_la_nota(nota):
    """Los valores de todos los números de la nota (titular, medio y texto), pasados a palabras como en el guion."""
    texto = " ".join(str(nota.get(c) or "") for c in ("titular", "medio", "texto"))
    dicho = decir_numeros(texto)
    # "US$ 1,5 millones" queda "uno coma cinco dólares millones": la moneda va después de la escala
    dicho = re.sub(_MONEDAS + r"\s+(mil millones|millones|millón|mil)\b", r"\2 \1", dicho)
    return [v for v, _, _ in numeros_dichos(dicho)]


def _esta_el_numero(valor, de_la_nota, aproximado):
    for n in de_la_nota:
        if abs(n - valor) <= max(0.001, abs(n) * 0.005):
            return True
        if aproximado and n and abs(n - valor) <= abs(n) * 0.15:
            return True
        if valor <= 12 and float(valor).is_integer() and abs(n - (valor + 12)) < 0.001:
            return True   # "las ocho de la noche" por "20 h"
    return False


# ------------------------------------------------------------------------------------------- Nombres (C2)

def nombres_propios(texto):
    """[(palabra, número de oración)] de las palabras con mayúscula que no arrancan una oración."""
    salida = []
    for n, o in enumerate(oraciones(texto)):
        arranque = True
        for crudo in re.split(r"(\s+)", o):
            limpio = re.sub(r"^[¿¡\"'«(]+|[^\w]+$", "", crudo)
            if not limpio:
                continue
            if not arranque and limpio[:1].isupper() and not limpio.isdigit():
                salida.append((limpio, n))
            arranque = crudo.rstrip().endswith((":", ".", "?", "!"))
    return salida


# Una sigla de 2 a 6 mayúsculas al principio de una palabra, aunque venga pegada a la siguiente ("PROy" -> "PRO").
_SIGLA = re.compile(r"(?<![^\W\d_])([A-ZÁÉÍÓÚÑ]{2,6})(?![A-ZÁÉÍÓÚÑ])")
_UNEN_NOMBRES = {"de", "del", "la", "las", "los", "el"}   # "Partido de la Costa" es un solo nombre


# palabras comunes que en un titular escrito todo en mayúscula parecerían siglas
_NO_SON_SIGLAS = {"EL", "LA", "LOS", "LAS", "DE", "DEL", "EN", "UN", "UNA", "CON", "POR", "QUE", "SE", "SU", "SUS",
                  "AL", "ES", "NO", "YA", "MAS", "LO", "LE", "LES", "MUY", "HAY", "SIN", "PARA"}


def siglas_de(texto):
    """Las siglas de un texto, en mayúscula y sin tildes."""
    return {sin_tildes(s).upper() for s in _SIGLA.findall(str(texto))} - _NO_SON_SIGLAS


def nombres_por_sigla(texto, siglas):
    """Las palabras (sin tildes) de los nombres de varias palabras con mayúscula que explican una sigla de la nota:
    sus iniciales son la sigla ("Unión Cívica Radical" por UCR) o la sigla es el principio de la primera palabra
    ("Propuesta Republicana" por PRO; sólo con siglas de 3 letras o más, para que un "EL" de un titular en mayúscula
    no tape un nombre inventado). El pedido de guiones obliga a explicar las siglas, así que esto no es un dato nuevo."""
    aceptadas = set()

    def cerrar(nombre):
        # se prueban los tramos del nombre, porque delante puede ir otra palabra con mayúscula ("La Unión Cívica
        # Radical" al arrancar una oración, "Según Propuesta Republicana")
        palabras = [sin_tildes(p) for p in nombre]
        for i in range(len(palabras) - 1):
            if any(len(s) >= 3 and palabras[i].upper().startswith(s) for s in siglas):
                aceptadas.update(palabras[i:])
            for j in range(i + 2, len(palabras) + 1):
                if "".join(p[0] for p in palabras[i:j]).upper() in siglas:
                    aceptadas.update(palabras[i:j])

    nombre = []
    for ficha in re.findall(r"\w+|[^\w\s]", str(texto)):
        if ficha[:1].isupper() and not ficha.isdigit():
            nombre.append(ficha)
        elif nombre and ficha.lower() in _UNEN_NOMBRES:
            continue
        else:
            cerrar(nombre)
            nombre = []
    cerrar(nombre)
    return aceptadas


# ------------------------------------------------------------------------------------------- Verbos (C5)

# Con una de estas palabras delante, lo que se escribe igual que un presente es un sustantivo: "la mejora",
# "la entrega", "el paga" no, pero "su paga" sí. Eso tapa la mayoría de los sustantivos sin una lista de palabras.
DETERMINANTES = {"el", "la", "los", "las", "un", "una", "unos", "unas", "su", "sus", "esta", "este", "esa", "ese",
                 "cada", "del", "al", "lo"}
# Los sustantivos que suelen ir SIN artículo ("en parte", "hace falta", "en busca de", "sin duda", "tren de carga",
# "a costa de"): ahí el filtro de arriba no alcanza.
NO_SON_VERBOS = {"parte", "forma", "falta", "baja", "alza", "espera", "casa", "suma", "busca", "costa", "ayuda",
                 "duda", "obra", "carga", "visita"}
# Futuro regular: raíz + a/e/i + "rá" o "rán", y el presente se arma con la misma raíz. Por eso sólo ve los verbos
# regulares que no cambian la raíz: "costará" da "costa" y no "cuesta", "volverá" da "volve" y no "vuelve" (esos no
# se marcan). Los irregulares tampoco: tendrá, podrá, saldrá, habrá, sabrá, querrá no tienen vocal antes de la r, y
# hará, dirá, será, irá, dará, verá tienen raíz de una letra, que no se marca. "Estará" tampoco: su presente lleva
# tilde ("está") y lo que daría la regla, "esta", es otra palabra ("esta medida").
_FUTURO = re.compile(r"\b(\w+?)([aei])r(á|án)\b")


def presentes_de_futuros(texto_nota):
    """{presente: futuro} de los futuros regulares de la nota: "funcionará" -> "funciona", "operarán" -> "operan"."""
    salida = {}
    for m in _FUTURO.finditer(str(texto_nota).lower()):
        raiz, vocal, final = m.group(1), m.group(2), m.group(3)
        futuro = m.group(0)
        if len(raiz) < 2 or raiz == "est":
            continue
        presente = raiz + ("a" if vocal == "a" else "e") + ("n" if final == "án" else "")
        if presente in NO_SON_VERBOS:
            continue
        salida.setdefault(presente, futuro)
    return salida


def _como_verbo(palabra, texto):
    """Si `palabra` aparece en `texto` (en minúscula) sin un artículo o determinante justo delante."""
    for m in re.finditer(r"(?<!\w)" + re.escape(palabra) + r"(?!\w)", texto):
        antes = re.findall(r"\w+", texto[:m.start()][-30:])
        if not antes or antes[-1] not in DETERMINANTES:
            return True
    return False


def verbos_cambiados(texto_guion, texto_nota):
    """[(presente, futuro)] de lo que el guion cuenta en presente y la nota sólo en futuro."""
    nota = str(texto_nota).lower()
    guion = str(texto_guion).lower()
    salida = []
    for presente, futuro in presentes_de_futuros(nota).items():
        if _como_verbo(presente, guion) and not _como_verbo(presente, nota):
            salida.append((presente, futuro))
    return salida


_POSIBLE = re.compile(
    r"\b(puede|pueden|podría|podrían|podrá|podrán|está previst[oa]s?|están previst[oa]s|se prevé|prevé|se espera|"
    r"se esperan|planea|planean|busca|buscan|apunta a|apuntan a|estiman?|proyecta|proyectan)\b"
    r"|\b\w{2,}r(á|án)\b|\b\w{2,}(aría|ería|iría|dría)n?\b", re.I)
_NO_CONDICIONAL = {"lotería", "relojería", "galería", "batería", "minería", "ingeniería", "panadería", "librería",
                   "cafetería", "carnicería", "ferretería", "joyería", "lavandería", "pizzería", "cervecería",
                   "tesorería", "secretaría", "sastrería", "frutería", "mensajería", "peluquería", "zapatería"}


def frases_de_futuro(nota, tope=12):
    """Las oraciones de la nota que dicen algo que va a pasar o que es posible (futuros, condicionales, "puede",
    "está previsto"...): van al revisor, para que no las deje pasar como hechos."""
    salida = []
    for o in oraciones(nota.get("texto", "")):
        encontradas = [m.group(0).lower() for m in _POSIBLE.finditer(o)]
        if any(e not in _NO_CONDICIONAL for e in encontradas):
            salida.append(o[:300])
        if len(salida) >= tope:
            break
    return salida


# Futuros de cualquier verbo, regulares e irregulares ("funcionará", "tendrán", "podremos"), y el futuro con "ir a"
# ("va a funcionar"), para ver si el arreglo pasó algo que va a pasar a algo que ya pasa (18/11, nota del Cybercab:
# "sólo funcionará en zonas autorizadas" quedó "sólo circula en zonas habilitadas" y C5 no lo vio, porque cambió
# también el verbo). Con tilde: "ahora" no cuenta. Con un artículo delante es un sustantivo y tampoco cuenta.
_FUTURO_CUALQUIERA = re.compile(r"(?<!\w)(\w+r(?:á|án|emos)|(?:va|van|vamos) a \w*(?:ar|er|ir))(?!\w)")
NO_SON_FUTUROS = {"extremos", "supremos", "remos"}


def contar_futuros(texto):
    """Cuántas formas de futuro tiene el texto (ver _FUTURO_CUALQUIERA)."""
    texto = str(texto).lower()
    cuenta = 0
    for m in _FUTURO_CUALQUIERA.finditer(texto):
        if m.group(1) in NO_SON_FUTUROS:
            continue
        antes = re.findall(r"\w+", texto[:m.start()][-30:])
        if antes and antes[-1] in DETERMINANTES:
            continue
        cuenta += 1
    return cuenta


# ------------------------------------------------------------------------------------------- Lo que mide el código

def _punto(criterio, tramo, gravedad, problema, arreglo=""):
    return {"criterio": criterio, "tramo": tramo, "gravedad": gravedad, "problema": problema, "arreglo": arreglo}


def _tramo_de(tramos, palabra):
    clave = sin_tildes(palabra)
    for i, t in enumerate(tramos):
        if re.search(r"(?<!\w)" + re.escape(clave) + r"(?!\w)", sin_tildes(t["texto"])):
            return i + 1
    return 0


def chequeos(nota, tramos, rango):
    """Lo que mide el código (C1 a C5) en un guion partido en tramos. `rango` = (mínimo, máximo) de palabras."""
    texto = " ".join(t["texto"] for t in tramos)
    puntos = []
    minimo, maximo = rango
    palabras = contrato.contar_palabras(texto)
    if palabras > maximo or palabras < minimo:
        puntos.append(_punto("C1", 0, "importante", f"tiene {palabras} palabras y van de {minimo} a {maximo}"))
    # C2: números
    de_la_nota = numeros_de_la_nota(nota)
    for valor, dicho, pos in numeros_dichos(texto):
        if valor <= 2 and len(dicho.split()) == 1:
            continue   # "dos" suelto casi siempre es "los dos", "ambos": lo mira el revisor
        antes = " ".join(_palabras(texto, cortes=True)[max(0, pos - 3):pos])
        aproximado = any(re.search(r"(?<!\w)" + a + r"$", antes) for a in _APROXIMA)
        if not _esta_el_numero(valor, de_la_nota, aproximado):
            puntos.append(_punto("C2", _tramo_de(tramos, dicho), "marca",
                                 f'el número "{dicho}" no está en la nota', "usar sólo números de la nota"))
    # C2: nombres propios
    toda_la_nota = " ".join(str(nota.get(c) or "") for c in ("titular", "medio", "texto"))
    en_la_nota = set(_palabras(toda_la_nota)) | nombres_por_sigla(texto, siglas_de(toda_la_nota))
    vistos = set()
    for nombre, _ in nombres_propios(texto):
        clave = sin_tildes(nombre)
        if clave in vistos:
            continue
        vistos.add(clave)
        if not all(parte in en_la_nota for parte in _palabras(nombre)):
            puntos.append(_punto("C2", _tramo_de(tramos, nombre), "marca",
                                 f'el nombre "{nombre}" no está en la nota', "usar sólo nombres de la nota"))
    # C3: lo que no se puede decir en voz alta
    if (re.search(r"https?://|www\.|\.(com|org|net)\b|[#%$\d]|[—–]", texto) or sin_emojis(texto) != texto):
        puntos.append(_punto("C3", 0, "importante", "tiene links, emojis, rayas, símbolos o números escritos con cifras"))
    # C4: la primera frase
    primera = (oraciones(texto) or [""])[0]
    if contrato.contar_palabras(primera) > TOPE_PRIMERA_FRASE:
        puntos.append(_punto("C4", 1, "importante",
                             f"la primera frase tiene {contrato.contar_palabras(primera)} palabras (tope "
                             f"{TOPE_PRIMERA_FRASE})"))
    # C5: verbos
    for presente, futuro in verbos_cambiados(texto, nota.get("texto", "")):
        puntos.append(_punto("C5", _tramo_de(tramos, presente), "marca",
                             f'dice "{presente}" y la nota dice "{futuro}": todavía no pasó',
                             f'decirlo como la nota, "{futuro}"'))
    puntos += chequeo_vuelta(tramos)
    return puntos


# ------------------------------------------------------------------------------------------- La vuelta (C6 y C7)
# El video se repite solo en redes y la última oración empalma con la primera (regla 8 de guiones.py). Que la unión
# suene natural se ESTIMA (lo miran el panel y los espectadores); acá se MIDE lo que se puede: que no se despida, que
# la primera oración sirva sola y que las tres versiones no usen la misma muletilla.

DESPEDIDAS = ("hasta la proxima", "nos vemos", "siguenos", "sigueme", "dale like", "suscribete", "gracias por ver",
              "eso es todo", "asi quedo todo", "fin de la historia", "comparte este video", "comparte esta noticia")
ARRANQUES_QUE_DEPENDEN = {"y", "pero", "porque", "que", "entonces", "ademas", "tambien", "asi"}


def _palabras_sueltas(frase):
    return re.findall(r"\w+", sin_tildes(frase))


def chequeo_vuelta(tramos):
    """C6: la última oración no se despide y la primera no arranca colgada de la anterior ("Y…", "Porque…")."""
    partes = oraciones(" ".join(t["texto"] for t in tramos))
    if not partes:
        return []
    puntos = []
    ultima = " ".join(_palabras_sueltas(partes[-1]))
    for d in DESPEDIDAS:
        if re.search(r"(?<!\w)" + d + r"(?!\w)", ultima):
            puntos.append(_punto("C6", len(tramos), "importante",
                                 f'la última frase se despide ("{d}") y corta la vuelta',
                                 "que la última frase empalme con la primera"))
            break
    primera = _palabras_sueltas(partes[0])
    if primera and primera[0] in ARRANQUES_QUE_DEPENDEN:
        puntos.append(_punto("C6", 1, "importante",
                             f'la primera frase arranca con "{primera[0]}" y no se entiende sola la primera vez',
                             "que la primera frase arranque con el hecho"))
    return puntos


def chequeo_uniones(items):
    """C7: {id: [puntos]} para las versiones cuya última oración empieza o termina con las mismas tres palabras que
    la de otra versión anterior de la misma nota (la misma muletilla en las tres uniones)."""
    salida = {it["id"]: [] for it in items}
    vistas = []
    for it in items:
        partes = oraciones(it["version"]["texto"])
        palabras = _palabras_sueltas(partes[-1]) if partes else []
        if len(palabras) < 3:
            continue
        inicio, final = palabras[:3], palabras[-3:]
        for enfoque, otro_inicio, otro_final in vistas:
            if otro_inicio == inicio or otro_final == final:
                repetido = " ".join(inicio if otro_inicio == inicio else final)
                salida[it["id"]].append(_punto(
                    "C7", len(it["version"]["tramos"]), "importante",
                    f'la unión de la vuelta repite "{repetido}", igual que el guion {enfoque}',
                    "otra forma de unir la última frase con la primera"))
                break
        vistas.append((it["enfoque"], inicio, final))
    return salida


def _clave(p):
    return (p["criterio"], p["problema"])


# ------------------------------------------------------------------------------------------- El revisor (Sonnet)

INSTRUCCIONES_REVISOR = """Revisas guiones de videos verticales de noticias (lo que dice un locutor en 15 a 60
segundos) antes de que los vea la persona que los va a publicar. Comparas cada guion con la nota y marcas sólo los
problemas de verdad. Si un guion está bien, no le pongas puntos. El video se repite solo en redes: al terminar vuelve a
empezar sin pausa, así que la última frase se escucha pegada a la primera (te paso cómo suena cada vuelta).

Criterios:
- R1 Fidelidad: no dice nada que la nota no diga, incluida una pregunta o insinuación que da a entender algo que la
  nota no dice; no exagera, no cambia quién dijo qué ni si ya pasó o va a pasar. Lo que la nota cuenta en futuro o
  como posible ("funcionará", "podría", "está previsto") no puede aparecer como hecho. Te paso aparte esas frases de
  la nota. Vale también para la vuelta: leídas seguidas, la última frase y la primera no pueden decir algo que la
  nota no dice (un "por eso" o un "porque" que inventa una causa).
- R2 Gancho (0 a 2 segundos): la primera frase trae el hecho más fuerte o qué le cambia al que mira, y deja una sola
  pregunta concreta en la cabeza. Saludos, "atención", "hoy te cuento" o ambientación son relleno.
- R3 A los 3 segundos se entiende qué pasó, a quién y por qué importa.
- R4 Entre los 2 y los 5 segundos hay algo concreto: un número, un nombre o un lugar de la nota.
- R5 Cada frase suma algo nuevo; nada se dice dos veces. Frase por frase hasta los 10 segundos (unas 25 palabras):
  ¿qué recibe de nuevo el que mira? Ningún tramo de más de 8 a 10 segundos (unas 20 a 25 palabras) sin algo nuevo.
- R6 Lo que se nombra como conocido se presentó antes ("la medida", "el proyecto" sin decir cuál). Tampoco depende de
  saber cosas de un solo país (una sigla, un cargo, un lugar) sin explicarlas.
- R7 La promesa se paga: el gancho no promete algo que el guion no cuenta.
- R8 El cierre según el enfoque: "dato" cierra con el dato que queda; "te-cambia", con qué hacer o qué mirar;
  "debate", con una pregunta con dos lados defendibles que no deja mal al que opina distinto, aunque la nota sea de
  política. La pregunta no puede suponer hechos fuera de la nota (eso es R1). La frase final no es una obviedad ni
  una moraleja: si se le puede poner "por eso" adelante y suena a sermón o a algo que cualquiera ya sabía, no sirve.
- R9 Tono en notas delicadas: sin morbo ni palabras de impacto; la emoción que deja el final es sobria, y la unión de
  la vuelta no le pregunta al que mira qué haría o qué siente ni habla de las víctimas.
- R10 Una frase que se pueda capturar sola, entera en un subtítulo.
- R11 La vuelta: leídas seguidas, la última frase y la primera suenan a una sola frase o a una pregunta con su
  respuesta, y no se nota que el video terminó. La última no se despide ni da la historia por cerrada. La primera
  sigue sirviendo sola para el que empieza a ver el video. Mejor si al volver la primera frase se escucha distinto
  por lo que se dijo al final.
- R12 Suena a una persona contando algo, no a un telegrama ni a un comunicado; una idea por frase.
- R13 Las uniones de la vuelta de los guiones de esta nota no usan la misma muletilla (míralos juntos; el punto va en
  el guion que repite).

Antes de marcar una duda, piensa si es una pregunta que el guion abre a propósito (la pregunta del debate, el final
abierto que completa la primera frase): esa va con "buscada": true y se deja como está. Una confusión (algo se
contradice, no se sabe a quién o a qué se refiere, o cuándo pasa) va con "buscada": false. Un problema de R1 nunca
es buscado.

Gravedad: "marca" sólo para R1 (siempre) y para R2 cuando la primera frase es relleno; "importante" para lo que
empeora el video; "menor" para detalles. Hasta 8 puntos por guion, los más graves primero.
"tramo": el número del tramo donde está el problema (el primero es 1), o 0 si es de todo el guion.
"problema": qué está mal, en una frase. "arreglo": cómo se arregla, en una frase, sin agregar nada que la nota no
diga. Contesta un elemento por guion, con su "id"."""

ESQUEMA_REVISOR = {"type": "object", "properties": {"guiones": {"type": "array", "items": {
    "type": "object", "properties": {
        "id": {"type": "string"},
        "puntos": {"type": "array", "items": {"type": "object", "properties": {
            "criterio": {"type": "string", "enum": CRITERIOS_REVISOR},
            "tramo": {"type": "integer"},
            "gravedad": {"type": "string", "enum": GRAVEDADES},
            "problema": {"type": "string"},
            "arreglo": {"type": "string"},
            "buscada": {"type": "boolean"},
        }, "required": ["criterio", "tramo", "gravedad", "problema", "arreglo", "buscada"]}},
    }, "required": ["id", "puntos"]}}}, "required": ["guiones"]}


def _nota_para_pedido(nota):
    return [f"Titular: {nota.get('titular', '')}", f"Medio: {nota.get('medio') or 'sin dato'}",
            f"Fecha: {nota.get('fecha') or 'sin dato'}", "", "Nota:", nota.get("texto", "")]


def _tramos_numerados(tramos, con_buscar=False):
    renglones = []
    for i, t in enumerate(tramos, 1):
        renglones.append(f"  {i}. {t['texto']}")
        if con_buscar:
            renglones.append(f"     buscar: {', '.join(t.get('buscar') or [])}")
    return renglones


def pedido_revisor(nota, items):
    sensible = nota.get("sensible") or nota.get("tema") in contrato.TEMAS_SENSIBLES
    renglones = [f"Nota delicada: {'sí' if sensible else 'no'}.", "", *_nota_para_pedido(nota), ""]
    futuro = frases_de_futuro(nota)
    renglones.append("Frases de la nota que cuentan algo que va a pasar o que es posible (no pueden quedar como "
                     "hechos):")
    renglones += [f"  - {f}" for f in futuro] or ["  (ninguna)"]
    for it in items:
        renglones += ["", f"Guion id {it['id']} (enfoque {it['enfoque']}), por tramos:",
                      *_tramos_numerados(it["version"]["tramos"]), la_vuelta(it["version"]["texto"])]
    return "\n".join(renglones)


def la_vuelta(texto):
    """Cómo suena la vuelta: la última oración y, enseguida, la primera."""
    partes = oraciones(texto) or [""]
    return f'  La vuelta: "{partes[-1]}" y enseguida, al volver a empezar, "{partes[0]}"'


def _puntos_del_revisor(respuesta, items):
    """{id: [puntos]} con la gravedad acomodada: R1 siempre marca; "marca" en otro que no sea R1 o R2 baja a
    importante. Hasta TOPE_PUNTOS por guion, los más graves primero."""
    ids = {it["id"]: it for it in items}
    salida = {i: [] for i in ids}
    for g in (respuesta or {}).get("guiones") or []:
        if g.get("id") not in ids:
            continue
        n_tramos = len(ids[g["id"]]["version"]["tramos"])
        for p in g.get("puntos") or []:
            criterio = p.get("criterio") if p.get("criterio") in CRITERIOS_REVISOR else None
            if not criterio or not str(p.get("problema") or "").strip():
                continue
            gravedad = p.get("gravedad") if p.get("gravedad") in GRAVEDADES else "importante"
            if criterio == "R1":
                gravedad = "marca"
            elif gravedad == "marca" and criterio != "R2":
                gravedad = "importante"
            tramo = p.get("tramo") if isinstance(p.get("tramo"), int) and 0 <= p["tramo"] <= n_tramos else 0
            problema = " ".join(str(p["problema"]).split())
            if p.get("buscada") is True and criterio != "R1":
                # una pregunta que el guion abre a propósito: se deja (no va al arreglo), como en el otro programa del autor
                gravedad, problema = "menor", "Pregunta buscada, se deja: " + problema
            salida[g["id"]].append(_punto(criterio, tramo, gravedad, problema,
                                          " ".join(str(p.get("arreglo") or "").split())))
    for i in salida:
        salida[i] = sorted(salida[i], key=lambda p: GRAVEDADES.index(p["gravedad"]))[:TOPE_PUNTOS]
    return salida


# ------------------------------------------------------------------------------------------- Los espectadores (Sonnet)
# Como en otro programa del autor ("Espectador de prueba"): tres que miran el video una vez y NO conocen la nota,
# porque el que revisa no puede saber más que el que mira. Van en el mismo momento que el panel, en otro pedido.
# Perfiles y países elegidos por el asistente, no por Lucio (docs/decisiones.md).

PERFILES = {
    "A": "el que mira TikTok todas las noches",
    "B": "el que no mira estos videos",
    "C": "el que trabaja del tema",
}

INSTRUCCIONES_ESPECTADORES = """Haces de tres espectadores de prueba de videos verticales de noticias. Cada uno ve el
video en el celular, una sola vez, pasando videos con el dedo. Sólo conocen lo que dice la voz del video: te paso el
guion por tramos. No conocen la noticia ni nada más que eso. El video se repite solo: al terminar vuelve a empezar
sin pausa, y te paso cómo suena esa vuelta.

Los tres:
- A: veintipico, de México, mira TikTok y Shorts todas las noches.
- B: cincuenta y pico, de Colombia, trabaja en una oficina y no mira este tipo de videos.
- C: de Argentina, trabaja de lo que trata la noticia (elige un oficio que tenga que ver, el mismo para todos los
  guiones) y desconfía de lo que se dice en redes.

Cada guion es un video distinto, y cada uno lo ve sin haber visto los otros: júzgalo como si fuera el único.
Para cada guion y cada espectador:
- "entendio": la noticia en una frase, con lo que entendió.
- "dudas": lo que no entendió o no se creyó, con el número de tramo. Antes de anotar una duda, decide si es una
  pregunta que el video abre a propósito ("buscada": se deja) o una confusión ("confusion": algo se contradice, no
  se sabe a quién o a qué se refiere, o cuándo pasa). Sin dudas inventadas: si entendió todo, la lista va vacía.
- "se_iria": el número del tramo donde pensó en irse, o 0 si lo vio entero.
- "corte": true si en la vuelta se nota que el video terminó y volvió a empezar; false si suena seguido.
  "corte_por_que": por qué, en una frase.
- "mandaria": a quién se lo mandaría ("a mi hermano que maneja de noche"), o "a nadie".
- "claridad" y "enganche": del 1 al 10.
Contesta un elemento por guion, con su "id", y en cada uno los tres espectadores."""

ESQUEMA_ESPECTADORES = {"type": "object", "properties": {"guiones": {"type": "array", "items": {
    "type": "object", "properties": {
        "id": {"type": "string"},
        "espectadores": {"type": "array", "items": {"type": "object", "properties": {
            "quien": {"type": "string", "enum": list(PERFILES)},
            "entendio": {"type": "string"},
            "dudas": {"type": "array", "items": {"type": "object", "properties": {
                "tramo": {"type": "integer"},
                "tipo": {"type": "string", "enum": ["buscada", "confusion"]},
                "que": {"type": "string"},
            }, "required": ["tramo", "tipo", "que"]}},
            "se_iria": {"type": "integer"},
            "corte": {"type": "boolean"},
            "corte_por_que": {"type": "string"},
            "mandaria": {"type": "string"},
            "claridad": {"type": "integer"},
            "enganche": {"type": "integer"},
        }, "required": ["quien", "entendio", "dudas", "se_iria", "corte", "corte_por_que", "mandaria", "claridad",
                        "enganche"]}},
    }, "required": ["id", "espectadores"]}}}, "required": ["guiones"]}


def pedido_espectadores(items):
    """Sin la nota, sin el titular, sin el medio y sin el enfoque: sólo lo que dice la voz y cómo suena la vuelta."""
    bloques = []
    for it in items:
        bloques.append("\n".join([f"Guion id {it['id']}, por tramos:", *_tramos_numerados(it["version"]["tramos"]),
                                  la_vuelta(it["version"]["texto"])]))
    return "\n\n".join(bloques)


def _corto(texto, largo=200):
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= largo else texto[:largo - 1].rstrip() + "…"


def _puntos_de_espectadores(respuesta, items):
    """La junta (gratis, la hace el código): {id: [puntos]}.
    - Una confusión de cualquier espectador es "importante" en su tramo (E1); varias en el mismo tramo van juntas.
    - Una pregunta buscada se deja: queda anotada como "menor" (E2) y no va al arreglo.
    - Si dos de los tres notan el corte en la vuelta, "importante" en el último tramo (E3).
    - Si dos de los tres se irían en el mismo tramo, "importante" en ese tramo (E4).
    Los puntajes, lo que entendió cada uno y a quién se lo mandaría van al registro, no a la revisión."""
    ids = {it["id"]: it for it in items}
    salida = {i: [] for i in ids}
    for g in (respuesta or {}).get("guiones") or []:
        if g.get("id") not in ids or salida[g["id"]]:
            continue
        n = len(ids[g["id"]]["version"]["tramos"])
        vistos, confusiones, buscadas, cortes, se_van, notas = set(), {}, {}, [], {}, []
        for e in g.get("espectadores") or []:
            quien = e.get("quien")
            if quien not in PERFILES or quien in vistos:
                continue
            vistos.add(quien)
            for d in e.get("dudas") or []:
                que = _corto(d.get("que"))
                if not que:
                    continue
                tramo = d.get("tramo") if isinstance(d.get("tramo"), int) and 0 <= d["tramo"] <= n else 0
                cual = confusiones if d.get("tipo") == "confusion" else buscadas
                cual.setdefault(tramo, []).append((quien, que))
            if e.get("corte") is True:
                cortes.append((quien, _corto(e.get("corte_por_que"), 150)))
            if isinstance(e.get("se_iria"), int) and 1 <= e["se_iria"] <= n:
                se_van.setdefault(e["se_iria"], []).append(quien)
            notas.append(f"{quien} claridad {e.get('claridad')}, enganche {e.get('enganche')}, entendió "
                         f"\"{_corto(e.get('entendio'), 120)}\", se lo mandaría {_corto(e.get('mandaria'), 80)}")

        def quienes(lista):
            return ", ".join(PERFILES[q] for q in dict.fromkeys(q for q, *_ in lista))
        for tramo, lista in sorted(confusiones.items()):
            salida[g["id"]].append(_punto("E1", tramo, "importante", f"no se entiende ({quienes(lista)}): "
                                          + "; ".join(q for _, q in lista)))
        for tramo, lista in sorted(se_van.items()):
            if len(lista) >= 2:
                salida[g["id"]].append(_punto("E4", tramo, "importante", f"{len(lista)} de los tres se irían en "
                                              f"este tramo ({quienes([(q,) for q in lista])})",
                                              "que este tramo traiga algo nuevo"))
        if len(cortes) >= 2:
            salida[g["id"]].append(_punto("E3", n, "importante", f"se nota el corte en la vuelta ({quienes(cortes)}): "
                                          + "; ".join(q for _, q in cortes if q),
                                          "que la última frase empalme con la primera"))
        for tramo, lista in sorted(buscadas.items()):
            salida[g["id"]].append(_punto("E2", tramo, "menor", f"Pregunta buscada, se deja ({quienes(lista)}): "
                                          + "; ".join(q for _, q in lista)))
        if notas:
            registro(f"  espectadores de {g['id']}: " + " | ".join(notas))
    return salida


# ------------------------------------------------------------------------------------------- El arreglo (Opus)

INSTRUCCIONES_ARREGLO_EXTRA = """

Ahora no escribes de cero: arreglas guiones que ya existen. Cambia SÓLO lo que dice cada punto a arreglar y deja el
resto palabra por palabra, con los mismos tramos y las mismas búsquedas. Nunca agregues datos, números ni nombres
que no estén en la nota: si un dato no está en la nota, se saca. No cambies el tiempo de ningún verbo, aunque el punto
a arreglar sea otro: lo que el guion o la nota dicen en futuro o como posible ("funcionará", "podrá", "está previsto")
sigue en futuro o como posible, nunca pasa a presente ni a pasado. Si cambias la primera o la última oración, la
unión de la vuelta (regla 8) tiene que seguir funcionando: leídas seguidas, la última empalma con la primera.
Los puntos marcados "grave" van primero y se arreglan siempre. Una duda de un espectador (no sabe qué es algo o quién
es alguien) se arregla diciéndolo con palabras que entienda cualquiera o explicándolo en pocas palabras, sin sacar el
dato; si no entra sin pasarte del largo, déjala como está. Respeta el largo que te pido para cada guion, también el
mínimo: un guion que queda más corto se descarta entero y lo grave queda sin arreglar. Si sacaste algo y quedas corto,
completa con otro dato de la nota. Contesta un elemento por guion, con su "id"."""


def _esquema_arreglo():
    import guiones as G   # acá adentro: guiones.py importa este archivo
    return {"type": "object", "properties": {"guiones": {"type": "array", "items": {"type": "object", "properties": {
        "id": {"type": "string"},
        "tramos": G.ESQUEMA_TRAMOS,
    }, "required": ["id", "tramos"]}}}, "required": ["guiones"]}


def pedido_arreglo(nota, items, para_arreglar, rango):
    sensible = nota.get("sensible") or nota.get("tema") in contrato.TEMAS_SENSIBLES
    renglones = [f"Nota delicada: {'sí' if sensible else 'no'}.", "", *_nota_para_pedido(nota)]
    for it in items:
        if it["id"] not in para_arreglar:
            continue
        actual = contrato.contar_palabras(it["version"]["texto"])
        minimo, maximo = rango
        renglones += ["", f"Guion id {it['id']} (enfoque {it['enfoque']}), {actual} palabras; tiene que quedar entre "
                      f"{min(minimo, actual)} y {maximo}. Tramos:", *_tramos_numerados(it["version"]["tramos"], True),
                      "Lo que hay que arreglar:"]
        for p in para_arreglar[it["id"]]:
            donde = f"tramo {p['tramo']}" if p["tramo"] else "todo el guion"
            cual = ("grave" if p["gravedad"] == "marca" else
                    "duda de un espectador" if str(p.get("criterio", "")).startswith("E") else "importante")
            renglones.append(f"  - ({donde}, {cual}) {p['problema']}" +
                             (f" Arreglo: {p['arreglo']}" if p["arreglo"] else ""))
    return "\n".join(renglones)


def _arreglar(nota, items, para_arreglar, rango, limite):
    """UN pedido a Claude Opus para todos los marcados. Devuelve {id: tramos nuevos} sólo de los que pasan la medida
    del código: entran en el largo, no traen un dato ni un verbo que el original no tenía y no tienen menos futuros
    que el original (contar_futuros)."""
    import guiones as G
    try:
        r = pedir_json(G.INSTRUCCIONES + INSTRUCCIONES_ARREGLO_EXTRA, pedido_arreglo(nota, items, para_arreglar, rango),
                       _esquema_arreglo(), temperatura=0.4, limite=limite)
    except (Falla, TopeDelDia) as e:
        registro(f"  el arreglo de los guiones no salió ({getattr(e, 'detalle', '') or e}): quedan como estaban")
        return {}
    except Exception as e:   # noqa: BLE001  (el arreglo nunca frena los guiones)
        registro(f"  el arreglo de los guiones no salió ({type(e).__name__}): quedan como estaban")
        return {}
    ids = {it["id"]: it for it in items if it["id"] in para_arreglar}
    minimo, maximo = rango
    salida = {}
    for g in (r or {}).get("guiones") or []:
        it = ids.get(g.get("id"))
        if not it or g["id"] in salida:
            continue
        tramos = G.limpiar_tramos(g.get("tramos"))
        if not tramos:
            continue
        if contrato.contar_palabras(G.texto_de(tramos)) > maximo:
            tramos = G.recortar(tramos, maximo)
        original = it["version"]
        palabras = contrato.contar_palabras(G.texto_de(tramos))
        if palabras < min(minimo, original["palabras"]) or palabras > maximo:
            registro(f"  el arreglo de {g['id']} no entra en el largo ({palabras} palabras): queda el original")
            continue
        antes = {_clave(p) for p in chequeos(nota, original["tramos"], (min(minimo, original["palabras"]), maximo))
                 if p["criterio"] in ("C2", "C5", "C6")}
        nuevos = [p for p in chequeos(nota, tramos, rango) if p["criterio"] in ("C2", "C5", "C6")
                  and _clave(p) not in antes]
        if nuevos:
            registro(f"  el arreglo de {g['id']} trajo algo que no está en la nota o rompió la vuelta: queda el "
                     "original")
            continue
        futuros_antes = contar_futuros(original["texto"])
        if futuros_antes and contar_futuros(G.texto_de(tramos)) < futuros_antes:
            registro(f"  el arreglo de {g['id']} pasó a presente algo que va a pasar: queda el original")
            continue
        if G.texto_de(tramos) == original["texto"]:
            continue
        salida[g["id"]] = tramos
    return salida


# ------------------------------------------------------------------------------------------- Todo junto

def _como_texto(p):
    donde = f" tramo {p['tramo']}" if p["tramo"] else ""
    return (f"{p['criterio']} ({p['gravedad']}){donde}: {p['problema']}"
            + (f" Arreglo: {p['arreglo']}" if p["arreglo"] and p["gravedad"] == "marca" else ""))


def _pedir_panel(nota, items, limite):
    """El panel (Claude Sonnet, con la nota). Devuelve ({id: [puntos]}, quién contestó o None si no contestó)."""
    try:
        r = pedir_json(INSTRUCCIONES_REVISOR, pedido_revisor(nota, items), ESQUEMA_REVISOR, temperatura=0.2,
                       modelo=MODELO_REVISOR, limite=limite)
        quien = "google" if comun.proveedor_de_este_hilo() == "google" else "claude-sonnet"
        return _puntos_del_revisor(r, items), quien
    except (Falla, TopeDelDia) as e:
        registro(f"  el revisor no contestó ({getattr(e, 'detalle', '') or e}): quedan los guiones como están")
    except Exception as e:   # noqa: BLE001  (el revisor nunca frena los guiones)
        registro(f"  el revisor no contestó ({type(e).__name__}): quedan los guiones como están")
    return {it["id"]: [] for it in items}, None


def _pedir_espectadores(items, limite):
    """Los espectadores (Claude Sonnet, SIN la nota). Devuelve {id: [puntos]} después de la junta."""
    try:
        r = pedir_json(INSTRUCCIONES_ESPECTADORES, pedido_espectadores(items), ESQUEMA_ESPECTADORES, temperatura=0.5,
                       modelo=MODELO_REVISOR, limite=limite)
        return _puntos_de_espectadores(r, items)
    except (Falla, TopeDelDia) as e:
        registro(f"  los espectadores no contestaron ({getattr(e, 'detalle', '') or e}): sigue el panel solo")
    except Exception as e:   # noqa: BLE001  (los espectadores nunca frenan los guiones)
        registro(f"  los espectadores no contestaron ({type(e).__name__}): sigue el panel solo")
    return {it["id"]: [] for it in items}


def revisar(nota, items, rango, quedan, con_revisor=True, minimo_para_arreglo=170, tope_arreglo=150,
            minimo_solo_importantes=200):
    """Revisa y, si hace falta, arregla. `items` = [{"id", "enfoque", "version"}], donde "version" es la versión del
    guion (con "texto", "palabras" y "tramos"); se cambia ahí mismo y se le agrega "revision".
    `rango` = (mínimo, máximo) de palabras. `quedan()` = segundos que quedan antes de que el Estudio corte el paso.
    Sin revisor (Más corto / Más simple) sólo mira el código.
    Al arreglo (UN pedido para todos) van los puntos "marca" y los "importante" del revisor de cada guion; los "menor"
    no. Un guion con alguna "marca" entra si quedan al menos `minimo_para_arreglo` segundos; uno que sólo tiene
    "importante", si quedan al menos `minimo_solo_importantes` (si no, queda como está, sin aviso: los importantes no
    dan aviso). El pedido tiene un tope de `tope_arreglo` segundos."""
    del_codigo = {it["id"]: chequeos(nota, it["version"]["tramos"], rango) for it in items}
    # lo que no es del código de cada guion: el panel, los espectadores y la muletilla repetida entre versiones
    del_revisor = {it["id"]: [] for it in items}
    quien = "codigo"
    if con_revisor:
        limite = min(90, int(quedan()) - 20)
        if limite >= 20:
            # el panel (con la nota) y los espectadores (sin la nota) salen al mismo tiempo: no se espera más que hoy
            with ThreadPoolExecutor(max_workers=2) as pool:
                panel = pool.submit(_pedir_panel, nota, items, limite)
                vista = pool.submit(_pedir_espectadores, items, limite)
                del_panel, quien_panel = panel.result()
                del_espectadores = vista.result()
            quien = quien_panel or quien
            for i in del_revisor:
                del_revisor[i] = del_panel[i] + del_espectadores[i]
        else:
            registro("  no queda tiempo para el revisor: sólo mira el código")
        for i, puntos in chequeo_uniones(items).items():
            del_revisor[i] += puntos
    hay = quedan()
    para_arreglar, sin_tiempo = {}, 0
    for it in items:
        marcas = [p for p in del_codigo[it["id"]] + del_revisor[it["id"]] if p["gravedad"] == "marca"]
        # la vuelta rota (C6) va al arreglo con los "importante" del revisor; en Más corto / Más simple, no
        vuelta = [p for p in del_codigo[it["id"]] if p["criterio"] == "C6"] if con_revisor else []
        importantes = [p for p in del_revisor[it["id"]] + vuelta if p["gravedad"] == "importante"]
        if not marcas and not importantes:
            continue
        if hay >= (minimo_para_arreglo if marcas else minimo_solo_importantes):
            para_arreglar[it["id"]] = marcas + importantes
        elif marcas:
            sin_tiempo += 1
    if sin_tiempo:
        registro(f"  no queda tiempo para arreglar {sin_tiempo} guion(es) marcado(s): van con aviso")
    arreglados = {}
    if para_arreglar:
        arreglados = _arreglar(nota, items, para_arreglar, rango, min(tope_arreglo, int(hay) - 20))
    for it in items:
        v = it["version"]
        if it["id"] in arreglados:
            antes = v["texto"]
            import fotos_del_guion as FG
            import guiones as G
            # las fotos no se vuelven a mirar: cada una pasa a la parte arreglada que dice lo mismo
            tramos = FG.reubicar(v["tramos"], arreglados[it["id"]])
            v["tramos"] = tramos
            v["texto"] = G.texto_de(tramos)
            v["palabras"] = contrato.contar_palabras(v["texto"])
            codigo = chequeos(nota, tramos, rango)
            enviados = {_clave(p) for p in para_arreglar[it["id"]]}
            # lo que queda del revisor habla del texto de antes (y de sus tramos): se dice
            revisor = [dict(p, problema="Antes del arreglo: " + p["problema"])
                       for p in del_revisor[it["id"]] if _clave(p) not in enviados]
            arreglado = True
            r1_sin_arreglar = False
        else:
            antes = None
            codigo = del_codigo[it["id"]]
            revisor = del_revisor[it["id"]]
            arreglado = False
            r1_sin_arreglar = any(p["criterio"] == "R1" for p in revisor)
        criterios = {p["criterio"] for p in codigo}
        if "C2" in criterios or r1_sin_arreglar:
            aviso = "DATO_NO_ESTA"
        elif "C5" in criterios:
            aviso = "VERBO_CAMBIADO"
        else:
            aviso = None
        puntos = sorted(codigo + revisor, key=lambda p: GRAVEDADES.index(p["gravedad"]))
        v["revision"] = {"puntos": [_como_texto(p) for p in puntos], "arreglado": arreglado, "aviso": aviso,
                         "quien": quien}
        if arreglado:
            v["revision"]["antes"] = antes
            v["revision"]["arreglados"] = [_como_texto(p) for p in para_arreglar[it["id"]]]
    return items


def revisar_guiones(nota, guiones, rango, quedan):
    """Los tres guiones o el de "Otro": con revisor, y arreglo si quedan 170 s (200 s si sólo hay puntos
    "importante"; tope 150 s)."""
    items = [{"id": g["id"], "enfoque": g["enfoque"], "version": g["versiones"][0]} for g in guiones]
    revisar(nota, items, rango, quedan, con_revisor=True, minimo_para_arreglo=170, tope_arreglo=150,
            minimo_solo_importantes=200)
    return guiones


def revisar_cambio(nota, enfoque, version, rango, quedan):
    """Más corto o Más simple: sólo el código, y arreglo si quedan 100 s (130 s si sólo hubiera puntos "importante",
    que hoy vienen del revisor y acá no hay; tope 120 s)."""
    items = [{"id": f"{nota['id']}-{enfoque}", "enfoque": enfoque, "version": version}]
    revisar(nota, items, rango, quedan, con_revisor=False, minimo_para_arreglo=100, tope_arreglo=120,
            minimo_solo_importantes=130)
    return version
