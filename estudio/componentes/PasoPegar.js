"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Aviso from "./Aviso";
import Pasos from "./Pasos";
import { IconoAviso, IconoCheck } from "./Iconos";
import { LARGOS, LARGO_INICIAL, linkValido, palabrasPara } from "@/lib/contrato";
import { PANTALLAS, guardarBorrador, leerBorrador } from "@/lib/borrador";
import { COMO_SIGUE, CUPO, EJEMPLOS, ERRORES, PEGAR, SALIDAS } from "@/lib/textos";

/** Paso 1: pegar el link (o el texto) de la nota y elegir el largo. */
export default function PasoPegar({ ejemplo, vitrina, cupo, sinVoces, inicial }) {
  const router = useRouter();
  const campoLink = useRef(null);
  const campoTexto = useRef(null);
  const aviso = useRef(null);

  const [link, setLink] = useState("");
  const [texto, setTexto] = useState("");
  const [largo, setLargo] = useState(LARGO_INICIAL);
  // Qué cuadros se ven. Después de un muro de pago se ven los dos: el link sigue escrito.
  const [verLink, setVerLink] = useState(true);
  const [verTexto, setVerTexto] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null); // { codigo, salida }
  const [errorLink, setErrorLink] = useState(null); // texto del error debajo del cuadro
  const [errorTexto, setErrorTexto] = useState(null);
  const [puedePegar, setPuedePegar] = useState(false);
  const [pegarNoSe, setPegarNoSe] = useState(false);
  const [simulando, setSimulando] = useState(false);
  // La casilla de "sin voces" cambia al instante; la pantalla se pone al día cuando contesta el Estudio.
  const [sinVocesMarcado, setSinVocesMarcado] = useState(Boolean(sinVoces));
  const [listo, setListo] = useState(false);
  // Un video a medio hacer (nota leída y una pantalla abierta después): { titular, href }.
  const [aMedio, setAMedio] = useState(null);

  useEffect(() => setSinVocesMarcado(Boolean(sinVoces)), [sinVoces]);

  // Vuelve a poner lo último que se escribió (por ejemplo, al volver desde "No, es otra nota").
  useEffect(() => {
    const { pedido, nota, pantalla } = leerBorrador();
    if (nota?.titular && PANTALLAS[pantalla]) setAMedio({ titular: nota.titular, href: PANTALLAS[pantalla] });
    if (pedido) {
      if (pedido.link) setLink(pedido.link);
      if (pedido.texto) setTexto(pedido.texto);
      if (LARGOS.includes(pedido.largo)) setLargo(pedido.largo);
      if (pedido.texto) {
        setVerTexto(true);
        setVerLink(Boolean(pedido.link));
      }
    }
    // Si alguien apretó "Leer la nota" antes de que la página terminara de cargar, el link llega en la dirección:
    // se vuelve a poner en el cuadro para que no se pierda, y se limpia la dirección.
    if (inicial?.link) {
      setLink(inicial.link);
      if (LARGOS.includes(inicial.largo)) setLargo(inicial.largo);
      window.history.replaceState(null, "", "/");
    }
    setListo(true);
    // El botón Pegar sólo anda en una página segura (en el wifi de la casa no lo es): si no anda, no se muestra.
    setPuedePegar(Boolean(window.isSecureContext && navigator.clipboard?.readText));
  }, []);

  useEffect(() => {
    if (error && error.salida !== "pegar-texto" && error.codigo !== "NOTA_MUY_CORTA") aviso.current?.focus();
  }, [error]);

  function abrirTexto({ conLink }) {
    setVerTexto(true);
    setVerLink(conLink);
    setErrorLink(null);
    requestAnimationFrame(() => campoTexto.current?.focus());
  }

  function abrirLink() {
    setVerTexto(false);
    setVerLink(true);
    setErrorTexto(null);
    setError(null);
    requestAnimationFrame(() => campoLink.current?.focus());
  }

  async function pegar() {
    try {
      const pegado = (await navigator.clipboard.readText()).trim();
      if (pegado) {
        setLink(pegado);
        setErrorLink(null);
      }
    } catch {
      setPegarNoSe(true);
    }
    campoLink.current?.focus();
  }

  function usarEjemplo(linkEjemplo) {
    setLink(linkEjemplo);
    setTexto("");
    setError(null);
    setErrorLink(null);
    setErrorTexto(null);
    setVerTexto(false);
    setVerLink(true);
    campoLink.current?.focus();
  }

  async function simularSinVoces(prender) {
    setSinVocesMarcado(prender);
    setSimulando(true);
    try {
      await fetch("/api/simular", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sinVoces: prender }),
      });
      router.refresh();
    } finally {
      setSimulando(false);
    }
  }

  async function leer(evento) {
    evento?.preventDefault();
    setError(null);
    const linkLimpio = link.trim();
    const textoLimpio = texto.trim();

    if (verTexto && !textoLimpio) {
      setErrorTexto(PEGAR.faltaTexto);
      campoTexto.current?.focus();
      return;
    }
    if (!verTexto) {
      if (!linkLimpio) {
        setErrorLink(PEGAR.faltaLink);
        campoLink.current?.focus();
        return;
      }
      if (!linkValido(linkLimpio)) {
        setErrorLink(`${ERRORES.LINK_INVALIDO.titulo}. ${ERRORES.LINK_INVALIDO.texto}`);
        campoLink.current?.focus();
        return;
      }
    }

    const pedido = { largo };
    if (verTexto) pedido.texto = textoLimpio;
    if (verLink && linkValido(linkLimpio)) pedido.link = linkLimpio;

    setEnviando(true);
    let respuesta;
    try {
      const r = await fetch("/api/nota", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pedido),
      });
      respuesta = await r.json();
    } catch {
      respuesta = { error: { codigo: "SIN_CONEXION", salida: "reintentar" } };
    }

    if (respuesta.nota) {
      guardarBorrador({ pedido, nota: respuesta.nota });
      // Desde el 2026-11-18 se va directo a los guiones: ya no hay pantalla de "¿Es esta la nota?".
      router.push("/guion");
      return; // queda "Leyendo" hasta que cambia la pantalla
    }

    setEnviando(false);
    const e = respuesta.error || { codigo: "DESCONOCIDO", salida: "reintentar" };
    if (e.codigo === "LINK_INVALIDO") {
      setErrorLink(`${ERRORES.LINK_INVALIDO.titulo}. ${ERRORES.LINK_INVALIDO.texto}`);
      campoLink.current?.focus();
      return;
    }
    setError(e);
    if (e.salida === "pegar-texto") abrirTexto({ conLink: true });
    if (e.codigo === "NOTA_MUY_CORTA") requestAnimationFrame(() => campoTexto.current?.focus());
  }

  const sinVocesHoy = cupo && cupo.voces.quedan === 0;
  const textoError = error ? ERRORES[error.codigo] || ERRORES.DESCONOCIDO : null;

  return (
    <main className="contenido">
      <Pasos actual={1} />

      {aMedio ? (
        <div className="a-medio">
          <Aviso
            tipo="info"
            titulo={PEGAR.aMedio}
            acciones={
              <Link className="boton boton-secundario boton-chico" href={aMedio.href}>
                {PEGAR.seguir}
              </Link>
            }
          >
            <p>{aMedio.titular}</p>
          </Aviso>
        </div>
      ) : null}

      <div className="dos-columnas">
        <div className="columna">
          <header className="encabezado">
            <h1 className="titulo">{PEGAR.titulo}</h1>
            <p className="bajada">{PEGAR.bajada}</p>
          </header>

          {sinVocesHoy ? (
            <Aviso tipo="info" titulo={ERRORES.SIN_VOCES_HOY.titulo}>
              <p>{ERRORES.SIN_VOCES_HOY.texto}</p>
            </Aviso>
          ) : null}

          {textoError ? (
            <div ref={aviso} tabIndex={-1} className="aviso-envoltura">
              <Aviso
                titulo={textoError.titulo}
                acciones={
                  error.salida === "reintentar" ? (
                    <button type="button" className="boton boton-secundario boton-chico" onClick={leer}>
                      {SALIDAS.reintentar}
                    </button>
                  ) : null
                }
              >
                <p>{textoError.texto}</p>
              </Aviso>
            </div>
          ) : null}

          <form className="formulario" onSubmit={leer} noValidate data-listo={listo ? "si" : undefined}>
            {verLink ? (
              <div className="grupo">
                <label className="rotulo" htmlFor="link">
                  {PEGAR.etiquetaLink}
                </label>
                <div className="campo-fila">
                  <input
                    ref={campoLink}
                    id="link"
                    name="link"
                    className="campo"
                    type="url"
                    inputMode="url"
                    autoComplete="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    placeholder={PEGAR.ejemploLink}
                    value={link}
                    disabled={enviando}
                    aria-invalid={errorLink ? "true" : undefined}
                    aria-describedby={errorLink ? "link-error" : undefined}
                    onChange={(e) => {
                      setLink(e.target.value);
                      setErrorLink(null);
                    }}
                  />
                  {puedePegar ? (
                    <button type="button" className="boton boton-secundario" onClick={pegar} disabled={enviando}>
                      {PEGAR.botonPegar}
                    </button>
                  ) : null}
                </div>
                {errorLink ? (
                  <p className="error-campo" id="link-error">
                    <IconoAviso tam={16} />
                    <span>{errorLink}</span>
                  </p>
                ) : null}
                {pegarNoSe ? <p className="ayuda">{PEGAR.pegarNoSe}</p> : null}
                {!verTexto ? (
                  <button type="button" className="enlace" onClick={() => abrirTexto({ conLink: false })}>
                    {PEGAR.aTexto}
                  </button>
                ) : null}
              </div>
            ) : null}

            {verTexto ? (
              <div className="grupo">
                <label className="rotulo" htmlFor="texto">
                  {PEGAR.etiquetaTexto}
                </label>
                <p className="ayuda" id="texto-ayuda">
                  {PEGAR.ayudaTexto}
                </p>
                <textarea
                  ref={campoTexto}
                  id="texto"
                  name="texto"
                  className="area"
                  value={texto}
                  disabled={enviando}
                  aria-invalid={errorTexto ? "true" : undefined}
                  aria-describedby={errorTexto ? "texto-ayuda texto-error" : "texto-ayuda"}
                  onChange={(e) => {
                    setTexto(e.target.value);
                    setErrorTexto(null);
                  }}
                />
                {errorTexto ? (
                  <p className="error-campo" id="texto-error">
                    <IconoAviso tam={16} />
                    <span>{errorTexto}</span>
                  </p>
                ) : null}
                <button type="button" className="enlace" onClick={abrirLink}>
                  {PEGAR.aLink}
                </button>
              </div>
            ) : null}

            <fieldset className="grupo">
              <legend className="rotulo">{PEGAR.largoTitulo}</legend>
              <div className="largos">
                {LARGOS.map((s) => (
                  <label key={s} className="largo">
                    <input
                      type="radio"
                      name="largo"
                      value={s}
                      checked={largo === s}
                      disabled={enviando}
                      onChange={() => setLargo(s)}
                    />
                    <span className="largo-segundos" aria-hidden="true">
                      {s}
                      <small>s</small>
                    </span>
                    <span className="solo-lectores">{PEGAR.segundos(s)}</span>
                    <span className="largo-nombre">{PEGAR.largos[s].nombre}</span>
                    <span className="largo-para">{PEGAR.largos[s].para}</span>
                    <span className="largo-palabras">{PEGAR.palabras(palabrasPara(s))}</span>
                    <span className="largo-check" aria-hidden="true">
                      <IconoCheck />
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <p className="nota-chica">{PEGAR.nadaSeGasta}</p>
            <div className="barra-acciones">
              <button type="submit" className="boton boton-principal" disabled={enviando} aria-busy={enviando}>
                {enviando ? PEGAR.leyendo : PEGAR.boton}
              </button>
            </div>
          </form>
        </div>

        <aside className="lateral">
          <section className="recuadro" aria-labelledby="como-sigue">
            <h2 className="recuadro-titulo" id="como-sigue">
              {COMO_SIGUE.titulo}
            </h2>
            <ol className="como-sigue">
              {COMO_SIGUE.pasos.map((p) => (
                <li key={p.nombre}>
                  <strong>{p.nombre}</strong>
                  <span>{p.texto}</span>
                </li>
              ))}
            </ol>
            <p className="sin-ia">{COMO_SIGUE.nuncaIA}</p>
            {cupo ? (
              <p className="nota-chica">
                {CUPO.voces(cupo.voces.quedan, cupo.voces.tope)}
              </p>
            ) : null}
          </section>

          {ejemplo && vitrina ? (
            <details className="recuadro ejemplos">
              <summary>{EJEMPLOS.titulo}</summary>
              <div className="ejemplos-cuerpo">
                <p className="nota-chica">{EJEMPLOS.bajada}</p>
                <div className="ejemplos-grupo">
                  <h3>{EJEMPLOS.notas}</h3>
                  {vitrina.notas.map((n) => (
                    <button key={n.link} type="button" className="ejemplo-boton" onClick={() => usarEjemplo(n.link)}>
                      {n.titular}
                      {n.sensible ? <span className="ejemplo-sensible">{EJEMPLOS.sensible}</span> : null}
                    </button>
                  ))}
                </div>
                <div className="ejemplos-grupo">
                  <h3>{EJEMPLOS.errores}</h3>
                  {vitrina.fallas.map((f) => (
                    <button key={f.link} type="button" className="ejemplo-boton" onClick={() => usarEjemplo(f.link)}>
                      {EJEMPLOS.fallas[f.clave] || f.clave}
                    </button>
                  ))}
                </div>
                <p className="nota-chica">{EJEMPLOS.cualquierLink}</p>
                <label className="interruptor">
                  <input
                    type="checkbox"
                    checked={sinVocesMarcado}
                    aria-busy={simulando || undefined}
                    onChange={(e) => simularSinVoces(e.target.checked)}
                  />
                  {EJEMPLOS.sinVoces}
                </label>
              </div>
            </details>
          ) : null}
        </aside>
      </div>
    </main>
  );
}
