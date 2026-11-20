#!/bin/bash
# Instala Portavoz Lite en una Mac. Lo maneja la skill portavoz-instalar (que pide permiso antes de cada pieza) y lo
# corre igual la prueba de la Mac de GitHub (.github/workflows/mac.yml).
#
# Todo queda ADENTRO de la carpeta de Portavoz Lite, en .herramientas/ (no pide contraseña ni toca el resto de la Mac):
#   Node    -> el archivo oficial de nodejs.org, comparado con su lista de huellas SHASUMS256.txt.
#   Python  -> el armado independiente de Astral (python-build-standalone, el mismo que usa uv), con su huella.
#   FFmpeg  -> los armados de Martin Riedl (ffmpeg.martin-riedl.de), con su huella comprobada y su firma verificada
#           con codesign. Es una firma casera del que lo arma, no de Apple: anda porque lo bajado con curl no lleva la
#           marca de cuarentena, y entonces la Mac no lo frena al abrirlo.
#   git     -> la ventanita de Apple (xcode-select --install), lo único que pide un clic.
# Lo bajado con curl no lleva la marca de cuarentena de Apple, así que no aparece el aviso de "descargado de internet";
# el paso `cuarentena` lo comprueba.
#
# Uso: bash instalar/mac.sh revisar | traer node|python|ffmpeg|git | preparar | icono | probar-llaves | abrir | cuarentena
# Cada paso imprime UNA línea de JSON. Compatible con el bash 3.2 que trae la Mac.
set -u

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
H="$RAIZ/.herramientas"
BIN="$H/bin"
BAJADAS="$H/bajadas"
AGENTE="portavoz-lite/0.1"
ICONO="$HOME/Desktop/Portavoz Lite.command"
export PATH="$BIN:$H/node/bin:$PATH"

esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
bajar() { curl -fsSL --retry 2 --connect-timeout 20 -A "$AGENTE" "$@"; }
mal() { printf '{"paso":"%s","ok":false,"motivo":"%s"}\n' "$(esc "$1")" "$(esc "$2")"; exit 1; }
procesador() { case "$(uname -m)" in arm64) echo arm64 ;; *) echo x64 ;; esac; }

# Baja $1 a $2 y compara su huella con $3. Si no coincide, lo borra.
bajar_con_huella() {
  mkdir -p "$(dirname "$2")"
  bajar -o "$2" "$1" || return 1
  local tiene
  tiene="$(shasum -a 256 "$2" | cut -d' ' -f1)"
  if [ "$tiene" != "$3" ]; then rm -f "$2"; return 2; fi
}

node_sirve() {
  local v
  v="$(node -v 2>/dev/null)" || return 1
  v="${v#v}"
  local may="${v%%.*}" resto="${v#*.}"
  local men="${resto%%.*}"
  [ "$may" -gt 20 ] || { [ "$may" -eq 20 ] && [ "$men" -ge 9 ]; }
}

revisar() {
  local git=false node=false nodev="" py=false pyv="" piezas=false ffmpeg=false ffprobe=false env=false icono=false
  # Ojo: si faltan las herramientas de Apple, llamar a git abre su ventanita. Por eso primero se mira xcode-select.
  local g
  g="$(command -v git || true)"
  if xcode-select -p >/dev/null 2>&1 || { [ -n "$g" ] && [ "$g" != "/usr/bin/git" ]; }; then
    git --version >/dev/null 2>&1 && git=true
  fi
  nodev="$(node -v 2>/dev/null || true)"
  node_sirve && node=true
  if [ -x "$BIN/python" ]; then
    pyv="$("$BIN/python" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null || true)"
    "$BIN/python" -c 'import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null && py=true
    "$BIN/python" -c 'import numpy, fontTools' 2>/dev/null && piezas=true
  fi
  ffmpeg -version >/dev/null 2>&1 && ffmpeg=true
  ffprobe -version >/dev/null 2>&1 && ffprobe=true
  [ -f "$RAIZ/.env" ] && env=true
  [ -f "$ICONO" ] && icono=true
  printf '{"paso":"revisar","ok":true,"sistema":"mac","carpeta":"%s","git":%s,"node":%s,"node_version":"%s","python":%s,"python_version":"%s","piezas_python":%s,"ffmpeg":%s,"ffprobe":%s,"env":%s,"icono":%s}\n' \
    "$(esc "$RAIZ")" "$git" "$node" "$(esc "$nodev")" "$py" "$(esc "$pyv")" "$piezas" "$ffmpeg" "$ffprobe" "$env" "$icono"
}

traer_node() {
  local base="https://nodejs.org/dist/latest-v24.x" linea archivo huella
  linea="$(bajar "$base/SHASUMS256.txt" | grep "darwin-$(procesador)\.tar\.gz$")" || mal traer "sin-internet"
  huella="${linea%% *}"
  archivo="${linea##* }"
  bajar_con_huella "$base/$archivo" "$BAJADAS/$archivo" "$huella" || mal traer "huella-distinta"
  rm -rf "$H/node" && mkdir -p "$H/node"
  tar -xzf "$BAJADAS/$archivo" -C "$H/node" --strip-components 1 || mal traer "no-se-abrio"
  rm -f "$BAJADAS/$archivo"
  printf '{"paso":"traer","pieza":"node","ok":true,"version":"%s"}\n' "$("$H/node/bin/node" -v)"
}

traer_python() {
  local repo="https://github.com/astral-sh/python-build-standalone" etiqueta pa linea huella archivo
  # La última versión publicada sale de adónde redirige /releases/latest (sin usar la API de GitHub, que tiene tope).
  etiqueta="$(curl -sI -A "$AGENTE" "$repo/releases/latest" | tr -d '\r' | grep -i '^location:' | sed 's#.*/tag/##')"
  [ -n "$etiqueta" ] || mal traer "sin-internet"
  case "$(procesador)" in arm64) pa=aarch64 ;; *) pa=x86_64 ;; esac
  linea="$(bajar "$repo/releases/download/$etiqueta/SHA256SUMS" |
    grep -E "cpython-3\.12\.[0-9]+\+$etiqueta-$pa-apple-darwin-install_only\.tar\.gz$" | head -1)"
  [ -n "$linea" ] || mal traer "sin-version"
  huella="${linea%% *}"
  archivo="${linea##* }"
  bajar_con_huella "$repo/releases/download/$etiqueta/${archivo//+/%2B}" "$BAJADAS/$archivo" "$huella" || mal traer "huella-distinta"
  rm -rf "$H/python" && mkdir -p "$H/python" "$BIN"
  tar -xzf "$BAJADAS/$archivo" -C "$H/python" --strip-components 1 || mal traer "no-se-abrio"
  rm -f "$BAJADAS/$archivo"
  ln -sf ../python/bin/python3 "$BIN/python"
  ln -sf ../python/bin/python3 "$BIN/python3"
  printf '{"paso":"traer","pieza":"python","ok":true,"version":"%s"}\n' "$("$BIN/python" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])')"
}

traer_ffmpeg() {
  local cpu firmas="" p real huella
  case "$(procesador)" in arm64) cpu=arm64 ;; *) cpu=amd64 ;; esac
  mkdir -p "$BIN"
  for p in ffmpeg ffprobe; do
    # La dirección "latest" redirige a la versión de verdad; la huella está al lado, con .sha256.
    real="$(curl -s -o /dev/null -w '%{redirect_url}' -A "$AGENTE" "https://ffmpeg.martin-riedl.de/redirect/latest/macos/$cpu/release/$p.zip")"
    [ -n "$real" ] || mal traer "sin-internet"
    huella="$(bajar "$real.sha256" | cut -d' ' -f1)"
    [ -n "$huella" ] || mal traer "sin-huella"
    bajar_con_huella "$real" "$BAJADAS/$p.zip" "$huella" || mal traer "huella-distinta"
    unzip -o -q "$BAJADAS/$p.zip" -d "$BIN" || mal traer "no-se-abrio"
    rm -f "$BAJADAS/$p.zip"
    chmod +x "$BIN/$p"
    if ! codesign --verify --strict "$BIN/$p" 2>/dev/null; then
      rm -f "$BIN/ffmpeg" "$BIN/ffprobe"
      mal traer "sin-firma"
    fi
    firmas="$firmas$(codesign -dv "$BIN/$p" 2>&1 | grep -m1 -E '^(Authority=|Signature=adhoc)' | sed 's/^Authority=//; s/^Signature=adhoc/casera/');"
  done
  printf '{"paso":"traer","pieza":"ffmpeg","ok":true,"firma":"%s"}\n' "$(esc "$firmas")"
}

traer_git() {
  if xcode-select -p >/dev/null 2>&1; then
    printf '{"paso":"traer","pieza":"git","ok":true,"ya_estaba":true}\n'
  else
    xcode-select --install >/dev/null 2>&1
    # Abre la ventanita de Apple. La persona toca "Instalar"; después se vuelve a correr `revisar`.
    printf '{"paso":"traer","pieza":"git","ok":true,"esperando":true}\n'
  fi
}

preparar() {
  "$BIN/python" -m pip install --disable-pip-version-check -q -r "$RAIZ/motor/requisitos.txt" >/dev/null 2>&1 || mal preparar "python"
  (cd "$RAIZ/estudio" && npm ci --no-audit --no-fund >/dev/null 2>&1) || mal preparar "piezas"
  (cd "$RAIZ/estudio" && npm run build >/dev/null 2>&1) || mal preparar "armado"
  printf '{"paso":"preparar","ok":true}\n'
}

icono() {
  local node
  if [ -x "$H/node/bin/node" ]; then node="$H/node/bin/node"; else node="$(command -v node)"; fi
  [ -n "$node" ] || mal icono "sin-node"
  mkdir -p "$(dirname "$ICONO")"
  printf '#!/bin/bash\n# Abre Portavoz Lite. Lo dejó la instalación; si se borra, se rehace pidiéndole a Claude "rehacé el ícono".\nexec "%s" "%s"\n' \
    "$node" "$RAIZ/estudio/scripts/arrancar.mjs" > "$ICONO"
  chmod +x "$ICONO"
  # El dibujo y la extensión escondida, con el JavaScript de Apple que ya viene en la Mac.
  osascript -l JavaScript - "$RAIZ/marca/portavoz.png" "$ICONO" >/dev/null 2>&1 <<'JXA' || true
ObjC.import('AppKit');
function run(argv) {
  var img = $.NSImage.alloc.initWithContentsOfFile(argv[0]);
  $.NSWorkspace.sharedWorkspace.setIconForFileOptions(img, argv[1], 0);
  $.NSFileManager.defaultManager.setAttributesOfItemAtPathError($({ NSFileExtensionHidden: true }), argv[1], null);
}
JXA
  printf '{"paso":"icono","ok":true,"donde":"%s"}\n' "$(esc "$ICONO")"
}

probar_llaves() {
  "$BIN/python" -B "$RAIZ/motor/chequeo.py" --llaves
}

cuarentena() {
  local marcados
  marcados="$(xattr -lr "$H" "$ICONO" 2>/dev/null | grep -c 'com.apple.quarantine' || true)"
  if [ "${marcados:-0}" -gt 0 ]; then
    printf '{"paso":"cuarentena","ok":false,"marcados":%s}\n' "$marcados"
    exit 1
  fi
  printf '{"paso":"cuarentena","ok":true,"marcados":0}\n'
}

case "${1:-}" in
  revisar) revisar ;;
  traer)
    case "${2:-}" in
      node) traer_node ;; python) traer_python ;; ffmpeg) traer_ffmpeg ;; git) traer_git ;;
      *) mal traer "pieza-desconocida" ;;
    esac ;;
  preparar) preparar ;;
  icono) icono ;;
  probar-llaves) probar_llaves ;;
  abrir) open "$ICONO" && printf '{"paso":"abrir","ok":true}\n' ;;
  cuarentena) cuarentena ;;
  *) mal "${1:-}" "paso-desconocido" ;;
esac
