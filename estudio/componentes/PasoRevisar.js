"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Aviso from "./Aviso";
import Pasos from "./Pasos";
import { IconoAviso } from "./Iconos";
import {
  LARGOS,
  LARGO_INICIAL,
  contarPalabras,
  entraEnLargo,
  esEncargo,
  linkValido,
  revisarGuionesDelTrabajo,
  revisarPedido,
  segundosPara,
} from "@/lib/contrato";
import { elegidoDelBorrador, guardarBorrador, leerBorrador, limpiarBorrador } from "@/lib/borrador";
import { CONFIRMAR, CUPO, ERRORES, GUION, REVISAR, SALIDAS } from "@/lib/textos";

const errorDe = (codigo) => ERRORES[codigo] || ERRORES.DESCONOCIDO;

/**
 * El pedido y los tres guiones del borrador, para que queden guardados con el trabajo ("Volver al guion" los
 * devuelve tal cual). Sólo se mandan si están bien: uno roto se deja afuera en vez de trabar el armado.
 */
function extrasDelBorrador(b, nota, largo, elegido) {
  const extras = {};
  const p = b.pedido;
  if (p && typeof p === "object") {
    const pedido = { largo };
    if (typeof p.texto === "string" && p.texto.trim()) pedido.texto = p.texto;
    if (typeof p.link === "string" && linkValido(p.link)) pedido.link = p.link.trim();
    if (revisarPedido(pedido).length === 0) extras.pedido = pedido;
  }
  if (b.guiones && elegido && revisarGuionesDelTrabajo({ nota, guion: elegido, guiones: b.guiones }).length === 0) {
    extras.guiones = b.guiones;
  }
  return extras;
}

/** Lo que se manda al tocar "Armar mi video", sin el encargo. Su texto es la huella: si cambia algo, otro encargo. */
const cuerpoDe = (nota, largo, guion, extras) => ({ nota, largo, guion, ...extras });

/** Una marca al azar para este "Armar mi video" (ver esEncargo en lib/contrato.js). getRandomValues anda también
 *  en el wifi de la casa, donde randomUUID no está (no es una dirección segura). */
function nuevoEncargo() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

/** El encargo guardado en el borrador, si es de este mismo pedido. */
function encargoDe(b, huella) {
  const e = b?.encargo;
  return e && esEncargo(e.id) && e.huella === huella ? e.id : null;
}

/** Mientras arma, los enlaces de Revisar no llevan a ningún lado: si la persona se va, el video sale igual. */
const frenar = (e) => e.preventDefault();

/** Paso 3: revisa lo que va a salir y arma el video. */
export default function PasoRevisar() {
  const router = useRouter();
  const [cargado, setCargado] = useState(false);
  const [nota, setNota] = useState(null);
  const [largo, setLargo] = useState(LARGO_INICIAL);
  const [elegido, setElegido] = useState(null); // { enfoque, texto }
  const [cupo, setCupo] = useState(null);
  const [cupoListo, setCupoListo] = useState(false);
  const [armando, setArmando] = useState(false);
  const [error, setError] = useState(null); // { codigo, salida }
  const [sinVocesMotivo, setSinVocesMotivo] = useState(false);
  const armandoYa = useRef(false); // freno del doble toque: se lee al instante, sin esperar a que se dibuje
  const montado = useRef(false);
  const avisoError = useRef(null);
  const extras = useRef({}); // pedido y guiones del borrador, si están bien

  useEffect(() => {
    montado.current = true;
    const b = leerBorrador();
    const n = b.nota || null;
    const e = elegidoDelBorrador(b);
    // Una versión "a mano" vacía cuenta como que no hay guion.
    const usable = e && contarPalabras(e.version.texto) > 0;
    setNota(n);
    setLargo(LARGOS.includes(b.pedido?.largo) ? b.pedido.largo : LARGO_INICIAL);
    const g = usable ? { enfoque: e.guion.enfoque, texto: e.version.texto } : null;
    setElegido(g);
    const l = LARGOS.includes(b.pedido?.largo) ? b.pedido.largo : LARGO_INICIAL;
    extras.current = n ? extrasDelBorrador(b, n, l, g) : {};
    if (n && usable) guardarBorrador({ pantalla: "revisar" });
    // Si ya se tocó "Armar mi video" con esto mismo y la página se cerró antes de llegar al video, se busca ese video.
    const pendiente = n && g ? encargoDe(b, JSON.stringify(cuerpoDe(n, l, g, extras.current))) : null;
    setCargado(true);

    (async () => {
      if (pendiente) {
        try {
          const r = await fetch("/api/trabajos", { cache: "no-store" });
          const ya = (await r.json()).trabajos?.find((t) => t.encargo === pendiente);
          if (ya && montado.current) {
            limpiarBorrador();
            router.replace(`/video/${ya.id}`);
            return;
          }
        } catch {
          // Si no se puede mirar, se sigue: al tocar Armar va el mismo encargo y el Estudio devuelve el que ya existe.
        }
      }
      try {
        const r = await fetch("/api/cupo", { cache: "no-store" });
        const j = await r.json();
        if (montado.current && j.cupo) setCupo(j.cupo);
      } catch {
        // Sin el cupo se puede seguir: si no quedan voces, lo dice el Estudio al tocar Armar.
      }
      if (montado.current) setCupoListo(true);
    })();
    return () => {
      montado.current = false;
    };
  }, []);

  useEffect(() => {
    if (error) avisoError.current?.focus();
  }, [error]);

  const sinVoces = Boolean(cupo && cupo.voces.quedan <= 0);
  const palabras = elegido ? contarPalabras(elegido.texto) : 0;
  const noEntra = Boolean(elegido) && !entraEnLargo(palabras, largo);

  async function armar() {
    if (armandoYa.current) return;
    setError(null);
    if (noEntra) {
      router.push("/guion");
      return;
    }
    if (sinVoces) {
      setSinVocesMotivo(true);
      return;
    }
    armandoYa.current = true;
    setArmando(true);
    const cuerpo = cuerpoDe(nota, largo, elegido, extras.current);
    const huella = JSON.stringify(cuerpo);
    // El mismo pedido lleva el mismo encargo (otro toque después de un corte); si cambió algo, uno nuevo. Se guarda
    // antes de mandarlo: si la página se cierra mientras arma, al volver a Revisar se encuentra el video.
    const encargo = encargoDe(leerBorrador(), huella) || nuevoEncargo();
    guardarBorrador({ encargo: { id: encargo, huella } });
    let r;
    try {
      const respuesta = await fetch("/api/trabajos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...cuerpo, encargo }),
      });
      r = await respuesta.json();
    } catch {
      r = { error: { codigo: "SIN_CONEXION", salida: "reintentar" } };
    }
    if (r?.trabajo?.id) {
      // Si la persona ya se fue de Revisar, no se la mueve ni se borra el borrador: al volver, la lleva al video.
      if (!montado.current) return;
      limpiarBorrador();
      router.push(`/video/${r.trabajo.id}`);
      return; // queda "Armando" hasta que cambia la pantalla
    }
    armandoYa.current = false;
    if (!montado.current) return;
    setArmando(false);
    const e = r?.error || { codigo: "DESCONOCIDO", salida: "reintentar" };
    if (e.codigo === "SIN_VOCES_HOY") {
      setSinVocesMotivo(true);
      setCupo((c) => (c ? { ...c, voces: { ...c.voces, usadas: c.voces.tope, quedan: 0 } } : c));
      return;
    }
    setError(e);
  }

  if (!cargado) {
    return (
      <main className="contenido" aria-busy="true">
        <Pasos actual={3} />
        <p className="solo-lectores">{REVISAR.cargando}</p>
        <div className="revisar" aria-hidden="true">
          <div className="revisar-tarjeta revisar-nota">
            <div className="esqueleto" style={{ height: 14, width: "30%" }} />
            <div className="esqueleto" style={{ height: 28, width: "80%" }} />
          </div>
          <div className="revisar-tarjeta revisar-guion-tarjeta">
            <div className="esqueleto" style={{ height: 160, width: "100%" }} />
          </div>
        </div>
      </main>
    );
  }

  if (!nota || !elegido) {
    return (
      <main className="contenido" data-listo="si">
        <Pasos actual={3} />
        <header className="encabezado">
          <h1 className="titulo">{REVISAR.titulo}</h1>
          <p className="bajada">{nota ? REVISAR.sinGuion : CONFIRMAR.sinNota}</p>
        </header>
        <div className="acciones">
          {nota ? (
            <Link className="boton boton-principal" href="/guion">
              {REVISAR.irAlGuion}
            </Link>
          ) : (
            <Link className="boton boton-principal" href="/">
              {CONFIRMAR.volverAlInicio}
            </Link>
          )}
        </div>
      </main>
    );
  }

  const { nombre } = GUION.enfoques[elegido.enfoque] || { nombre: elegido.enfoque };
  const textoError = error ? errorDe(error.codigo) : null;

  return (
    <main className="contenido" data-listo={cupoListo ? "si" : undefined}>
      <Pasos actual={3} />
      <header className="encabezado">
        <h1 className="titulo">{REVISAR.titulo}</h1>
        <p className="bajada">{REVISAR.bajada}</p>
      </header>

      {sinVoces ? (
        <Aviso tipo="info" titulo={ERRORES.SIN_VOCES_HOY.titulo}>
          <p>{ERRORES.SIN_VOCES_HOY.texto}</p>
        </Aviso>
      ) : null}

      {nota.sensible ? (
        <Aviso tipo="info" titulo={`${CONFIRMAR.sensibleTitulo}: ${CONFIRMAR.temas[nota.tema]}`}>
          <p>{CONFIRMAR.sensibleTexto}</p>
        </Aviso>
      ) : null}

      {noEntra ? (
        <Aviso
          titulo={REVISAR.noEntra.titulo}
          acciones={
            <Link className="boton boton-secundario boton-chico" href="/guion">
              {REVISAR.irAlGuion}
            </Link>
          }
        >
          <p>{REVISAR.noEntra.texto}</p>
        </Aviso>
      ) : null}

      {textoError ? (
        <div ref={avisoError} tabIndex={-1} className="aviso-envoltura">
          <Aviso
            titulo={textoError.titulo}
            acciones={
              error.salida === "volver-al-guion" ? (
                <Link className="boton boton-secundario boton-chico" href="/guion">
                  {SALIDAS["volver-al-guion"]}
                </Link>
              ) : (
                <button type="button" className="boton boton-secundario boton-chico" onClick={armar}>
                  {SALIDAS.reintentar}
                </button>
              )
            }
          >
            <p>{textoError.texto}</p>
          </Aviso>
        </div>
      ) : null}

      <div className="revisar">
        <section className="revisar-tarjeta revisar-nota" aria-labelledby="revisar-nota">
          <h2 className="revisar-rotulo" id="revisar-nota">
            {REVISAR.laNota}
          </h2>
          <p className="revisar-titular">{nota.titular}</p>
          <dl className="nota-datos">
            {nota.medio ? (
              <div>
                <dt>{CONFIRMAR.medio}</dt>
                <dd>{nota.medio}</dd>
              </div>
            ) : null}
            <div>
              <dt>{REVISAR.largo}</dt>
              <dd>{REVISAR.segundos(largo)}</dd>
            </div>
          </dl>
        </section>

        <section className="revisar-tarjeta revisar-guion-tarjeta" aria-labelledby="revisar-guion-rotulo">
          <h2 className="revisar-rotulo" id="revisar-guion-rotulo">
            {REVISAR.elGuion}: <span className="revisar-enfoque">{nombre}</span>
          </h2>
          <p className="revisar-guion">{elegido.texto}</p>
          <p className="guion-duracion" data-pasa={noEntra ? "si" : undefined}>
            {noEntra ? <IconoAviso tam={16} /> : null}
            <span>
              {noEntra ? GUION.sePasa(segundosPara(palabras), largo) : GUION.duracion(segundosPara(palabras), largo)}
            </span>
          </p>
          <Link
            className="enlace"
            href="/guion"
            aria-disabled={armando ? "true" : undefined}
            onClick={armando ? frenar : undefined}
          >
            {REVISAR.cambiarGuion}
          </Link>
        </section>

        <section className="revisar-tarjeta revisar-pie" aria-labelledby="revisar-pie">
          <h2 className="revisar-rotulo" id="revisar-pie">
            {REVISAR.pie}
          </h2>
          <ul className="revisar-lista">
            <li>{nota.medio ? REVISAR.fuente(nota.medio) : REVISAR.sinFuente}</li>
            <li>{REVISAR.ilustrativas}</li>
          </ul>
        </section>

        <section className="revisar-tarjeta revisar-voces" aria-labelledby="revisar-voces">
          <h2 className="revisar-rotulo" id="revisar-voces">
            {REVISAR.voces}
          </h2>
          {cupo ? (
            <p className="voces-quedan" data-sin={sinVoces ? "si" : undefined}>
              {CUPO.voces(cupo.voces.quedan, cupo.voces.tope)}
            </p>
          ) : !cupoListo ? (
            <div className="esqueleto" style={{ height: 20, width: "70%" }} aria-hidden="true" />
          ) : null}
          <p className="nota-chica">{REVISAR.siFalla}</p>
        </section>
      </div>

      <div className="barra-acciones barra-revisar">
        <button
          type="button"
          className="boton boton-principal"
          aria-busy={armando ? "true" : undefined}
          aria-describedby={sinVocesMotivo ? "armar-motivo" : undefined}
          onClick={armar}
        >
          {armando ? REVISAR.armando : REVISAR.armar}
        </button>
        <Link
          className="boton boton-secundario"
          href="/guion"
          aria-disabled={armando ? "true" : undefined}
          onClick={armando ? frenar : undefined}
        >
          {REVISAR.volver}
        </Link>
        {sinVocesMotivo ? (
          <p className="error-campo armar-motivo" id="armar-motivo" role="status">
            <IconoAviso tam={16} />
            <span>{REVISAR.sinVocesMotivo}</span>
          </p>
        ) : null}
      </div>
    </main>
  );
}
