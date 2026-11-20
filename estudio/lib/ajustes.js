// Ajustes: quién escribe los guiones y las llaves, guardados en el .env de la raíz (el mismo que lee el motor,
// motor/llaves.py). Sólo corre del lado de la compu. Reglas:
// - Una llave NUNCA sale entera de acá: la pantalla recibe los últimos 4 caracteres (los da motor/chequeo.py).
// - Cambiar el .env conserva todas las demás líneas tal cual (comentarios incluidos).
// - Una llave nueva se prueba con un pedido que no gasta antes de guardarla (chequeo.py --probar, la llave va por la
//   entrada del programa, nunca en sus argumentos).
// - Con el Estudio abierto al wifi (npm run celular) no se cambia nada: cualquiera en esa red podría hacerlo.
// PORTAVOZ_ENV cambia el archivo (las pruebas usan uno temporal); PORTAVOZ_MOTOR, la carpeta del motor.
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { carpetaMotor } from "./fuente/motor.js";

export const NOMBRE_EN_ENV = { google: "GEMINI_API_KEY", pexels: "PEXELS_API_KEY", anthropic: "ANTHROPIC_API_KEY" };
export const LLAVES = Object.keys(NOMBRE_EN_ENV);
export const QUIEN_ESCRIBE = ["", "claude", "anthropic", "google"];
const TOPE = 30 * 1000;

export const rutaEnv = () => process.env.PORTAVOZ_ENV || join(/*turbopackIgnore: true*/ process.cwd(), "..", ".env");
export const soloMirar = () => process.env.PORTAVOZ_CELULAR === "si";

/** Corre chequeo.py con `args` y, si hace falta, le pasa `entrada` por la entrada. Devuelve lo que imprimió o null. */
function chequeo(args, entrada = "") {
  return new Promise((resolver) => {
    let salida = "";
    let hijo;
    try {
      hijo = spawn("python", ["-B", join(/*turbopackIgnore: true*/ carpetaMotor(), "chequeo.py"), ...args], {
        windowsHide: true,
        stdio: ["pipe", "pipe", "ignore"],
        env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1", PORTAVOZ_ENV: rutaEnv() },
      });
    } catch {
      resolver(null);
      return;
    }
    const reloj = setTimeout(() => hijo.kill(), TOPE);
    hijo.stdout.setEncoding("utf8");
    hijo.stdout.on("data", (d) => (salida += d));
    hijo.on("error", () => resolver(null));
    hijo.on("close", () => {
      clearTimeout(reloj);
      try {
        resolver(JSON.parse(salida.trim().split("\n").pop()));
      } catch {
        resolver(null);
      }
    });
    hijo.stdin.end(entrada ? `${entrada}\n` : "");
  });
}

/** Una llave queda reducida a sus últimos 4 caracteres. Se usa como red: aunque chequeo.py ya los manda así. */
export function finalDe(valor) {
  if (!valor) return null;
  const v = String(valor);
  return v.startsWith("…") && v.length <= 5 ? v : `…${v.slice(-4)}`;
}

/** Lo que muestra la pantalla: { escribe, elegido, claudeCode, llaves: { google: "…abcd" | null, ... }, prestadas,
 *  soloMirar }, o null si no se pudo leer. */
export async function leerAjustes() {
  const datos = await chequeo([]);
  if (!datos || datos.error) return null;
  const llaves = {};
  for (const n of LLAVES) llaves[n] = finalDe(datos.llaves?.[n]);
  return {
    escribe: datos.escribe,
    elegido: QUIEN_ESCRIBE.includes(datos.elegido) ? datos.elegido : "",
    claudeCode: Boolean(datos.claude_code),
    llaves,
    prestadas: Boolean(datos.prestadas),
    soloMirar: soloMirar(),
  };
}

/** Cambia (o agrega) líneas NOMBRE=valor del .env y deja todo lo demás como estaba. */
export function cambiarEnv(texto, cambios) {
  const lineas = texto.length ? texto.replace(/\r\n/g, "\n").replace(/\n$/, "").split("\n") : [];
  const faltan = new Map(Object.entries(cambios));
  const nuevas = lineas.map((l) => {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=/.exec(l);
    if (m && faltan.has(m[1])) {
      const v = faltan.get(m[1]);
      faltan.delete(m[1]);
      return `${m[1]}=${v}`;
    }
    return l;
  });
  for (const [k, v] of faltan) nuevas.push(`${k}=${v}`);
  return nuevas.join("\n") + "\n";
}

function guardarEnv(cambios) {
  let texto = "";
  try {
    texto = readFileSync(rutaEnv(), "utf8").replace(/^﻿/, "");
  } catch {
    // no había .env: se crea
  }
  writeFileSync(rutaEnv(), cambiarEnv(texto, cambios));
}

/** Una llave tiene forma razonable: sin espacios ni saltos (no se puede colar otra línea en el .env). */
export const llaveValida = (v) => typeof v === "string" && /^[A-Za-z0-9_\-.]{8,300}$/.test(v.trim());

/** Prueba la llave nueva y, si anda, la guarda. Devuelve "guardada", "mala", "sin-internet" o "vacia". */
export async function ponerLlave(nombre, valor) {
  if (!LLAVES.includes(nombre)) return "mala";
  if (!valor || !String(valor).trim()) return "vacia";
  if (!llaveValida(valor)) return "mala";
  const r = await chequeo(["--probar", nombre], valor.trim());
  const resultado = r?.resultado;
  if (resultado !== "anda") return resultado === "sin-internet" ? "sin-internet" : "mala";
  guardarEnv({ [NOMBRE_EN_ENV[nombre]]: valor.trim() });
  return "guardada";
}

export function elegirQuienEscribe(quien) {
  if (!QUIEN_ESCRIBE.includes(quien)) return false;
  guardarEnv({ PORTAVOZ_TEXTO: quien });
  return true;
}
