# Copiado de marca/propuestas/lite/subtitulo/armar_pruebas.py el 2026-11-17: esa carpeta es de pruebas y puede borrarse, y el armado del Estudio no puede depender de ella.
"""Estilos y líneas de subtítulo del video vertical de Portavoz Lite (1080x1920), listos para FFmpeg.

Qué cambió respecto del original (lo demás es igual, probado allá el 2026-11-16 con las letras reales):
  - los colores del resaltado (subtitulo.json, "colores") quedan escritos acá: el celeste #7DD3DF con la letra
    tinta #142431, el tono C que eligió Lucio el 2026-11-17;
  - FONTSDIR sale de medir.LETRAS (la carpeta marca/letras del proyecto), escapado para el filtro de FFmpeg;
  - pie() recibe sus renglones ya escritos: las palabras que ve la gente no viven en este archivo;
  - cabecera() deja sumar estilos (el cartel de "imagen de ejemplo" lo suma armar_video_ejemplo.py);
  - no están render(), video() ni main(), que escribían las pruebas dentro de la carpeta de la marca.

Sumado después (2026-11-17, decisiones de Lucio):
  - los emojis no se dibujan: limpiar() y dialogos() los sacan (sin_emojis). Una palabra que era sólo un emoji se
    va con su tiempo. Las letras de otros alfabetos se quedan aunque la letra de la marca no las tenga: libass
    pone otra en su lugar, y letras_que_faltan() dice cuáles, para anotarlo en el registro del armado;
  - un link que no entra en el ancho se muestra partido en pedazos que entren (cortando en / . -), uno detrás
    del otro, cada pedazo solo y a tamaño normal, con el tiempo de la palabra repartido según el largo de cada uno.
"""
import re

import medir

# El ":" de la unidad va escapado para el filtro de FFmpeg, y la ruta va entre comillas simples al usarla.
FONTSDIR = str(medir.LETRAS).replace("\\", "/").replace(":", r"\:")


def ass(hex_rgb, alfa=0):
    """#RRGGBB -> &HAABBGGRR (alfa 0 = opaco, 255 = invisible)."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


def tag(hex_rgb):
    """#RRGGBB -> &HBBGGRR& (forma de color para usar adentro del texto, en \\1c o \\3c)."""
    return f"&H{hex_rgb[5:7]}{hex_rgb[3:5]}{hex_rgb[1:3]}&".upper()


# Colores de tokens.json (familia Studio)
TINTA, MENTA, BLANCO, APAGADO, PAPEL = "#142431", "#D2E3DB", "#FFFFFF", "#A9C9BC", "#F1F3EF"
# La caja de la palabra que se dice y su letra (subtitulo.json, "colores": tono C, elegido el 2026-11-17)
RESALTE, LETRA_RESALTE = "#7DD3DF", "#142431"

BASE_Y = 1290          # línea de abajo del texto; la caja baja unos 15 px más (medido: termina en y 1305)
MARGEN_V = 1920 - BASE_Y
PIE_MARGEN_V = 1920 - 1440 + 12   # la caja del pie termina justo arriba de y 1440

PRINCIPAL = dict(letra="Inter Display ExtraBold", archivo="InterDisplay-ExtraBold.ttf", tamano=92, caja=20)
SOBRIA = dict(letra="Inter Display Bold", archivo="InterDisplay-Bold.ttf", tamano=84, caja=18)
PIE = dict(letra="Inter SemiBold", archivo="Inter-SemiBold.ttf", tamano=38, caja=10)

FORMATO = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
           "MarginL, MarginR, MarginV, Encoding")


def estilo(nombre, d, texto, caja_color, alineacion, margen_v, margen_l_extra=0):
    # BorderStyle 3 = caja opaca detrás del texto; Outline = cuánto sobresale la caja alrededor de las letras
    return (f"Style: {nombre},{d['letra']},{d['tamano']},{texto},{texto},{caja_color},{caja_color},"
            f"0,0,0,0,100,100,0,0,3,{d['caja']},0,{alineacion},{140 + margen_l_extra},140,{margen_v},1")


ESTILOS = [
    estilo("Principal", PRINCIPAL, ass(BLANCO), ass(TINTA), 2, MARGEN_V),
    estilo("Sobria", SOBRIA, ass(APAGADO), ass(TINTA), 2, MARGEN_V),
    estilo("Pie", PIE, ass(PAPEL), ass(TINTA), 1, PIE_MARGEN_V, PIE["caja"]),  # la caja arranca justo en x 140
]

# Las letras que tienen que estar en marca/letras para que FFmpeg no ponga Arial sin avisar.
ARCHIVOS_LETRAS = [PRINCIPAL["archivo"], SOBRIA["archivo"], PIE["archivo"]]


def cabecera(extra=()):
    """La cabecera del .ass con los tres estilos y, si se pasan, otros más."""
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "ScaledBorderAndShadow: yes",
        "WrapStyle: 2", "YCbCr Matrix: None", "", "[V4+ Styles]", FORMATO, *ESTILOS, *extra, "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text", ""])


CABECERA = cabecera()

# Resaltado de la palabra que se dice
# Principal: una segunda capa encima, igual a la primera pero invisible salvo esa palabra, que lleva su propia caja.
#   (Con una sola capa, la caja oscura de la palabra siguiente se pinta encima de la de color y le come la última letra.)
INVISIBLE = r"{\alpha&HFF&}"


# Aire entre palabras del principal: se suma al espacio de la letra (12,8 puntos a tamaño 92). La celeste sobresale
# MARGEN_ADENTRO hacia las vecinas, la mitad del hueco: así nunca llega a sus letras. Medido con probar_subtitulos.py.
ESPACIO_EXTRA = 12
MARGEN_ADENTRO = 12
ESPACIO = rf"{{\fsp{ESPACIO_EXTRA}}} {{\fsp0}}"
SIN_ANCHO = "​"   # carácter invisible sin ancho: lleva el margen de la punta cuando la palabra es de una letra


def resalte_principal(caja=RESALTE, letra=LETRA_RESALTE):
    """Etiqueta de la palabra que se dice: su caja de color y, si no es el blanco del estilo, el color de su letra.
    Arriba y abajo, el mismo margen que la caja oscura; a los costados, MARGEN_ADENTRO (las puntas, en marcar())."""
    color_letra = rf"\1c{tag(letra)}" if letra.upper() != BLANCO else ""
    return rf"{{\alpha&H00&\3c{tag(caja)}{color_letra}\xbord{MARGEN_ADENTRO}\ybord{PRINCIPAL['caja']}}}"


def marcar(palabra, primera, ultima):
    """La palabra dicha con el margen de la caja oscura en la punta del renglón donde esté (en la primera letra si es
    la primera palabra, en la última si es la última). libass pinta la caja letra por letra."""
    punta, adentro = rf"{{\xbord{PRINCIPAL['caja']}}}", rf"{{\xbord{MARGEN_ADENTRO}}}"
    if primera and ultima:
        return punta + palabra
    if len(palabra) == 1:
        # una letra sola: el margen grande iría también hacia la vecina; lo lleva un carácter sin ancho pegado a ella
        if primera:
            return punta + SIN_ANCHO + adentro + palabra
        return palabra + punta + SIN_ANCHO if ultima else palabra
    if primera:
        return punta + palabra[0] + adentro + palabra[1:]
    if ultima:
        return palabra[:-1] + punta + palabra[-1]
    return palabra


RESALTE_PRINCIPAL = resalte_principal()
RES_SOBRIA = rf"{{\1c{tag(BLANCO)}}}", rf"{{\1c{tag(APAGADO)}}}"   # esa palabra en blanco, las otras apagadas
ENTRADA_PRINCIPAL = r"{\fscx94\fscy94\t(0,110,\fscx100\fscy100)}"  # el grupo entra creciendo apenas


# ------------------------------------------------------------------------------------------- Emojis
# Lo que se saca: los dibujos (Extended_Pictographic de Unicode 17, tomado de Node 24, sin (c), (r) ni TM, que son
# signos de texto) con lo que se les pega: tonos de piel, el selector de dibujo, los que unen dos dibujos en uno, las
# banderas y los números en tecla.
_DIBUJOS = (
    "203c 2049 2139 2194-2199 21a9-21aa 231a-231b 2328 23cf 23e9-23f3 23f8-23fa 24c2 25aa-25ab 25b6 25c0 25fb-25fe "
    "2600-2604 260e 2611 2614-2615 2618 261d 2620 2622-2623 2626 262a 262e-262f 2638-263a 2640 2642 2648-2653 "
    "265f-2660 2663 2665-2666 2668 267b 267e-267f 2692-2697 2699 269b-269c 26a0-26a1 26a7 26aa-26ab 26b0-26b1 "
    "26bd-26be 26c4-26c5 26c8 26ce-26cf 26d1 26d3-26d4 26e9-26ea 26f0-26f5 26f7-26fa 26fd 2702 2705 2708-270d 270f "
    "2712 2714 2716 271d 2721 2728 2733-2734 2744 2747 274c 274e 2753-2755 2757 2763-2764 2795-2797 27a1 27b0 27bf "
    "2934-2935 2b05-2b07 2b1b-2b1c 2b50 2b55 3030 303d 3297 3299 1f004 1f02c-1f02f 1f094-1f09f 1f0af-1f0b0 1f0c0 "
    "1f0cf-1f0d0 1f0f6-1f0ff 1f170-1f171 1f17e-1f17f 1f18e 1f191-1f19a 1f1ae-1f1e5 1f201-1f20f 1f21a 1f22f "
    "1f232-1f23a 1f23c-1f23f 1f249-1f25f 1f266-1f321 1f324-1f393 1f396-1f397 1f399-1f39b 1f39e-1f3f0 1f3f3-1f3f5 "
    "1f3f7-1f3fa 1f400-1f4fd 1f4ff-1f53d 1f549-1f54e 1f550-1f567 1f56f-1f570 1f573-1f57a 1f587 1f58a-1f58d 1f590 "
    "1f595-1f596 1f5a4-1f5a5 1f5a8 1f5b1-1f5b2 1f5bc 1f5c2-1f5c4 1f5d1-1f5d3 1f5dc-1f5de 1f5e1 1f5e3 1f5e8 1f5ef "
    "1f5f3 1f5fa-1f64f 1f680-1f6c5 1f6cb-1f6d2 1f6d5-1f6e5 1f6e9 1f6eb-1f6f0 1f6f3-1f6ff 1f7da-1f7ff 1f80c-1f80f "
    "1f848-1f84f 1f85a-1f85f 1f888-1f88f 1f8ae-1f8af 1f8bc-1f8bf 1f8c2-1f8cf 1f8d9-1f8ff 1f90c-1f93a 1f93c-1f945 "
    "1f947-1f9ff 1fa58-1fa5f 1fa6e-1faff 1fc00-1fffd")


def _clase(rangos):
    partes = []
    for r in rangos.split():
        a, _, b = r.partition("-")
        partes.append(re.escape(chr(int(a, 16))) + (f"-{re.escape(chr(int(b, 16)))}" if b else ""))
    return f"[{''.join(partes)}]"


_PEGADO = "[︎️\U0001f3fb-\U0001f3ff\U000e0020-\U000e007f]"
_UNO = f"{_clase(_DIBUJOS)}{_PEGADO}*"
EMOJI = re.compile(f"{_UNO}(?:‍{_UNO})*|[\U0001f1e6-\U0001f1ff]|[0-9#*]️?⃣|{_PEGADO}|⃣")


def sin_emojis(texto, cambio=""):
    """El texto sin emojis. cambio: lo que queda en su lugar ("" dentro de una palabra, " " en un texto)."""
    return EMOJI.sub(cambio, str(texto))


def letras_que_faltan(texto, archivo):
    """Las letras del texto que no están en ese archivo de letras (libass las dibuja con otra). Sin repetir."""
    cmap = medir._fuente(archivo)[0]
    return sorted({c for c in str(texto) if not c.isspace() and ord(c) not in cmap})


# ------------------------------------------------------------------------------------------- Links
_LINK = re.compile(r"(?i)https?://|www\.|^[(«\"'“¿¡]*[\w-]+(?:\.[\w-]+)*\.[^\W\d_]{2,}(?:[/?#]\S*)?[.,;:!?)\]»”'\"]*$")


def es_link(palabra):
    return bool(_LINK.search(palabra))


def _entra(texto, d, mayus):
    texto = texto.upper() if mayus else texto
    return medir.ancho_con_caja(texto, d["tamano"], d["caja"], d["archivo"]) <= medir.ANCHO_UTIL


def partir_link(palabra, d, mayus):
    """Un link que no entra en el ancho, en pedazos que sí entran a tamaño normal (cortando después de / . -).
    Un pedazo sin cortes que solo no entra se corta por letras. Cualquier otra palabra vuelve entera."""
    if not es_link(palabra) or _entra(palabra, d, mayus):
        return [palabra]
    trozos = re.findall(r"[^/.\-]*[/.\-]+|[^/.\-]+$", palabra)
    if "".join(trozos) != palabra:
        trozos = [palabra]
    finos = []
    for trozo in trozos:
        if _entra(trozo, d, mayus):
            finos.append(trozo)
            continue
        actual = ""
        for c in trozo:
            if actual and not _entra(actual + c, d, mayus):
                finos.append(actual)
                actual = c
            else:
                actual += c
        finos.append(actual)
    pedazos, actual = [], ""
    for trozo in finos:
        if actual and not _entra(actual + trozo, d, mayus):
            pedazos.append(actual)
            actual = trozo
        else:
            actual += trozo
    pedazos.append(actual)
    return pedazos


def t(seg):
    cs = int(round(seg * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def dialogos(palabras, tiempos, variante="Principal", resalte=None):
    """palabras: lista del guion; tiempos: [(inicio, fin)] de cada una. Devuelve las líneas Dialogue.
    resalte: etiqueta de la palabra que se dice (sale de resalte_principal); si no se pasa, la celeste.
    Los emojis se sacan (una palabra que era sólo eso se va con su tiempo) y un link que no entra sale en pedazos."""
    resalte = resalte or RESALTE_PRINCIPAL
    d = PRINCIPAL if variante == "Principal" else SOBRIA
    mayus = variante == "Principal"
    tandas, normales = [], ([], [])   # tandas: (palabras, tiempos, es_pedazo_de_link)
    for palabra, (ini, fin) in zip(palabras, tiempos):
        palabra = sin_emojis(palabra)
        if not palabra:
            # Su tiempo se lo queda la palabra de antes, para que la pantalla no quede vacía en el medio.
            if normales[1]:
                normales[1][-1] = (normales[1][-1][0], fin)
            elif tandas:
                tandas[-1][1][-1] = (tandas[-1][1][-1][0], fin)
            continue
        pedazos = partir_link(palabra, d, mayus)
        if len(pedazos) == 1:
            normales[0].append(palabra)
            normales[1].append((ini, fin))
            continue
        if normales[0]:
            tandas.append((*normales, False))
            normales = ([], [])
        total, desde = sum(len(p) for p in pedazos), ini
        for p in pedazos:
            hasta = desde + (fin - ini) * len(p) / total
            tandas.append(([p], [(desde, hasta)], True))
            desde = hasta
    if normales[0]:
        tandas.append((*normales, False))
    lineas = []
    for ps, ts, pedazo in tandas:
        grupos = ([(ps, d["tamano"])] if pedazo
                  else medir.agrupar(ps, d["tamano"], d["caja"], d["archivo"], mayusculas=mayus,
                                     espacio_extra=ESPACIO_EXTRA if mayus else 0))
        lineas += _lineas(grupos, ts, variante, d, mayus, resalte)
    return lineas


def _lineas(grupos, tiempos, variante, d, mayus, resalte):
    lineas, k = [], 0
    for grupo, tamano in grupos:
        idx = list(range(k, k + len(grupo))); k += len(grupo)
        fin_grupo = tiempos[idx[-1]][1]
        for j, i in enumerate(idx):
            ini = tiempos[i][0]
            fin = tiempos[idx[j + 1]][0] if j + 1 < len(idx) else fin_grupo
            textos = [(w.upper() if mayus else w) for w in grupo]
            pre = rf"{{\fs{tamano}}}" if tamano != d["tamano"] else ""
            if mayus:
                if j == 0:
                    pre += ENTRADA_PRINCIPAL
                # "EL {resalte}GOBIERNO{invisible} ANUNCIÓ": todo invisible menos la palabra que se dice
                antes, despues = ESPACIO.join(textos[:j]), ESPACIO.join(textos[j + 1:])
                dicha = marcar(textos[j], j == 0, j == len(textos) - 1)
                encima = ((INVISIBLE + antes + ESPACIO if antes else "") + resalte + dicha
                          + (INVISIBLE + ESPACIO + despues if despues else ""))
                lineas.append(f"Dialogue: 0,{t(ini)},{t(fin)},{variante},,0,0,0,,{pre}{ESPACIO.join(textos)}")
                lineas.append(f"Dialogue: 1,{t(ini)},{t(fin)},{variante},,0,0,0,,{pre}{encima}")
            else:
                textos[j] = RES_SOBRIA[0] + textos[j] + RES_SOBRIA[1]
                lineas.append(f"Dialogue: 0,{t(ini)},{t(fin)},{variante},,0,0,0,,{pre}{' '.join(textos)}")
    return lineas


def pie(renglones, fin=60):
    """El pie de abajo a la izquierda (por ejemplo "Fuente: el medio" e "Imágenes ilustrativas"), todo el video."""
    texto = "\\N".join(limpiar(r) for r in renglones if r)
    return f"Dialogue: 2,{t(0)},{t(fin)},Pie,,0,0,0,,{texto}"


def limpiar(texto):
    """Lo que escribe la gente no puede abrir etiquetas del subtítulo ni cortar el renglón por su cuenta.
    Tampoco lleva emojis: no se dibujan (y la voz tampoco los lee)."""
    return " ".join(sin_emojis(texto, " ").replace("{", "(").replace("}", ")").replace("\\", "/").split())
