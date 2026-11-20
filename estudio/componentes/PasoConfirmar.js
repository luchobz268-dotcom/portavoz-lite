"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Aviso from "./Aviso";
import Pasos from "./Pasos";
import { IconoFlecha } from "./Iconos";
import { LARGOS, LARGO_INICIAL } from "@/lib/contrato";
import { guardarBorrador, leerBorrador } from "@/lib/borrador";
import { CONFIRMAR } from "@/lib/textos";

const PARRAFOS_A_LA_VISTA = 2;

function fechaLinda(fecha) {
  if (!fecha) return CONFIRMAR.sinFecha;
  const d = new Date(`${fecha}T12:00:00`);
  if (Number.isNaN(d.getTime())) return CONFIRMAR.sinFecha;
  return d.toLocaleDateString("es", { day: "numeric", month: "long", year: "numeric" });
}

/** Paso 1, segunda pantalla: ¿es esta la nota? */
export default function PasoConfirmar() {
  const router = useRouter();
  const [cargado, setCargado] = useState(false);
  const [nota, setNota] = useState(null);
  const [pedido, setPedido] = useState(null);
  const [todo, setTodo] = useState(false);

  useEffect(() => {
    const borrador = leerBorrador();
    if (borrador.nota) guardarBorrador({ pantalla: "nota" });
    setNota(borrador.nota || null);
    setPedido(borrador.pedido || null);
    setCargado(true);
  }, []);

  if (!cargado) {
    return (
      <main className="contenido" aria-busy="true">
        <Pasos actual={1} />
        <p className="solo-lectores">{CONFIRMAR.cargando}</p>
        <div className="nota-tarjeta" aria-hidden="true">
          <div className="esqueleto" style={{ height: 14, width: "40%" }} />
          <div className="esqueleto" style={{ height: 34, width: "85%" }} />
          <div className="esqueleto" style={{ height: 16, width: "100%" }} />
          <div className="esqueleto" style={{ height: 16, width: "92%" }} />
          <div className="esqueleto" style={{ height: 16, width: "70%" }} />
        </div>
      </main>
    );
  }

  if (!nota) {
    return (
      <main className="contenido">
        <Pasos actual={1} />
        <header className="encabezado">
          <h1 className="titulo">{CONFIRMAR.titulo}</h1>
          <p className="bajada">{CONFIRMAR.sinNota}</p>
        </header>
        <div className="acciones">
          <Link className="boton boton-principal" href="/">
            {CONFIRMAR.volverAlInicio}
          </Link>
        </div>
      </main>
    );
  }

  const largo = LARGOS.includes(pedido?.largo) ? pedido.largo : LARGO_INICIAL;
  const parrafos = nota.texto.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const hayMas = parrafos.length > PARRAFOS_A_LA_VISTA;
  const medio = nota.medio || (nota.origen === "texto" ? CONFIRMAR.textoPegado : null);

  function cambiarLargo(s) {
    const nuevo = { ...(pedido || {}), largo: s };
    setPedido(nuevo);
    guardarBorrador({ pedido: nuevo });
  }

  return (
    <main className="contenido">
      <Pasos actual={1} />
      <header className="encabezado">
        <h1 className="titulo">{CONFIRMAR.titulo}</h1>
        <p className="bajada">{CONFIRMAR.bajada}</p>
      </header>

      {nota.sensible ? (
        <Aviso tipo="info" titulo={`${CONFIRMAR.sensibleTitulo}: ${CONFIRMAR.temas[nota.tema]}`}>
          <p>{CONFIRMAR.sensibleTexto}</p>
        </Aviso>
      ) : null}

      <article className="nota-tarjeta" aria-labelledby="nota-titular">
        <dl className="nota-datos">
          {medio ? (
            <div>
              <dt>{CONFIRMAR.medio}</dt>
              <dd>{medio}</dd>
            </div>
          ) : null}
          <div>
            <dt>{CONFIRMAR.fecha}</dt>
            <dd>{fechaLinda(nota.fecha)}</dd>
          </div>
          <div>
            <dt>{CONFIRMAR.largoNota}</dt>
            <dd>{CONFIRMAR.palabras(nota.palabras)}</dd>
          </div>
        </dl>

        <h2 className="nota-titular" id="nota-titular">
          {nota.titular}
        </h2>

        <div className="nota-texto" id="nota-texto" data-recortada={hayMas && !todo ? "true" : "false"}>
          {parrafos.map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>

        {hayMas || (nota.link && !nota.ejemplo) ? (
          <div className="nota-pie">
            {hayMas ? (
              <button
                type="button"
                className="enlace"
                aria-expanded={todo}
                aria-controls="nota-texto"
                onClick={() => setTodo((v) => !v)}
              >
                {todo ? CONFIRMAR.verMenos : CONFIRMAR.verTodo}
              </button>
            ) : null}
            {nota.link && !nota.ejemplo ? (
              <a className="enlace" href={nota.link} target="_blank" rel="noopener noreferrer">
                {CONFIRMAR.abrirOriginal}
                <IconoFlecha />
              </a>
            ) : null}
          </div>
        ) : null}
      </article>

      <fieldset className="largo-elegido">
        <legend className="rotulo">{CONFIRMAR.video}</legend>
        <div className="segmentos">
          {LARGOS.map((s) => (
            <label key={s} className="segmento">
              <input type="radio" name="largo" value={s} checked={largo === s} onChange={() => cambiarLargo(s)} />
              <span aria-hidden="true">{s} s</span>
              <span className="solo-lectores">{CONFIRMAR.largoElegido(s)}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="barra-acciones">
        <button type="button" className="boton boton-principal" onClick={() => router.push("/guion")}>
          {CONFIRMAR.si}
        </button>
        <button
          type="button"
          className="boton boton-secundario"
          onClick={() => {
            // No es esta nota: el inicio no tiene que ofrecer "seguir" con ella. El link queda escrito.
            guardarBorrador({ pantalla: null });
            router.push("/");
          }}
        >
          {CONFIRMAR.no}
        </button>
      </div>
    </main>
  );
}
