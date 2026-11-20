"""Las cifras del subtítulo, en números: la voz dice "veintinueve mil novecientos noventa dólares" y la pantalla muestra
"US$ 29.990", en una sola pantalla y resaltada entera mientras la voz la dice.

Sólo cambia lo que se ve: la voz y el control de la voz siguen con las palabras del guion. Pedido de Lucio del
2026-11-18 ("las cifras en números, todas"). Formato (decidido por el asistente, en docs/decisiones.md):
- hasta 4 cifras sin punto (1500, 2026); de 5 en adelante con punto de miles (30.000);
- decimales con coma (2,2); "por ciento" es " %" (2,2 %);
- millones en palabra (1 millón, 2,5 millones);
- "dólares" va delante como "US$" y "pesos" como "$" (US$ 29.990, $ 300);
- "un", "una" y "uno" solos quedan en palabras (casi siempre son "un auto", no una cantidad).
Lo que no reconoce ("treinta y pico") queda en palabras, como antes.
"""
import re

from revisar_guion import _ESCALAS, _UNIDADES, _valor, sin_tildes

_ARTICULOS = {"un", "uno", "una"}
_MONEDAS = {"dolares": "US$", "dolar": "US$", "pesos": "$", "peso": "$"}
_SIGNOS_ANTES = re.compile(r"^[(«\"'“¿¡]+")
_SIGNOS_DESPUES = re.compile(r"[.,;:!?)\]»”'\"]+$")


def _partes(palabra):
    """(signos de adelante, la palabra normalizada, signos de atrás)."""
    antes = _SIGNOS_ANTES.match(palabra)
    despues = _SIGNOS_DESPUES.search(palabra)
    a = antes.group(0) if antes else ""
    d = despues.group(0) if despues else ""
    medio = palabra[len(a):len(palabra) - len(d)] if d else palabra[len(a):]
    return a, sin_tildes(medio), d


def _con_puntos(n):
    return f"{n:,}".replace(",", ".") if n >= 10000 else str(n)


def _decimal(x):
    """2.5 -> '2,5'; 2.0 -> '2'."""
    texto = f"{x:.6f}".rstrip("0").rstrip(".")
    entero, _, dec = texto.partition(".")
    return _con_puntos(int(entero)) + ("," + dec if dec else "")


def _leer(normales, i):
    """Lee una cifra desde la palabra i. Devuelve (texto en números, cuántas palabras usa) o None si ahí no hay una.
    `normales`: [(signos antes, palabra normalizada, signos después)]."""
    n = len(normales)
    fichas, decimales, escala_final, j, medio = [], [], 1, i, False

    def corta(k):   # una coma o un punto pegados a la palabra k cierran la cifra
        return bool(normales[k][2])

    while j < n:
        w = normales[j][1]
        if w in _UNIDADES or w in _ESCALAS:
            if w in ("cien", "ciento") and j > 0 and normales[j - 1][1] == "por":
                break
            fichas.append(w)
            j += 1
            if corta(j - 1):
                break
        elif (w == "y" and fichas and fichas[-1] not in _ESCALAS and j + 1 < n and normales[j + 1][1] in _UNIDADES
              and _UNIDADES[normales[j + 1][1]] < 10):
            j += 1   # "noventa y nueve"
        elif w == "coma" and fichas and j + 1 < n and normales[j + 1][1] in _UNIDADES:
            j += 1
            while j < n and normales[j][1] in _UNIDADES:
                decimales.append(normales[j][1])
                j += 1
                if corta(j - 1):
                    break
            while j < n and normales[j][1] in _ESCALAS and not corta(j - 1):   # "dos coma cinco millones"
                escala_final *= _ESCALAS[normales[j][1]]
                j += 1
            break
        else:
            break
    if not fichas:
        return None
    if all(f in _ARTICULOS for f in fichas) and not decimales and not (j < n and normales[j][1] in _ESCALAS):
        return None   # "un auto", "una medida"
    valor = _valor(fichas)
    if decimales:
        cifras = ("".join(str(_UNIDADES[d]) for d in decimales) if decimales[0] == "cero"
                  else str(_valor(decimales)))
        valor = (valor + float("0." + cifras)) * escala_final
    # "dos millones y medio"
    if (j + 1 < n and not corta(j - 1) and normales[j][1] == "y" and normales[j + 1][1] in ("medio", "media")
            and fichas[-1] in _ESCALAS):
        valor += 0.5 * _ESCALAS[fichas[-1]] * escala_final
        j += 2
    millones = valor >= 1_000_000 and (valor * 10) % 100_000 == 0   # se escribe corto: 1 millón, 2,5 millones
    if millones:
        cuantos = valor / 1_000_000
        texto = _decimal(cuantos) + (" millón" if cuantos == 1 else " millones")
    elif isinstance(valor, float) and valor != int(valor):
        texto = _decimal(valor)
    else:
        texto = _con_puntos(int(valor))
    # lo que sigue: "por ciento", la moneda ("de dólares" después de millones)
    if not corta(j - 1):
        if j + 1 < n and normales[j][1] == "por" and normales[j + 1][1] in ("ciento", "cien"):
            return texto + " %", j + 2 - i
        k = j + 1 if (millones and j + 1 < n and normales[j][1] == "de") else j
        if k < n and normales[k][1] in _MONEDAS and (k == j or not corta(j)):
            return _MONEDAS[normales[k][1]] + " " + texto, k + 1 - i
    return texto, j - i


def juntar_cifras(palabras_tiempos):
    """[(palabra del guion, inicio, fin)] -> lo mismo, con cada cifra dicha en palabras (con su moneda o su "por
    ciento") en una sola palabra en números, que dura desde que empieza la primera hasta que termina la última.
    Los signos de la primera y la última palabra se conservan ("dólares," -> "US$ 29.990,")."""
    normales = [_partes(w) for w, _, _ in palabras_tiempos]
    salida, i = [], 0
    while i < len(palabras_tiempos):
        leido = _leer(normales, i)
        if not leido:
            salida.append(palabras_tiempos[i])
            i += 1
            continue
        texto, largo = leido
        ultima = i + largo - 1
        salida.append((normales[i][0] + texto + normales[ultima][2], palabras_tiempos[i][1],
                       palabras_tiempos[ultima][2]))
        i += largo
    return salida
