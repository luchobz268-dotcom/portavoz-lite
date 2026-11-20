// Lo que comparten las dos fuentes (ejemplos.js y motor.js) para guardar trabajos y armarlos de a uno:
// - escribir un JSON entero o nada, leerlo sin romperse;
// - el id de un trabajo y la lectura de su carpeta;
// - la FILA del armado: UNA para todo el Estudio (vive en globalThis para que la compartan todas las rutas), un armado
//   por vez. Cada trabajo tiene además un candado en su carpeta (armando.lock: { pid, hora }), para que otro proceso
//   no lo arme a la vez. El candado nunca se borra: al terminar se pisa con { libre: true };
// - "una vez": dos pedidos iguales a la vez reciben la misma respuesta.
// Salió de ejemplos.js el 2026-11-18 sin cambiar cómo se porta: lo único nuevo es que cada lugar de la fila lleva la
// función que lo arma (la de los ejemplos o la del motor).
import { spawnSync } from "node:child_process";
import { randomInt } from "node:crypto";
import { readFileSync, renameSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { crearError, esCodigoError, esIdTrabajo, linkValido, revisarTrabajoGuardado } from "../contrato.js";

export const dos = (n) => String(n).padStart(2, "0");
const LETRAS_ID = "abcdefghijklmnopqrstuvwxyz0123456789";

/** AAAAMMDD-HHMMSS-xxxx con la hora local. Lo arma siempre el servidor, nunca la pantalla. */
export function nuevoId(fecha) {
  const dia = `${fecha.getFullYear()}${dos(fecha.getMonth() + 1)}${dos(fecha.getDate())}`;
  const hora = `${dos(fecha.getHours())}${dos(fecha.getMinutes())}${dos(fecha.getSeconds())}`;
  const azar = Array.from({ length: 4 }, () => LETRAS_ID[randomInt(LETRAS_ID.length)]).join("");
  return `${dia}-${hora}-${azar}`;
}

export const rutaDe = (carpeta, id, archivo) => join(/*turbopackIgnore: true*/ carpeta, id, archivo);

/** Lee un trabajo de su carpeta. Devuelve el trabajo, o null si falta, está roto o no cumple el contrato. */
export function leerUno(carpeta, id) {
  if (!esIdTrabajo(id)) return null;
  try {
    const t = JSON.parse(readFileSync(/*turbopackIgnore: true*/ join(carpeta, id, "trabajo.json"), "utf8"));
    // La revisión liviana: si cambia una cuenta que se estima (las palabras por segundo), un video hecho no desaparece.
    if (t?.id !== id || revisarTrabajoGuardado(t).length > 0) return null;
    // Un código de error que no está en la lista (de otra versión, o un nombre como "constructor") sale como
    // DESCONOCIDO: la pantalla sólo recibe códigos que conoce.
    return t.error && !esCodigoError(t.error.codigo) ? { ...t, error: { ...t.error, ...crearError("DESCONOCIDO").error } } : t;
  } catch {
    return null;
  }
}

/** Lee un JSON; null si falta o está roto. */
export function leerJson(ruta) {
  try {
    return JSON.parse(readFileSync(/*turbopackIgnore: true*/ ruta, "utf8"));
  } catch {
    return null;
  }
}

const pausa = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

/** Escribe un JSON entero o nada: primero a un nombre temporal y después lo renombra. */
export function escribirJson(ruta, datos) {
  const temporal = `${ruta}.${process.pid}-${randomInt(1e9)}.tmp`;
  writeFileSync(/*turbopackIgnore: true*/ temporal, `${JSON.stringify(datos, null, 2)}\n`);
  for (let vuelta = 0; ; vuelta += 1) {
    try {
      renameSync(/*turbopackIgnore: true*/ temporal, ruta);
      return;
    } catch (e) {
      // En Windows, si otro lo está leyendo justo, el renombre falla un instante.
      if (vuelta >= 10 || !["EPERM", "EBUSY", "EACCES"].includes(e.code)) throw e;
      pausa(20);
    }
  }
}

/** Deja sólo lo que se guarda del pedido. Con texto pegado, un link que no sirve se saca (como en leerNota). */
export function limpiarPedido(p) {
  if (!p || typeof p !== "object") return p;
  const link = typeof p.link === "string" ? p.link.trim() : p.link;
  const limpio = { largo: p.largo };
  if (p.texto) limpio.texto = p.texto;
  if (link && !(p.texto && !linkValido(link))) limpio.link = link;
  return limpio;
}

/** Saca de un texto de error la carpeta personal de quien usa la PC. */
export const sinCarpetaPersonal = (texto) => String(texto ?? "").split(homedir()).join("~").trim().slice(0, 300);

export function marcarFallo(carpeta, t, error) {
  const nuevo = { ...t, estado: "fallo", error };
  escribirJson(rutaDe(carpeta, t.id, "trabajo.json"), nuevo);
  return nuevo;
}

/** Anota en el trabajo que falló cuál lo volvió a probar. Se parte de lo guardado tal cual (leerUno cambia los
 *  códigos de error que no conoce). Si no se puede, se lo encuentra igual por el reintentoDe del nuevo. */
export function anotarReintento(carpeta, id, idNuevo) {
  const ruta = rutaDe(carpeta, id, "trabajo.json");
  const guardado = leerJson(ruta);
  if (guardado?.id !== id) return;
  try {
    escribirJson(ruta, { ...guardado, reintentadoEn: idNuevo });
  } catch {
    // Queda sin anotar.
  }
}

/** Pedidos que se están atendiendo, por clave. Si llega otro con la misma clave mientras tanto (dos toques, dos
 *  pestañas), espera al primero y recibe lo mismo. Vive en globalThis, como la fila: lo comparten todas las rutas. */
const enCurso = () => (globalThis.__portavozEnCurso ??= new Map());
export function unaVez(clave, hacer) {
  const m = enCurso();
  if (m.has(clave)) return m.get(clave);
  const p = Promise.resolve()
    .then(hacer)
    .finally(() => m.delete(clave));
  m.set(clave, p);
  return p;
}

// ---------------------------------------------------------------------------------------------
// La fila

/** Un candado más viejo que esto es de un armado que se murió. */
export const VENCE_CANDADO = 10 * 60 * 1000;

export const fila = () => (globalThis.__portavozFilaArmado ??= { pendientes: [], enCurso: null, corridas: {}, hijo: null });

/** Para las pruebas: qué hay en la fila y cuántas veces se corrió el armado de cada trabajo. */
export function estadoFila() {
  const f = fila();
  return { pendientes: f.pendientes.map((p) => p.id), enCurso: f.enCurso?.id ?? null, corridas: { ...f.corridas } };
}

/** Corta Python y lo que haya abierto (FFmpeg). En Windows, matar sólo a Python deja a FFmpeg andando. */
export function matar(hijo) {
  if (!hijo?.pid || hijo.exitCode !== null) return;
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(hijo.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
  } else {
    hijo.kill("SIGKILL");
  }
}

/** Vacía la fila y corta el armado en curso (para que las pruebas terminen sin dejar nada andando). */
export function pararFila() {
  const f = fila();
  f.pendientes.length = 0;
  matar(f.hijo);
}

function pidVivo(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM";
  }
}

/** El candado, si alguien lo tiene de verdad: no está libre, no se venció y su proceso sigue vivo. */
export function candadoVivo(carpeta, id, vence = VENCE_CANDADO) {
  const c = leerJson(rutaDe(carpeta, id, "armando.lock"));
  return c && !c.libre && Date.now() - Number(c.hora) < vence && pidVivo(c.pid) ? c : null;
}

export function tomarCandado(carpeta, id, vence = VENCE_CANDADO) {
  const ruta = rutaDe(carpeta, id, "armando.lock");
  const datos = JSON.stringify({ pid: process.pid, hora: Date.now() });
  try {
    writeFileSync(/*turbopackIgnore: true*/ ruta, datos, { flag: "wx" });
    return true;
  } catch (e) {
    if (e.code !== "EEXIST") throw e;
    if (candadoVivo(carpeta, id, vence)) return false;
    writeFileSync(/*turbopackIgnore: true*/ ruta, datos);
    return true;
  }
}

export const escribirCandado = (carpeta, id, datos) =>
  writeFileSync(/*turbopackIgnore: true*/ rutaDe(carpeta, id, "armando.lock"), JSON.stringify(datos));

/** Si el trabajo está en la fila (esperando o armándose en este Estudio). */
export const enFila = (id) => {
  const f = fila();
  return f.enCurso?.id === id || f.pendientes.some((p) => p.id === id);
};

/** Pone un trabajo en la fila. `armar({ carpeta, id })` es la función que lo arma (devuelve una promesa). */
export function encolar(carpeta, id, armar) {
  const f = fila();
  if (enFila(id)) return;
  f.pendientes.push({ carpeta, id, armar });
  if (!f.enCurso) siguiente();
}

function siguiente() {
  const f = fila();
  const item = f.pendientes.shift();
  if (!item) return;
  f.enCurso = item;
  // Se llama en el acto (no en la vuelta siguiente), como antes en ejemplos.js: el candado se toma ya.
  let armado;
  try {
    armado = Promise.resolve(item.armar(item));
  } catch (e) {
    armado = Promise.reject(e);
  }
  armado
    .catch(() => {})
    .finally(() => {
      f.enCurso = null;
      siguiente();
    });
}

/** Cuántos videos hay antes que éste en la fila del armado (0 si no está esperando su turno). */
export function videosAntes(id) {
  const f = fila();
  const i = f.pendientes.findIndex((p) => p.id === id);
  if (i < 0) return 0;
  return i + (f.enCurso && f.enCurso.id !== id ? 1 : 0);
}

const DIA_PACIFICO = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit" });
/** El día (AAAA-MM-DD) en la hora del Pacífico: Google renueva los topes del día a esa medianoche. */
export const diaPacifico = (fecha) => DIA_PACIFICO.format(fecha);
