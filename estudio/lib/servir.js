// Manda un archivo del disco (el video o la portada de un trabajo) por partes, como lo piden los navegadores para
// poder adelantar un video: con "Range" responde 206 y sólo ese pedazo; sin "Range", 200 y el archivo entero.
// La ruta la arma siempre la fuente (lib/fuente) a partir de un id comprobado, nunca con lo que manda la pantalla.
import { createReadStream } from "node:fs";
import { Readable } from "node:stream";

/** Lee "bytes=a-b", "bytes=a-" o "bytes=-n". Devuelve { inicio, fin }, null si no hay pedido o "fuera" si no entra. */
export function leerRango(cabecera, tamano) {
  if (!cabecera) return null;
  const m = /^bytes=(\d*)-(\d*)$/.exec(String(cabecera).trim());
  if (!m || (m[1] === "" && m[2] === "")) return "fuera";
  let inicio;
  let fin;
  if (m[1] === "") {
    const ultimos = Number(m[2]);
    if (ultimos === 0) return "fuera";
    inicio = Math.max(0, tamano - ultimos);
    fin = tamano - 1;
  } else {
    inicio = Number(m[1]);
    fin = m[2] === "" ? tamano - 1 : Math.min(Number(m[2]), tamano - 1);
  }
  if (!Number.isSafeInteger(inicio) || !Number.isSafeInteger(fin) || inicio >= tamano || inicio > fin) return "fuera";
  return { inicio, fin };
}

const dos = (n) => String(n).padStart(2, "0");

const LETRAS = new Intl.Segmenter("es", { granularity: "grapheme" });
/** Las primeras `n` letras enteras: nunca media letra (una letra de adorno o un emoji ocupan dos lugares). */
const primeras = (texto, n) => Array.from(LETRAS.segment(texto), (l) => l.segment).slice(0, n).join("");

/** El nombre del archivo al bajarlo: el titular corto en letras simples, guiones y la fecha. */
export function nombreDescarga(trabajo, extension = "mp4") {
  const d = new Date(trabajo.creado);
  const fecha = Number.isNaN(d.getTime()) ? "" : `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
  // Con las tildes pegadas a su letra (un texto copiado puede traerlas separadas) y sin medias letras sueltas.
  const titular = String(trabajo.nota?.titular ?? "").toWellFormed().normalize("NFC").toLocaleLowerCase("es");
  const corto = (texto, permitidas) =>
    primeras(texto.replace(permitidas, "-").replace(/-+/g, "-").replace(/^-|-$/g, ""), 50).replace(/-$/, "");
  // En letras simples: NFKD pasa las letras de adorno a las comunes y separa las tildes, que se sacan.
  const ascii = corto(titular.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase(), /[^a-z0-9]+/g) || "video";
  const conTildes = corto(titular, /[^\p{L}\p{M}\p{N}]+/gu) || ascii;
  const juntar = (base) => `${[base, fecha].filter(Boolean).join("-")}.${extension}`;
  return { ascii: juntar(ascii), utf8: juntar(conTildes) };
}

/**
 * La respuesta con el archivo. archivo: { ruta, tamano, tipo }. Con `descarga` ({ ascii, utf8 }), el navegador lo
 * baja con ese nombre en vez de mostrarlo.
 */
export function servirArchivo(request, archivo, descarga = null) {
  const { ruta, tamano, tipo } = archivo;
  const cabeceras = { "Content-Type": tipo, "Accept-Ranges": "bytes", "Cache-Control": "private, no-cache" };
  if (descarga) {
    cabeceras["Content-Disposition"] =
      `attachment; filename="${descarga.ascii}"; filename*=UTF-8''${encodeURIComponent(descarga.utf8)}`;
  }
  const rango = leerRango(request.headers.get("range"), tamano);
  if (rango === "fuera") {
    return new Response(null, { status: 416, headers: { ...cabeceras, "Content-Range": `bytes */${tamano}` } });
  }
  const { inicio, fin } = rango || { inicio: 0, fin: tamano - 1 };
  const cuerpo = tamano === 0 ? null : Readable.toWeb(createReadStream(/*turbopackIgnore: true*/ ruta, { start: inicio, end: fin }));
  return new Response(cuerpo, {
    status: rango ? 206 : 200,
    headers: {
      ...cabeceras,
      "Content-Length": String(tamano === 0 ? 0 : fin - inicio + 1),
      ...(rango ? { "Content-Range": `bytes ${inicio}-${fin}/${tamano}` } : {}),
    },
  });
}
