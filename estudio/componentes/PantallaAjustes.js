"use client";

import { useState } from "react";
import Aviso from "./Aviso";
import { IconoCheck } from "./Iconos";
import { AJUSTES } from "@/lib/textos";

// Ajustes: quién escribe los guiones y las llaves. Los cambios van a /api/ajustes (que sólo los acepta desde esta
// misma compu). De cada llave la pantalla sólo conoce sus últimos 4 caracteres.

const QUIENES = ["", "claude", "anthropic", "google"];
const LLAVES = ["google", "pexels", "anthropic"];

const MENSAJE = {
  guardada: AJUSTES.guardada,
  mala: AJUSTES.mala,
  "sin-internet": AJUSTES.sinInternet,
  vacia: AJUSTES.vacia,
};

async function mandar(cuerpo) {
  try {
    const r = await fetch("/api/ajustes", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    const datos = await r.json().catch(() => ({}));
    return datos.resultado || datos.error || "falla";
  } catch {
    return "sin-internet";
  }
}

async function releer() {
  try {
    const r = await fetch("/api/ajustes", { cache: "no-store" });
    return (await r.json()).ajustes || null;
  } catch {
    return null;
  }
}

/** Una llave: cómo está (sólo su final) y, al tocar "Cambiar", el cuadro para pegar la nueva. */
function Llave({ nombre, fin, prestadas, soloMirar, alGuardar }) {
  const t = AJUSTES.llaves[nombre];
  const [abierta, setAbierta] = useState(false);
  const [valor, setValor] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [resultado, setResultado] = useState(null);
  const id = `llave-${nombre}`;
  const fallo = resultado && resultado !== "guardada";

  async function guardar(e) {
    e.preventDefault();
    setOcupado(true);
    setResultado(null);
    const r = await mandar({ llave: nombre, valor });
    setOcupado(false);
    setResultado(r);
    if (r === "guardada") {
      setValor("");
      setAbierta(false);
      alGuardar();
    }
  }

  let estado = AJUSTES.sinLlave;
  if (fin) estado = AJUSTES.terminaEn(fin);
  else if (prestadas && nombre !== "anthropic") estado = AJUSTES.prestadas;

  return (
    <li className="ajuste-llave" data-llave={nombre}>
      <div className="ajuste-llave-cabeza">
        <p className="ajuste-llave-nombre">{t.nombre}</p>
        <p className="nota-chica">{t.para}</p>
        <p className="ajuste-llave-estado" data-hay={fin ? "si" : "no"}>
          {estado}
        </p>
      </div>
      {resultado === "guardada" ? (
        <p className="ayuda" role="status">
          {MENSAJE.guardada}
        </p>
      ) : null}
      {soloMirar ? null : abierta ? (
        <form className="ajuste-llave-form" onSubmit={guardar} noValidate>
          <label className="rotulo" htmlFor={id}>
            {AJUSTES.rotuloNueva(t.nombre)}
          </label>
          <input
            id={id}
            className="campo"
            type="password"
            autoComplete="off"
            spellCheck="false"
            value={valor}
            disabled={ocupado}
            onChange={(e) => setValor(e.target.value)}
            aria-invalid={fallo ? "true" : undefined}
            aria-describedby={fallo ? `${id}-error` : undefined}
          />
          {fallo ? (
            <p className="error-campo" id={`${id}-error`}>
              {MENSAJE[resultado] || AJUSTES.noGuardo}
            </p>
          ) : null}
          <div className="ajuste-llave-acciones">
            <button type="submit" className="boton boton-principal boton-chico" disabled={ocupado} aria-busy={ocupado}>
              {ocupado ? AJUSTES.probando : AJUSTES.guardar}
            </button>
            <button
              type="button"
              className="boton boton-secundario boton-chico"
              disabled={ocupado}
              onClick={() => {
                setAbierta(false);
                setResultado(null);
              }}
            >
              {AJUSTES.cancelar}
            </button>
          </div>
        </form>
      ) : (
        <div className="ajuste-llave-acciones">
          <button
            type="button"
            className="boton boton-secundario boton-chico"
            onClick={() => {
              setAbierta(true);
              setResultado(null);
            }}
          >
            {fin ? AJUSTES.cambiar : AJUSTES.poner}
          </button>
          <a className="enlace" href={t.link} target="_blank" rel="noreferrer">
            {t.sacar}
          </a>
        </div>
      )}
      <p className="nota-chica">
        {t.nota}
        {t.notaLink ? (
          <>
            {" "}
            <a className="enlace" href={t.notaLink} target="_blank" rel="noreferrer">
              {t.notaLinkTexto}
            </a>
          </>
        ) : null}
      </p>
    </li>
  );
}

export default function PantallaAjustes({ inicial }) {
  const [ajustes, setAjustes] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);

  async function refrescar() {
    const nuevos = await releer();
    if (nuevos) setAjustes(nuevos);
  }

  async function elegir(quien) {
    setGuardando(true);
    setAviso(null);
    const r = await mandar({ escribe: quien });
    setGuardando(false);
    setAviso(r === "guardado" ? AJUSTES.guardadoEscribe : AJUSTES.noGuardo);
    await refrescar();
  }

  return (
    <div className="ajustes" data-solo-mirar={ajustes.soloMirar ? "si" : undefined}>
      {ajustes.soloMirar ? <Aviso tipo="info" titulo={AJUSTES.soloMirar} /> : null}

      <fieldset className="grupo" disabled={ajustes.soloMirar || guardando}>
        <legend className="rotulo">{AJUSTES.escribeTitulo}</legend>
        <p className="ayuda" data-escribe={ajustes.escribe}>
          {AJUSTES.escribeAhora(AJUSTES.quien[ajustes.escribe] || AJUSTES.quien.google)}
        </p>
        <div className="ajustes-quien">
          {QUIENES.map((q) => (
            <label key={q || "auto"} className="largo">
              <input
                type="radio"
                name="escribe"
                value={q}
                checked={ajustes.elegido === q}
                onChange={() => elegir(q)}
              />
              <span className="largo-nombre">{AJUSTES.opciones[q].nombre}</span>
              <span className="largo-para">
                {q === "claude" && !ajustes.claudeCode ? AJUSTES.sinClaudeCode : AJUSTES.opciones[q].ayuda}
              </span>
              <span className="largo-check" aria-hidden="true">
                <IconoCheck />
              </span>
            </label>
          ))}
        </div>
        {aviso ? (
          <p className="ayuda" role="status">
            {aviso}
          </p>
        ) : null}
      </fieldset>

      <section className="grupo" aria-labelledby="llaves-titulo">
        <h2 className="rotulo" id="llaves-titulo">
          {AJUSTES.llavesTitulo}
        </h2>
        <ul className="ajustes-llaves">
          {LLAVES.map((n) => (
            <Llave
              key={n}
              nombre={n}
              fin={ajustes.llaves[n]}
              prestadas={ajustes.prestadas}
              soloMirar={ajustes.soloMirar}
              alGuardar={refrescar}
            />
          ))}
        </ul>
      </section>
    </div>
  );
}
