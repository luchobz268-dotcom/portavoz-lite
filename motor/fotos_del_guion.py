"""Las fotos de la nota en el guion (Tanda B, etapa 3, 2026-11-20): cuáles se pueden usar, la lista que va en el
pedido de los guiones, el reparto por partes y la reubicación cuando el guion cambia.

Lo usan guiones.py y revisar_guion.py. Las fotos las junta medios_pagina.py al leer la nota; la mirada (si la foto
tiene que ver y cómo se encuadra) la hace mirar_clips.mirar_fotos.

El reparto sigue las cinco reglas del plan que Lucio aprobó el 18/11, en este orden (la de arriba manda):
  1. una foto va sólo en la parte que habla de lo que muestra (lo sugiere Claude), y cada foto una sola vez;
  2. como mucho, la mitad de las partes, redondeando para abajo;
  3. si a la primera parte le corresponde una foto, se queda;
  4. si sobran, se prefieren las que no quedan pegadas a otra foto, y entre esas, las que van antes;
  5. dos fotos seguidas, sólo si no hay otra forma de llegar a las que corresponden.

Qué se mide y qué no: el reparto y la reubicación se MIDEN (son cuentas). Que la foto sugerida hable de lo mismo que
su parte se ESTIMA: lo decide Claude leyendo el pie, y por eso la persona la ve antes de armar (etapa 4).
"""
import re
import unicodedata
from pathlib import Path

import contrato
import medios_pagina

ID_NOTA = re.compile(r"^(nota|texto)-[a-f0-9]{10}$")
ARCHIVO = re.compile(r"^\d{2}\.jpg$")
# palabras que no dicen de qué habla una parte (para reubicar por palabras en común)
VACIAS = set("""a al algo ante antes asi aun aunque bajo cada como con contra cual cuando de del desde donde dos e el
ella ellas ellos en entre era es esa ese eso esta este esto estos fue fueron ha hace han hasta hay la las le les lo los
mas me mientras muy ni no nos o otra otro para pero poco por porque que quien se ser si sin sobre son su sus tambien
tan te tiene tienen tu un una uno unos unas y ya yo""".split())
MINIMO_EN_COMUN = 2   # palabras con contenido que tiene que compartir la parte nueva con la de antes


def fotos_de_la_nota(nota, carpeta_base=None):
    """Las fotos de nota["medios"] que se pueden usar: con la forma del contrato y con sus dos archivos en la PC
    (la grande y la chica). Lo demás se saltea. Sin fotos, []."""
    medios = nota.get("medios")
    if not isinstance(medios, list) or not ID_NOTA.match(str(nota.get("id") or "")):
        return []
    carpeta = Path(carpeta_base or medios_pagina.CARPETA) / nota["id"]
    salida, vistas = [], set()
    for m in medios[:contrato.MAXIMO_FOTOS]:
        if not isinstance(m, dict):
            continue
        n, archivo = m.get("n"), str(m.get("archivo") or "")
        if (not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= contrato.MAXIMO_FOTOS or n in vistas
                or not ARCHIVO.match(archivo) or archivo != f"{n:02d}.jpg"):
            continue
        if not (carpeta / archivo).is_file() or not (carpeta / archivo.replace(".jpg", "-chica.jpg")).is_file():
            continue
        vistas.add(n)
        salida.append(m)
    return salida


def ruta_chica(nota, foto, carpeta_base=None):
    return Path(carpeta_base or medios_pagina.CARPETA) / nota["id"] / foto["archivo"].replace(".jpg", "-chica.jpg")


def que_muestra(foto, nota):
    """Lo que se sabe de una foto sin mirarla: su pie, o su descripción, o de qué nota es."""
    pie = " ".join(str(foto.get("pie") or "").split())[:300]
    alt = " ".join(str(foto.get("alt") or "").split())[:300]
    if pie:
        return pie
    if alt:
        return f"(sin pie) {alt}"
    return f'(sin pie ni descripción: es una foto de la nota "{nota.get("titular", "")}")'


def lista_para_pedido(fotos, nota):
    """El bloque que se suma al pedido de los guiones cuando la nota trae fotos."""
    renglones = [
        "Fotos de la nota: son fotos de verdad que trae la página de la noticia; van adjuntas, cada una con su rótulo "
        "\"Foto N:\". En cada tramo, \"foto\" es el número de la foto que muestra justo lo que dice ese tramo (la "
        "persona, el lugar o el objeto del que habla), o 0 si ninguna. Elige por lo que SE VE en la imagen, no por el "
        "pie: el pie de un diario suele contar la noticia y no describir la foto (un pie sobre la cuota mensual puede "
        "ir con una foto del auto andando por la calle; esa foto va en el tramo que habla del auto o de dónde anda, no "
        "en el de la cuota). Si en la foto se lee un lugar, un cartel o una fecha que no coincide con lo que dice el "
        "tramo, va 0. Nunca de relleno: si ninguna foto muestra lo que dice el tramo, va 0. Cada foto va en un solo "
        "tramo. Si una foto le sirve al gancho (el primer tramo), va ahí. Las fotos no cambian lo que dice el guion: "
        "escríbelo igual que si no hubiera fotos.",
        "Lo que se sabe de cada foto (su pie, que no siempre dice lo que se ve):",
    ]
    renglones += [f"  {f['n']}. {que_muestra(f, nota)}" for f in fotos]
    return "\n".join(renglones)


def imagenes_para_pedido(nota, fotos, carpeta_base=None):
    """Las copias chicas de `fotos` para mandar con el pedido, [(rótulo "Foto N:", bytes)], y las fotos que se
    pudieron leer (en el mismo orden). Una que no se puede leer no va ni en la lista ni en las imágenes."""
    imagenes, leidas = [], []
    for f in fotos:
        try:
            datos = ruta_chica(nota, f, carpeta_base).read_bytes()
        except OSError:
            continue
        imagenes.append((f"Foto {f['n']}:", datos))
        leidas.append(f)
    return imagenes, leidas


def reparto(sugeridas, partes):
    """Las partes (desde 0) que se quedan con su foto, de las `sugeridas`, con las reglas 2 a 5 (la 1 la cumplen las
    sugerencias). Devuelve la lista ordenada."""
    tope = partes // 2
    candidatas = sorted({i for i in sugeridas if 0 <= i < partes})
    elegidas = []
    if tope and 0 in candidatas:
        elegidas.append(0)
    while len(elegidas) < tope:
        quedan = [i for i in candidatas if i not in elegidas]
        if not quedan:
            break
        sueltas = [i for i in quedan if i - 1 not in elegidas and i + 1 not in elegidas]
        elegidas.append((sueltas or quedan)[0])
    return sorted(elegidas)


def repartir(tramos, sirven=None):
    """Deja la foto sólo en las partes que quedan con el reparto; con `sirven` (los números de las fotos que la
    mirada aprobó), saca antes las demás. Cambia los tramos ahí mismo y los devuelve."""
    for t in tramos:
        if "foto" in t and (sirven is not None and t["foto"] not in sirven):
            del t["foto"]
    quedan = set(reparto([i for i, t in enumerate(tramos) if t.get("foto")], len(tramos)))
    for i, t in enumerate(tramos):
        if "foto" in t and i not in quedan:
            del t["foto"]
    return tramos


def _palabras(texto):
    t = "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")
    return {p for p in re.sub(r"[^\w]+", " ", t).split() if len(p) > 2 and p not in VACIAS}


def reubicar(viejos, nuevos):
    """Cuando el guion cambia ("Más corto", "Más simple" o el arreglo del revisor) las fotos no se vuelven a mirar:
    cada una pasa a la parte nueva que más palabras con contenido comparte con la de antes (al menos
    MINIMO_EN_COMUN). Si ninguna dice lo mismo, la foto se cae. Después va el reparto. Devuelve los tramos nuevos
    (copias); si los viejos no tenían fotos, quedan exactamente como vinieron."""
    con_foto = [(t["foto"], _palabras(t.get("texto", ""))) for t in viejos or [] if t.get("foto")]
    nuevos = [{k: v for k, v in t.items() if k != "foto"} for t in nuevos]
    if not con_foto:
        return nuevos
    palabras = [_palabras(t["texto"]) for t in nuevos]
    pares = sorted(((len(antes & palabras[j]), -j, foto, j) for foto, antes in con_foto for j in range(len(nuevos))),
                   reverse=True)
    puestas = set()
    for comun, _, foto, j in pares:
        if comun < MINIMO_EN_COMUN:
            break
        if foto in puestas or "foto" in nuevos[j]:
            continue
        nuevos[j]["foto"] = foto
        puestas.add(foto)
    return repartir(nuevos)
