// Contrato de datos del Estudio: las formas con las que hablan la pantalla y el motor.
// La explicación en criollo está en docs/contrato.md. Si cambia algo acá, cambia allá en el mismo viaje.
//
// Regla de fondo: el motor devuelve CÓDIGOS (por ejemplo "MURO_DE_PAGO") y la pantalla pone las palabras,
// que viven todas en lib/textos.js. Así los textos se aprueban en un solo lugar.

/** Largos posibles del video, en segundos. */
export const LARGOS = [15, 30, 60];
export const LARGO_INICIAL = 30;

/** Se estima: la voz neutra de Google lee unas 150 palabras por minuto. Se mide de verdad en la Fase 5. */
export const PALABRAS_POR_SEGUNDO = 3.3;
export const palabrasPara = (segundos) => Math.round((segundos * PALABRAS_POR_SEGUNDO) / 5) * 5;
export const segundosPara = (palabras) => Math.round(palabras / PALABRAS_POR_SEGUNDO);

/** Se estima: cuánto se puede pasar un guion del largo elegido y que igual entre (la voz se acomoda).
 *  El margen es para lo que escribe la persona: lo que propone el Estudio entra sin margen (entraJusto). */
export const MARGEN_LARGO = 0.1;
export const entraEnLargo = (palabras, largo) => segundosPara(palabras) <= largo * (1 + MARGEN_LARGO);
export const entraJusto = (palabras, largo) => segundosPara(palabras) <= largo;

/** Las tres formas de contar la nota. Los nombres que ve la persona están en textos.js (GUION.enfoques). */
export const ENFOQUES = ["dato", "te-cambia", "debate"];
/** Lo que se le puede pedir a un guion: más corto, más simple, otro distinto. */
export const CAMBIOS = ["corto", "simple", "otro"];
/** De dónde salió cada versión de un guion. */
export const ORIGENES = ["propuesta", "corto", "simple", "otro", "a-mano"];

/**
 * Lo que puede marcar la revisión de un guion cuando no lo pudo arreglar sola. El motor compara esta lista con la
 * suya (motor/contrato.py). Los textos que ve la persona están en textos.js (GUION.avisos).
 * - DATO_NO_ESTA: el guion dice algo que no está en la nota.
 * - VERBO_CAMBIADO: el guion cuenta como hecho algo que la nota dice que va a pasar.
 */
export const AVISOS_REVISION = ["DATO_NO_ESTA", "VERBO_CAMBIADO"];
/** Quién revisó el guion. */
export const REVISORES = ["claude-sonnet", "google", "codigo"];
/** Los campos de la revisión de una versión (el motor compara esta lista con la suya, motor/contrato.py). */
export const CAMPOS_REVISION = ["puntos", "arreglado", "aviso", "quien", "antes", "arreglados"];

// Las fotos de la página de la nota (Tanda B, desde el 2026-11-20). Las junta motor/medios_pagina.py al leer la nota.
/** Cuántas fotos se guardan por nota, como mucho. */
export const MAXIMO_FOTOS = 8;
/** Cómo se encuadra una foto en el video, según la mira Claude: acercamiento lento, recorrido de costado, o entera
 *  (con franjas, cuando recortarla dejaría afuera algo importante). */
export const ENCUADRES = ["acercamiento", "recorrido", "entera"];
/** Los campos de cada foto de nota.medios y de lo que vio Claude en ella (mirada). */
export const CAMPOS_FOTO = ["n", "archivo", "ancho", "alto", "pie", "alt", "credito", "mirada"];
export const CAMPOS_MIRADA = ["sirve", "encuadre", "centro"];
/** Los campos del pie del video que la persona puede cambiar o sacar (trabajo.pie). */
export const CAMPOS_PIE = ["mostrar", "fuente", "ilustrativas"];
/** Cómo va cada foto aprobada en el video (desde el 2026-11-20): a pantalla completa, en lugar del clip de su parte,
 *  o en un recuadro encima del clip, que se sigue moviendo detrás. Una foto sin forma va a pantalla completa. */
export const FORMAS = ["pantalla", "encima"];
/** Los campos de cada foto aprobada del trabajo (trabajo.imagenes). */
export const CAMPOS_IMAGEN = ["tramo", "foto", "credito", "forma"];
/** Lo que se puede agrandar una foto para llenar la pantalla parada sin que se vea pixelada: más que esto, la foto va
 *  encima del clip (lo eligió Lucio el 2026-11-20 viendo videos de prueba). */
export const AGRANDAR_HASTA = 2;
/** La pantalla del video, parada: 1080 de ancho por 1920 de alto. */
export const PANTALLA_VIDEO = { ancho: 1080, alto: 1920 };
/** El nombre del archivo de cada foto: su número con dos cifras y .jpg (01.jpg a 08.jpg). Con esta forma exacta se
 *  comprueba antes de usarlo para buscar el archivo. */
export const ARCHIVO_FOTO = /^\d{2}\.jpg$/;

/** Una nota con menos palabras que esto no alcanza para un video. */
export const PALABRAS_MINIMAS_NOTA = 60;

/** Tope de la voz gratis de Google: 10 voces por día por llave. */
export const TOPE_VOCES_DIA = 10;

/** Tope de YouTube para las etiquetas, contando las comas que las separan. Ya estaba antes del 2026-11-17 y ese día
 *  NO se encontró en las páginas de ayuda de YouTube (answer/57407 y answer/146402): queda porque es más estricto. */
export const TOPE_ETIQUETAS_YOUTUBE = 500;

export const TEMAS = ["general", "politica", "crimen", "tragedia"];
export const TEMAS_SENSIBLES = ["politica", "crimen", "tragedia"];

/** Etapas del armado, en orden. Los nombres que ve la persona están en textos.js. */
export const ETAPAS = ["clips", "voz", "tiempos", "armado", "textos"];

/** Redes para las que salen textos. Los nombres que ve la persona están en textos.js (REDES). */
export const REDES = ["tiktok", "instagram", "youtube", "facebook", "x", "linkedin"];

/**
 * Topes de cada red para lo que se publica. SÓLO los que están escritos en una página oficial, abierta el
 * 2026-11-17 (la fuente al lado de cada uno). Lo que no se pudo comprobar no tiene tope acá: no se pone de memoria.
 * - texto: largo máximo del texto de esa red. Se cuenta en unidades de JavaScript (.length), que es como cuenta
 *   TikTok ("UTF-16 runes") y para el resto da de más, nunca de menos. X cuenta con peso: ver largoX().
 * - hashtags: cuántos hashtags puede llevar ese texto.
 */
export const TOPES_REDES = {
  // "caption ... max 2200 UTF-16 runes": https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
  // (la documentación oficial de TikTok para programas que publican; la ayuda para usuarios no lo dice).
  tiktok: { texto: 2200 },
  // "Maximum 2200 characters, 30 hashtags, and 20 @ tags":
  // https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media
  // (la documentación oficial de Meta para programas; la ayuda de Instagram no se pudo abrir).
  instagram: { texto: 2200, hashtags: 30 },
  // Título 100 y descripción 5.000: https://support.google.com/youtube/answer/57407
  // Con más de 60 hashtags, YouTube los ignora todos: https://support.google.com/youtube/answer/6390658
  youtube: { titulo: 100, texto: 5000, hashtags: 60 },
  // Facebook: no se encontró el tope en ninguna página oficial. Sin tope hasta que alguien lo compruebe.
  facebook: {},
  // 280, con peso (letras latinas 1, el resto 2, links 23): https://docs.x.com/fundamentals/counting-characters
  x: { texto: 280 },
  // "Posts can contain up to 3,000 characters.": https://www.linkedin.com/help/linkedin/answer/a528176
  linkedin: { texto: 3000 },
};

/** El peso de X sin mirar links: las letras latinas y la puntuación común valen 1; lo demás, 2. */
function pesoX(texto) {
  let n = 0;
  for (const c of String(texto)) {
    const p = c.codePointAt(0);
    const liviano = p <= 0x10ff || (p >= 0x2000 && p <= 0x200d) || (p >= 0x2010 && p <= 0x201f) || (p >= 0x2032 && p <= 0x2037);
    n += liviano ? 1 : 2;
  }
  return n;
}

// Los links, en una sola pasada de izquierda a derecha:
// - con http o https: sólo letras y signos simples (lo que sigue pegado, como una letra con tilde o un emoji, se
//   cuenta aparte);
// - un dominio suelto: palabra.palabra que termina en dos letras o más, sin una letra, un número, una arroba, un
//   punto ni una barra justo antes, con lo que siga hasta el espacio.
const LINKS_X = /https?:\/\/[\x21-\x7e]+|(?<![\p{L}\p{N}_@./-])[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)*\.\p{L}{2,}(?![\p{L}\p{N}-])(?:\/\S*)?/giu;
// Los signos del final que X no toma como parte del link ("ver https://a.com/nota." termina en "nota").
const FINAL_LINK_X = /[.,;:!?)\]}"'»”’]+$/u;

/**
 * Cuenta como X (https://docs.x.com/fundamentals/counting-characters): cada link vale 23, las letras latinas y
 * la puntuación común valen 1 y todo lo demás (emojis, otros alfabetos) vale 2. Los rangos exactos de X están en
 * su biblioteca twitter-text, que no se abrió; estos son los de su documentación y, si se equivocan, cuentan de más.
 * - A un link con http o https se le separan los signos del final (que cuentan como letras) y vale 23.
 * - Un dominio suelto ("ejemplo.com/nota") vale lo que sea más grande entre 23 y su propio largo: X lo toma como
 *   link si conoce la terminación, y si no, lo cuenta entero. Así no se cuenta de menos (y "EE.UU." cuenta 23).
 */
export function largoX(texto) {
  let n = 0;
  const resto = String(texto ?? "").replace(LINKS_X, (m) => {
    const final = m.match(FINAL_LINK_X)?.[0] ?? "";
    const link = m.slice(0, m.length - final.length);
    n += /^https?:\/\//i.test(link) ? 23 : Math.max(23, pesoX(link));
    return final;
  });
  return n + pesoX(resto);
}

/** Cuántos hashtags hay en un texto. */
export const contarHashtags = (texto) => (String(texto ?? "").match(/#[\p{L}\p{N}_]+/gu) || []).length;
const HASHTAG = /^#[\p{L}\p{N}_]+$/u;

/** Lo que se puede pedir de nuevo con "Pedir otro". "redes" necesita además cuál red. */
export const CAMPOS_TEXTO = ["titulo", "descripcion", "hashtags", "etiquetasYoutube", "redes"];

/** En qué etapa se ve cada error del armado (los demás, en el armado). */
export const ETAPA_DEL_ERROR = { FALLO_VOZ: "voz", SIN_CLIPS: "clips", FALLO_ARMADO: "armado" };

/**
 * Errores. `salida` dice qué camino le ofrece la pantalla a la persona:
 * - corregir: arreglar lo que escribió;
 * - pegar-texto: abrir ahí mismo el cuadro para pegar el texto de la nota;
 * - reintentar: probar de nuevo lo mismo;
 * - volver-al-guion: volver al guion elegido, que queda intacto;
 * - manana: no se puede hoy (se renuevan las voces).
 * `cuenta` es siempre false: lo que falla no cuenta como video del mes.
 */
export const ERRORES = {
  LINK_INVALIDO: { salida: "corregir" },
  LINK_NO_ABRE: { salida: "pegar-texto" },
  NOTA_SIN_TEXTO: { salida: "pegar-texto" },
  MURO_DE_PAGO: { salida: "pegar-texto" },
  NOTA_MUY_CORTA: { salida: "corregir" },
  SIN_VOCES_HOY: { salida: "manana" },
  GUION_A_CORREGIR: { salida: "volver-al-guion" },
  SIN_CLIPS: { salida: "volver-al-guion" },
  FALLO_VOZ: { salida: "reintentar" },
  FALLO_ARMADO: { salida: "reintentar" },
  SIN_CONEXION: { salida: "reintentar" },
  DESCONOCIDO: { salida: "reintentar" },
};

export const SALIDAS = ["corregir", "pegar-texto", "reintentar", "volver-al-guion", "manana"];

/** Si un código es uno de ERRORES (con Object.hasOwn: "constructor" o "toString" no son códigos). */
export const esCodigoError = (codigo) => typeof codigo === "string" && Object.hasOwn(ERRORES, codigo);

export function crearError(codigo, detalle) {
  const conocido = esCodigoError(codigo) ? codigo : "DESCONOCIDO";
  return { error: { codigo: conocido, salida: ERRORES[conocido].salida, cuenta: false, ...(detalle ? { detalle } : {}) } };
}

/** Un link se acepta si es http o https y tiene un dominio con punto. */
export function linkValido(texto) {
  try {
    const u = new URL(String(texto).trim());
    return (u.protocol === "https:" || u.protocol === "http:") && u.hostname.includes(".");
  } catch {
    return false;
  }
}

export const contarPalabras = (texto) => (String(texto || "").trim().match(/\S+/g) || []).length;

// ---------------------------------------------------------------------------------------------
// Comprobaciones. Cada una devuelve la lista de problemas (vacía si está bien).
// Las usan scripts/contrato.mjs y, en la Fase 5, la entrada del motor real.

const esTexto = (v) => typeof v === "string" && v.trim().length > 0;
const esFechaCorta = (v) => v === null || /^\d{4}-\d{2}-\d{2}$/.test(v);

/** Pedido: lo que manda la persona en el Paso 1. */
export function revisarPedido(p) {
  const mal = [];
  if (!p || typeof p !== "object") return ["el pedido no es un objeto"];
  if (!LARGOS.includes(p.largo)) mal.push(`largo ${p.largo} no es 15, 30 ni 60`);
  if (!p.link && !p.texto) mal.push("falta el link o el texto");
  if (p.link && !linkValido(p.link)) mal.push("el link no es válido");
  return mal;
}

const esEntero = (v, desde, hasta) => Number.isInteger(v) && v >= desde && v <= hasta;
const camposRaros = (o, campos) => Object.keys(o).filter((k) => !campos.includes(k));

/** Lo que vio Claude en una foto: { sirve, encuadre, centro } (centro: dónde está lo importante, de 0 a 1 de
 *  izquierda a derecha). */
export function revisarMirada(m) {
  if (!m || typeof m !== "object" || Array.isArray(m)) return ["la mirada no es un objeto"];
  const mal = [];
  if (typeof m.sirve !== "boolean") mal.push("sirve tiene que ser sí o no");
  if (!ENCUADRES.includes(m.encuadre)) mal.push(`encuadre ${m.encuadre} no está en la lista`);
  if (typeof m.centro !== "number" || !(m.centro >= 0 && m.centro <= 1)) mal.push("centro tiene que ser un número de 0 a 1");
  const raros = camposRaros(m, CAMPOS_MIRADA);
  if (raros.length) mal.push(`la mirada trae campos que no están en el contrato: ${raros.join(", ")}`);
  return mal;
}

/** Lo que vio Claude al escribir los guiones (guiones.py devuelve { guiones, fotos }): [{ n, sirve, encuadre,
 *  centro }], una por foto mirada, cada una de una foto de la nota. El Estudio lo guarda como nota.medios[].mirada. */
export function revisarMiradas(fotos, medios) {
  if (!Array.isArray(fotos)) return ["fotos tiene que ser una lista"];
  const hay = new Set(Array.isArray(medios) ? medios.map((f) => f?.n) : []);
  const vistas = new Set();
  const mal = [];
  fotos.forEach((f, i) => {
    if (!f || typeof f !== "object" || Array.isArray(f)) { mal.push(`mirada ${i}: no es un objeto`); return; }
    const { n, ...mirada } = f;
    if (!hay.has(n)) mal.push(`mirada ${i}: la foto ${n} no está en la nota`);
    else if (vistas.has(n)) mal.push(`mirada ${i}: la foto ${n} está dos veces`);
    vistas.add(n);
    mal.push(...revisarMirada(mirada).map((p) => `mirada ${i}: ${p}`));
  });
  return mal;
}

/** Las fotos de la nota (nota.medios): [{ n, archivo, ancho, alto, pie, alt, credito, mirada? }]. n va de 1 a
 *  MAXIMO_FOTOS, sin repetir, y archivo es su número con dos cifras y .jpg. */
export function revisarMedios(medios) {
  if (!Array.isArray(medios)) return ["medios tiene que ser una lista"];
  const mal = [];
  if (medios.length > MAXIMO_FOTOS) mal.push(`son más de ${MAXIMO_FOTOS} fotos`);
  const vistos = new Set();
  medios.forEach((f, i) => {
    if (!f || typeof f !== "object" || Array.isArray(f)) { mal.push(`foto ${i}: no es un objeto`); return; }
    if (!esEntero(f.n, 1, MAXIMO_FOTOS)) mal.push(`foto ${i}: n tiene que ser un número de 1 a ${MAXIMO_FOTOS}`);
    else if (vistos.has(f.n)) mal.push(`foto ${i}: el número ${f.n} está repetido`);
    vistos.add(f.n);
    if (typeof f.archivo !== "string" || !ARCHIVO_FOTO.test(f.archivo) || f.archivo !== `${String(f.n).padStart(2, "0")}.jpg`) {
      mal.push(`foto ${i}: archivo con forma rara`);
    }
    if (!esEntero(f.ancho, 1, 100000) || !esEntero(f.alto, 1, 100000)) mal.push(`foto ${i}: ancho y alto tienen que ser números enteros`);
    for (const campo of ["pie", "alt", "credito"]) if (typeof f[campo] !== "string") mal.push(`foto ${i}: ${campo} tiene que ser texto`);
    if (f.mirada !== undefined) mal.push(...revisarMirada(f.mirada).map((p) => `foto ${i}: ${p}`));
    const raros = camposRaros(f, CAMPOS_FOTO);
    if (raros.length) mal.push(`foto ${i}: trae campos que no están en el contrato: ${raros.join(", ")}`);
  });
  return mal;
}

/** Las fotos sugeridas en los tramos de cada versión: un tramo puede traer `foto` (el número de una foto de
 *  nota.medios) o no traerla. Cada foto va una sola vez por versión, y en la mitad de los tramos como mucho,
 *  redondeando para abajo (el reparto del plan del 18/11). Sin `medios` no se compara con la nota. */
export function revisarFotosDeTramos(versiones, medios) {
  const mal = [];
  const hay = Array.isArray(medios) ? new Set(medios.map((f) => f?.n)) : null;
  (versiones || []).forEach((v, i) => {
    if (v?.tramos === undefined) return;
    if (!Array.isArray(v.tramos)) { mal.push(`versión ${i}: tramos tiene que ser una lista`); return; }
    const fotos = [];
    v.tramos.forEach((t, j) => {
      if (!t || typeof t !== "object") { mal.push(`versión ${i}, tramo ${j}: no es un objeto`); return; }
      if (t.foto === undefined || t.foto === null) return;
      if (!esEntero(t.foto, 1, MAXIMO_FOTOS)) mal.push(`versión ${i}, tramo ${j}: foto tiene que ser un número de 1 a ${MAXIMO_FOTOS}`);
      else if (hay && !hay.has(t.foto)) mal.push(`versión ${i}, tramo ${j}: la foto ${t.foto} no está en la nota`);
      fotos.push(t.foto);
    });
    if (new Set(fotos).size !== fotos.length) mal.push(`versión ${i}: una foto va en más de un tramo`);
    if (fotos.length > Math.floor(v.tramos.length / 2)) mal.push(`versión ${i}: fotos en más de la mitad de los tramos`);
  });
  return mal;
}

/** Nota: lo que se leyó. Si trae fotos (medios), se revisan con revisarMedios. */
export function revisarNota(n) {
  const mal = [];
  if (!n || typeof n !== "object") return ["la nota no es un objeto"];
  for (const campo of ["id", "titular", "texto"]) if (!esTexto(n[campo])) mal.push(`falta ${campo}`);
  if (!["link", "texto"].includes(n.origen)) mal.push("origen tiene que ser link o texto");
  if (n.origen === "link" && !linkValido(n.link)) mal.push("una nota leída de un link necesita el link");
  if (n.origen === "link" && !esTexto(n.medio)) mal.push("una nota leída de un link necesita el medio");
  if (n.medio !== null && n.medio !== undefined && typeof n.medio !== "string") mal.push("medio tiene que ser texto o null");
  if (!esFechaCorta(n.fecha ?? null)) mal.push("fecha tiene que ser AAAA-MM-DD o null");
  if (!TEMAS.includes(n.tema)) mal.push(`tema ${n.tema} no está en la lista`);
  if (n.sensible !== TEMAS_SENSIBLES.includes(n.tema)) mal.push("sensible no coincide con el tema");
  if (n.palabras !== contarPalabras(n.texto)) mal.push("palabras no coincide con el texto");
  if (typeof n.ejemplo !== "boolean") mal.push("falta marcar si es de ejemplo");
  if (n.medios !== undefined) {
    mal.push(...revisarMedios(n.medios).map((p) => `medios: ${p}`));
    if (!linkValido(n.link)) mal.push("las fotos salen de la página: una nota con fotos necesita el link");
  }
  return mal;
}

/**
 * La revisión de una versión (opcional): lo que se comparó contra la nota, si se arregló algo y si queda un aviso.
 * { puntos: [texto], arreglado, aviso: null | AVISOS_REVISION, quien: REVISORES, antes?, arreglados? }. `antes` es
 * el texto de antes del arreglo y `arreglados` los puntos que se mandaron a arreglar (lista de textos); los dos sólo
 * vienen cuando `arreglado` es true. La pantalla no los muestra.
 */
export function revisarRevision(r) {
  const mal = [];
  if (!r || typeof r !== "object" || Array.isArray(r)) return ["la revisión no es un objeto"];
  if (!Array.isArray(r.puntos) || !r.puntos.every((p) => typeof p === "string")) mal.push("puntos tiene que ser una lista de textos");
  if (typeof r.arreglado !== "boolean") mal.push("arreglado tiene que ser sí o no");
  if (r.aviso !== null && !AVISOS_REVISION.includes(r.aviso)) mal.push(`aviso ${r.aviso} no está en la lista`);
  if (!REVISORES.includes(r.quien)) mal.push(`quien ${r.quien} no está en la lista`);
  if (r.antes !== undefined) {
    if (!esTexto(r.antes)) mal.push("antes tiene que ser un texto");
    if (r.arreglado !== true) mal.push("antes sólo viene cuando se arregló algo");
  }
  if (r.arreglados !== undefined) {
    if (!Array.isArray(r.arreglados) || !r.arreglados.every((p) => typeof p === "string")) mal.push("arreglados tiene que ser una lista de textos");
    if (r.arreglado !== true) mal.push("arreglados sólo viene cuando se arregló algo");
  }
  const raros = Object.keys(r).filter((k) => !CAMPOS_REVISION.includes(k));
  if (raros.length) mal.push(`la revisión trae campos que no están en el contrato: ${raros.join(", ")}`);
  return mal;
}

/**
 * Guion: una de las tres propuestas, con sus versiones.
 * { id, enfoque, versiones: [{ texto, palabras, origen, revision? }], actual }. Deshacer es bajar `actual`.
 */
export function revisarGuion(g) {
  const mal = [];
  if (!g || typeof g !== "object") return ["el guion no es un objeto"];
  if (!esTexto(g.id)) mal.push("falta id");
  if (!ENFOQUES.includes(g.enfoque)) mal.push(`enfoque ${g.enfoque} no está en la lista`);
  if (!Array.isArray(g.versiones) || g.versiones.length === 0) return [...mal, "faltan versiones"];
  if (!Number.isInteger(g.actual) || g.actual < 0 || g.actual >= g.versiones.length) mal.push("actual fuera de rango");
  g.versiones.forEach((v, i) => {
    if (!esTexto(v.texto)) mal.push(`versión ${i} sin texto`);
    if (v.palabras !== contarPalabras(v.texto)) mal.push(`versión ${i}: palabras no coincide`);
    if (!ORIGENES.includes(v.origen)) mal.push(`versión ${i}: origen ${v.origen} no está en la lista`);
    if (v.revision !== undefined) mal.push(...revisarRevision(v.revision).map((p) => `versión ${i}: ${p}`));
  });
  mal.push(...revisarFotosDeTramos(g.versiones));
  return mal;
}

/** Estados de un trabajo. Los nombres que ve la persona están en textos.js (MIS_VIDEOS.estados). */
export const ESTADOS_TRABAJO = ["armando", "listo", "fallo"];

/** Identificador de un trabajo: AAAAMMDD-HHMMSS-xxxx (hora local y cuatro letras o números al azar).
 *  Lo arma el servidor; con esta forma exacta se comprueba antes de usarlo para buscar una carpeta. */
export const ID_TRABAJO = /^\d{8}-\d{6}-[a-z0-9]{4}$/;
export const esIdTrabajo = (id) => typeof id === "string" && ID_TRABAJO.test(id);

/** Encargo: la marca que la pantalla le pone a un "Armar mi video" antes de mandarlo (letras de la a a la f y
 *  números, de 16 a 64). Si el mismo encargo llega dos veces (se cerró la página, se cortó la respuesta), se
 *  devuelve el trabajo que ya existe en vez de armar otro y gastar otra voz. */
export const ENCARGO = /^[a-f0-9]{16,64}$/;
export const esEncargo = (e) => typeof e === "string" && ENCARGO.test(e);

/** Los dos problemas del guion que la persona arregla volviendo al guion (error GUION_A_CORREGIR). */
export const GUION_VACIO = "el guion está vacío";
export const GUION_SE_PASA = "el guion se pasa del largo";

/** Un error guardado, con la forma que arma crearError. */
function revisarError(e) {
  if (!e || typeof e !== "object") return ["el error no es un objeto"];
  const mal = [];
  if (!esCodigoError(e.codigo)) mal.push(`código de error desconocido ${e.codigo}`);
  else if (e.salida !== ERRORES[e.codigo].salida) mal.push("la salida del error no es la de su código");
  if (e.cuenta !== false) mal.push("un error nunca cuenta como video");
  if (e.detalle !== undefined && typeof e.detalle !== "string") mal.push("el detalle del error tiene que ser texto");
  return mal;
}

/** Los tres guiones guardados con el trabajo (la forma de lib/borrador.js): { notaId, lista, elegido }.
 *  t es el trabajo (o lo que se va a mandar para crearlo): mira t.guiones contra t.nota y t.guion. */
export function revisarGuionesDelTrabajo(t) {
  const gs = t.guiones;
  if (!gs || typeof gs !== "object") return ["guiones no es un objeto"];
  const mal = [];
  if (gs.notaId !== t.nota?.id) mal.push("los guiones son de otra nota");
  if (!Array.isArray(gs.lista) || gs.lista.length !== ENFOQUES.length) return [...mal, `guiones: tienen que ser ${ENFOQUES.length}`];
  gs.lista.forEach((g, i) => mal.push(...revisarGuion(g).map((p) => `guiones ${i}: ${p}`)));
  gs.lista.forEach((g, i) => mal.push(...revisarFotosDeTramos(g?.versiones, t.nota?.medios ?? [])
    .filter((p) => p.includes("no está en la nota")).map((p) => `guiones ${i}: ${p}`)));
  if (new Set(gs.lista.map((g) => g?.enfoque)).size !== gs.lista.length) mal.push("guiones con enfoques repetidos");
  const elegido = gs.lista.find((g) => g && g.id === gs.elegido);
  if (!elegido) {
    mal.push("el guion elegido no está en la lista");
  } else {
    const texto = String(elegido.versiones?.[elegido.actual]?.texto ?? "").trim();
    if (elegido.enfoque !== t.guion?.enfoque || texto !== String(t.guion?.texto ?? "").trim()) {
      mal.push("el guion del trabajo no es el elegido en su versión actual");
    }
  }
  return mal;
}

/**
 * Trabajo: lo que queda guardado al tocar "Armar mi video". Cada uno vive en <carpeta>/<id>/trabajo.json.
 * { id, creado, largo, nota, guion: { enfoque, texto, palabras }, estado } y, si están:
 * - pedido: lo que pidió la persona en el Paso 1 (se revisa como revisarPedido);
 * - guiones: los tres guiones del Paso 2 ({ notaId, lista, elegido }, como lib/borrador.js). El elegido, en su
 *   versión actual, tiene que ser el mismo texto y enfoque que `guion`;
 * - reintentoDe: el id del trabajo que falló y que éste vuelve a probar;
 * - reintentadoEn: en un trabajo que falló, el id del que lo volvió a probar. "Volver a probar" otra vez devuelve
 *   ése en vez de armar otro (y gastar otra voz);
 * - encargo: la marca del pedido que lo creó (ver esEncargo);
 * - error: por qué falló (la forma de crearError). Sólo en un trabajo en "fallo";
 * - imagenes: las fotos aprobadas, una por tramo (ver revisarImagenes). Las usa el armado desde la etapa 5;
 * - pie: lo que dice el pie del video y si se muestra (ver revisarPie).
 */
export function revisarTrabajo(t) {
  const mal = [];
  if (!t || typeof t !== "object") return ["el trabajo no es un objeto"];
  if (!esIdTrabajo(t.id)) mal.push("id con forma rara");
  if (typeof t.creado !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(t.creado) || Number.isNaN(Date.parse(t.creado))) {
    mal.push("creado no es una fecha y hora");
  }
  if (!LARGOS.includes(t.largo)) mal.push(`largo ${t.largo} no es 15, 30 ni 60`);
  mal.push(...revisarNota(t.nota).map((p) => `nota: ${p}`));
  const g = t.guion;
  if (!g || typeof g !== "object") {
    mal.push("falta el guion");
  } else {
    if (!ENFOQUES.includes(g.enfoque)) mal.push(`enfoque ${g.enfoque} no está en la lista`);
    if (!esTexto(g.texto)) {
      mal.push(GUION_VACIO);
    } else {
      if (g.palabras !== contarPalabras(g.texto)) mal.push("palabras del guion no coincide con el texto");
      if (LARGOS.includes(t.largo) && !entraEnLargo(contarPalabras(g.texto), t.largo)) mal.push(GUION_SE_PASA);
    }
  }
  if (!ESTADOS_TRABAJO.includes(t.estado)) mal.push(`estado ${t.estado} no está en la lista`);
  if (t.pedido !== undefined) mal.push(...revisarPedido(t.pedido).map((p) => `pedido: ${p}`));
  if (t.guiones !== undefined) mal.push(...revisarGuionesDelTrabajo(t));
  if (t.reintentoDe !== undefined) {
    if (!esIdTrabajo(t.reintentoDe)) mal.push("reintentoDe con forma rara");
    else if (t.reintentoDe === t.id) mal.push("un trabajo no puede ser reintento de sí mismo");
  }
  if (t.reintentadoEn !== undefined) {
    if (!esIdTrabajo(t.reintentadoEn)) mal.push("reintentadoEn con forma rara");
    else if (t.reintentadoEn === t.id) mal.push("un trabajo no puede volver a probarse en sí mismo");
    if (t.estado !== "fallo") mal.push("sólo un trabajo que falló se vuelve a probar");
  }
  if (t.encargo !== undefined && !esEncargo(t.encargo)) mal.push("encargo con forma rara");
  if (t.error !== undefined) {
    mal.push(...revisarError(t.error).map((p) => `error: ${p}`));
    if (t.estado !== "fallo") mal.push("un trabajo con error tiene que estar en fallo");
  }
  if (t.imagenes !== undefined) mal.push(...revisarImagenes(t.imagenes, t.nota?.medios));
  if (t.pie !== undefined) mal.push(...revisarPie(t.pie));
  return mal;
}

/**
 * La forma que sugiere el programa para una foto de la nota (sin preguntarle nada nuevo a Claude): una foto parada va
 * a pantalla completa (se llena sola, y en un recuadro quedaría enorme o chiquita); una que Claude dijo que no se
 * puede recortar sin perder algo ("entera"), o que habría que agrandar más de AGRANDAR_HASTA veces para llenar la
 * pantalla, va encima del clip; el resto, a pantalla completa. Es una cuenta simple: la persona la cambia.
 */
export function sugerirForma(medio) {
  const ancho = Number(medio?.ancho);
  const alto = Number(medio?.alto);
  if (!(ancho > 0) || !(alto > 0)) return "pantalla";
  if (alto >= ancho) return "pantalla";
  if (medio?.mirada?.encuadre === "entera") return "encima";
  const agrandar = Math.max(PANTALLA_VIDEO.ancho / ancho, PANTALLA_VIDEO.alto / alto);
  return agrandar > AGRANDAR_HASTA ? "encima" : "pantalla";
}

/** Las fotos aprobadas del trabajo (sin las que quedaron en "No"): [{ tramo, foto, credito, forma? }]. tramo es el
 *  número de parte (desde 0) de la última versión con partes del guion elegido: la actual, o la de antes si se
 *  corrigió a mano. foto es el número de una foto de nota.medios; credito, lo que dice el pie con esa foto (la
 *  persona lo puede cambiar); forma, una de FORMAS (si falta, "pantalla"). */
export function revisarImagenes(imagenes, medios) {
  if (!Array.isArray(imagenes)) return ["imagenes tiene que ser una lista"];
  const mal = [];
  const hay = new Set(Array.isArray(medios) ? medios.map((f) => f?.n) : []);
  const tramos = new Set();
  const fotos = new Set();
  if (imagenes.length > MAXIMO_FOTOS) mal.push(`imagenes: son más de ${MAXIMO_FOTOS}`);
  imagenes.forEach((im, i) => {
    if (!im || typeof im !== "object" || Array.isArray(im)) { mal.push(`imagen ${i}: no es un objeto`); return; }
    if (!esEntero(im.tramo, 0, 200)) mal.push(`imagen ${i}: tramo tiene que ser un número desde 0`);
    else if (tramos.has(im.tramo)) mal.push(`imagen ${i}: el tramo ${im.tramo} ya tiene foto`);
    tramos.add(im.tramo);
    if (!esEntero(im.foto, 1, MAXIMO_FOTOS) || !hay.has(im.foto)) mal.push(`imagen ${i}: la foto ${im.foto} no está en la nota`);
    else if (fotos.has(im.foto)) mal.push(`imagen ${i}: la foto ${im.foto} va dos veces`);
    fotos.add(im.foto);
    if (typeof im.credito !== "string" || im.credito.length > 120) mal.push(`imagen ${i}: credito tiene que ser un texto corto`);
    if (im.forma !== undefined && !FORMAS.includes(im.forma)) mal.push(`imagen ${i}: forma ${im.forma} no está en la lista`);
    const raros = camposRaros(im, CAMPOS_IMAGEN);
    if (raros.length) mal.push(`imagen ${i}: trae campos que no están en el contrato: ${raros.join(", ")}`);
  });
  return mal;
}

/** El pie del video: { mostrar, fuente, ilustrativas }. mostrar en false lo saca de todo el video; fuente es lo que
 *  dice de dónde sale la nota ("Fuente: Infobae") e ilustrativas lo que dice con los clips de banco ("Imágenes
 *  ilustrativas"). Los dos se pueden cambiar en la cajita del pie. */
export function revisarPie(p) {
  if (!p || typeof p !== "object" || Array.isArray(p)) return ["el pie no es un objeto"];
  const mal = [];
  if (typeof p.mostrar !== "boolean") mal.push("pie: mostrar tiene que ser sí o no");
  for (const campo of ["fuente", "ilustrativas"]) {
    if (typeof p[campo] !== "string" || p[campo].length > 120) mal.push(`pie: ${campo} tiene que ser un texto corto`);
  }
  const raros = camposRaros(p, CAMPOS_PIE);
  if (raros.length) mal.push(`pie: trae campos que no están en el contrato: ${raros.join(", ")}`);
  return mal;
}

/**
 * Lo mínimo para leer un trabajo ya guardado y mostrarlo en "Mis videos". revisarTrabajo es para crear: mira cuentas
 * que se estiman (si el guion entra en el largo, las palabras por segundo, la lista de enfoques) y, si alguna cambia,
 * un video que ya salió no puede desaparecer. "Volver a probar" crea un trabajo nuevo, que sí pasa por revisarTrabajo.
 * Un código de error que ya no existe se deja pasar: al leerlo, el Estudio lo entrega como DESCONOCIDO.
 */
export function revisarTrabajoGuardado(t) {
  if (!t || typeof t !== "object") return ["el trabajo no es un objeto"];
  const mal = [];
  if (!esIdTrabajo(t.id)) mal.push("id con forma rara");
  if (typeof t.creado !== "string" || Number.isNaN(Date.parse(t.creado))) mal.push("creado no es una fecha y hora");
  if (!ESTADOS_TRABAJO.includes(t.estado)) mal.push(`estado ${t.estado} no está en la lista`);
  if (!Number.isInteger(t.largo) || t.largo <= 0) mal.push("el largo no es un número de segundos");
  if (!t.nota || typeof t.nota !== "object" || !esTexto(t.nota.titular)) mal.push("falta el titular de la nota");
  if (!t.guion || typeof t.guion !== "object" || !esTexto(t.guion.texto)) mal.push(GUION_VACIO);
  if (t.error !== undefined && (!t.error || typeof t.error !== "object" || typeof t.error.codigo !== "string")) {
    mal.push("el error no tiene código");
  }
  return mal;
}

/**
 * Avance: cómo va el armado. { etapas: [{ id, estado }], porcentaje, restante?, fila?, error? }.
 * restante: segundos que faltan, estimados (entero, 0 cuando terminó).
 * fila: cuántos videos hay antes que éste esperando su turno para armarse (entero de 1 en adelante). Sólo viene
 * mientras espera; si no viene, no está esperando (o la fuente no lo sabe).
 */
export function revisarAvance(a) {
  const mal = [];
  if (!a || typeof a !== "object") return ["el avance no es un objeto"];
  if (!Array.isArray(a.etapas) || a.etapas.length !== ETAPAS.length) return ["etapas incompletas"];
  a.etapas.forEach((e, i) => {
    if (e.id !== ETAPAS[i]) mal.push(`la etapa ${i} tendría que ser ${ETAPAS[i]}`);
    if (!["espera", "haciendo", "listo", "fallo"].includes(e.estado)) mal.push(`estado raro en ${e.id}`);
  });
  if (typeof a.porcentaje !== "number" || a.porcentaje < 0 || a.porcentaje > 100) mal.push("porcentaje fuera de 0 a 100");
  if (a.restante !== undefined && (!Number.isInteger(a.restante) || a.restante < 0)) mal.push("restante tiene que ser un entero de 0 en adelante");
  if (a.fila !== undefined && (!Number.isInteger(a.fila) || a.fila < 1)) mal.push("fila tiene que ser un entero de 1 en adelante");
  if (a.error) mal.push(...revisarError(a.error).map((p) => `error: ${p}`));
  return mal;
}

/** Cuenta las etiquetas como las cuenta YouTube: el largo de todas juntas separadas por comas. */
export const largoEtiquetas = (etiquetas) => (etiquetas || []).join(",").length;

/** El largo de un texto para una red: X cuenta con peso, las demás como JavaScript. */
export const largoPara = (red, texto) => (red === "x" ? largoX(texto) : String(texto ?? "").length);

/**
 * Resultado: lo que queda cuando el video terminó (resultado.json en la carpeta del trabajo).
 * { video, portada, textos: { titulo, descripcion, hashtags: [], etiquetasYoutube: [], redes: { <red>: texto } } }.
 * video y portada son las direcciones para pedirlos (/api/trabajos/<id>/video y .../portada).
 * Se aplican los topes comprobados (TOPES_REDES): el título y la descripción son los de YouTube, y la lista de
 * hashtags se pega en cualquier red, así que va con el tope más chico (el de Instagram).
 */
export function revisarResultado(r) {
  const mal = [];
  if (!r || typeof r !== "object") return ["el resultado no es un objeto"];
  if (!esTexto(r.video)) mal.push("falta el video");
  if (!esTexto(r.portada)) mal.push("falta la portada");
  const t = r.textos || {};
  for (const campo of ["titulo", "descripcion"]) if (!esTexto(t[campo])) mal.push(`falta ${campo}`);
  const yt = TOPES_REDES.youtube;
  if (esTexto(t.titulo) && t.titulo.length > yt.titulo) mal.push(`el título pasa los ${yt.titulo} de YouTube`);
  if (esTexto(t.descripcion) && t.descripcion.length > yt.texto) mal.push(`la descripción pasa los ${yt.texto} de YouTube`);
  if (esTexto(t.descripcion) && contarHashtags(t.descripcion) > yt.hashtags) mal.push("la descripción tiene demasiados hashtags");
  if (!Array.isArray(t.hashtags) || t.hashtags.length === 0 || t.hashtags.some((h) => typeof h !== "string" || !HASHTAG.test(h))) {
    mal.push("hashtags mal formados");
  } else if (t.hashtags.length > TOPES_REDES.instagram.hashtags) {
    mal.push("hay más hashtags de los que acepta Instagram");
  }
  if (!Array.isArray(t.etiquetasYoutube) || t.etiquetasYoutube.length === 0) mal.push("faltan etiquetas de YouTube");
  else if (t.etiquetasYoutube.some((e) => !esTexto(e) || e.includes(","))) mal.push("una etiqueta de YouTube está vacía o tiene una coma");
  else if (largoEtiquetas(t.etiquetasYoutube) > TOPE_ETIQUETAS_YOUTUBE) mal.push("las etiquetas pasan el tope de YouTube");
  for (const red of REDES) {
    const texto = t.redes?.[red];
    if (!esTexto(texto)) { mal.push(`falta el texto para ${red}`); continue; }
    const tope = TOPES_REDES[red] || {};
    if (tope.texto && largoPara(red, texto) > tope.texto) mal.push(`el texto para ${red} pasa los ${tope.texto}`);
    if (tope.hashtags && contarHashtags(texto) > tope.hashtags) mal.push(`el texto para ${red} tiene demasiados hashtags`);
  }
  if (t.redes && typeof t.redes === "object") {
    for (const red of Object.keys(t.redes)) if (!REDES.includes(red)) mal.push(`red desconocida ${red}`);
  }
  return mal;
}

/** Cupo: cuántas voces quedan hoy y cuántos videos van en el mes. */
export function revisarCupo(c) {
  const mal = [];
  if (!c || typeof c !== "object") return ["el cupo no es un objeto"];
  const v = c.voces || {};
  if (v.tope !== TOPE_VOCES_DIA) mal.push("el tope de voces no es el de Google");
  if (v.quedan !== Math.max(0, v.tope - v.usadas)) mal.push("quedan no coincide con tope menos usadas");
  if (!Number.isInteger(c.videosMes) || c.videosMes < 0) mal.push("videosMes tiene que ser un entero");
  return mal;
}
