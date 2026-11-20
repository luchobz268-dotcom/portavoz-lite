"""Los clips de fondo, de Pexels (nunca video hecho con inteligencia artificial).

Lo usa armar.py. Busca con GET https://api.pexels.com/videos/search (la llave va en el encabezado Authorization), con
orientation=portrait y size=medium, pocos resultados por pedido. Guarda las búsquedas y los clips bajados en
motor/cache/ para no pedir dos veces lo mismo.

Regla de Pexels y Pixabay (docs/decisiones.md): en política, crímenes y tragedias, nada de gente reconocible. Ahí
sólo se buscan imágenes de ambiente y se saltean los clips cuya página nombra personas.

Antes de usar un clip, Claude lo mira (mirar_clips.py): de cada candidato ve tres fotitos que Pexels da con la
búsqueda, y saca los que muestran gente en notas delicadas, marcas ajenas, otro lugar o algo que contradice la voz.

Cuenta cada pedido a la búsqueda de Pexels en motor/cache/pedidos-pexels.json (Pexels pone un tope de
200 por hora por llave). Bajar el archivo del clip no cuenta como pedido a la búsqueda, pero se cuenta aparte.
"""
import datetime
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import llaves
from comun import CACHE, Falla, bajar, escribir_json, leer_json, registro

BUSQUEDA = "https://api.pexels.com/videos/search"
POR_PAGINA = 8
CARPETA_CLIPS = CACHE / "clips"
CARPETA_BUSQUEDAS = CACHE / "busquedas"
CUENTA = CACHE / "pedidos-pexels.json"
DIAS_BUSQUEDA = 7            # una búsqueda guardada vale una semana
LADO_MAXIMO = 2048           # nunca 4K: pesa mucho y no se ve mejor en un celular

# Palabras que nombran gente (en inglés, como se busca en Pexels). En notas sensibles no se buscan ni se usan clips
# cuya página las nombra.
GENTE = {"man", "men", "woman", "women", "people", "person", "persons", "crowd", "child", "children", "kid", "kids",
         "boy", "girl", "baby", "family", "couple", "face", "portrait", "police", "policeman", "officer", "soldier",
         "politician", "president", "protest", "protester", "protesters", "worker", "workers", "doctor", "nurse",
         "student", "students", "teenager", "guy", "lady", "businessman", "businesswoman", "player", "players",
         "fan", "fans", "audience", "victim", "criminal", "thief", "gun", "weapon", "blood", "corpse",
         "senior", "elderly", "friends", "group", "team", "selfie", "athlete", "boxer", "dancer", "model"}

# Lo que se busca cuando nada de lo pedido trae clips (por tema). Son ambientes, sin gente.
GENERICOS = {
    "general": ["city skyline", "city street", "news background", "abstract light"],
    "politica": ["government building", "city skyline", "flag waving", "empty street"],
    "crimen": ["city at night", "empty street night", "street lights", "dark alley"],
    "tragedia": ["cloudy sky", "rain on window", "empty road", "city at night"],
}


def _sumar(clave):
    try:
        d = leer_json(CUENTA)
    except (OSError, ValueError):
        d = {}
    hoy = datetime.date.today().isoformat()
    d.setdefault("total", {}).setdefault(clave, 0)
    d["total"][clave] += 1
    d.setdefault(hoy, {}).setdefault(clave, 0)
    d[hoy][clave] += 1
    CUENTA.parent.mkdir(parents=True, exist_ok=True)
    escribir_json(CUENTA, d)


def contados():
    """{"busquedas": n, "bajadas": n} desde que existe la cuenta."""
    try:
        return dict(leer_json(CUENTA).get("total", {}))
    except (OSError, ValueError):
        return {}


def tiene_gente(texto):
    palabras = set(re.findall(r"[a-z]+", str(texto).lower()))
    return bool(palabras & GENTE)


# Lo que en una noticia casi nunca va y Pexels igual devuelve entre los primeros (medido el 2026-11-17: para
# "supermarket shelves" el primero era una persona disfrazada comprando fideos). No se descartan: van al final.
RAROS = {"cosplay", "costume", "halloween", "dance", "dancing", "dancer", "wedding", "selfie", "fashion", "yoga",
         "tiktok", "makeup", "influencer"}


def _raiz(palabra):
    return palabra[:5]


def puntaje(video, consulta):
    """Cuánto se parece el nombre del clip en Pexels a lo que se buscó (las palabras de la búsqueda que aparecen en
    el nombre, por raíz), menos si es algo raro para una noticia. Se ESTIMA: el nombre lo escribe Pexels."""
    nombre = set(re.findall(r"[a-z]+", str(video.get("pagina", "")).lower().rsplit("/video/", 1)[-1]))
    raices = {_raiz(w) for w in nombre}
    buscadas = [w for w in re.findall(r"[a-z]+", consulta.lower()) if len(w) > 2]
    return sum(_raiz(w) in raices for w in buscadas) - 3 * bool(nombre & RAROS)


def sin_gente(consulta):
    """La consulta sin las palabras que nombran gente (para notas sensibles)."""
    return " ".join(p for p in str(consulta).split() if p.lower() not in GENTE).strip()


def buscar(consulta, orientacion="portrait", pagina=1):
    """Los videos de una búsqueda (de la guardada si es de esta semana). Sin llave tira Falla."""
    clave = hashlib.md5(f"v2|{consulta}|{orientacion}|{pagina}|{POR_PAGINA}".encode("utf-8")).hexdigest()
    guardada = CARPETA_BUSQUEDAS / f"{clave}.json"
    if guardada.exists() and time.time() - guardada.stat().st_mtime < DIAS_BUSQUEDA * 86400:
        try:
            return leer_json(guardada).get("videos", [])
        except (OSError, ValueError):
            pass
    llave = llaves.pexels()
    if not llave:
        raise Falla("DESCONOCIDO", "falta la llave de Pexels (PEXELS_API_KEY)")
    parametros = {"query": consulta, "orientation": orientacion, "size": "medium", "per_page": POR_PAGINA,
                  "page": pagina}
    codigo, cuerpo, _ = bajar(f"{BUSQUEDA}?{urlencode(parametros)}", {"Authorization": llave}, timeout=30)
    _sumar("busquedas")
    if codigo == 429:
        raise Falla("DESCONOCIDO", "Pexels pide esperar: se llegó a su tope de pedidos por hora")
    if codigo in (401, 403):
        raise Falla("DESCONOCIDO", "Pexels no acepta la llave")
    if codigo != 200:
        raise Falla("DESCONOCIDO", f"Pexels contestó {codigo}")
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except ValueError:
        raise Falla("DESCONOCIDO", "Pexels devolvió algo que no se entiende")
    videos = [{"id": v.get("id"), "ancho": v.get("width"), "alto": v.get("height"), "duracion": v.get("duration"),
               "pagina": v.get("url", ""), "imagen": v.get("image"),
               "cuadros": [p.get("picture") for p in sorted(v.get("video_pictures") or [],
                                                            key=lambda p: p.get("nr") or 0) if p.get("picture")],
               "archivos": [{"ancho": f.get("width"), "alto": f.get("height"), "link": f.get("link"),
                             "tipo": f.get("file_type"), "fps": f.get("fps")} for f in v.get("video_files", [])]}
              for v in datos.get("videos", []) if v.get("id")]
    CARPETA_BUSQUEDAS.mkdir(parents=True, exist_ok=True)
    escribir_json(guardada, {"consulta": consulta, "orientacion": orientacion, "videos": videos})
    return videos


def elegir_archivo(video, ancho, alto):
    """El archivo mp4 del video más cercano a ancho x alto, sin pasar de LADO_MAXIMO (nunca 4K). None si no hay."""
    buenos = [f for f in video.get("archivos", []) if f.get("link") and f.get("ancho") and f.get("alto")
              and (f.get("tipo") or "video/mp4") == "video/mp4" and max(f["ancho"], f["alto"]) <= LADO_MAXIMO]
    if not buenos:
        return None

    def distancia(f):
        # que cubra la pantalla después de recortar: el lado corto del archivo contra el ancho pedido
        corto = min(f["ancho"], f["alto"])
        falta = max(0, ancho - corto)
        return (falta > ancho * 0.25, abs(corto - ancho) + abs(max(f["ancho"], f["alto"]) - alto) / 4)

    return min(buenos, key=distancia)


def bajar_clip(video, archivo):
    """Baja el clip (o usa el guardado). Devuelve la ruta en motor/cache/clips."""
    CARPETA_CLIPS.mkdir(parents=True, exist_ok=True)
    destino = CARPETA_CLIPS / f"{video['id']}-{archivo['ancho']}x{archivo['alto']}.mp4"
    if destino.exists() and destino.stat().st_size > 10_000:
        return destino
    codigo, cuerpo, _ = bajar(archivo["link"], {"Accept": "video/mp4"}, timeout=120, tope_bytes=80_000_000)
    _sumar("bajadas")
    if codigo != 200 or len(cuerpo) < 10_000:
        raise Falla("DESCONOCIDO", f"no se pudo bajar un clip de Pexels ({codigo})")
    parcial = destino.with_name(f"{destino.stem}.{os.getpid()}.parcial.mp4")
    parcial.write_bytes(cuerpo)
    os.replace(parcial, destino)
    return destino


def consultas_para(buscar_en, sensible, tema):
    """Las consultas de un tramo, de la más precisa a la más general, sin repetir."""
    salida = []
    for c in buscar_en or []:
        c = " ".join(str(c).lower().split())
        if sensible:
            c = sin_gente(c)
        if c and c not in salida:
            salida.append(c)
    # más general: la última palabra de cada consulta de dos o más palabras ("rain on window" -> "window")
    for c in list(salida):
        partes = c.split()
        if len(partes) > 1 and partes[-1] not in salida and len(partes[-1]) > 3:
            salida.append(partes[-1])
    return salida


def candidatos(consulta, sensible, usados, ancho, alto):
    """Videos usables de una consulta: primero verticales; si no hay, apaisados (se recortan al centro)."""
    for orientacion in ("portrait", "landscape"):
        lista = []
        for v in buscar(consulta, orientacion):
            if v["id"] in usados:
                continue
            if sensible and tiene_gente(v.get("pagina", "").replace("-", " ")):
                continue
            archivo = elegir_archivo(v, ancho, alto)
            if archivo and (v.get("duracion") or 0) >= 3:
                lista.append((v, archivo))
        if lista:
            # los que más se parecen a lo buscado primero; entre iguales, el orden de Pexels
            return sorted(lista, key=lambda va: -puntaje(va[0], consulta))
    return []


CANDIDATOS = 4   # cuántos clips se miran por tramo (el primero va y el resto queda de repuesto)


def _juntar(consultas, sensible, vistos, ancho, alto, cuantos=CANDIDATOS):
    """Hasta `cuantos` candidatos [(video, archivo, consulta)] de las consultas, en orden y sin repetir clips ya
    vistos en otro tramo. Devuelve también las consultas que no se llegaron a usar."""
    salida = []
    restantes = list(consultas)
    while restantes and len(salida) < cuantos:
        consulta = restantes.pop(0)
        for v, a in candidatos(consulta, sensible, vistos, ancho, alto):
            if v["id"] in vistos or any(v["id"] == x[0]["id"] for x in salida):
                continue
            salida.append((v, a, consulta))
            if len(salida) >= cuantos:
                break
    return salida, restantes


def _normal(consulta):
    """Una búsqueda para comparar: en minúscula y sin espacios de más."""
    return " ".join(str(consulta).lower().split())


def _probadas(lista, restantes):
    """Las consultas de `lista` que _juntar llegó a buscar (las que no quedaron en `restantes`, que es su final)."""
    return {_normal(c) for c in lista[:len(lista) - len(restantes)]}


def _mirar(grupos, mirar, mirada, vuelta=1):
    """Llama a la mirada y guarda lo que dijo. Si no pudo, todos quedan "sin mirar" y se anota por qué: la primera
    vuelta en "hecha" y "no_se_pudo"; las otras, cada una en "vueltas_fallidas" ([{"vuelta", "detalle"}])."""
    if not mirar:
        mirada.update({"hecha": False, "no_se_pudo": "no hay quién mire"})
        return {}
    if not grupos:
        return {}
    t = time.time()
    try:
        veredictos = mirar(grupos)
    except Exception as e:   # noqa: BLE001  (sin internet, tope, lo que sea: el video sale igual que antes)
        detalle = str(getattr(e, "detalle", "") or e)[:200]
        if vuelta > 1:
            mirada.setdefault("vueltas_fallidas", []).append({"vuelta": vuelta, "detalle": detalle})
        else:
            mirada.update({"hecha": False, "no_se_pudo": detalle})
        registro(f"  no se pudieron mirar los clips ({detalle}): sigo como antes, con el filtro de palabras")
        return {}
    import comun
    mirada["hecha"] = True
    mirada["quien"] = comun.ULTIMO_PROVEEDOR[0]
    mirada["vueltas"] = mirada.get("vueltas", 0) + 1
    mirada["segundos"] = round(mirada.get("segundos", 0) + time.time() - t, 1)
    return veredictos


def _orden(motivo):
    """Qué clip se prefiere: los que sirven (0), después los no mirados (1), y "no tiene que ver" (2) sólo como último
    recurso, después de pedir prestado uno que sirve a otro tramo. Los graves (gente en nota delicada, marca, lugar,
    pantalla, dibujo, contradice, blanco y negro) nunca: None."""
    import mirar_clips as M
    if motivo in M.GRAVES:
        return None
    return {M.SIRVE: 0, M.SIN_MIRAR: 1, M.FLOJO: 2}.get(motivo, 1)


def elegir_clips(tramos, sensible, tema, ancho, alto, segundos_por_palabra=0.4, mirar=None, mirada=None,
                 busquedas=None):
    """Para cada tramo, el clip elegido (bajado) y sus repuestos. Tira SIN_CLIPS si algún tramo se queda sin ninguno
    (antes de gastar la voz). Devuelve [{"tramo": i, "buscado": c, "usados": [...], "repuestos": [...]}].

    mirar: función(grupos) -> {id: {"motivo", "detalle"}} (mirar_clips.mirar con la nota). Sin ella, o si falla, se
    elige como antes (el orden de Pexels y el filtro de palabras). Si a un tramo no le queda ningún clip que sirva, se
    hace UNA vuelta más: primero con las búsquedas nuevas que escribió Claude para ese tramo y después con sus otras
    búsquedas y las de ambiente. Si después de esa vuelta sigue sin ninguno que sirva y Claude escribió búsquedas
    nuevas otra vez, una tercera vuelta, la última. Recién ahí se presta un clip de otro tramo.
    Ninguna vuelta repite una búsqueda ya probada para ese tramo (en minúscula y sin espacios de más): se sacan antes,
    y un tramo al que no le queda ninguna no hace la vuelta (18/11: la tercera repetía las cuatro de la segunda). A
    Claude se le pasan las ya probadas de cada tramo ("probadas" en cada grupo), para que no las vuelva a escribir.
    `busquedas`: el diccionario donde `mirar` deja las búsquedas nuevas de Claude ({tramo: [consultas]}; armar.py se
    lo pasa a mirar_clips.mirar). Sin él, todo como antes.
    `mirada` (un dict) se llena con lo que pasó, para armado.json: si se miró, quién, cuánto tardó, qué clips se
    sacaron y por qué, "busquedas_nuevas" ([{"tramo", "vuelta", "consultas"}], tramo desde 0 como en el resto),
    "busquedas_repetidas" (las que Claude escribió y ya se habían probado: no se buscan), "tercera_vuelta"
    ({"tramos": los que la hicieron, "clips_nuevos": cuántos clips nuevos trajo; 0 si Pexels no trajo ninguno y no se
    miró nada}), "vueltas_fallidas" (las vueltas 2 y 3 que no se pudieron mirar, con por qué) y "prestados" (cuántos
    TRAMOS usan clips de otro tramo, no cuántas tomas; qué toma es prestada y de dónde lo dice "prestado_de" en cada
    toma de armado.json). Cada elección prestada lleva "prestado": True y "prestado_de": {id del clip: tramo de donde
    sale, desde 0}, también para sus repuestos."""
    mirada = {} if mirada is None else mirada
    busquedas = {} if busquedas is None else busquedas
    genericos = GENERICOS.get(tema, GENERICOS["general"])
    vistos = set()
    por_tramo = []
    for i, tramo in enumerate(tramos):
        consultas = consultas_para(tramo.get("buscar"), sensible, tema)
        juntos, restantes = _juntar(consultas, sensible, vistos, ancho, alto)
        probadas = _probadas(consultas, restantes)
        restantes += [g for g in genericos if g not in consultas]
        if not juntos:
            lista = restantes
            juntos, restantes = _juntar(lista, sensible, vistos, ancho, alto)
            probadas |= _probadas(lista, restantes)
        vistos.update(v["id"] for v, _, _ in juntos)
        por_tramo.append({"tramo": i, "texto": tramo["texto"], "juntos": juntos, "restantes": restantes,
                          "probadas": probadas})

    def grupos_de(lista):
        return [{"tramo": t["tramo"], "texto": t["texto"], "candidatos": [v for v, _, _ in t["juntos"]],
                 "probadas": sorted(t["probadas"])}
                for t in lista if t["juntos"]]

    def nuevas_de(t, de_claude, vuelta):
        """Las búsquedas de Claude para el tramo que todavía no se probaron. Las repetidas se anotan y no se buscan."""
        propias = consultas_para(de_claude.get(t["tramo"]), sensible, tema)   # sin gente si es delicada
        repetidas = [c for c in propias if _normal(c) in t["probadas"]]
        if repetidas:
            mirada.setdefault("busquedas_repetidas", []).append({"tramo": t["tramo"], "vuelta": vuelta,
                                                                 "consultas": repetidas})
        return [c for c in propias if _normal(c) not in t["probadas"]]

    def mirar_y_anotar(grupos, vuelta=1):
        """Mira y devuelve también las búsquedas nuevas que Claude escribió en esa mirada."""
        busquedas.clear()
        v = _mirar(grupos, mirar, mirada, vuelta)
        return v, dict(busquedas)

    def sin_ninguno_que_sirva():
        return [t for t in por_tramo if not any(veredictos.get(v["id"], {}).get("motivo") == M.SIRVE
                                                for v, _, _ in t["juntos"])]

    def otra_vuelta(flojos, de_claude, vuelta):
        """Busca más clips para los tramos flojos (primero con las búsquedas de Claude) y los mira."""
        nuevos, hechos = [], []
        for t in flojos:
            propias = nuevas_de(t, de_claude, vuelta)
            lista = propias + [c for c in t["restantes"] if c not in propias and _normal(c) not in t["probadas"]]
            if not lista:
                registro(f"  tramo {t['tramo'] + 1}: no queda ninguna búsqueda sin probar, no hace la vuelta {vuelta}")
                continue
            hechos.append(t["tramo"])
            if propias:
                mirada.setdefault("busquedas_nuevas", []).append({"tramo": t["tramo"], "vuelta": vuelta,
                                                                  "consultas": propias})
            mas, t["restantes"] = _juntar(lista, sensible, vistos, ancho, alto)
            t["probadas"] |= _probadas(lista, t["restantes"])
            vistos.update(v["id"] for v, _, _ in mas)
            if mas:
                nuevos.append({"tramo": t["tramo"], "texto": t["texto"], "juntos": mas, "probadas": t["probadas"]})
                t["juntos"] = t["juntos"] + mas
        if vuelta == 3 and hechos:
            mirada["tercera_vuelta"] = {"tramos": hechos, "clips_nuevos": sum(len(n["juntos"]) for n in nuevos)}
        if not nuevos:
            return {}
        registro(f"  {len(nuevos)} tramo(s) sin clips que sirvan: miro otros (vuelta {vuelta})")
        mas_veredictos, de_claude_nuevas = mirar_y_anotar(grupos_de(nuevos), vuelta)
        veredictos.update(mas_veredictos)
        return de_claude_nuevas

    import mirar_clips as M
    veredictos, de_claude = mirar_y_anotar(grupos_de(por_tramo))
    if veredictos:
        # segunda vuelta para los tramos que se quedaron sin ninguno que sirva
        de_claude = otra_vuelta(sin_ninguno_que_sirva(), de_claude, 2)
        # tercera y última: sólo si sigue sin ninguno que sirva y Claude escribió búsquedas nuevas para ese tramo
        # (nuevas de verdad: si todas ya se probaron, se anotan como repetidas y el tramo no hace la tercera)
        terceros = []
        for t in sin_ninguno_que_sirva():
            if not de_claude.get(t["tramo"]):
                continue
            if any(_normal(c) not in t["probadas"] for c in consultas_para(de_claude[t["tramo"]], sensible, tema)):
                terceros.append(t)
            else:
                nuevas_de(t, de_claude, 3)
                registro(f"  tramo {t['tramo'] + 1}: Claude repitió búsquedas ya probadas, no hace la vuelta 3")
        if terceros:
            otra_vuelta(terceros, de_claude, 3)
        mirada["descartados"] = [{"clip": id_, "motivo": d["motivo"], "detalle": d["detalle"]}
                                 for id_, d in veredictos.items() if d["motivo"] not in (M.SIRVE,)]
        mirada["mirados"] = sum(1 for d in veredictos.values() if d["motivo"] != M.SIN_MIRAR)

    usados = set()
    elegidos = {}

    def utiles_de(candidatos, necesita, hasta=1):
        """Los candidatos sin usar con orden <= hasta (0: sólo los que sirven; 1: también los no mirados; 2: también
        "no tiene que ver"), ordenados del mejor al peor."""
        salida = []
        for pos, (v, a, consulta) in enumerate(candidatos):
            if v["id"] in usados:
                continue
            orden = _orden(veredictos[v["id"]]["motivo"]) if v["id"] in veredictos else 1
            if orden is None or orden > hasta:
                continue
            salida.append((orden, (v.get("duracion") or 0) < necesita, pos, v, a, consulta))
        return sorted(salida, key=lambda x: x[:3])

    def mirado_de(id_):
        """Lo que dijo Claude del clip (su motivo), o None si no lo miró."""
        motivo = veredictos.get(id_, {}).get("motivo")
        return None if motivo in (None, M.SIN_MIRAR) else motivo

    def elegir(t, utiles, prestado=False, origen=None, rechazado=False):
        """Elige el primero de `utiles` que tenga algún pedazo bueno (medir_clip.py). False si ninguno tiene."""
        i = t["tramo"]
        # el primero va; los repuestos, sólo de los mejores que quedan (nunca uno peor que el elegido, y nunca uno
        # "no tiene que ver": la segunda toma de un tramo sale de los que sirven, o de los no mirados si el primero
        # tampoco se miró; si no hay, el primero dura todo el tramo)
        while utiles:
            _, _, _, video, archivo, buscado = utiles[0]
            usados.add(video["id"])
            ruta = bajar_clip(video, archivo)
            clip = {"id": video["id"], "ruta": str(ruta), "duracion": float(video.get("duracion") or 0)}
            if preparar(clip):
                break
            sacado_al_medir(mirada.setdefault("sin_pedazos", []), i, clip)
            utiles = [u for u in utiles[1:] if u[3]["id"] not in usados]
        else:
            return False
        motivo = veredictos.get(video["id"], {}).get("motivo", "sin mirar")
        cual = "rechazado_ultimo_recurso" if rechazado else "prestado" if prestado else "propio"
        if rechazado:
            registro(f"  ATENCIÓN tramo {i + 1}: no queda ningún clip que sirva, ni propio ni de otro tramo. Entra el "
                     f"clip {video['id']} de '{buscado}', que Claude marcó '{motivo}' "
                     f"({veredictos.get(video['id'], {}).get('detalle', '')})")
        else:
            registro(f"  tramo {i + 1}: clip {video['id']} ({archivo['ancho']}x{archivo['alto']}, {video['duracion']} s) "
                     f"de '{buscado}' ({motivo}{', prestado de otro tramo' if prestado else ''})")
        repuestos = [] if rechazado else [(v, a) for o, _, _, v, a, _ in utiles[1:4] if o <= min(utiles[0][0], 1)]
        elegidos[i] = {"tramo": i, "buscado": buscado, "mirado": motivo, "usados": [clip],
                       "repuestos": repuestos,
                       # para armado.json: qué dijo Claude de cada clip (None si no lo miró) y de dónde sale
                       "motivos": {v["id"]: mirado_de(v["id"]) for v in [video] + [r for r, _ in repuestos]},
                       "origen": cual}
        if prestado:
            # de qué tramo (desde 0) sale cada clip prestado, el elegido y sus repuestos: armar.py lo pone en cada toma
            elegidos[i].update({"prestado": True, "prestado_de": {v["id"]: origen[v["id"]]
                                                                  for v in [video] + [r for r, _ in repuestos]}})
        return True

    sin_propios = []
    for t in por_tramo:
        necesita = max(2.0, len(t["texto"].split()) * segundos_por_palabra)
        utiles = utiles_de(t["juntos"], necesita, hasta=1)   # los que sirven y los no mirados
        if not (utiles and elegir(t, utiles)):
            sin_propios.append((t, necesita))
    for t, necesita in sin_propios:
        # Ninguno de sus clips sirve: antes de frenar el video, uno que Claude aprobó para otro tramo y quedó sin usar
        # (una pared, unos papeles). Nunca uno grave ni uno sin mirar (18/11: en la nota del robo, todo lo que Pexels
        # daba para "vidriera de relojería" tenía gente o carteles de otro país).
        ajenos = [x for o in por_tramo if o is not t for x in o["juntos"]]
        origen = {x[0]["id"]: o["tramo"] for o in por_tramo if o is not t for x in o["juntos"]}
        utiles = utiles_de(ajenos, necesita, hasta=0) if veredictos else []
        if utiles and elegir(t, utiles, prestado=True, origen=origen):
            mirada["prestados"] = mirada.get("prestados", 0) + 1   # cuenta tramos, no tomas
            continue
        # Último recurso: uno propio que Claude marcó "no tiene que ver" (18/11, Tesla: unas páginas de libro entraban
        # antes de pedir prestado uno bueno). Los graves nunca.
        utiles = utiles_de(t["juntos"], necesita, hasta=2)
        if not (utiles and elegir(t, utiles, rechazado=True)):
            for v, _, consulta in t["juntos"]:
                d = veredictos.get(v["id"], {})
                registro(f"  tramo {t['tramo'] + 1}, sacado: clip {v['id']} de '{consulta}': {d.get('motivo', '?')} "
                         f"({d.get('detalle', '')})")
            raise Falla("SIN_CLIPS", f"no hay clips para el tramo {t['tramo'] + 1}")
        mirada.setdefault("rechazados_ultimo_recurso", []).append(t["tramo"])
    salida = [elegidos[t["tramo"]] for t in por_tramo]
    for e in salida:   # los de repuesto no pueden repetir uno ya elegido en otro tramo
        e["repuestos"] = [(v, a) for v, a in e["repuestos"] if v["id"] not in usados]
    return salida


def preparar(clip):
    """Mide el clip ya bajado (medir_clip.py: blanco y negro, liso, pantalla verde) y, si se le cortó algo, le deja su
    pedazo bueno más largo: "desde" y "hasta" (segundos del clip), "duracion" (lo que dura ese pedazo) y "cortado"
    (qué se le sacó y por qué). Devuelve False si no le queda ningún pedazo bueno. Si no se pudo medir, va entero, como
    antes. Sólo el más largo: una toma no pasa de LARGO_TOMA, y saltar de un pedazo a otro del mismo clip sería un
    corte en el medio de la toma (decidido por el asistente, 2026-11-18)."""
    import medir_clip as MC
    medida = MC.medir(clip["ruta"])
    if medida is None:
        return True
    clip["cortado"] = medida["cortado"]
    if not medida["pedazos"]:
        return False
    if medida["cortado"]:
        desde, hasta = max(medida["pedazos"], key=lambda p: p[1] - p[0])
        clip.update({"desde": desde, "hasta": hasta, "duracion": round(hasta - desde, 2)})
    return True


def sacado_al_medir(lista, tramo, clip):
    """Anota un clip que quedó afuera porque no le quedó ningún pedazo bueno (para armado.json y el registro)."""
    motivos = sorted({c["motivo"] for c in clip.get("cortado") or []})
    lista.append({"tramo": tramo, "clip": clip["id"], "motivos": motivos})
    registro(f"  tramo {tramo + 1}, sacado al medir: clip {clip['id']} ({', '.join(motivos) or 'sin pedazos'})")


LARGO_TOMA = 5.0   # una toma no pasa de unos 5 s si hay otro clip de la misma búsqueda (si no, la imagen se estanca)


def completar(eleccion, segundos_tramo, usados):
    """Suma repuestos de la misma búsqueda (sin repetir ids) si los clips del tramo no alcanzan para sus segundos o si
    una sola toma pasaría de LARGO_TOMA. Devuelve la lista de clips [{"id", "ruta", "duracion", "mirado", "origen"}]
    del tramo; si no hay repuestos, el último se repite en bucle. "mirado": lo que dijo Claude de ese clip (None si
    no lo miró); "origen": propio, prestado o rechazado_ultimo_recurso. Cada toma queda también en el registro.
    Cada repuesto se mide al bajarlo (preparar): "duracion" es lo que dura su pedazo bueno, y uno sin ningún pedazo
    bueno no entra (queda en eleccion["sin_pedazos"]). El que se repite en bucle repite sólo su pedazo bueno."""
    clips = list(eleccion["usados"])
    tomas_que_quiero = max(1, -int(-segundos_tramo // LARGO_TOMA))
    while ((sum(c["duracion"] for c in clips) < segundos_tramo or len(clips) < tomas_que_quiero)
           and eleccion["repuestos"]):
        video, archivo = eleccion["repuestos"].pop(0)
        if video["id"] in usados:
            continue
        try:
            ruta = bajar_clip(video, archivo)
        except Falla:
            continue
        usados.add(video["id"])
        clip = {"id": video["id"], "ruta": str(ruta), "duracion": float(video.get("duracion") or 0)}
        if not preparar(clip):   # sin ningún pedazo bueno: pasa el repuesto siguiente
            sacado_al_medir(eleccion.setdefault("sin_pedazos", []), eleccion["tramo"], clip)
            continue
        clips.append(clip)
    motivos, origen = eleccion.get("motivos") or {}, eleccion.get("origen", "propio")
    for k, c in enumerate(clips):
        c["mirado"] = motivos.get(c["id"])
        c["origen"] = origen
        registro(f"  tramo {eleccion['tramo'] + 1}, toma {k + 1}: clip {c['id']}, "
                 f"{'Claude dijo: ' + c['mirado'] if c['mirado'] else 'sin mirar'}, {origen.replace('_', ' ')}")
    return clips


def tomas(clips, segundos_tramo):
    """Cuántos segundos de cada clip van en el tramo: se reparten para que cada clip sume como mucho su largo (el de su
    pedazo bueno, si se le cortó algo)."""
    if len(clips) == 1:
        return [(clips[0], segundos_tramo)]
    parte = segundos_tramo / len(clips)
    salida, sobra = [], 0.0
    for c in clips:
        quiero = parte + sobra
        uso = min(quiero, max(c["duracion"] - 0.1, 0.5))
        sobra = quiero - uso
        salida.append([c, uso])
    if sobra > 0.01:
        salida[-1][1] += sobra   # el último se repite en bucle si hace falta
    return [(c, s) for c, s in salida]

