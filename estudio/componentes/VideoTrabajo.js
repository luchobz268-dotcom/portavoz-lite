"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Aviso from "./Aviso";
import EstadoTrabajo from "./EstadoTrabajo";
import Pasos from "./Pasos";
import { IconoAviso, IconoBajar, IconoCheck, IconoCopiar, IconoEspera, IconoInfo, IconoOtro, IconoReloj } from "./Iconos";
import {
  ENFOQUES,
  ERRORES as SALIDA_DE,
  REDES as LISTA_REDES,
  TOPES_REDES,
  TOPE_ETIQUETAS_YOUTUBE,
  contarPalabras,
  esCodigoError,
  largoEtiquetas,
  largoX,
} from "@/lib/contrato";
import { guardarBorrador } from "@/lib/borrador";
import { ERRORES, ETAPAS, MARCA, MIS_VIDEOS, REDES, SALIDAS, VIDEO } from "@/lib/textos";

// Paso 3, "El video": cómo va el armado (se pregunta cada segundo mientras se arma), el video terminado con sus
// textos para cada red, o por qué no salió y qué hacer. Los datos llegan de /api/trabajos/<id> (docs/contrato.md).

const CADA = 1000;
const ICONO_ETAPA = { espera: IconoEspera, haciendo: IconoReloj, listo: IconoCheck, fallo: IconoAviso };

/** El código y la salida de un error: la salida la dice el contrato según el código. */
function errorDe(e) {
  const codigo = esCodigoError(e?.codigo) ? e.codigo : "DESCONOCIDO";
  return { codigo, salida: SALIDA_DE[codigo].salida };
}

/** Lo que muestra cada pestaña: uno o más textos, cada uno con su "Copiar" y su "Pedir otro". */
function itemsDe(red, textos) {
  const t = textos || {};
  const redes = t.redes || {};
  if (red === "instagram") {
    return [
      { clave: "texto", rotulo: VIDEO.campos.texto, texto: redes.instagram, campo: "redes", red },
      { clave: "hashtags", rotulo: VIDEO.campos.hashtags, texto: (t.hashtags || []).join(" "), campo: "hashtags" },
    ];
  }
  if (red === "youtube") {
    return [
      { clave: "titulo", rotulo: VIDEO.campos.titulo, texto: t.titulo, campo: "titulo" },
      { clave: "descripcion", rotulo: VIDEO.campos.descripcion, texto: t.descripcion, campo: "descripcion" },
      {
        clave: "etiquetas",
        rotulo: VIDEO.campos.etiquetas,
        texto: (t.etiquetasYoutube || []).join(", "),
        campo: "etiquetasYoutube",
        cuenta: { n: largoEtiquetas(t.etiquetasYoutube), tope: TOPE_ETIQUETAS_YOUTUBE },
      },
    ];
  }
  const item = { clave: "texto", rotulo: VIDEO.campos.texto, texto: redes[red], campo: "redes", red };
  if (red === "x") item.cuenta = { n: largoX(redes.x), tope: TOPES_REDES.x.texto };
  return [item];
}

/** Del resultado nuevo se toma sólo el texto que se pidió: si llegan dos respuestas cruzadas, ninguna pisa a la otra. */
function mezclar(actual, nuevo, item) {
  const a = actual.textos;
  const n = nuevo.textos;
  const textos = item.campo === "redes" ? { ...a, redes: { ...a.redes, [item.red]: n.redes[item.red] } } : { ...a, [item.campo]: n[item.campo] };
  return { ...actual, textos };
}

/**
 * Copia en tres escalones: el portapapeles del navegador (sólo en una conexión segura), el modo viejo con un cuadro
 * escondido, y si nada anda deja el texto seleccionado para copiarlo a mano. Devuelve "ok" o "a-mano".
 */
async function copiarTexto(texto, nodo) {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(texto);
      return "ok";
    } catch {
      // Sigue con el modo viejo.
    }
  }
  const antes = document.activeElement;
  try {
    const area = document.createElement("textarea");
    area.value = texto;
    area.setAttribute("readonly", "");
    area.setAttribute("aria-hidden", "true");
    area.style.cssText = "position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none";
    document.body.appendChild(area);
    area.focus();
    area.select();
    area.setSelectionRange(0, area.value.length);
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } finally {
      area.remove();
      antes?.focus?.();
    }
    if (ok) return "ok";
  } catch {
    // Sigue con el último escalón.
  }
  try {
    const rango = document.createRange();
    rango.selectNodeContents(nodo);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(rango);
  } catch {
    // Sin selección: igual queda el texto a la vista.
  }
  return "a-mano";
}

/** Los tres guiones que acepta el Paso 2 para un trabajo viejo que no los guardó: el elegido intacto, los otros vacíos. */
function guionesMinimos(t) {
  const enfoque = ENFOQUES.includes(t.guion?.enfoque) ? t.guion.enfoque : ENFOQUES[0];
  const texto = String(t.guion?.texto ?? "");
  const lista = ENFOQUES.map((e) => ({
    id: `${t.nota.id}-${e}`,
    enfoque: e,
    versiones: [e === enfoque ? { texto, palabras: contarPalabras(texto), origen: "propuesta" } : { texto: "", palabras: 0, origen: "a-mano" }],
    actual: 0,
  }));
  return { notaId: t.nota.id, lista, elegido: `${t.nota.id}-${enfoque}` };
}

function Etapas({ avance }) {
  if (!avance?.etapas) return null;
  return (
    <ol className="video-etapas">
      {avance.etapas.map((e) => {
        const Icono = ICONO_ETAPA[e.estado] || IconoEspera;
        return (
          <li key={e.id} className="video-etapa" data-estado={e.estado}>
            <span className="video-etapa-icono">
              <Icono tam={16} />
            </span>
            <span className="video-etapa-nombre">{ETAPAS[e.id] || e.id}</span>
            <span className="video-etapa-estado">{VIDEO.estadosEtapa[e.estado] || ""}</span>
          </li>
        );
      })}
    </ol>
  );
}

export default function VideoTrabajo({ inicial }) {
  const router = useRouter();
  const [trabajo, setTrabajo] = useState(inicial.trabajo);
  const [avance, setAvance] = useState(inicial.avance);
  const [resultado, setResultado] = useState(inicial.resultado);
  const [sinConexion, setSinConexion] = useState(false);
  const [anuncio, setAnuncio] = useState("");
  const [red, setRed] = useState(LISTA_REDES[0]);
  const [copiado, setCopiado] = useState(null); // clave del texto recién copiado
  const [aMano, setAMano] = useState(null); // clave del texto que hay que copiar a mano
  const [pidiendo, setPidiendo] = useState({}); // { clave: true } mientras se pide otro
  const [falloOtro, setFalloOtro] = useState(null);
  const [reintentando, setReintentando] = useState(false);
  const [errorAccion, setErrorAccion] = useState(null);
  const titulo = useRef(null);
  const aviso = useRef(null);
  const pestanas = useRef([]);
  const cuerpos = useRef({});
  const pidiendoYa = useRef(new Set());
  const reintentandoYa = useRef(false);
  const montado = useRef(false);
  const relojCopiado = useRef(null);
  const relojAnuncio = useRef(null);

  const id = trabajo.id;
  const estado = trabajo.estado;
  // Listo pero sin resultado (justo entre dos lecturas): se sigue preguntando hasta que llegue.
  const vista = estado === "listo" && resultado ? "listo" : estado === "fallo" ? "fallo" : "armando";
  const vistaAntes = useRef(vista);

  useEffect(() => {
    montado.current = true;
    return () => {
      montado.current = false;
      clearTimeout(relojCopiado.current);
      clearTimeout(relojAnuncio.current);
    };
  }, []);

  // Los avisos para quien usa un lector de pantalla van a la zona que está siempre (un aviso que aparece ya escrito
  // no siempre se lee). Se vacía y se escribe un instante después, para que el mismo aviso dos veces se lea dos veces.
  function anunciar(texto) {
    clearTimeout(relojAnuncio.current);
    setAnuncio("");
    relojAnuncio.current = setTimeout(() => {
      if (montado.current) setAnuncio(texto);
    }, 100);
  }

  // Mientras se arma, se pregunta cada segundo. Si se corta la conexión se sigue probando y queda lo último que llegó.
  useEffect(() => {
    if (vista !== "armando") return undefined;
    let vivo = true;
    let reloj;
    async function preguntar() {
      try {
        const r = await fetch(`/api/trabajos/${id}`, { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        const j = await r.json();
        if (!vivo) return;
        if (j.trabajo?.id === id) {
          setTrabajo(j.trabajo);
          if (j.avance) setAvance(j.avance);
          if (j.resultado) setResultado(j.resultado);
        }
        setSinConexion(false);
      } catch {
        if (vivo) setSinConexion(true);
      }
      if (vivo) reloj = setTimeout(preguntar, CADA);
    }
    reloj = setTimeout(preguntar, CADA);
    return () => {
      vivo = false;
      clearTimeout(reloj);
    };
  }, [vista, id]);

  // El título de la pestaña dice cómo va. Al terminar se avisa una sola vez (no cada segundo) y el foco va al título.
  useEffect(() => {
    const nombre = vista === "listo" ? VIDEO.listo : vista === "fallo" ? VIDEO.fallo : VIDEO.armando;
    document.title = `${nombre} | ${MARCA.titulo}`;
    const venia = vistaAntes.current;
    vistaAntes.current = vista;
    if (venia !== "armando" || vista === "armando") return;
    if (vista === "listo") {
      setAnuncio(VIDEO.anuncioListo);
      titulo.current?.focus();
    } else {
      anunciar(VIDEO.anuncioFallo);
      aviso.current?.focus();
    }
  }, [vista]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (sinConexion) anunciar(VIDEO.sinConexion);
  }, [sinConexion]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (errorAccion) aviso.current?.focus();
  }, [errorAccion]);

  async function copiar(item, clave) {
    const como = await copiarTexto(String(item.texto ?? ""), cuerpos.current[clave]);
    if (!montado.current) return;
    clearTimeout(relojCopiado.current);
    if (como === "ok") {
      setAMano(null);
      setCopiado(clave);
      relojCopiado.current = setTimeout(() => setCopiado(null), 2500);
    } else {
      setCopiado(null);
      setAMano(clave);
      anunciar(VIDEO.copiarAMano);
    }
  }

  async function pedirOtro(item, clave, deRed) {
    if (pidiendoYa.current.has(clave)) return;
    pidiendoYa.current.add(clave);
    setPidiendo((p) => ({ ...p, [clave]: true }));
    setFalloOtro((f) => (f === clave ? null : f));
    let j = null;
    try {
      const r = await fetch(`/api/trabajos/${id}/otro`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ campo: item.campo, ...(item.red ? { red: item.red } : {}) }),
      });
      j = await r.json();
    } catch {
      j = null;
    }
    pidiendoYa.current.delete(clave);
    if (!montado.current) return;
    setPidiendo((p) => ({ ...p, [clave]: false }));
    if (j?.resultado?.textos) {
      setResultado((actual) => mezclar(actual, j.resultado, item));
      const nuevo = itemsDe(deRed, j.resultado.textos).find((x) => `${deRed}-${x.clave}` === clave) || item;
      setAMano((a) => (a === clave ? null : a));
      setCopiado((c) => (c === clave ? null : c));
      setAnuncio(VIDEO.llegoOtro(String(nuevo.texto ?? "")));
    } else {
      setFalloOtro(clave);
      anunciar(VIDEO.noLlegoOtro);
    }
  }

  function volverAlGuion() {
    const t = trabajo;
    const g = t.guiones;
    const guardados = g && g.notaId === t.nota?.id && Array.isArray(g.lista) && g.lista.length === ENFOQUES.length;
    const pedido = t.pedido && typeof t.pedido === "object" ? { ...t.pedido, largo: t.largo } : { largo: t.largo };
    guardarBorrador({ pedido, nota: t.nota, guiones: guardados ? g : guionesMinimos(t), pantalla: "guion" });
    router.push("/guion");
  }

  async function probarDeNuevo() {
    if (reintentandoYa.current) return;
    reintentandoYa.current = true;
    setReintentando(true);
    setErrorAccion(null);
    let j;
    try {
      const r = await fetch(`/api/trabajos/${id}/reintentar`, { method: "POST" });
      j = await r.json();
    } catch {
      j = { error: { codigo: "SIN_CONEXION" } };
    }
    if (j?.trabajo?.id) {
      router.push(`/video/${j.trabajo.id}`);
      return; // queda "Probando de nuevo" hasta que cambia la pantalla
    }
    reintentandoYa.current = false;
    if (!montado.current) return;
    setReintentando(false);
    setErrorAccion(errorDe(j?.error));
  }

  function teclaRed(e, i) {
    const n = LISTA_REDES.length;
    const destino = { ArrowRight: (i + 1) % n, ArrowLeft: (i - 1 + n) % n, Home: 0, End: n - 1 }[e.key];
    if (destino === undefined) return;
    e.preventDefault();
    setRed(LISTA_REDES[destino]);
    pestanas.current[destino]?.focus();
  }

  const nota = trabajo.nota || {};
  const tituloPantalla = vista === "listo" ? VIDEO.listo : vista === "fallo" ? VIDEO.fallo : VIDEO.armando;
  const bajada = vista === "listo" ? VIDEO.bajada : vista === "armando" ? VIDEO.puedesCerrar : null;

  function salidaDe(error) {
    const { salida } = error;
    if (salida === "volver-al-guion") {
      return (
        <button type="button" className="boton boton-principal boton-chico" onClick={volverAlGuion}>
          {SALIDAS["volver-al-guion"]}
        </button>
      );
    }
    if (salida === "reintentar") {
      return (
        <button
          type="button"
          className="boton boton-principal boton-chico"
          aria-busy={reintentando ? "true" : "false"}
          aria-disabled={reintentando ? "true" : undefined}
          onClick={probarDeNuevo}
        >
          {reintentando ? VIDEO.probando : SALIDAS.reintentar}
        </button>
      );
    }
    if (salida === "manana") {
      return (
        <Link className="boton boton-principal boton-chico" href="/mis-videos">
          {SALIDAS.manana}
        </Link>
      );
    }
    return (
      <Link className="boton boton-principal boton-chico" href="/">
        {SALIDAS[salida] || SALIDAS.corregir}
      </Link>
    );
  }

  const falla = vista === "fallo" ? errorAccion || errorDe(trabajo.error) : null;
  const textoFalla = falla ? ERRORES[falla.codigo] || ERRORES.DESCONOCIDO : null;

  return (
    <main className="contenido video" data-listo="si" data-trabajo={id} data-estado={vista}>
      <Pasos actual={3} />
      <header className="encabezado">
        <h1 className="titulo" id="video-titulo" tabIndex={-1} ref={titulo}>
          {tituloPantalla}
        </h1>
        {bajada ? <p className="bajada">{bajada}</p> : null}
      </header>
      <p className="solo-lectores" aria-live="polite">
        {anuncio}
      </p>

      {vista === "fallo" ? (
        <div ref={aviso} tabIndex={-1} className="video-falla">
          <Aviso titulo={textoFalla.titulo} acciones={salidaDe(falla)}>
            <p>{textoFalla.texto}</p>
          </Aviso>
        </div>
      ) : null}

      {vista !== "listo" ? (
        <article className="video-armando" aria-labelledby="video-titular">
          <EstadoTrabajo estado={vista} />
          <h2 className="video-titular" id="video-titular">
            {nota.titular}
          </h2>
          <p className="nota-chica">{MIS_VIDEOS.largo(trabajo.largo)}</p>
          {vista === "armando" ? (
            <div className="video-avance">
              <div className="video-avance-datos">
                <p className="video-avance-rotulo" id="video-avance">
                  {VIDEO.avance}
                </p>
                {Number.isInteger(avance?.restante) ? <p className="video-falta">{VIDEO.faltan(avance.restante)}</p> : null}
              </div>
              <div
                className="video-barra"
                role="progressbar"
                aria-labelledby="video-avance"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.round(avance?.porcentaje ?? 0)}
              >
                <span className="video-barra-lleno" style={{ width: `${Math.round(avance?.porcentaje ?? 0)}%` }} />
              </div>
              {avance?.fila > 0 ? (
                <p className="video-fila">
                  <IconoInfo tam={18} />
                  <span>{VIDEO.fila(avance.fila)}</span>
                </p>
              ) : null}
            </div>
          ) : null}
          <Etapas avance={avance} />
          {vista === "armando" && sinConexion ? (
            <p className="video-sin-conexion">
              <IconoAviso tam={18} />
              <span>{VIDEO.sinConexion}</span>
            </p>
          ) : null}
        </article>
      ) : (
        <div className="video-listo">
          <section className="video-ver" aria-labelledby="video-titular">
            <video
              className="video-reproductor"
              src={resultado.video}
              poster={resultado.portada}
              controls
              playsInline
              preload="metadata"
              aria-label={VIDEO.reproductor(nota.titular)}
            />
            <EstadoTrabajo estado="listo" />
            <h2 className="video-titular" id="video-titular">
              {nota.titular}
            </h2>
            <p className="nota-chica">{MIS_VIDEOS.largo(trabajo.largo)}</p>
            <a className="boton boton-principal video-bajar" href={`${resultado.video}?bajar=1`} download>
              <IconoBajar />
              <span>{VIDEO.bajar}</span>
            </a>
          </section>

          <section className="video-textos" aria-labelledby="textos-titulo">
            <h2 className="video-textos-titulo" id="textos-titulo">
              {VIDEO.textos}
            </h2>
            <p className="nota-chica">{VIDEO.textosBajada}</p>
            <div className="video-redes" role="tablist" aria-label={VIDEO.redes}>
              {LISTA_REDES.map((r, i) => {
                const sel = r === red;
                return (
                  <button
                    key={r}
                    type="button"
                    role="tab"
                    id={`red-${r}`}
                    className="guion-pestana video-red"
                    aria-selected={sel}
                    aria-controls={`panel-${r}`}
                    tabIndex={sel ? 0 : -1}
                    ref={(el) => {
                      pestanas.current[i] = el;
                    }}
                    onClick={() => setRed(r)}
                    onKeyDown={(e) => teclaRed(e, i)}
                  >
                    {REDES[r]}
                  </button>
                );
              })}
            </div>
            {LISTA_REDES.map((r) => (
              <div key={r} className="video-panel" role="tabpanel" id={`panel-${r}`} aria-labelledby={`red-${r}`} hidden={r !== red}>
                {itemsDe(r, resultado.textos).map((item) => {
                  const clave = `${r}-${item.clave}`;
                  const rotulo = `rotulo-${clave}`;
                  const ocupado = Boolean(pidiendo[clave]);
                  return (
                    <div key={clave} className="texto-item" data-campo={item.clave}>
                      <div className="texto-cabeza">
                        <h3 className="texto-rotulo" id={rotulo}>
                          {item.rotulo}
                        </h3>
                        {item.cuenta ? (
                          <p className="texto-contador" data-pasa={item.cuenta.n > item.cuenta.tope ? "si" : undefined}>
                            {VIDEO.contador(item.cuenta.n, item.cuenta.tope)}
                          </p>
                        ) : null}
                      </div>
                      <p
                        className="texto-cuerpo"
                        ref={(el) => {
                          cuerpos.current[clave] = el;
                        }}
                      >
                        {item.texto}
                      </p>
                      <div className="texto-botones">
                        <button
                          type="button"
                          className="boton boton-secundario boton-chico"
                          aria-describedby={rotulo}
                          onClick={() => copiar(item, clave)}
                        >
                          <IconoCopiar />
                          <span>{VIDEO.copiar}</span>
                        </button>
                        <button
                          type="button"
                          className="boton boton-secundario boton-chico"
                          aria-describedby={rotulo}
                          aria-busy={ocupado ? "true" : "false"}
                          aria-disabled={ocupado ? "true" : undefined}
                          onClick={() => pedirOtro(item, clave, r)}
                        >
                          <IconoOtro />
                          <span>{VIDEO.pedirOtro}</span>
                        </button>
                        <p className="guion-guardado" aria-live="polite">
                          {copiado === clave ? (
                            <>
                              <IconoCheck />
                              <span>{VIDEO.copiado}</span>
                            </>
                          ) : null}
                        </p>
                      </div>
                      {aMano === clave ? (
                        <p className="texto-a-mano">
                          <IconoInfo tam={18} />
                          <span>{VIDEO.copiarAMano}</span>
                        </p>
                      ) : null}
                      {falloOtro === clave ? (
                        <p className="error-campo">
                          <IconoAviso tam={16} />
                          <span>{VIDEO.noLlegoOtro}</span>
                        </p>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ))}
          </section>
        </div>
      )}

      <div className="acciones">
        <Link className={`boton ${vista === "armando" ? "boton-principal" : "boton-secundario"}`} href="/mis-videos">
          {VIDEO.irAMisVideos}
        </Link>
        <Link className="boton boton-secundario" href="/">
          {VIDEO.otro}
        </Link>
      </div>
    </main>
  );
}
