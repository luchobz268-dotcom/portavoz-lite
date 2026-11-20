// Fuente de VERDAD: llama a los programas de Python de ../motor (leer la nota, escribir los guiones, armar el video y
// pedir otro texto). Cumple el mismo contrato que ejemplos.js, así la pantalla no sabe cuál anda.
// - Cada programa imprime UNA línea de JSON: lo pedido, o { error } con un código de lib/contrato.js. Lo que va
//   contando sale por el otro canal y sólo se guarda para el detalle de un error.
// - Se corren sin ventana, con los argumentos separados (la carpeta del proyecto tiene un espacio) y con tope de tiempo.
// - Los trabajos van en PORTAVOZ_TRABAJOS o, sin nada, en ../trabajos (fuera del Estudio, no se sube).
// - La fila del armado, el candado de cada carpeta y la recuperación después de apagar el Estudio son los de fila.js,
//   los mismos que usan los ejemplos. El motor escribe avance.json etapa por etapa; de ahí sale el avance.
// - Las voces del día se cuentan desde los trabajos (vocesGastadas, también los que fallaron) en el día de la hora
//   del Pacífico, que es cuando Google renueva el tope.
// PORTAVOZ_MOTOR cambia la carpeta del motor (las pruebas usan uno de mentira que no sale a internet) y
// PORTAVOZ_VELOCIDAD=rapida arma el video chico.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  CAMBIOS, CAMPOS_TEXTO, ENFOQUES, ETAPAS, ETAPA_DEL_ERROR, GUION_SE_PASA, GUION_VACIO, LARGOS, MAXIMO_FOTOS, REDES,
  TOPE_VOCES_DIA, contarPalabras, crearError, esCodigoError, esEncargo, esIdTrabajo, revisarAvance,
  revisarFotosDeTramos, revisarGuion, revisarMiradas, revisarNota, revisarPedido, revisarResultado, revisarTrabajo,
} from "../contrato.js";
import {
  anotarReintento, candadoVivo, diaPacifico, dos, encolar as ponerEnFila, enFila, escribirCandado, escribirJson,
  estadoFila, fila, leerJson, leerUno, limpiarPedido, marcarFallo, matar, nuevoId, pararFila, rutaDe,
  sinCarpetaPersonal, tomarCandado, unaVez, videosAntes,
} from "./fila.js";

export { estadoFila, pararFila };

export const carpetaMotor = () => process.env.PORTAVOZ_MOTOR || join(/*turbopackIgnore: true*/ process.cwd(), "..", "motor");
const rutaPrograma = (programa) => join(/*turbopackIgnore: true*/ carpetaMotor(), programa);
export const carpetaTrabajos = () => process.env.PORTAVOZ_TRABAJOS || join(/*turbopackIgnore: true*/ process.cwd(), "..", "trabajos");

/** Topes de tiempo de cada programa. Google reintenta cuando está saturado, y el armado baja clips y hace el video. */
export const TOPES = { nota: 4 * 60 * 1000, guiones: 6 * 60 * 1000, cambiar: 4 * 60 * 1000, armar: 15 * 60 * 1000, otro: 4 * 60 * 1000 };
/** El tope de un cambio de guion. "Escribir otro" escribe y además revisa el guion nuevo contra la nota (desde el
 *  2026-11-18), como los tres primeros: lleva el tope de los guiones. "Más corto" y "Más simple" siguen con el suyo. */
export const topeDeCambio = (accion) => (accion === "otro" ? TOPES.guiones : TOPES.cambiar);
/** Un candado del motor vence un poco después del tope del armado (el de los ejemplos vence a los 10 minutos). */
export const VENCE_CANDADO_MOTOR = TOPES.armar + 60 * 1000;
/** Cuántas veces se larga el armado de un trabajo antes de darlo por fallado (si se corta solo, sin decir por qué). */
export const CORRIDAS_MAXIMAS = 3;

// ---------------------------------------------------------------------------------------------
// Correr un programa del motor

/**
 * Corre `python -B <motor>/<programa> ...args`. Devuelve { datos } (lo que imprimió) o { error } (crearError).
 * alArrancar(hijo) se llama con el proceso recién largado (el armado lo anota en la fila y en el candado).
 */
export function correrMotor(programa, args, { tope, alArrancar } = {}) {
  return new Promise((resolver) => {
    let hijo;
    // La ruta y los argumentos se arman antes (como en ejemplos.js): así el armado del Estudio no rastrea todo el disco.
    const todos = ["-B", rutaPrograma(programa), ...args];
    try {
      hijo = spawn("python", todos, {
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      });
    } catch (e) {
      resolver(crearError("DESCONOCIDO", sinCarpetaPersonal(`no se pudo correr Python: ${e.message}`)));
      return;
    }
    let salida = "";
    let errores = "";
    let vencido = false;
    hijo.stdout.setEncoding("utf8");
    hijo.stderr.setEncoding("utf8");
    hijo.stdout.on("data", (d) => {
      salida = (salida + d).slice(-4_000_000);
    });
    hijo.stderr.on("data", (d) => {
      errores = (errores + d).slice(-2000);
    });
    const reloj = tope ? setTimeout(() => { vencido = true; matar(hijo); }, tope) : null;
    if (alArrancar) alArrancar(hijo);
    hijo.on("error", (e) => {
      if (reloj) clearTimeout(reloj);
      resolver(crearError("DESCONOCIDO", sinCarpetaPersonal(`no se pudo correr Python: ${e.message}`)));
    });
    hijo.on("close", (codigo) => {
      if (reloj) clearTimeout(reloj);
      if (vencido) return resolver(crearError("DESCONOCIDO", `${programa} tardó demasiado y se cortó`));
      const ultima = salida.trim().split(/\r?\n/).at(-1) || "";
      let datos = null;
      try {
        datos = JSON.parse(ultima);
      } catch {
        datos = null;
      }
      if (datos?.error) return resolver(errorDelMotor(datos.error));
      if (codigo === 0 && datos && typeof datos === "object") return resolver({ datos });
      resolver(crearError("DESCONOCIDO", sinCarpetaPersonal(`${programa} terminó con el código ${codigo}: ${errores.trim().split(/\r?\n/).at(-1) || "sin detalle"}`)));
    });
  });
}

/** El error que mandó Python, rearmado acá: código de la lista (o DESCONOCIDO) y detalle sin la carpeta personal. */
function errorDelMotor(e) {
  const codigo = esCodigoError(e?.codigo) ? e.codigo : "DESCONOCIDO";
  const detalle = typeof e?.detalle === "string" && e.detalle.trim() ? sinCarpetaPersonal(e.detalle) : undefined;
  return crearError(codigo, detalle);
}

/** Guarda un dato para pasárselo a Python. El nombre sale del contenido: lo mismo pisa el mismo archivo. */
function archivoTemporal(tipo, contenido) {
  const carpeta = join(/*turbopackIgnore: true*/ tmpdir(), "portavoz-lite");
  mkdirSync(/*turbopackIgnore: true*/ carpeta, { recursive: true });
  const texto = typeof contenido === "string" ? contenido : JSON.stringify(contenido);
  const ruta = join(/*turbopackIgnore: true*/ carpeta, `${tipo}-${createHash("sha256").update(texto).digest("hex").slice(0, 24)}.txt`);
  writeFileSync(/*turbopackIgnore: true*/ ruta, texto, "utf8");
  return ruta;
}

const huella = (...partes) => createHash("sha256").update(JSON.stringify(partes)).digest("hex").slice(0, 24);

// ---------------------------------------------------------------------------------------------
// Nota y guiones

/** Lee la nota del pedido (link o texto pegado). Devuelve { nota } o { error }. */
export async function leerNota(pedido) {
  const problemas = revisarPedido(pedido).filter((p) => !(pedido?.texto && p === "el link no es válido"));
  if (problemas.length === 1 && problemas[0] === "el link no es válido") return crearError("LINK_INVALIDO");
  if (problemas.length) return crearError("DESCONOCIDO", problemas.join("; "));
  const p = limpiarPedido(pedido);
  return unaVez(`nota:${huella(p.texto ?? null, p.link ?? null)}`, async () => {
    const args = p.texto
      ? ["--texto", archivoTemporal("texto", p.texto), ...(p.link ? ["--link", p.link] : [])]
      : [p.link];
    const r = await correrMotor("leer_nota.py", args, { tope: TOPES.nota });
    if (r.error) return r;
    const mal = revisarNota(r.datos.nota);
    return mal.length ? crearError("DESCONOCIDO", `la nota del motor no cumple el contrato: ${mal.join("; ")}`) : { nota: r.datos.nota };
  });
}

function revisarPedidoGuion({ nota, largo, enfoque, accion } = {}, conCambio = false) {
  const mal = revisarNota(nota);
  if (!LARGOS.includes(largo)) mal.push(`largo ${largo} no es 15, 30 ni 60`);
  if (conCambio && !ENFOQUES.includes(enfoque)) mal.push(`enfoque ${enfoque} no está en la lista`);
  if (conCambio && !CAMBIOS.includes(accion)) mal.push(`acción ${accion} no está en la lista`);
  return mal;
}

/** Las fotos de los tramos tienen que ser fotos de la nota (la forma ya la mira revisarGuion). */
const fotosAjenas = (versiones, nota) =>
  revisarFotosDeTramos(versiones, nota.medios ?? []).filter((p) => p.includes("no está en la nota"));

/** Los tres guiones (con sus tramos: qué clips buscar para cada parte, y la foto sugerida si la nota tiene fotos).
 *  Devuelve { guiones, fotos? } o { error }. `fotos` es lo que vio Claude en cada foto de la nota ({ n, sirve,
 *  encuadre, centro }); sólo viene si se miraron. */
export async function guiones(pedido) {
  const mal = revisarPedidoGuion(pedido);
  if (mal.length) return crearError("DESCONOCIDO", mal.join("; "));
  const { nota, largo } = pedido;
  return unaVez(`guiones:${huella(nota, largo)}`, async () => {
    const r = await correrMotor("guiones.py", [archivoTemporal("nota", nota), "--duracion", String(largo)], { tope: TOPES.guiones });
    if (r.error) return r;
    const lista = r.datos.guiones;
    const fotos = r.datos.fotos ?? [];
    const problemas = Array.isArray(lista) && lista.length === ENFOQUES.length
      ? lista.flatMap((g, i) => [...revisarGuion(g), ...fotosAjenas(g.versiones, nota)].map((x) => `guion ${i}: ${x}`))
      : ["no vinieron los tres guiones"];
    problemas.push(...revisarMiradas(fotos, nota.medios));
    if (problemas.length) return crearError("DESCONOCIDO", problemas.join("; "));
    return fotos.length ? { guiones: lista, fotos } : { guiones: lista };
  });
}

/** Los tramos de la versión que se cambia ("Más corto" o "Más simple"), si la pantalla los manda: el motor los usa
 *  para que cada foto siga con la parte que dice lo mismo. Sólo pasa lo que hace falta: el texto y la foto. */
function tramosParaCambiar(tramos) {
  if (!Array.isArray(tramos) || tramos.length === 0 || tramos.length > 60) return null;
  const limpios = tramos.map((t) => ({
    texto: String(t?.texto ?? "").slice(0, 2000),
    ...(Number.isInteger(t?.foto) && t.foto >= 1 && t.foto <= MAXIMO_FOTOS ? { foto: t.foto } : {}),
  }));
  return limpios.some((t) => t.foto) ? limpios : null;
}

/** Más corto, más simple u otro: un pedido a Google cada uno. Devuelve { version } o { error }. */
export async function cambiarGuion(pedido) {
  const mal = revisarPedidoGuion(pedido, true);
  const texto = String(pedido?.texto ?? "").trim();
  if (!mal.length && pedido.accion !== "otro" && !contarPalabras(texto)) mal.push("no hay texto para cambiar");
  if (!mal.length && pedido.accion === "corto" && contarPalabras(texto) < 2) mal.push("ya no se puede acortar");
  if (mal.length) return crearError("DESCONOCIDO", mal.join("; "));
  const { nota, largo, enfoque, accion } = pedido;
  const tramos = accion === "otro" ? null : tramosParaCambiar(pedido.tramos);
  return unaVez(`cambio:${huella(nota.id, largo, enfoque, accion, texto, tramos)}`, async () => {
    const base = [archivoTemporal("nota", nota), "--duracion", String(largo), "--enfoque", enfoque];
    const args = accion === "otro"
      ? [...base, ...(texto ? ["--evitar", archivoTemporal("guion", texto)] : [])]
      : [...base, "--cambiar", accion, "--texto", archivoTemporal("guion", texto),
        ...(tramos ? ["--tramos", archivoTemporal("tramos", tramos)] : [])];
    const r = await correrMotor("guiones.py", args, { tope: topeDeCambio(accion) });
    if (r.error) return r;
    const v = accion === "otro" ? r.datos?.guion?.versiones?.[0] : r.datos?.version;
    // Sin versión, revisarGuion se rompía en v.texto y la pantalla mostraba un error sin código.
    if (!v || typeof v !== "object") return crearError("DESCONOCIDO", "el motor no devolvió la versión del guion");
    const problemas = [...revisarGuion({ id: "x", enfoque, versiones: [v], actual: 0 }), ...fotosAjenas([v], nota)];
    if (problemas.length || v.origen !== accion) return crearError("DESCONOCIDO", `el cambio del motor no cumple el contrato: ${problemas.join("; ") || "origen"}`);
    if (v.texto.trim() === texto) return crearError("DESCONOCIDO", "el cambio dio el mismo texto");
    return { version: v };
  });
}

// ---------------------------------------------------------------------------------------------
// Trabajos

const hayVideo = (carpeta, id) =>
  existsSync(/*turbopackIgnore: true*/ rutaDe(carpeta, id, "video.mp4")) &&
  existsSync(/*turbopackIgnore: true*/ rutaDe(carpeta, id, "portada.jpg"));

const resultadoSano = (carpeta, id) => {
  const r = leerJson(rutaDe(carpeta, id, "resultado.json"));
  return r && revisarResultado(r).length === 0 ? r : null;
};

/** Todos los trabajos sanos, del más nuevo al más viejo. Si la carpeta no se puede leer, tira el error. */
function leerTodos() {
  const carpeta = carpetaTrabajos();
  if (!existsSync(/*turbopackIgnore: true*/ carpeta)) return [];
  return readdirSync(/*turbopackIgnore: true*/ carpeta, { withFileTypes: true })
    .filter((e) => e.isDirectory() && esIdTrabajo(e.name))
    .map((e) => leerUno(carpeta, e.name))
    .filter(Boolean)
    .map((t) => alDia(carpeta, t))
    .sort((a, b) => Date.parse(b.creado) - Date.parse(a.creado) || (a.id < b.id ? 1 : -1));
}

export async function trabajos() {
  try {
    return { trabajos: leerTodos() };
  } catch (e) {
    return crearError("DESCONOCIDO", sinCarpetaPersonal(`no se pudieron leer los trabajos: ${e.message}`));
  }
}

function buscar(id) {
  if (!esIdTrabajo(id)) return crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara");
  const carpeta = carpetaTrabajos();
  const t = leerUno(carpeta, id);
  return t ? { trabajo: alDia(carpeta, t), carpeta } : crearError("DESCONOCIDO", "no existe ese trabajo");
}

export async function trabajo(id) {
  const b = buscar(id);
  return b.error ? b : { trabajo: b.trabajo };
}

function buscarGuardado(condicion) {
  try {
    return leerTodos().find(condicion) || null;
  } catch {
    return null;
  }
}

/** Crea el trabajo de "Armar mi video" y lo pone en la fila. Igual que en los ejemplos (encargo, reintento, cupo). */
export async function crearTrabajo(datos = {}) {
  const { encargo } = datos;
  if (!esEncargo(encargo)) return crearAhora(datos);
  return unaVez(`encargo:${encargo}`, async () => {
    const ya = buscarGuardado((t) => t.encargo === encargo);
    return ya ? { trabajo: ya } : crearAhora(datos);
  });
}

async function crearAhora({ nota, largo, guion, pedido, guiones: propuestos, reintentoDe, encargo, sinVoces = false } = {}) {
  const ahora = new Date();
  const texto = String(guion?.texto ?? "").trim();
  const nuevo = {
    id: nuevoId(ahora),
    creado: ahora.toISOString(),
    largo,
    nota,
    guion: { enfoque: guion?.enfoque, texto, palabras: contarPalabras(texto) },
    estado: "armando",
    ...(pedido !== undefined ? { pedido: limpiarPedido(pedido) } : {}),
    // Los tres guiones del Paso 2 con sus tramos: el motor busca los clips con ellos sin volver a pedirle a Google.
    ...(propuestos !== undefined ? { guiones: propuestos } : {}),
    ...(reintentoDe !== undefined ? { reintentoDe } : {}),
    ...(encargo !== undefined ? { encargo } : {}),
  };
  const mal = revisarTrabajo(nuevo);
  if (mal.length) {
    const delTexto = mal.every((p) => p === GUION_VACIO || p === GUION_SE_PASA);
    return crearError(delTexto ? "GUION_A_CORREGIR" : "DESCONOCIDO", mal.join("; "));
  }
  if (reintentoDe !== undefined && !leerUno(carpetaTrabajos(), reintentoDe)) {
    return crearError("DESCONOCIDO", "no existe el trabajo que se quiere reintentar");
  }
  // Contar y guardar sin ninguna espera en el medio: dos pedidos juntos con una sola voz libre no la usan los dos.
  const c = cupoAhora({ sinVoces });
  if (c.error) return c;
  if (c.cupo.voces.quedan <= 0) return crearError("SIN_VOCES_HOY");
  try {
    const carpeta = carpetaTrabajos();
    mkdirSync(/*turbopackIgnore: true*/ carpeta, { recursive: true });
    for (let vuelta = 0; vuelta < 5; vuelta += 1) {
      const id = vuelta === 0 ? nuevo.id : nuevoId(ahora);
      try {
        mkdirSync(/*turbopackIgnore: true*/ join(carpeta, id));
      } catch (e) {
        if (e.code === "EEXIST") continue;
        throw e;
      }
      const trabajoNuevo = { ...nuevo, id };
      escribirJson(join(/*turbopackIgnore: true*/ carpeta, id, "trabajo.json"), trabajoNuevo);
      encolar(carpeta, id);
      return { trabajo: trabajoNuevo };
    }
    return crearError("DESCONOCIDO", "no se encontró un id libre");
  } catch (e) {
    return crearError("DESCONOCIDO", sinCarpetaPersonal(`no se pudo guardar el trabajo: ${e.message}`));
  }
}

// ---------------------------------------------------------------------------------------------
// El armado: uno por vez, en la fila de fila.js

const encolar = (carpeta, id) => ponerEnFila(carpeta, id, armarUno);

/** Lo que dejó el motor si falló: su error por la salida, el de avance.json o el de armado-error.txt ("CODIGO: detalle"). */
function errorGuardado(carpeta, id) {
  const a = leerJson(rutaDe(carpeta, id, "avance.json"));
  if (a?.error) return errorDelMotor(a.error);
  try {
    const linea = readFileSync(/*turbopackIgnore: true*/ rutaDe(carpeta, id, "armado-error.txt"), "utf8").trim();
    const [codigo, ...resto] = linea.split(":");
    return errorDelMotor({ codigo: codigo.trim(), detalle: resto.join(":").trim() });
  } catch {
    return null;
  }
}

/** Deja el trabajo listo (con las voces que dijo el motor, si gastó más de las anotadas). */
function marcarListo(carpeta, t, voces) {
  const listo = { ...t, estado: "listo" };
  const antes = Number.isInteger(t.vocesGastadas) ? t.vocesGastadas : 0;
  if (Number.isInteger(voces) && voces > antes) listo.vocesGastadas = voces;
  escribirJson(rutaDe(carpeta, t.id, "trabajo.json"), listo);
  return listo;
}

/** Arma un trabajo con motor/armar.py. Al terminar lo marca listo o fallo (el motor no toca el estado). */
async function armarUno({ carpeta, id }) {
  const t = leerUno(carpeta, id);
  if (!t || t.estado !== "armando") return;
  if (hayVideo(carpeta, id) && resultadoSano(carpeta, id)) {
    marcarListo(carpeta, t);
    return;
  }
  if (!tomarCandado(carpeta, id, VENCE_CANDADO_MOTOR)) return;
  const f = fila();
  f.corridas[id] = (f.corridas[id] || 0) + 1;
  const desde = Date.now();
  let r;
  try {
    const args = [join(/*turbopackIgnore: true*/ carpeta, id)];
    if (process.env.PORTAVOZ_VELOCIDAD === "rapida") args.push("--rapida");
    r = await correrMotor("armar.py", args, {
      tope: TOPES.armar,
      alArrancar: (hijo) => {
        fila().hijo = hijo;
        if (hijo.pid) escribirCandado(carpeta, id, { pid: hijo.pid, hora: desde, estudio: process.pid });
      },
    });
  } finally {
    fila().hijo = null;
    escribirCandado(carpeta, id, { libre: true, hora: Date.now(), desde });
  }
  const ahora = leerUno(carpeta, id);
  if (ahora?.estado !== "armando") return;
  if (!r.error && hayVideo(carpeta, id) && resultadoSano(carpeta, id)) {
    marcarListo(carpeta, ahora, r.datos.vocesGastadas);
    return;
  }
  const error = r.error ? r : errorGuardado(carpeta, id) || crearError("FALLO_ARMADO", "el armado terminó sin video");
  // Si se cortó por tiempo o sin decir nada, vale más lo que dejó escrito el motor (su etapa y su código).
  const mejor = error.error.codigo === "DESCONOCIDO" ? errorGuardado(carpeta, id) || error : error;
  marcarFallo(carpeta, ahora, mejor.error);
}

/**
 * Pone al día un trabajo "armando" que nadie está armando (por ejemplo, después de apagar el Estudio): si el motor
 * llegó a terminar queda listo; si dejó un error, falla con ese error; si no, vuelve a la fila (hasta CORRIDAS_MAXIMAS).
 */
function ponerAlDia(carpeta, t) {
  if (t.estado !== "armando" || enFila(t.id) || candadoVivo(carpeta, t.id, VENCE_CANDADO_MOTOR)) return t;
  if (hayVideo(carpeta, t.id) && resultadoSano(carpeta, t.id)) return marcarListo(carpeta, t);
  const a = leerJson(rutaDe(carpeta, t.id, "avance.json"));
  if (a?.error) return marcarFallo(carpeta, t, errorDelMotor(a.error).error);
  if ((fila().corridas[t.id] || 0) >= CORRIDAS_MAXIMAS) {
    return marcarFallo(carpeta, t, crearError("FALLO_ARMADO", "el armado se cortó varias veces").error);
  }
  encolar(carpeta, t.id);
  return t;
}

function alDia(carpeta, t) {
  try {
    return ponerAlDia(carpeta, t);
  } catch {
    return t;
  }
}

// ---------------------------------------------------------------------------------------------
// Avance

/** Segundos de trabajo por segundo de video mientras no hay medidas (los mismos de motor/armar.py). Son una estimación. */
const POR_SEGUNDO_INICIAL = { clips: 0.8, voz: 0.9, tiempos: 0.05, armado: 1.2, textos: 0.5 };

/** Cuánto tarda en total, estimado, un trabajo que todavía no arrancó (con motor/medidas.json si ya hay). */
function estimadoTotal(t) {
  const m = leerJson(join(/*turbopackIgnore: true*/ carpetaMotor(), "medidas.json")) || {};
  const por = { ...POR_SEGUNDO_INICIAL, ...(m.por_segundo || {}) };
  const pps = Number(m.palabras_por_segundo) > 0 ? Number(m.palabras_por_segundo) : 2.5;
  const segundosVideo = (t.guion?.palabras || 0) / pps;
  return Math.max(1, Math.round(ETAPAS.reduce((s, e) => s + (Number(por[e]) || 0) * segundosVideo, 0)));
}

const etapaDelError = (codigo) =>
  typeof codigo === "string" && Object.hasOwn(ETAPA_DEL_ERROR, codigo) ? ETAPA_DEL_ERROR[codigo] : "armado";

function calcularAvance(carpeta, t) {
  if (t.estado === "listo") return { etapas: ETAPAS.map((id) => ({ id, estado: "listo" })), porcentaje: 100, restante: 0 };
  const a = leerJson(rutaDe(carpeta, t.id, "avance.json"));
  const sano = a && revisarAvance({ etapas: a.etapas, porcentaje: a.porcentaje, restante: a.restante }).length === 0;
  if (t.estado === "fallo") {
    // La etapa que falló: la que el motor marcó (o la que estaba haciendo); si no hay avance, la de su código.
    let i = sano ? a.etapas.findIndex((e) => e.estado === "fallo" || e.estado === "haciendo") : -1;
    if (i < 0) i = ETAPAS.indexOf(etapaDelError(t.error?.codigo));
    return {
      etapas: ETAPAS.map((id, k) => ({ id, estado: k < i ? "listo" : k === i ? "fallo" : "espera" })),
      porcentaje: sano ? Math.min(99, a.porcentaje) : 0,
      restante: 0,
      ...(t.error ? { error: t.error } : {}),
    };
  }
  const antes = videosAntes(t.id);
  // avance.json es de esta corrida si el trabajo se está armando ahora (en esta fila o en otro Estudio). Si el motor
  // acaba de fallar y todavía no se anotó el fallo, la etapa sigue "haciendo" un instante.
  if (sano && (enFila(t.id) ? fila().enCurso?.id === t.id : true)) {
    return {
      etapas: a.etapas.map((e) => ({ id: e.id, estado: e.estado === "fallo" ? "haciendo" : e.estado })),
      porcentaje: Math.min(99, a.porcentaje),
      restante: a.restante,
      ...(antes > 0 ? { fila: antes } : {}),
    };
  }
  // Esperando su turno (o recién creado): todo en espera, con lo que se estima que tarda.
  return {
    etapas: ETAPAS.map((id) => ({ id, estado: "espera" })),
    porcentaje: 0,
    restante: estimadoTotal(t),
    ...(antes > 0 ? { fila: antes } : {}),
  };
}

export async function avance(id) {
  const b = buscar(id);
  return b.error ? b : { avance: calcularAvance(b.carpeta, b.trabajo) };
}

// ---------------------------------------------------------------------------------------------
// Resultado, Pedir otro, reintentar, archivos

export async function resultado(id) {
  const b = buscar(id);
  if (b.error) return b;
  if (b.trabajo.estado !== "listo" || !hayVideo(b.carpeta, id)) return crearError("DESCONOCIDO", "el video todavía no está listo");
  const r = resultadoSano(b.carpeta, id);
  return r ? { resultado: r } : crearError("DESCONOCIDO", "el resultado del video está roto");
}

/** "Pedir otro" de a uno por trabajo: el motor reescribe resultado.json y dos a la vez se pisarían. */
const colaTextos = () => (globalThis.__portavozOtroTexto ??= new Map());

export async function otroTexto(id, campo, red) {
  if (!CAMPOS_TEXTO.includes(campo)) return crearError("DESCONOCIDO", "ese texto no se puede pedir de nuevo");
  if (campo === "redes" && !REDES.includes(red)) return crearError("DESCONOCIDO", "falta decir de qué red");
  if (!esIdTrabajo(id)) return crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara");
  const m = colaTextos();
  const anterior = m.get(id) || Promise.resolve();
  const este = anterior.then(async () => {
    const r = await resultado(id);
    if (r.error) return r;
    const s = await correrMotor("otro_texto.py", [join(/*turbopackIgnore: true*/ carpetaTrabajos(), id), campo, ...(campo === "redes" ? [red] : [])], { tope: TOPES.otro });
    if (s.error) return s;
    const nuevo = s.datos.resultado;
    return revisarResultado(nuevo).length === 0 ? { resultado: nuevo } : crearError("DESCONOCIDO", "el texto nuevo no cumple el contrato");
  });
  const cola = este.catch(() => {});
  m.set(id, cola);
  cola.finally(() => {
    if (m.get(id) === cola) m.delete(id);
  });
  return este;
}

export async function reintentar(id, { sinVoces = false } = {}) {
  if (!esIdTrabajo(id)) return crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara");
  return unaVez(`reintento:${id}`, async () => {
    const b = buscar(id);
    if (b.error) return b;
    const t = b.trabajo;
    if (t.estado !== "fallo") return crearError("DESCONOCIDO", "sólo se vuelve a probar un trabajo que falló");
    const ya = yaReintentado(b.carpeta, t);
    if (ya) return { trabajo: ya };
    const r = await crearTrabajo({
      nota: t.nota,
      largo: t.largo,
      guion: t.guion,
      ...(t.pedido !== undefined ? { pedido: t.pedido } : {}),
      ...(t.guiones !== undefined ? { guiones: t.guiones } : {}),
      reintentoDe: t.id,
      sinVoces,
    });
    if (r.trabajo) anotarReintento(b.carpeta, t.id, r.trabajo.id);
    return r;
  });
}

function yaReintentado(carpeta, t) {
  if (esIdTrabajo(t.reintentadoEn)) {
    const n = leerUno(carpeta, t.reintentadoEn);
    if (n) return alDia(carpeta, n);
  }
  return buscarGuardado((x) => x.reintentoDe === t.id);
}

export async function archivo(id, cual) {
  const nombres = { video: ["video.mp4", "video/mp4"], portada: ["portada.jpg", "image/jpeg"] };
  if (!Object.hasOwn(nombres, cual)) return crearError("DESCONOCIDO", "sólo hay video y portada");
  const b = buscar(id);
  if (b.error) return b;
  const [nombre, tipo] = nombres[cual];
  const ruta = rutaDe(b.carpeta, id, nombre);
  if (!existsSync(/*turbopackIgnore: true*/ ruta)) return crearError("DESCONOCIDO", "todavía no está");
  return { archivo: { ruta, tamano: statSync(/*turbopackIgnore: true*/ ruta).size, tipo, trabajo: b.trabajo } };
}

// ---------------------------------------------------------------------------------------------
// Cupo

/** Las voces que cuenta un trabajo: las que anotó el motor; uno que se está armando y no anotó nada guarda una. */
export const vocesDe = (t) =>
  Number.isInteger(t.vocesGastadas) && t.vocesGastadas >= 0 ? t.vocesGastadas : t.estado === "armando" ? 1 : 0;

export async function cupo(opciones) {
  return cupoAhora(opciones);
}

function cupoAhora({ sinVoces = false } = {}) {
  let lista;
  try {
    lista = leerTodos();
  } catch (e) {
    return crearError("DESCONOCIDO", sinCarpetaPersonal(`no se pudieron contar las voces: ${e.message}`));
  }
  const ahora = new Date();
  const hoy = diaPacifico(ahora);
  const gastadas = lista.filter((t) => diaPacifico(new Date(t.creado)) === hoy).reduce((s, t) => s + vocesDe(t), 0);
  const usadas = sinVoces ? TOPE_VOCES_DIA : gastadas;
  const mismoMes = (d) => d.getFullYear() === ahora.getFullYear() && d.getMonth() === ahora.getMonth();
  return {
    cupo: {
      voces: { usadas, tope: TOPE_VOCES_DIA, quedan: Math.max(0, TOPE_VOCES_DIA - usadas) },
      videosMes: lista.filter((t) => t.estado === "listo" && mismoMes(new Date(t.creado))).length,
      mes: `${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}`,
    },
  };
}
