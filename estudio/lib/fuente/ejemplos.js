// Fuente de EJEMPLO: noticias inventadas (datos/ejemplos/notas.json) y demoras simuladas, para probar las
// pantallas sin llaves ni motor. Cumple el mismo contrato que el motor de verdad.
// - Los links de datos/ejemplos/notas.json -> su nota.
// - Los links de "fallas" -> el error que fuerzan.
// - Cualquier otro link -> una de las tres notas, siempre la misma para el mismo link.
// - "Sin voces hoy" se simula con la cookie `simular=sin-voces`.
// - Guiones: los de datos/ejemplos/guiones.json para las notas de ejemplo; para un texto pegado, un armado
//   genérico con las oraciones de la propia nota.
// - Trabajos ("Armar mi video"): una carpeta por trabajo con su trabajo.json, en PORTAVOZ_TRABAJOS o, sin
//   nada, en datos/trabajos-de-ejemplo/ (no se sube: está en el .gitignore del Estudio).
// - El video: lo arma de verdad herramientas/armar_video_ejemplo.py (el guion como subtítulo sobre un fondo de
//   prueba), uno por vez. Deja también armado.json (cómo salió, y qué letras no tenía la letra de la marca). Las demás etapas (voz, clips, textos) siguen el reloj; los textos para publicar salen de
//   datos/ejemplos/textos.json. Las fallas "sin-clips" y "falla-armado" fallan en su etapa sin armar nada.
// PORTAVOZ_VELOCIDAD=rapida hace todo quince veces más rápido (para las pruebas automáticas) y el video sale chico.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { domainToUnicode } from "node:url";
import {
  CAMBIOS, CAMPOS_TEXTO, ENFOQUES, ETAPAS, ETAPA_DEL_ERROR, GUION_SE_PASA, GUION_VACIO, LARGOS, PALABRAS_MINIMAS_NOTA,
  REDES, TEMAS_SENSIBLES, TOPES_REDES, TOPE_ETIQUETAS_YOUTUBE, TOPE_VOCES_DIA, contarPalabras, crearError, entraJusto,
  esCodigoError, esEncargo, esIdTrabajo, largoEtiquetas, largoPara, linkValido, palabrasPara, revisarNota, revisarPedido, revisarResultado,
  revisarTrabajo, revisarTrabajoGuardado, PALABRAS_POR_SEGUNDO,
} from "../contrato.js";
import { estimarTema } from "../sensible.js";
import {
  VENCE_CANDADO, anotarReintento, candadoVivo, dos, encolar as ponerEnFila, escribirCandado, escribirJson, estadoFila, fila,
  leerJson, leerUno, limpiarPedido, marcarFallo, matar, nuevoId, pararFila, rutaDe, sinCarpetaPersonal, tomarCandado, unaVez,
  videosAntes,
} from "./fila.js";

// La fila, el candado, el id y la lectura de los trabajos viven en fila.js (los comparte con el motor de verdad).
export { VENCE_CANDADO, estadoFila, pararFila };
const encolar = (carpeta, id) => ponerEnFila(carpeta, id, correr);

const DATOS = join(process.cwd(), "datos", "ejemplos", "notas.json");
const cargar = () => JSON.parse(readFileSync(DATOS, "utf8"));
const DATOS_GUIONES = join(process.cwd(), "datos", "ejemplos", "guiones.json");
const cargarGuiones = () => JSON.parse(readFileSync(DATOS_GUIONES, "utf8")).guiones;
/** Lo guardado con esa clave, sin lo que trae JavaScript de fábrica: una nota con id "constructor" no encuentra nada. */
const propio = (lista, clave) => (lista && typeof clave === "string" && Object.hasOwn(lista, clave) ? lista[clave] : undefined);

const factor = () => (process.env.PORTAVOZ_VELOCIDAD === "rapida" ? 1 / 15 : 1);
const esperar = (ms) => new Promise((r) => setTimeout(r, Math.round(ms * factor())));

export const DEMORAS = { nota: 1500, guiones: 2000, cambiar: 1200, armar: 800 };

function completar(nota) {
  return {
    ...nota,
    palabras: contarPalabras(nota.texto),
    sensible: TEMAS_SENSIBLES.includes(nota.tema),
    ejemplo: true,
  };
}

function huella(texto) {
  let h = 0;
  for (const c of String(texto)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h;
}

/** Arma una nota a partir de un texto pegado. La primera línea es el título. */
function notaDeTexto(texto, link) {
  const renglones = String(texto).split(/\r?\n/).map((r) => r.trim()).filter(Boolean);
  let titular;
  let cuerpo;
  if (renglones.length > 1) {
    titular = renglones[0];
    cuerpo = renglones.slice(1).join("\n\n");
  } else {
    const frase = renglones[0] || "";
    titular = (frase.match(/^.+?[.!?](\s|$)/)?.[0] || frase).trim();
    cuerpo = frase;
  }
  if (titular.length > 120) titular = `${titular.slice(0, 117).trimEnd()}...`;
  let medio = null;
  // Un dominio con letras como la ñ viaja como "xn--...": se pasa a como se lee antes de mostrarlo.
  if (link && linkValido(link)) medio = domainToUnicode(new URL(link).hostname).replace(/^www\./, "") || null;
  return completar({
    id: `texto-${huella(cuerpo).toString(36)}`,
    origen: "texto",
    link: link && linkValido(link) ? link : null,
    medio,
    fecha: null,
    titular,
    tema: estimarTema(`${titular} ${cuerpo}`),
    texto: cuerpo,
  });
}

/** Lee la nota del pedido. Devuelve { nota } o { error }. */
export async function leerNota(pedido) {
  // Con texto pegado, el link es opcional (puede venir de un muro de pago). Sin texto, el link manda.
  const problemas = revisarPedido(pedido).filter((p) => !(pedido?.texto && p === "el link no es válido"));
  if (problemas.length === 1 && problemas[0] === "el link no es válido") return crearError("LINK_INVALIDO");
  if (problemas.length) return crearError("DESCONOCIDO", problemas.join("; "));

  await esperar(DEMORAS.nota);

  if (pedido.texto) {
    const nota = notaDeTexto(pedido.texto, pedido.link);
    if (nota.palabras < PALABRAS_MINIMAS_NOTA) return crearError("NOTA_MUY_CORTA");
    return { nota };
  }

  const { notas, fallas } = cargar();
  const link = pedido.link.trim();
  const falla = fallas.find((f) => f.link === link && f.en === "nota");
  if (falla) return crearError(falla.codigo);
  const exacta = notas.find((n) => n.link === link);
  const nota = exacta || notas[huella(link) % notas.length];
  // Las fallas del armado (sin-clips, falla-armado) leen bien la nota: fallan recién al armar.
  const deArmado = fallas.find((f) => f.link === link && f.en === "armado");
  return { nota: completar({ ...nota, link: exacta || deArmado ? link : nota.link }) };
}

// ---------------------------------------------------------------------------------------------
// Guiones

/**
 * Lo más largo (en palabras) que entra en el largo elegido SIN el margen: lo que propone el Estudio nunca dice
 * "unos 62 s de 60". El margen queda para lo que escribe la persona.
 */
export function topePalabras(largo) {
  let p = palabrasPara(largo);
  while (entraJusto(p + 1, largo)) p += 1;
  while (p > 0 && !entraJusto(p, largo)) p -= 1;
  return p;
}

/** Cuántas palabras se buscan para un largo: las de la tarjeta del inicio, sin pasar el tope (en 15 s se pasaría). */
const objetivoPalabras = (largo) => Math.min(palabrasPara(largo), topePalabras(largo));

/** Parte un texto en oraciones, sin repetidas. */
function partir(texto) {
  const limpio = String(texto || "").replace(/\s+/g, " ").trim();
  if (!limpio) return [];
  const vistas = new Set();
  return limpio.split(/(?<=[.!?])\s+/).map((o) => o.trim()).filter((o) => {
    if (!o || vistas.has(o)) return false;
    vistas.add(o);
    return true;
  });
}

const juntar = (oraciones) => oraciones.filter(Boolean).join(" ");
const mayuscula = (o) => o.charAt(0).toLocaleUpperCase("es") + o.slice(1);
const esPregunta = (o) => /\?\s*$/.test(o);

/** Deja las primeras `n` palabras y cierra la frase como corresponde. */
function recortarPalabras(texto, n) {
  const palabras = String(texto).trim().split(/\s+/).slice(0, Math.max(1, n));
  let corto = palabras.join(" ").replace(/[,;:¿¡\s]+$/, "");
  if (/[.!?]$/.test(corto)) return corto;
  const abiertas = (corto.match(/¿/g) || []).length > (corto.match(/\?/g) || []).length;
  corto = corto.replace(/[.!?]+$/, "");
  return `${corto}${abiertas ? "?" : "."}`;
}

/**
 * Toma oraciones en orden hasta acercarse al objetivo, sin pasar el tope. La primera entra siempre
 * (recortada si sola ya se pasa). La apertura y el cierre, si hay, ocupan su lugar fijo.
 * Con `saltar`, una oración que no entra se saltea y se prueba la siguiente (en el armado genérico el
 * orden importa menos que llegar al largo); sin `saltar`, ahí se corta, para no perder el hilo.
 */
function elegir(oraciones, objetivo, tope, { apertura = null, cierre = null, saltar = false } = {}) {
  const fijas = contarPalabras(juntar([apertura, cierre]));
  let total = fijas;
  const tomadas = [];
  for (const o of oraciones) {
    const n = contarPalabras(o);
    if (tomadas.length === 0) { tomadas.push(o); total += n; continue; }
    if (total >= objetivo) break;
    if (total + n > tope) {
      if (saltar) continue;
      break;
    }
    tomadas.push(o);
    total += n;
  }
  let cuerpo = juntar(tomadas);
  if (total > tope) cuerpo = recortarPalabras(cuerpo, Math.max(1, tope - fijas));
  return juntar([apertura, cuerpo, cierre]);
}

/** Separa la pregunta final (si la hay), que en "Para debatir" no se saca nunca. */
function separarCierre(oraciones) {
  if (oraciones.length > 1 && esPregunta(oraciones.at(-1))) {
    return { cuerpo: oraciones.slice(0, -1), cierre: oraciones.at(-1) };
  }
  return { cuerpo: oraciones, cierre: null };
}

/** Arma un guion de una lista del archivo de ejemplos, para un largo. */
function deLista(lista, objetivo, tope) {
  const { cuerpo, cierre } = separarCierre(lista);
  return elegir(cuerpo, objetivo, tope, { cierre });
}

// Armado genérico: para notas que no están en guiones.json (un texto pegado).
// Cada enfoque tiene dos variantes; "Escribir otro" pasa de una a la otra.
const GENERICO = {
  dato: [
    {},
    { apertura: "Te lo contamos en pocas palabras." },
  ],
  "te-cambia": [
    { cierre: "Si esto te toca de cerca, vale la pena seguirlo." },
    { apertura: "Mira esto, porque te puede tocar de cerca." },
  ],
  debate: [
    { cierre: "¿Y tú qué piensas de esto?" },
    { cierre: "¿Te parece bien o lo harías distinto?" },
  ],
};

function ordenGenerico(enfoque, oraciones) {
  if (enfoque === "te-cambia") return [...oraciones.slice(1), ...oraciones.slice(0, 1)];
  if (enfoque === "debate") return [...oraciones.slice(2), ...oraciones.slice(0, 2)];
  return oraciones;
}

function generico(nota, enfoque, largo, variante) {
  const oraciones = ordenGenerico(enfoque, partir(nota.texto));
  return elegir(oraciones, objetivoPalabras(largo), topePalabras(largo), { ...GENERICO[enfoque][variante], saltar: true });
}

// Palabras después de una coma que dejan la segunda mitad colgando si se corta ahí ("..., que supera...").
const NO_CORTAR_ANTES = new Set(["que", "quien", "quienes", "donde", "cuando", "como", "cual", "cuales", "cuyo", "cuya", "y", "o", "pero", "e", "u", "ni"]);

/** Parte en dos las oraciones largas, por la coma o los dos puntos más cerca del medio. */
function partirLargas(texto) {
  const salida = [];
  for (const o of partir(texto)) {
    const palabras = o.split(" ");
    if (palabras.length <= 12 || esPregunta(o)) { salida.push(o); continue; }
    const medio = palabras.length / 2;
    let mejor = -1;
    palabras.forEach((p, i) => {
      if (i < 3 || i > palabras.length - 5) return;
      const corta = /[,:;]$/.test(p) && !NO_CORTAR_ANTES.has(palabras[i + 1].toLocaleLowerCase("es"));
      if (corta && (mejor < 0 || Math.abs(i - medio) < Math.abs(mejor - medio))) mejor = i;
    });
    if (mejor < 0) { salida.push(o); continue; }
    const primera = palabras.slice(0, mejor + 1).join(" ").replace(/[,:;]$/, "");
    salida.push(`${primera}.`, mayuscula(palabras.slice(mejor + 1).join(" ")));
  }
  return juntar(salida);
}

/** Lo más simple que se puede hacer sin saber de qué habla: partir las largas, o sacar la última. */
function simplificar(texto) {
  const partido = partirLargas(texto);
  if (!iguales(partido, texto)) return partido;
  const { cuerpo, cierre } = separarCierre(partir(texto));
  if (cuerpo.length > 1) return juntar([...cuerpo.slice(0, -1), cierre]);
  return recortarPalabras(texto, Math.max(1, Math.floor(contarPalabras(texto) * 0.75)));
}

/**
 * Saca oraciones del final (menos la pregunta de cierre) y se queda con el corte más cerca de unas 3/4 de
 * las palabras. Siempre queda al menos una oración; si hay una sola, se recortan palabras.
 */
function acortar(texto) {
  const total = contarPalabras(texto);
  const meta = Math.floor(total * 0.75);
  const { cuerpo, cierre } = separarCierre(partir(texto));
  let mejor = null;
  for (let n = cuerpo.length - 1; n >= 1; n -= 1) {
    const candidato = juntar([...cuerpo.slice(0, n), cierre]);
    const p = contarPalabras(candidato);
    if (p < total && (mejor === null || Math.abs(p - meta) < Math.abs(contarPalabras(mejor) - meta))) mejor = candidato;
  }
  if (mejor) return mejor;
  // Una sola oración (o una y la pregunta): se recortan palabras.
  const lugar = meta - contarPalabras(cierre);
  return lugar >= 1 ? juntar([recortarPalabras(juntar(cuerpo), lugar), cierre]) : recortarPalabras(texto, meta);
}

const iguales = (a, b) => String(a).replace(/\s+/g, " ").trim() === String(b).replace(/\s+/g, " ").trim();

function revisarPedidoGuion({ nota, largo, enfoque, accion } = {}, conCambio = false) {
  const mal = revisarNota(nota);
  if (!LARGOS.includes(largo)) mal.push(`largo ${largo} no es 15, 30 ni 60`);
  if (conCambio && !ENFOQUES.includes(enfoque)) mal.push(`enfoque ${enfoque} no está en la lista`);
  if (conCambio && !CAMBIOS.includes(accion)) mal.push(`acción ${accion} no está en la lista`);
  return mal;
}

const version = (texto, origen) => ({ texto, palabras: contarPalabras(texto), origen });

/**
 * La revisión de ejemplo: el guion "El dato" de la nota de la biblioteca trae un aviso, para que las pruebas vean la
 * línea "Revisa este guion" (los demás guiones de ejemplo vienen sin revisión, como un motor viejo). Está acá y no
 * en datos/ejemplos/guiones.json porque scripts/revisar.mjs revisa cada lista de ese archivo como texto que se ve.
 */
const REVISIONES_DE_EJEMPLO = {
  "ejemplo-biblioteca-dato": {
    puntos: ["La nota dice que el horario de noche empieza en diciembre."],
    arreglado: false,
    aviso: "VERBO_CAMBIADO",
    quien: "codigo",
  },
};

/** Los tres guiones para una nota y un largo. Devuelve { guiones } o { error }. */
export async function guiones(pedido) {
  const mal = revisarPedidoGuion(pedido);
  if (mal.length) return crearError("DESCONOCIDO", mal.join("; "));
  const { nota, largo } = pedido;

  await esperar(DEMORAS.guiones);

  const propios = propio(cargarGuiones(), nota.id);
  const objetivo = objetivoPalabras(largo);
  const tope = topePalabras(largo);
  return {
    guiones: ENFOQUES.map((enfoque) => {
      const texto = propios
        ? deLista(propios[enfoque].oraciones, objetivo, tope)
        : generico(nota, enfoque, largo, 0);
      const id = `${nota.id}-${enfoque}`;
      const revision = REVISIONES_DE_EJEMPLO[id];
      return { id, enfoque, versiones: [{ ...version(texto, "propuesta"), ...(revision ? { revision } : {}) }], actual: 0 };
    }),
  };
}

/** Un cambio a un guion: más corto, más simple u otro. Devuelve { version } o { error }. */
export async function cambiarGuion(pedido) {
  const mal = revisarPedidoGuion(pedido, true);
  const texto = String(pedido?.texto ?? "").trim();
  if (!mal.length && pedido.accion !== "otro" && !contarPalabras(texto)) mal.push("no hay texto para cambiar");
  if (!mal.length && pedido.accion === "corto" && contarPalabras(texto) < 2) mal.push("ya no se puede acortar");
  if (mal.length) return crearError("DESCONOCIDO", mal.join("; "));
  const { nota, largo, enfoque, accion } = pedido;

  await esperar(DEMORAS.cambiar);

  const propios = propio(propio(cargarGuiones(), nota.id), enfoque);
  let nuevo;
  if (accion === "corto") {
    // Más corto hasta que entre sin margen (un texto escrito a mano puede venir muy pasado).
    nuevo = acortar(texto);
    while (!entraJusto(contarPalabras(nuevo), largo)) {
      const otraVez = acortar(nuevo);
      if (contarPalabras(otraVez) >= contarPalabras(nuevo)) break;
      nuevo = otraVez;
    }
  } else if (accion === "simple") {
    const tenia = contarPalabras(texto);
    if (propios) nuevo = deLista(propios.simple, tenia, tenia);
    if (!nuevo || iguales(nuevo, texto)) nuevo = simplificar(texto);
  } else {
    const objetivo = objetivoPalabras(largo);
    const tope = topePalabras(largo);
    if (propios) {
      const desdeOtra = texto.includes(propios.otra[0]);
      nuevo = deLista(desdeOtra ? propios.oraciones : propios.otra, objetivo, tope);
      if (iguales(nuevo, texto)) nuevo = deLista(desdeOtra ? propios.otra : propios.oraciones, objetivo, tope);
    } else {
      nuevo = generico(nota, enfoque, largo, 0);
      if (iguales(nuevo, texto)) nuevo = generico(nota, enfoque, largo, 1);
    }
  }
  if (!nuevo || iguales(nuevo, texto)) return crearError("DESCONOCIDO", "el cambio dio el mismo texto");
  return { version: version(nuevo, accion) };
}

// ---------------------------------------------------------------------------------------------
// Trabajos: lo que queda guardado al tocar "Armar mi video". Cada uno en <carpeta>/<id>/, con:
//   trabajo.json (el trabajo), armando.lock (quién lo está armando y desde cuándo), video.mp4 y portada.jpg (los
//   deja el armado), subtitulos.ass, armado.json (el registro del armado), armado-error.txt (sólo si el armado
//   falló) y resultado.json (al terminar).

export const carpetaTrabajos = () => process.env.PORTAVOZ_TRABAJOS || join(/*turbopackIgnore: true*/ process.cwd(), "datos", "trabajos-de-ejemplo");

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

const mismoDia = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
const mismoMes = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();

/** Los trabajos para "Mis videos", puestos al día. Devuelve { trabajos } o { error }. Una carpeta rota se saltea. */
export async function trabajos() {
  try {
    return { trabajos: leerTodos() };
  } catch (e) {
    return crearError("DESCONOCIDO", `no se pudieron leer los trabajos: ${e.message}`);
  }
}

/** Busca un trabajo por id y lo pone al día. Devuelve { trabajo, carpeta } o { error }. */
function buscar(id) {
  if (!esIdTrabajo(id)) return crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara");
  const carpeta = carpetaTrabajos();
  const t = leerUno(carpeta, id);
  return t ? { trabajo: alDia(carpeta, t), carpeta } : crearError("DESCONOCIDO", "no existe ese trabajo");
}

/** Un trabajo por su id. El id se comprueba con su forma exacta antes de armar ninguna ruta. */
export async function trabajo(id) {
  const b = buscar(id);
  return b.error ? b : { trabajo: b.trabajo };
}


/** El primer trabajo guardado que cumple la condición, puesto al día, o null (también si la carpeta no se lee). */
function buscarGuardado(condicion) {
  try {
    return leerTodos().find(condicion) || null;
  } catch {
    return null;
  }
}

/**
 * Crea el trabajo de "Armar mi video" y lo pone en la fila del armado. Devuelve { trabajo } o { error }.
 * Además de nota, largo y guion acepta, si vienen: pedido, guiones (los del Paso 2), reintentoDe y encargo.
 * Con un encargo que ya creó un trabajo (la página se cerró mientras armaba, o se cortó la respuesta), devuelve ése:
 * no arma otro ni gasta otra voz. Dos pedidos a la vez con el mismo encargo reciben el mismo trabajo.
 */
export async function crearTrabajo(datos = {}) {
  const { encargo } = datos;
  // Sin encargo, o con uno de forma rara (que revisarTrabajo rechaza), va derecho.
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

  // La cuenta rápida contesta "sin voces" sin hacer esperar.
  const c = cupoAhora({ sinVoces });
  if (c.error) return c;
  if (c.cupo.voces.quedan <= 0) return crearError("SIN_VOCES_HOY");

  await esperar(DEMORAS.armar);

  // Y otra vez justo antes de guardar, sin ninguna espera en el medio: si dos pedidos llegan juntos con una sola voz
  // libre, el primero que guarda la usa y el otro ya la ve gastada.
  const otraVez = cupoAhora({ sinVoces });
  if (otraVez.error) return otraVez;
  if (otraVez.cupo.voces.quedan <= 0) return crearError("SIN_VOCES_HOY");

  try {
    const carpeta = carpetaTrabajos();
    mkdirSync(/*turbopackIgnore: true*/ carpeta, { recursive: true });
    // Si justo existe una carpeta con ese id (mismo segundo y mismas letras), se prueban otras letras.
    for (let vuelta = 0; vuelta < 5; vuelta += 1) {
      const id = vuelta === 0 ? nuevo.id : nuevoId(ahora);
      try {
        mkdirSync(/*turbopackIgnore: true*/ join(carpeta, id));
      } catch (e) {
        if (e.code === "EEXIST") continue;
        throw e;
      }
      const trabajoNuevo = { ...nuevo, id };
      escribirJson(join(carpeta, id, "trabajo.json"), trabajoNuevo);
      if (!fallaSimulada(trabajoNuevo)) encolar(carpeta, id);
      return { trabajo: trabajoNuevo };
    }
    return crearError("DESCONOCIDO", "no se encontró un id libre");
  } catch (e) {
    return crearError("DESCONOCIDO", `no se pudo guardar el trabajo: ${e.message}`);
  }
}

// ---------------------------------------------------------------------------------------------
// El armado: las etapas siguen el reloj desde `creado`; el video lo hace Python, uno por vez.

/** Cuánto dura cada etapa a velocidad normal, en milisegundos (son de mentira: la voz y los clips no existen). */
export const DEMORAS_ETAPAS = { clips: 15000, voz: 12000, tiempos: 6000, armado: 4000, textos: 5000 };
/** Lo que se suma al armado por cada segundo de video. Medido en esta PC el 2026-11-17: el video de 15 s a tamaño
 *  real tardó unos 16 s con el fondo ya hecho. Si el video tarda más, la etapa espera al video. */
export const ARMADO_POR_SEGUNDO = 1100;
/** Si Python tarda más que esto, se corta y el trabajo falla (la primera vez también hace el fondo, que tarda). */
export const TOPE_ARMADO = 8 * 60 * 1000;
/** Mientras el video no llega, lo que falta nunca baja de esto. */
const FALTA_MINIMA = 2000;

const SCRIPT_ARMADO = () => join(/*turbopackIgnore: true*/ process.cwd(), "herramientas", "armar_video_ejemplo.py");
const DATOS_TEXTOS = join(process.cwd(), "datos", "ejemplos", "textos.json");
const cargarTextos = () => JSON.parse(readFileSync(DATOS_TEXTOS, "utf8"));

const hayVideo = (carpeta, id) =>
  existsSync(/*turbopackIgnore: true*/ rutaDe(carpeta, id, "video.mp4")) &&
  existsSync(/*turbopackIgnore: true*/ rutaDe(carpeta, id, "portada.jpg"));

/** Las fallas de ejemplo del armado. "falla-armado" no vuelve a fallar si es un reintento. */
function fallaSimulada(t) {
  const f = cargar().fallas.find((x) => x.en === "armado" && x.link === t.nota?.link);
  if (!f || (f.codigo === "FALLO_ARMADO" && t.reintentoDe)) return null;
  return f;
}

const duraciones = (largo) =>
  ETAPAS.map((e) => (DEMORAS_ETAPAS[e] + (e === "armado" ? largo * ARMADO_POR_SEGUNDO : 0)) * factor());
const suma = (lista) => lista.reduce((a, b) => a + b, 0);

/**
 * Dónde empieza y termina cada etapa, en milisegundos desde `creado`. El armado no termina hasta que están el
 * video y la portada (si llegan tarde, los textos arrancan cuando llegan).
 */
function lineaDeTiempo(carpeta, t, ahora = Date.now()) {
  const dur = duraciones(t.largo);
  const inicio = [];
  const plan = [];
  let acumulado = 0;
  for (const d of dur) {
    inicio.push(acumulado);
    acumulado += d;
    plan.push(acumulado);
  }
  const fin = [...plan];
  const iArmado = ETAPAS.indexOf("armado");
  const iTextos = ETAPAS.indexOf("textos");
  const creado = Date.parse(t.creado);
  const video = hayVideo(carpeta, t.id);
  if (video) {
    const llego = statSync(/*turbopackIgnore: true*/ rutaDe(carpeta, t.id, "video.mp4")).mtimeMs - creado;
    fin[iArmado] = Math.max(plan[iArmado], llego);
  } else {
    fin[iArmado] = Infinity;
  }
  inicio[iTextos] = fin[iArmado];
  fin[iTextos] = inicio[iTextos] + dur[iTextos];
  const transcurrido = ahora - creado;
  return { dur, inicio, fin, plan, transcurrido, video, terminado: video && transcurrido >= fin[iTextos] };
}


/** En qué etapa se muestra un error. Un código que no está en la lista (o "constructor") cae en el armado. */
const etapaDelError = (codigo) =>
  typeof codigo === "string" && Object.hasOwn(ETAPA_DEL_ERROR, codigo) ? ETAPA_DEL_ERROR[codigo] : "armado";


/**
 * Pone al día un trabajo "armando": falla si le toca una falla de ejemplo, termina si el reloj y el video ya
 * llegaron, y si no hay video ni nadie armándolo (por ejemplo, después de apagar el Estudio) lo vuelve a la fila.
 */
function ponerAlDia(carpeta, t) {
  if (t.estado !== "armando") return t;
  const linea = lineaDeTiempo(carpeta, t);
  const falla = fallaSimulada(t);
  if (falla) {
    const etapa = ETAPAS.indexOf(etapaDelError(falla.codigo));
    return linea.transcurrido >= linea.plan[etapa] ? marcarFallo(carpeta, t, crearError(falla.codigo).error) : t;
  }
  if (linea.terminado) {
    // Si los textos no se pueden armar, el trabajo falla con su código en vez de quedar "armando" para siempre.
    // Sólo se cuida el armado de los textos: un archivo trabado un instante al escribir se reintenta en la próxima
    // lectura, sin hacer fallar un video bueno.
    let r;
    try {
      r = armarResultado(t);
    } catch (e) {
      const detalle = sinCarpetaPersonal(`no se pudieron armar los textos para publicar: ${e.message}`);
      return marcarFallo(carpeta, t, crearError("FALLO_ARMADO", detalle).error);
    }
    escribirJson(rutaDe(carpeta, t.id, "resultado.json"), r);
    const listo = { ...t, estado: "listo" };
    escribirJson(rutaDe(carpeta, t.id, "trabajo.json"), listo);
    return listo;
  }
  if (!linea.video && !candadoVivo(carpeta, t.id)) encolar(carpeta, t.id);
  return t;
}

/** ponerAlDia sin romper la lectura: si no se puede escribir, se devuelve como estaba. */
function alDia(carpeta, t) {
  try {
    return ponerAlDia(carpeta, t);
  } catch {
    return t;
  }
}

/** Cómo va un trabajo, etapa por etapa. */
function calcularAvance(carpeta, t, ahora = Date.now()) {
  if (t.estado === "listo") return { etapas: ETAPAS.map((id) => ({ id, estado: "listo" })), porcentaje: 100, restante: 0 };
  if (t.estado === "fallo") {
    const i = ETAPAS.indexOf(etapaDelError(t.error?.codigo));
    const dur = duraciones(t.largo);
    return {
      etapas: ETAPAS.map((id, k) => ({ id, estado: k < i ? "listo" : k === i ? "fallo" : "espera" })),
      porcentaje: Math.round((suma(dur.slice(0, i)) / suma(dur)) * 100),
      restante: 0,
      ...(t.error ? { error: t.error } : {}),
    };
  }
  const L = lineaDeTiempo(carpeta, t, ahora);
  const etapas = ETAPAS.map((id, k) => ({
    id,
    estado: L.transcurrido >= L.fin[k] ? "listo" : L.transcurrido >= L.inicio[k] ? "haciendo" : "espera",
  }));
  const hecho = suma(L.dur.map((d, k) => Math.min(d, Math.max(0, L.transcurrido - L.inicio[k]))));
  const iArmado = ETAPAS.indexOf("armado");
  const falta = L.video
    ? Math.max(0, L.fin.at(-1) - L.transcurrido)
    : Math.max(L.plan[iArmado] - L.transcurrido, FALTA_MINIMA * factor()) + L.dur.at(-1);
  const antes = videosAntes(t.id);
  return {
    etapas,
    porcentaje: Math.min(99, Math.floor((hecho / suma(L.dur)) * 100)),
    // Lo que falta se dice siempre a velocidad normal: en el modo rápido de las pruebas, una barra recién empezada
    // diría "Ya casi está" (todo dura quince veces menos) y las capturas mostrarían algo que nunca se ve de verdad.
    restante: Math.ceil(falta / factor() / 1000),
    ...(antes > 0 ? { fila: antes } : {}),
  };
}


/** Cómo va el armado de un trabajo. Devuelve { avance } o { error }. */
export async function avance(id) {
  const b = buscar(id);
  return b.error ? b : { avance: calcularAvance(b.carpeta, b.trabajo) };
}

// ---------------------------------------------------------------------------------------------
// La fila es la de fila.js: UNA para todo el Estudio, un armado por vez, con su candado en cada carpeta.

/** Corre Python para un trabajo. Si falla, el trabajo queda en "fallo" con FALLO_ARMADO. */
async function correr({ carpeta, id }) {
  const t = leerUno(carpeta, id);
  if (!t || t.estado !== "armando" || hayVideo(carpeta, id) || fallaSimulada(t)) return;
  if (!tomarCandado(carpeta, id)) return;
  const f = fila();
  f.corridas[id] = (f.corridas[id] || 0) + 1;
  const desde = Date.now();
  let salida;
  try {
    salida = await new Promise((resolver) => {
      // La velocidad de la voz la pone el contrato: Python no tiene una copia que se pueda quedar vieja.
      const args = [SCRIPT_ARMADO(), join(carpeta, id), `--palabras-por-segundo=${PALABRAS_POR_SEGUNDO}`];
      if (process.env.PORTAVOZ_VELOCIDAD === "rapida") args.push("--rapida");
      const hijo = spawn("python", args, { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });
      fila().hijo = hijo;
      let errores = "";
      let vencido = false;
      hijo.stderr.on("data", (d) => {
        errores = (errores + d).slice(-2000);
      });
      if (hijo.pid) escribirCandado(carpeta, id, { pid: hijo.pid, hora: desde, estudio: process.pid });
      const reloj = setTimeout(() => {
        vencido = true;
        matar(hijo);
      }, TOPE_ARMADO);
      hijo.on("error", (e) => {
        clearTimeout(reloj);
        resolver({ ok: false, detalle: `no se pudo correr Python: ${e.message}` });
      });
      hijo.on("close", (codigo) => {
        clearTimeout(reloj);
        if (codigo === 0 && hayVideo(carpeta, id)) return resolver({ ok: true });
        let detalle = vencido ? "el armado tardó demasiado y se cortó" : "";
        if (!detalle) {
          try {
            detalle = readFileSync(/*turbopackIgnore: true*/ rutaDe(carpeta, id, "armado-error.txt"), "utf8");
          } catch {
            detalle = errores || `el armado terminó con el código ${codigo}`;
          }
        }
        resolver({ ok: false, detalle });
      });
    });
  } finally {
    fila().hijo = null;
    escribirCandado(carpeta, id, { libre: true, hora: Date.now(), desde });
  }
  if (!salida.ok) {
    const ahora = leerUno(carpeta, id);
    if (ahora?.estado === "armando") marcarFallo(carpeta, ahora, crearError("FALLO_ARMADO", sinCarpetaPersonal(salida.detalle)).error);
  }
}

// ---------------------------------------------------------------------------------------------
// Los textos para publicar: los de datos/ejemplos/textos.json para las notas de ejemplo; para un texto pegado,
// las plantillas con el titular, la fuente y hashtags sacados del titular. Cada campo tiene varias versiones.

// Palabras largas que no dicen de qué trata la nota (no sirven de hashtag).
const PALABRAS_VACIAS = new Set([
  "durante", "sobre", "entre", "desde", "hasta", "porque", "cuando", "donde", "todos", "todas", "estos", "estas",
  "tiene", "tienen", "según", "hacia", "contra", "otros", "otras", "puede", "pueden", "después", "antes", "mientras",
  "también", "además", "ahora", "nuevo", "nueva", "nuevos", "nuevas",
]);

function clavesDe(titular) {
  const vistas = new Set();
  for (const p of String(titular).toLocaleLowerCase("es").split(/[^\p{L}\p{N}]+/u)) {
    if (p.length >= 5 && !PALABRAS_VACIAS.has(p) && !/^\p{N}+$/u.test(p)) vistas.add(p);
  }
  return [...vistas];
}

/** El titular sin el punto final, recortado con "..." si se pasa de `max` letras. */
function titularCorto(titular, max) {
  const t = String(titular ?? "").trim().replace(/(?<!\.)\.$/, "");
  return t.length <= max ? t : `${t.slice(0, Math.max(1, max - 3)).trimEnd()}...`;
}

const unicos = (lista) => [...new Set(lista)];

function rellenar(plantilla, valores) {
  return plantilla
    .replace(/\{(titular|fuente|hashtags)\}/g, (_, k) => valores[k] ?? "")
    .replace(/(\.\.\.|[!?…])\./g, "$1")
    .split("\n")
    .map((r) => r.replace(/[ \t]+/g, " ").trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Arma un texto para una red y, si se pasa de su tope, saca hashtags y acorta el titular hasta que entre. */
function paraRed(red, plantilla, valores, fijos) {
  const tope = TOPES_REDES[red]?.texto;
  let texto = rellenar(plantilla, valores);
  if (!tope || largoPara(red, texto) <= tope) return texto;
  let largo = valores.titular.length;
  do {
    texto = rellenar(plantilla, { ...valores, hashtags: fijos.join(" "), titular: titularCorto(valores.titular, largo) });
    largo -= 10;
  } while (largoPara(red, texto) > tope && largo > 10);
  return texto;
}

function dePlantillas(p, nota, video) {
  const titular = titularCorto(nota.titular, 120);
  const fuente = nota.medio ? video.fuente.replace("{medio}", nota.medio) : "";
  const claves = clavesDe(nota.titular);
  const hashtags = p.hashtags.map((fijos, i) => unicos([...fijos, ...claves.slice(i, i + 3).map((c) => `#${c}`)]));
  const etiquetas = p.etiquetasYoutube.map((fijas, i) => {
    const lista = unicos([titularCorto(nota.titular, 100).replace(/\.\.\.$/, ""), ...claves.slice(i, i + 4), ...fijas]
      .map((e) => e.replace(/,/g, " ").replace(/\s+/g, " ").trim())
      .filter(Boolean));
    while (largoEtiquetas(lista) > TOPE_ETIQUETAS_YOUTUBE && lista.length > 1) lista.pop();
    return lista;
  });
  const valores = (i) => ({ titular, fuente, hashtags: hashtags[i].join(" ") });
  return {
    titulo: p.titulo.map((pl) => rellenar(pl, { titular: titularCorto(nota.titular, TOPES_REDES.youtube.titulo - pl.replace("{titular}", "").length) })),
    descripcion: p.descripcion.map((pl, i) => rellenar(pl, valores(i))),
    hashtags,
    etiquetasYoutube: etiquetas,
    redes: Object.fromEntries(REDES.map((red) => [red, p.redes[red].map((pl, i) => paraRed(red, pl, valores(i), p.hashtags[i]))])),
  };
}

/** Todas las versiones de los textos para una nota (cada campo, una lista). Exportada para las pruebas. */
export function variantes(nota) {
  const todo = cargarTextos();
  return propio(todo.notas, nota.id) || dePlantillas(todo.plantillas[nota.sensible ? "sensible" : "general"], nota, todo.video);
}

function armarResultado(t) {
  const v = variantes(t.nota);
  return {
    video: `/api/trabajos/${t.id}/video`,
    portada: `/api/trabajos/${t.id}/portada`,
    textos: {
      titulo: v.titulo[0],
      descripcion: v.descripcion[0],
      hashtags: v.hashtags[0],
      etiquetasYoutube: v.etiquetasYoutube[0],
      redes: Object.fromEntries(REDES.map((red) => [red, v.redes[red][0]])),
    },
  };
}

/** El resultado guardado; si falta o está roto, se vuelve a armar y se guarda. */
function leerResultado(carpeta, t) {
  const ruta = rutaDe(carpeta, t.id, "resultado.json");
  const r = leerJson(ruta);
  if (r && revisarResultado(r).length === 0) return r;
  const nuevo = armarResultado(t);
  escribirJson(ruta, nuevo);
  return nuevo;
}

/** El resultado de un trabajo listo, sin esperas. Devuelve { resultado, carpeta, trabajo } o { error }. */
function resultadoAhora(id) {
  const b = buscar(id);
  if (b.error) return b;
  if (b.trabajo.estado !== "listo" || !hayVideo(b.carpeta, id)) return crearError("DESCONOCIDO", "el video todavía no está listo");
  return { resultado: leerResultado(b.carpeta, b.trabajo), carpeta: b.carpeta, trabajo: b.trabajo };
}

/** El resultado de un trabajo listo. Devuelve { resultado } o { error }. */
export async function resultado(id) {
  const r = resultadoAhora(id);
  return r.error ? r : { resultado: r.resultado };
}

/**
 * "Pedir otro": cambia un texto por su versión siguiente y lo guarda. campo es uno de CAMPOS_TEXTO; si es "redes",
 * `red` dice cuál. Devuelve { resultado } (el resultado entero, ya cambiado) o { error }.
 */
export async function otroTexto(id, campo, red) {
  if (!CAMPOS_TEXTO.includes(campo)) return crearError("DESCONOCIDO", "ese texto no se puede pedir de nuevo");
  if (campo === "redes" && !REDES.includes(red)) return crearError("DESCONOCIDO", "falta decir de qué red");
  // Leer, cambiar y guardar sin ninguna espera en el medio: dos pedidos a la vez (título y descripción) no se pisan.
  const r = resultadoAhora(id);
  if (r.error) return r;
  const { carpeta, trabajo: t } = r;
  const v = variantes(t.nota);
  const lista = campo === "redes" ? v.redes[red] : v[campo];
  const actual = campo === "redes" ? r.resultado.textos.redes[red] : r.resultado.textos[campo];
  const i = lista.findIndex((x) => JSON.stringify(x) === JSON.stringify(actual));
  const nuevo = lista[(i + 1) % lista.length];
  const textos = campo === "redes"
    ? { ...r.resultado.textos, redes: { ...r.resultado.textos.redes, [red]: nuevo } }
    : { ...r.resultado.textos, [campo]: nuevo };
  const cambiado = { ...r.resultado, textos };
  escribirJson(rutaDe(carpeta, id, "resultado.json"), cambiado);
  return { resultado: cambiado };
}

/**
 * Vuelve a probar un trabajo que falló: uno nuevo con los mismos datos y reintentoDe. Gasta una voz.
 * Una sola vez por trabajo: en el que falló queda reintentadoEn con el id del nuevo, y si vuelve a llegar el pedido
 * (Atrás, otra pestaña, Mis videos) se devuelve ése, sin armar otro ni gastar otra voz. Dos pedidos a la vez
 * reciben el mismo.
 */
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

/** El trabajo que ya volvió a probar a éste, puesto al día, o null. Primero por reintentadoEn; si no quedó anotado
 *  (uno de antes, o se cortó justo al anotarlo), por el reintentoDe del nuevo. */
function yaReintentado(carpeta, t) {
  if (esIdTrabajo(t.reintentadoEn)) {
    const n = leerUno(carpeta, t.reintentadoEn);
    if (n) return alDia(carpeta, n);
  }
  return buscarGuardado((x) => x.reintentoDe === t.id);
}


/** La ruta en disco del video o la portada de un trabajo. Devuelve { archivo: { ruta, tamano, tipo, trabajo } } o { error }. */
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

/** Cuántas voces quedan hoy y cuántos videos van en el mes, contados desde los trabajos. */
export async function cupo(opciones) {
  return cupoAhora(opciones);
}

/** La misma cuenta sin esperas, para contar y guardar sin que otro pedido se meta en el medio. */
function cupoAhora({ sinVoces = false } = {}) {
  let lista;
  try {
    lista = leerTodos();
  } catch (e) {
    return crearError("DESCONOCIDO", `no se pudieron contar las voces: ${e.message}`);
  }
  const ahora = new Date();
  // Una voz por trabajo creado hoy (día local) que no falló. Con la simulación, el tope.
  const hoy = lista.filter((t) => t.estado !== "fallo" && mismoDia(new Date(t.creado), ahora)).length;
  const usadas = sinVoces ? TOPE_VOCES_DIA : hoy;
  return {
    cupo: {
      voces: { usadas, tope: TOPE_VOCES_DIA, quedan: Math.max(0, TOPE_VOCES_DIA - usadas) },
      videosMes: lista.filter((t) => t.estado === "listo" && mismoMes(new Date(t.creado), ahora)).length,
      mes: `${ahora.getFullYear()}-${dos(ahora.getMonth() + 1)}`,
    },
  };
}

/** Para el panel "Probar con un ejemplo": los links de las notas y de las fallas. */
export function vitrina() {
  const { notas, fallas } = cargar();
  return {
    notas: notas.map((n) => ({ link: n.link, titular: n.titular, sensible: TEMAS_SENSIBLES.includes(n.tema) })),
    fallas: fallas.map((f) => ({ link: f.link, clave: f.clave })),
  };
}
