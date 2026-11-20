# Copiado de marca/propuestas/lite/subtitulo/medir.py el 2026-11-17: esa carpeta es de pruebas y puede borrarse,
# y el armado del Estudio no puede depender de ella. Único cambio: las letras se buscan en marca/letras desde acá.
"""Mide cuánto ocupa un texto en el video (1080x1920) con las letras reales, y decide cómo agrupar las palabras.

La regla de corte (calibrada contra lo que dibuja FFmpeg/libass, ver calibrar() abajo):
  - se muestran de 1 a 3 palabras por vez, siempre en UN renglón;
  - el renglón, con su caja, tiene que entrar en el ancho útil (x 140 a 940 = 800 px);
  - si la palabra siguiente no entra, el grupo se cierra y esa palabra arranca el próximo;
  - una palabra sola que no entra ni sola se achica (hasta TAMANO_MINIMO); si ni así entra, se deja y se avisa.
Uso de prueba:  python medir.py "MUNICIPALIDAD ANUNCIÓ HOY"
"""
import sys
from pathlib import Path
from fontTools.ttLib import TTFont

LETRAS = Path(__file__).resolve().parents[2] / "marca" / "letras"   # la carpeta marca/letras del proyecto
ANCHO_UTIL = 800          # x 140 a 940
MAX_PALABRAS = 3
TAMANO_MINIMO = 72

# igual que en otro programa del autor (subtitulos.py): palabras que no conviene dejar al final
DEBILES = {"tu", "tus", "el", "la", "los", "las", "un", "una", "unos", "de", "del", "y", "que", "en", "a", "al",
           "con", "por", "para", "mi", "su", "sus", "no", "lo", "se", "te", "me", "le", "es", "esa", "ese", "esta",
           "este", "como", "sin", "mas", "más", "muy", "tan"}


def _limpia(p):
    return p.lower().strip(".,;:!?¡¿\"'«»“”()")


_cache = {}


def _fuente(archivo):
    if archivo not in _cache:
        t = TTFont(str(LETRAS / archivo))
        os2 = t["OS/2"]
        _cache[archivo] = (t.getBestCmap(), t["hmtx"].metrics,
                           os2.usWinAscent + os2.usWinDescent,  # libass escala el tamaño a esta altura
                           t["kern"] if "kern" in t else None)
    return _cache[archivo]


def ancho_texto(texto, tamano, archivo="InterDisplay-ExtraBold.ttf", espacio_extra=0):
    """Ancho en px del texto dibujado por libass con ese Fontsize (sin caja). No suma el interletrado
    por pares (kerning), así que da unos px de más: es a favor de la seguridad.
    espacio_extra: puntos que se suman a cada espacio (el aire entre palabras del subtítulo principal)."""
    cmap, hmtx, alto, _ = _fuente(archivo)
    unidades = sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in texto)
    return unidades * tamano / alto + texto.count(" ") * espacio_extra


def ancho_con_caja(texto, tamano, caja, archivo="InterDisplay-ExtraBold.ttf", espacio_extra=0):
    return ancho_texto(texto, tamano, archivo, espacio_extra) + 2 * caja


def agrupar(palabras, tamano=100, caja=20, archivo="InterDisplay-ExtraBold.ttf", mayusculas=True, espacio_extra=0):
    """Devuelve [(lista_de_palabras, tamano_a_usar)]. Corte por ancho, no por cantidad de letras."""
    grupos, grupo = [], []
    ver = (lambda p: p.upper()) if mayusculas else (lambda p: p)

    def mide(texto, t):   # el ancho con caja y con el aire entre palabras
        return ancho_con_caja(texto, t, caja, archivo, espacio_extra)

    for p in palabras:
        prueba = grupo + [p]
        entra = mide(" ".join(ver(x) for x in prueba), tamano) <= ANCHO_UTIL
        termina_frase = grupo and grupo[-1].rstrip('"»”').endswith((".", "?", "!", ":"))
        if grupo and (not entra or len(grupo) >= MAX_PALABRAS or termina_frase):
            pasa = []
            # no dejar "el", "de", "un"... colgando al final del grupo: pasan al siguiente si entran ahí
            while (not termina_frase and len(grupo) > 1 and _limpia(grupo[-1]) in DEBILES
                   and len(pasa) + 2 <= MAX_PALABRAS
                   and mide(" ".join(ver(x) for x in [grupo[-1], *pasa, p]), tamano) <= ANCHO_UTIL):
                pasa.insert(0, grupo.pop())
            grupos.append(grupo); grupo = pasa
        grupo.append(p)
    if grupo:
        grupos.append(grupo)
    salida = []
    for g in grupos:
        t = tamano
        while mide(" ".join(ver(x) for x in g), t) > ANCHO_UTIL and t > TAMANO_MINIMO:
            t -= 2
        salida.append((g, t))
    return salida


if __name__ == "__main__":
    texto = sys.argv[1] if len(sys.argv) > 1 else "MUNICIPALIDAD ANUNCIÓ HOY"
    for g, t in agrupar(texto.split()):
        print(f"{' '.join(g).upper():40s} tamaño {t}  ancho {ancho_con_caja(' '.join(g).upper(), t, 20):.0f} px")
