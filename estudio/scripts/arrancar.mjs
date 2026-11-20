// El arranque de Portavoz Lite: lo que corre el ícono del escritorio (lo crea la skill portavoz-instalar).
// 1. Si el Estudio ya está prendido (doble clic repetido), sólo abre el navegador.
// 2. Trae lo nuevo de GitHub, sin pedir clave y con tope de tiempo. Sin internet sigue con lo que tiene.
//    Si la carpeta tiene cambios propios o se desvió, NO actualiza y lo dice: nunca se borra nada de la persona.
//    Lo de la persona (.env, trabajos/, estudio/datos/...) está fuera de git: una actualización no lo toca nunca.
// 3. Arma el Estudio nuevo EN UNA CARPETA APARTE (.next-nuevo) y sólo si salió bien reemplaza al que anda (.next).
//    Si falla, vuelve los archivos del programa a la versión de antes, anota la versión mala (estudio/datos/arranque.json)
//    y no la vuelve a probar hasta que llegue una más nueva.
// 4. Prende el Estudio con el motor de verdad en esta compu (127.0.0.1) y abre el navegador.
// La ventana queda abierta (minimizada) mientras el Estudio anda: cerrarla lo apaga.
// Las pruebas (scripts/arranque.mjs) llaman a arrancar() con sus propias piezas, sin internet y sin Next.
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, delimiter, join, resolve } from "node:path";
import { connect } from "node:net";
import { fileURLToPath, pathToFileURL } from "node:url";
import { ARRANQUE } from "../lib/textos.js";

const ESTUDIO_DE_ACA = fileURLToPath(new URL("../", import.meta.url));
export const PUERTO = 3100;

// Lo que se le dice a la persona: está en lib/textos.js (ARRANQUE), donde lo revisa scripts/revisar.mjs.
export const DICE = ARRANQUE;

// ---------------------------------------------------------------------------------------------
// Piezas chicas

export function leerEnv(ruta) {
  const datos = {};
  let texto = "";
  try {
    texto = readFileSync(ruta, "utf8").replace(/^﻿/, "");
  } catch {
    return datos;
  }
  for (const crudo of texto.split(/\r?\n/)) {
    const linea = crudo.trim();
    if (!linea || linea.startsWith("#") || !linea.includes("=")) continue;
    const i = linea.indexOf("=");
    const v = linea.slice(i + 1).trim().replace(/^["']|["']$/g, "");
    if (v) datos[linea.slice(0, i).trim()] = v;
  }
  return datos;
}

/** Qué llaves faltan para armar un video (los nombres en criollo). Las prestadas de Lucio cuentan como Google. */
export function llavesQueFaltan(env) {
  const faltan = [];
  const google = env.GEMINI_API_KEY || env.GEMINI_API_KEY_REPUESTO || process.env.GEMINI_API_KEY || env.PORTAVOZ_LLAVES_PRESTADAS;
  if (!google) faltan.push(DICE.faltaGoogle);
  if (!(env.PEXELS_API_KEY || process.env.PEXELS_API_KEY)) faltan.push(DICE.faltaPexels);
  return faltan;
}

/** El entorno del Estudio: la carpeta de Python elegido al instalar y las piezas de la Mac van primero en la lista
 *  de carpetas donde se buscan programas, así "python", "ffmpeg" y "ffprobe" son los de la instalación. */
export function entornoDelEstudio(raiz, env, base = process.env) {
  const claveRuta = Object.keys(base).find((k) => k.toUpperCase() === "PATH") || "PATH";
  const primero = [];
  if (env.PORTAVOZ_PYTHON) primero.push(dirname(env.PORTAVOZ_PYTHON));
  for (const sub of [join(".herramientas", "bin"), join(".herramientas", "node", "bin")]) {
    if (existsSync(join(raiz, sub))) primero.push(join(raiz, sub));
  }
  const entorno = { ...base, PORTAVOZ_FUENTE: "motor" };
  entorno[claveRuta] = [...primero, base[claveRuta] || ""].filter(Boolean).join(delimiter);
  return entorno;
}

function huella(ruta) {
  try {
    return createHash("sha256").update(readFileSync(ruta)).digest("hex");
  } catch {
    return "";
  }
}

const rutaEstado = (estudio) => join(estudio, "datos", "arranque.json");
export function leerEstado(estudio) {
  try {
    return JSON.parse(readFileSync(rutaEstado(estudio), "utf8"));
  } catch {
    return {};
  }
}
function guardarEstado(estudio, estado) {
  mkdirSync(join(estudio, "datos"), { recursive: true });
  writeFileSync(rutaEstado(estudio), JSON.stringify(estado, null, 2) + "\n");
}

/** git sin preguntar nunca nada (ni clave ni usuario) y con tope de tiempo. Devuelve { ok, salida }. */
export function git(raiz, args, tope = 20_000) {
  const r = spawnSync("git", ["-C", raiz, ...args], {
    encoding: "utf8",
    windowsHide: true,
    timeout: tope,
    env: { ...process.env, GIT_TERMINAL_PROMPT: "0", GCM_INTERACTIVE: "never", GIT_ASKPASS: "", SSH_ASKPASS: "" },
  });
  return { ok: r.status === 0, salida: (r.stdout || "").trim() };
}

// ---------------------------------------------------------------------------------------------
// Armar aparte y cambiar

/** Arma en .next-nuevo con `armar(carpeta)` y, sólo si salió bien, lo pone en lugar de .next. */
export async function armarAparte(estudio, armar) {
  const nuevo = join(estudio, ".next-nuevo");
  const anterior = join(estudio, ".next-anterior");
  const actual = join(estudio, ".next");
  rmSync(nuevo, { recursive: true, force: true });
  const ok = await armar(".next-nuevo");
  if (!ok || !existsSync(join(nuevo, "BUILD_ID"))) {
    rmSync(nuevo, { recursive: true, force: true });
    return false;
  }
  rmSync(anterior, { recursive: true, force: true });
  if (existsSync(actual)) renameSync(actual, anterior);
  renameSync(nuevo, actual);
  rmSync(anterior, { recursive: true, force: true });
  return true;
}

// ---------------------------------------------------------------------------------------------
// Actualizar

/**
 * Trae lo nuevo si se puede. Devuelve el resultado en una palabra (las pruebas lo miran):
 * sin-git | sin-internet | al-dia | cambios-propios | desviada | version-mala | no-se-pudo | actualizada | fallo
 */
export async function actualizar({ raiz, estudio, armar, instalar, decir }) {
  if (!existsSync(join(raiz, ".git"))) return "sin-git";
  decir(DICE.buscando);
  if (!git(raiz, ["fetch", "--quiet", "origin"]).ok) {
    decir(DICE.sinInternet);
    return "sin-internet";
  }
  const local = git(raiz, ["rev-parse", "HEAD"]).salida;
  const remoto = git(raiz, ["rev-parse", "@{u}"]).salida;
  if (!local || !remoto) {
    decir(DICE.noSePudo);
    return "no-se-pudo";
  }
  if (local === remoto) {
    decir(DICE.alDia);
    return "al-dia";
  }
  const cambios = git(raiz, ["status", "--porcelain", "--untracked-files=no"]);
  if (!cambios.ok || cambios.salida) {
    decir(DICE.cambiosPropios);
    return "cambios-propios";
  }
  const adelante = Number(git(raiz, ["rev-list", "--count", "@{u}..HEAD"]).salida || "0");
  if (adelante > 0) {
    decir(DICE.desviada);
    return "desviada";
  }
  const estado = leerEstado(estudio);
  if (estado.versionMala === remoto) {
    decir(DICE.versionMala);
    return "version-mala";
  }
  decir(DICE.actualizando);
  const lock = join(estudio, "package-lock.json");
  const lockAntes = huella(lock);
  if (!git(raiz, ["merge", "--ff-only", "--quiet", "@{u}"], 60_000).ok) {
    decir(DICE.noSePudo);
    return "no-se-pudo";
  }
  const cambioLock = huella(lock) !== lockAntes;
  const anduvo = (!cambioLock || (await instalar())) && (await armarAparte(estudio, armar));
  if (anduvo) {
    guardarEstado(estudio, { ...estado, versionMala: null, version: remoto });
    decir(DICE.actualizada);
    return "actualizada";
  }
  // Volver a la versión que andaba. Sólo se llega acá sin cambios propios: lo de la persona está fuera de git.
  git(raiz, ["reset", "--hard", "--quiet", local], 60_000);
  if (cambioLock) await instalar();
  guardarEstado(estudio, { ...estado, versionMala: remoto, version: local });
  decir(DICE.fallo);
  return "fallo";
}

// ---------------------------------------------------------------------------------------------
// ¿Ya está prendido?

/** "nuestro" si en ese lugar contesta Portavoz Lite, "ajeno" si contesta otro programa, "libre" si no hay nadie. */
export async function quienEsta(puerto) {
  // Si la pregunta falla por algo raro (una conexión vieja que se cortó, por ejemplo), se repite una vez y, si sigue
  // fallando, se mira directo si hay algún programa escuchando en ese lugar.
  for (let vez = 0; vez < 2; vez += 1) {
    try {
      const r = await fetch(`http://127.0.0.1:${puerto}/api/salud`, {
        signal: AbortSignal.timeout(2000),
        headers: { connection: "close" },
      });
      const datos = await r.json().catch(() => ({}));
      return datos?.portavoz === "lite" ? "nuestro" : "ajeno";
    } catch (e) {
      if (e?.cause?.code === "ECONNREFUSED") return "libre";
    }
  }
  return (await hayAlguien(puerto)) ? "ajeno" : "libre";
}

function hayAlguien(puerto) {
  return new Promise((listo) => {
    const s = connect({ host: "127.0.0.1", port: puerto });
    const fin = (hay) => {
      s.destroy();
      listo(hay);
    };
    s.setTimeout(2000, () => fin(true));
    s.once("connect", () => fin(true));
    s.once("error", () => fin(false));
  });
}

async function esperarQueConteste(puerto, tope = 60_000) {
  const hasta = Date.now() + tope;
  while (Date.now() < hasta) {
    if ((await quienEsta(puerto)) === "nuestro") return true;
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

// ---------------------------------------------------------------------------------------------
// Lo de verdad: Next, npm y el navegador

const nextDe = (estudio) => join(estudio, "node_modules", "next", "dist", "bin", "next");

function armarConNext(estudio, entorno) {
  return (carpeta) =>
    new Promise((listo) => {
      const hijo = spawn(process.execPath, [nextDe(estudio), "build"], {
        cwd: estudio,
        env: { ...entorno, PORTAVOZ_ARMADO: carpeta },
        stdio: ["ignore", "ignore", "inherit"],
        windowsHide: true,
      });
      hijo.on("exit", (c) => listo(c === 0));
      hijo.on("error", () => listo(false));
    });
}

function instalarConNpm(estudio, entorno) {
  return () =>
    new Promise((listo) => {
      const npm = process.platform === "win32" ? "npm.cmd" : "npm";
      const hijo = spawn(npm, ["ci", "--no-audit", "--no-fund", "--loglevel=error"], {
        cwd: estudio,
        env: entorno,
        stdio: ["ignore", "ignore", "inherit"],
        shell: process.platform === "win32",
        windowsHide: true,
      });
      hijo.on("exit", (c) => listo(c === 0));
      hijo.on("error", () => listo(false));
    });
}

function prenderConNext(estudio, entorno, puerto) {
  return spawn(process.execPath, [nextDe(estudio), "start", "-H", "127.0.0.1", "-p", String(puerto)], {
    cwd: estudio,
    env: entorno,
    stdio: ["ignore", "ignore", "inherit"],
  });
}

export function abrirNavegador(link) {
  const [programa, args] =
    process.platform === "win32" ? ["cmd", ["/c", "start", "", link]] : process.platform === "darwin" ? ["open", [link]] : ["xdg-open", [link]];
  try {
    spawn(programa, args, { stdio: "ignore", detached: true, windowsHide: true }).unref();
  } catch {
    // si no se puede abrir, el link queda escrito en la ventana
  }
}

function minimizarEnMac() {
  if (process.platform !== "darwin") return;
  try {
    spawn("osascript", ["-e", 'tell application "Terminal" to set miniaturized of front window to true'], { stdio: "ignore" });
  } catch {
    // no pasa nada si no se puede
  }
}

function esperarEnter() {
  if (!process.stdin.isTTY) return Promise.resolve();
  console.log(`\n${DICE.cerrar}`);
  return new Promise((r) => {
    process.stdin.resume();
    process.stdin.once("data", () => r());
  });
}

// ---------------------------------------------------------------------------------------------
// Todo junto

/**
 * Arranca Portavoz Lite. Las piezas (armar, instalar, prender, abrir, decir) se pueden cambiar en las pruebas.
 * Devuelve { como, actualizacion, link, servidor }.
 */
export async function arrancar(op = {}) {
  const estudio = resolve(op.estudio || ESTUDIO_DE_ACA);
  const raiz = resolve(op.raiz || join(estudio, ".."));
  const puerto = op.puerto || PUERTO;
  const decir = op.decir || ((t) => console.log(t));
  const abrir = op.abrir || abrirNavegador;
  const env = leerEnv(join(raiz, ".env"));
  const entorno = entornoDelEstudio(raiz, env);
  const armar = op.armar || armarConNext(estudio, entorno);
  const instalar = op.instalar || instalarConNpm(estudio, entorno);
  const prender = op.prender || (() => prenderConNext(estudio, entorno, puerto));
  const link = `http://127.0.0.1:${puerto}`;

  const ahora = await quienEsta(puerto);
  if (ahora === "nuestro") {
    decir(DICE.yaPrendido);
    abrir(link);
    return { como: "ya-prendido", link };
  }
  if (ahora === "ajeno") {
    decir(DICE.puertoAjeno);
    return { como: "puerto-ajeno", link };
  }

  const actualizacion = op.sinActualizar ? "sin-actualizar" : await actualizar({ raiz, estudio, armar, instalar, decir });

  if (!existsSync(join(estudio, ".next", "BUILD_ID"))) {
    decir(DICE.primeraVez);
    if (!(await armarAparte(estudio, armar))) {
      decir(DICE.sinArmado);
      return { como: "sin-armado", actualizacion, link };
    }
  }

  const faltan = llavesQueFaltan(env);
  decir(DICE.prendiendo);
  const servidor = prender();
  if (!(await esperarQueConteste(puerto, op.tope || 90_000))) {
    try {
      servidor.kill();
    } catch {
      // ya se cerró
    }
    decir(DICE.noPrendio);
    return { como: "no-prendio", actualizacion, link };
  }
  if (faltan.length) {
    decir(DICE.faltanLlaves(faltan.join(" y ")));
    abrir(`${link}/ajustes`);
  } else {
    abrir(link);
  }
  decir(DICE.prendido(link));
  return { como: "prendido", actualizacion, link, servidor, faltan };
}

// Corrido directo (el ícono): arranca y queda vivo mientras el Estudio ande.
if (import.meta.url === pathToFileURL(process.argv[1] || "").href) {
  process.title = "Portavoz Lite";
  const r = await arrancar();
  if (r.como === "prendido") {
    minimizarEnMac();
    r.servidor.on("exit", async () => {
      console.log(DICE.noPrendio);
      await esperarEnter();
      process.exit(1);
    });
    process.on("SIGINT", () => r.servidor.kill());
  } else if (r.como !== "ya-prendido") {
    await esperarEnter();
    process.exit(1);
  }
}
