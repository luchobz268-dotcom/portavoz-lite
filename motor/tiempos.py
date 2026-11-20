"""El momento de cada palabra del guion, sacado de la transcripción de la voz.

Las palabras que se muestran son las del guion; la transcripción sólo pone los tiempos. Se MIDE en lo que coincide y
se ESTIMA en lo que no (se reparte entre la palabra anterior y la siguiente que sí coinciden).
"""
import difflib

from comun import Falla, normalizar, palabras_normalizadas


def segundos(s):
    return float(str(s).rstrip("s"))


# Copiado de otro programa del autor (subtitulos.py: tiempos_imposibles y tiempos_de_la_parte, líneas 36-97) el
# 2026-11-17. Cambio: si no coincide ninguna palabra tira Falla FALLO_VOZ en vez de cortar el programa.
def tiempos_imposibles(t, largo_maximo=0.25):
    """La transcripción a veces anota mal el arranque de una palabra (S001-C3, 2026-11-11: "No" figuraba de 3,4 a 13,6 s,
    sin el 1 del principio) y el recorte de esa frase se llevaba todo lo del medio. Una palabra no puede empezar antes de
    que empiece la anterior ni después de su propio final (dos palabras con el mismo tiempo, como "diez mil" de "10.000",
    sí valen): ahí arranca donde terminó la anterior, como mucho 0,25 s antes de su final. t: [(inicio, fin) o None] en el
    orden del guion; se cambia en el lugar."""
    anterior = None
    for i, x in enumerate(t):
        if not x:
            continue
        ini, fin = x
        if ini > fin or (anterior is not None and ini < anterior[0] - 0.05):
            ini = min(max(anterior[1] if anterior else fin - largo_maximo, fin - largo_maximo), fin)
            t[i] = (ini, fin)
        anterior = t[i]


def tiempos_de_la_parte(texto, transcripcion, desplazamiento):
    """Devuelve [(palabra_del_guion, inicio, fin)] con tiempos tomados de la transcripción."""
    guion = [w for w in texto.split() if normalizar(w)]
    norm_guion = [normalizar(w) for w in guion]
    # cada palabra transcripta puede valer varias normalizadas (por ejemplo "20.000" = "veinte mil")
    # Cambiado el 2026-11-18: cada pedazo de una palabra transcripta que vale varias ("2,2%" = "dos coma dos por
    # ciento") se queda con su parte del tiempo, para que el resaltado del subtítulo avance palabra por palabra.
    norm_tr, origen = [], []
    for w in transcripcion.get("words", []):
        partes = palabras_normalizadas(w["word"])
        a, b = segundos(w["startOffset"]), segundos(w["endOffset"])
        for k, n in enumerate(partes):
            norm_tr.append(n)
            origen.append((a + (b - a) * k / len(partes), a + (b - a) * (k + 1) / len(partes)))
    t = [None] * len(guion)
    sm = difflib.SequenceMatcher(a=norm_guion, b=norm_tr, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        # "replace" uno por uno: la misma palabra escrita distinto por la transcripción. Se usan sus tiempos.
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                ini, fin = origen[j1 + k]
                t[i1 + k] = (ini + desplazamiento, fin + desplazamiento)
        # "replace" de distinto largo: lo que se dice en varias palabras y se escribe en una. Se reparten adentro del
        # tiempo de lo transcripto.
        elif op == "replace" and j2 > j1:
            ini = origen[j1][0] + desplazamiento
            fin = origen[j2 - 1][1] + desplazamiento
            paso = max(fin - ini, 0.0) / (i2 - i1)
            for k in range(i2 - i1):
                t[i1 + k] = (ini + paso * k, ini + paso * (k + 1))
    tiempos_imposibles(t)
    # las que no coinciden se reparten entre la anterior y la siguiente que sí coinciden
    conocidos = [i for i, x in enumerate(t) if x]
    if not conocidos:
        raise Falla("FALLO_VOZ", "la transcripción no coincide con el guion en ninguna palabra")
    for i in range(len(t)):
        if t[i]:
            continue
        ant = max([k for k in conocidos if k < i], default=None)
        sig = min([k for k in conocidos if k > i], default=None)
        ini = t[ant][1] if ant is not None else desplazamiento
        fin = t[sig][0] if sig is not None else t[ant][1] + 0.4
        a = ant if ant is not None else -1
        b = sig if sig is not None else len(t)
        paso = max(fin - ini, 0.0) / (b - a - 1)
        t[i] = (ini + paso * (i - a - 1), ini + paso * (i - a))
    return [(guion[i], t[i][0], t[i][1]) for i in range(len(guion))]
# ---- fin de lo copiado de subtitulos.py


def tiempos_del_guion(texto, transcripcion, total):
    """[(palabra, inicio, fin)] del guion entero, sin pasarse del largo de la voz y sin solaparse. La última palabra
    queda en pantalla hasta el final."""
    t = tiempos_de_la_parte(texto, transcripcion, 0.0)
    salida = []
    for i, (w, ini, fin) in enumerate(t):
        ini = min(max(ini, 0.0), total)
        fin = min(max(fin, ini), total)
        if salida and ini < salida[-1][1]:
            # dos palabras con el mismo tiempo ("diez mil"): se reparten en partes iguales
            prev_w, prev_ini, prev_fin = salida[-1]
            medio = prev_ini + (max(fin, prev_fin) - prev_ini) / 2 if ini <= prev_ini else ini
            salida[-1] = (prev_w, prev_ini, max(medio, prev_ini))
            ini = salida[-1][2]
            fin = max(fin, ini)
        salida.append((w, ini, fin))
    if salida:
        w, ini, _ = salida[-1]
        salida[-1] = (w, ini, total)
    # Una palabra de duración cero no se ve: se le da al menos un instante del hueco que sigue
    for i in range(len(salida) - 1):
        w, ini, fin = salida[i]
        sig_ini = salida[i + 1][1]
        if sig_ini > fin:
            salida[i] = (w, ini, sig_ini)   # sin huecos: la palabra queda hasta que arranca la siguiente
    return salida
