"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Aviso from "./Aviso";
import Pasos from "./Pasos";
import { IconoAviso, IconoCheck } from "./Iconos";
import {
  ENFOQUES, LARGOS, LARGO_INICIAL, contarPalabras, entraEnLargo, esEncargo, linkValido, revisarGuion,
  revisarGuionesDelTrabajo, revisarPedido, segundosPara,
} from "@/lib/contrato";
import { elegidoDelBorrador, guardarBorrador, leerBorrador, limpiarBorrador } from "@/lib/borrador";
import { CONFIRMAR, CUPO, ERRORES, GUION, REVISAR, SALIDAS } from "@/lib/textos";

// Debajo de este ancho los tres guiones no entran lado a lado: se muestran en pestañas.
const ANGOSTO = "(max-width: 960px)";
// Al escribir, se guarda después de esta pausa (y siempre al cerrar u ocultar la página).
const PAUSA_ESCRITURA = 700;
// Desde el 2026-11-18 el motor escribe los guiones y después los revisa contra la nota, sin avisar cuándo pasa de
// una cosa a la otra. Pasado este rato de espera se cambia "Escribiendo" por "Revisando los guiones". Es una
// estimación: escribir los tres tardaba de 6 a 30 s (docs/velocidad.md) y uno solo, menos.
const ESPERA_REVISION = { guiones: 12000, otro: 8000 };

/** Los guiones guardados sirven si son los tres y tienen la forma del contrato (el texto puede estar vacío). */
function sirven(lista) {
  return (
    Array.isArray(lista) &&
    lista.length === ENFOQUES.length &&
    lista.every((g) => revisarGuion(g).filter((p) => !p.endsWith("sin texto")).length === 0)
  );
}

async function pedir(url, cuerpo) {
  let respuesta;
  try {
    respuesta = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  } catch {
    return { error: { codigo: "SIN_CONEXION" } };
  }
  try {
    return await respuesta.json();
  } catch {
    return { error: { codigo: "DESCONOCIDO" } };
  }
}

const errorDe = (codigo) => ERRORES[codigo] || ERRORES.DESCONOCIDO;

// ---------------------------------------------------------------------------------------------
// "Armar mi video". Vivía en "Revisa antes de armar" (PasoRevisar.js) y se mudó acá el 2026-11-18, tal cual.

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

/**
 * El cuerpo de "Armar mi video" según el borrador, o null si no hay nota o guion elegido con texto. Es la misma
 * cuenta que hacía Revisar al entrar: así un armado que quedó a medias desde Revisar se encuentra igual.
 */
function armadoDelBorrador(b) {
  const nota = b.nota || null;
  const e = elegidoDelBorrador(b);
  // Una versión "a mano" vacía cuenta como que no hay guion.
  if (!nota || !e || contarPalabras(e.version.texto) === 0) return null;
  const largo = LARGOS.includes(b.pedido?.largo) ? b.pedido.largo : LARGO_INICIAL;
  const guion = { enfoque: e.guion.enfoque, texto: e.version.texto };
  return cuerpoDe(nota, largo, guion, extrasDelBorrador(b, nota, largo, guion));
}

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

/** Mientras arma, los enlaces de esta pantalla no llevan a ningún lado: si la persona se va, el video sale igual. */
const frenar = (e) => e.preventDefault();

/** true cuando `activo` lleva más de `espera` milisegundos (para pasar de "Escribiendo" a "Revisando"). */
function usePasado(activo, espera) {
  const [pasado, setPasado] = useState(false);
  useEffect(() => {
    setPasado(false);
    if (!activo) return undefined;
    const t = setTimeout(() => setPasado(true), espera);
    return () => clearTimeout(t);
  }, [activo, espera]);
  return activo && pasado;
}

/** Uno de los tres guiones: nombre, cuadro para corregir, duración y los cuatro botones. */
function TarjetaGuion({
  guion, elegido, angosto, largo, ocupado, falla, motivo, armando, refCuadro,
  onEscribir, onCambiar, onDeshacer, onElegir, panel,
}) {
  const v = guion.versiones[guion.actual];
  const revisandoOtro = usePasado(ocupado === "otro", ESPERA_REVISION.otro);
  // La línea de la revisión: sólo si el motor dejó un aviso que la pantalla conoce. Al corregir a mano, la versión
  // nueva no trae revisión y la línea se va; con Deshacer vuelve.
  const avisoRevision = (v.revision?.aviso && GUION.avisos[v.revision.aviso]) || null;
  const palabras = contarPalabras(v.texto);
  const s = segundosPara(palabras);
  const sePasa = !entraEnLargo(palabras, largo);
  const vacio = palabras === 0;
  const { nombre, que } = GUION.enfoques[guion.enfoque];
  const base = `guion-${guion.enfoque}`;
  const describe = [avisoRevision ? `${base}-revision` : null, `${base}-duracion`, motivo ? `${base}-motivo` : null]
    .filter(Boolean)
    .join(" ");
  const quieto = Boolean(ocupado) || armando;
  const boton = (accion, texto, bloqueado, extra = {}) => (
    <button
      type="button"
      className="boton boton-secundario guion-boton"
      aria-disabled={bloqueado ? "true" : undefined}
      aria-busy={ocupado === accion ? "true" : undefined}
      onClick={() => {
        if (!bloqueado) (accion === "deshacer" ? onDeshacer() : onCambiar(accion));
      }}
      {...extra}
    >
      {texto}
    </button>
  );

  return (
    <section
      className="guion"
      id={base}
      data-enfoque={guion.enfoque}
      data-elegido={elegido ? "si" : "no"}
      aria-busy={ocupado ? "true" : "false"}
      aria-labelledby={panel ? undefined : `${base}-nombre`}
      {...panel}
    >
      <div className="guion-cabeza">
        <h2 className="guion-nombre" id={`${base}-nombre`}>
          {nombre}
        </h2>
        {elegido ? (
          <p className="guion-elegido">
            <IconoCheck />
            {GUION.elegido}
          </p>
        ) : !angosto ? (
          <button
            type="button"
            className="boton boton-secundario guion-elegir"
            aria-label={GUION.elegirEste(nombre)}
            aria-disabled={armando ? "true" : undefined}
            onClick={armando ? undefined : onElegir}
          >
            {GUION.elegir}
          </button>
        ) : null}
      </div>
      <p className="guion-que">{que}</p>
      {avisoRevision ? (
        <p className="guion-revision" id={`${base}-revision`} data-aviso={v.revision.aviso}>
          <IconoAviso tam={16} />
          <span>{avisoRevision}</span>
        </p>
      ) : null}

      <label className="solo-lectores" htmlFor={`${base}-cuadro`}>
        {GUION.cuadro(nombre)}
      </label>
      <textarea
        ref={refCuadro}
        id={`${base}-cuadro`}
        className="area guion-cuadro"
        value={v.texto}
        readOnly={quieto}
        spellCheck
        aria-invalid={motivo ? "true" : undefined}
        aria-describedby={describe}
        onChange={(e) => onEscribir(e.target.value)}
      />
      <p className="guion-duracion" id={`${base}-duracion`} data-pasa={sePasa ? "si" : undefined}>
        {sePasa ? <IconoAviso tam={16} /> : null}
        <span>{sePasa ? GUION.sePasa(s, largo) : GUION.duracion(s, largo)}</span>
      </p>
      {motivo ? (
        <p className="error-campo" id={`${base}-motivo`}>
          <IconoAviso tam={16} />
          <span>{motivo === "vacio" ? GUION.errorVacio : GUION.errorLargo(s, largo)}</span>
        </p>
      ) : null}
      {ocupado ? (
        <p className="guion-ocupado" role="status">
          {revisandoOtro ? GUION.revisandoUno : GUION.cambiando[ocupado] || ""}
        </p>
      ) : null}
      {falla ? (
        <Aviso
          titulo={GUION.fallaCambio.titulo}
          acciones={
            <button type="button" className="boton boton-secundario boton-chico" onClick={() => onCambiar(falla)}>
              {SALIDAS.reintentar}
            </button>
          }
        >
          <p>{GUION.fallaCambio.texto}</p>
        </Aviso>
      ) : null}

      <div className="guion-botones">
        {boton("corto", GUION.masCorto, quieto || palabras < 2, {
          "data-resaltado": sePasa ? "si" : undefined,
        })}
        {boton("simple", GUION.masSimple, quieto || vacio)}
        {boton("deshacer", GUION.deshacer, quieto || guion.actual === 0)}
        {boton("otro", GUION.escribirOtro, quieto)}
      </div>
    </section>
  );
}

/** Paso 2: elige y corrige el guion, y arma el video. */
export default function PasoGuion() {
  const router = useRouter();
  const [cargado, setCargado] = useState(false);
  const [nota, setNota] = useState(null);
  const [largo, setLargo] = useState(LARGO_INICIAL);
  const [lista, setLista] = useState(null);
  const [elegido, setElegido] = useState(null);
  const [escribiendo, setEscribiendo] = useState(false);
  const [errorCarga, setErrorCarga] = useState(null);
  const [ocupados, setOcupados] = useState({});
  const [fallas, setFallas] = useState({});
  const [motivo, setMotivo] = useState(null); // { id, tipo: "vacio" | "largo" } al tocar Armar
  const [guardado, setGuardado] = useState(false);
  const [angosto, setAngosto] = useState(false);
  const [cupo, setCupo] = useState(null);
  const [cupoListo, setCupoListo] = useState(false);
  const [armando, setArmando] = useState(false);
  const [error, setError] = useState(null); // { codigo, salida } al armar
  const [sinVocesMotivo, setSinVocesMotivo] = useState(false);
  const armandoYa = useRef(false); // freno del doble toque: se lee al instante, sin esperar a que se dibuje
  const avisoError = useRef(null);
  const revisandoGuiones = usePasado(escribiendo, ESPERA_REVISION.guiones);

  // Lo último, para guardar sin esperar a que se dibuje la pantalla (al cerrar, al ocultar, al salir).
  const ultimo = useRef({ notaId: null, lista: null, elegido: null });
  const reloj = useRef(null);
  const montado = useRef(false);
  const pidiendo = useRef(false);
  const cuadros = useRef({});
  const pestanas = useRef([]);

  function guardarYa(avisar = true) {
    clearTimeout(reloj.current);
    reloj.current = null;
    const { notaId, lista: l, elegido: e } = ultimo.current;
    if (!notaId || !l) return;
    guardarBorrador({ guiones: { notaId, lista: l, elegido: e } });
    if (avisar && montado.current) setGuardado(true);
  }

  function aplicar(nuevaLista, nuevoElegido, pausa = 0) {
    ultimo.current = { ...ultimo.current, lista: nuevaLista, elegido: nuevoElegido };
    setLista(nuevaLista);
    setElegido(nuevoElegido);
    setGuardado(false);
    clearTimeout(reloj.current);
    if (pausa) reloj.current = setTimeout(() => guardarYa(), pausa);
    else guardarYa();
  }

  async function escribirGuiones(n, l) {
    if (pidiendo.current) return;
    pidiendo.current = true;
    setErrorCarga(null);
    setEscribiendo(true);
    const r = await pedir("/api/guiones", { nota: n, largo: l });
    pidiendo.current = false;
    if (!montado.current) return;
    setEscribiendo(false);
    if (r.error || !sirven(r.guiones)) {
      setErrorCarga(r.error?.codigo || "DESCONOCIDO");
      return;
    }
    aplicar(r.guiones, r.guiones[0].id);
  }

  // Al entrar: lo guardado, o tres guiones nuevos si no hay (o si son de otra nota).
  useEffect(() => {
    montado.current = true;
    const b = leerBorrador();
    const n = b.nota || null;
    const l = LARGOS.includes(b.pedido?.largo) ? b.pedido.largo : LARGO_INICIAL;
    setNota(n);
    setLargo(l);
    const mq = window.matchMedia(ANGOSTO);
    setAngosto(mq.matches);
    if (n) {
      guardarBorrador({ pantalla: "guion" });
      const g = b.guiones;
      ultimo.current = { notaId: n.id, lista: null, elegido: null };
      if (g && g.notaId === n.id && sirven(g.lista)) {
        const e = g.lista.some((x) => x.id === g.elegido) ? g.elegido : g.lista[0].id;
        ultimo.current = { notaId: n.id, lista: g.lista, elegido: e };
        setLista(g.lista);
        setElegido(e);
      } else {
        escribirGuiones(n, l);
      }
    }
    setCargado(true);

    // Si ya se tocó "Armar mi video" con esto mismo y la página se cerró antes de llegar al video, se busca ese video.
    const armado = n ? armadoDelBorrador(b) : null;
    const pendiente = armado ? encargoDe(b, JSON.stringify(armado)) : null;
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

    const alCambiarAncho = () => setAngosto(mq.matches);
    const alSalir = () => guardarYa(false);
    const alOcultar = () => {
      if (document.visibilityState === "hidden") guardarYa(false);
    };
    mq.addEventListener("change", alCambiarAncho);
    window.addEventListener("pagehide", alSalir);
    document.addEventListener("visibilitychange", alOcultar);
    return () => {
      mq.removeEventListener("change", alCambiarAncho);
      window.removeEventListener("pagehide", alSalir);
      document.removeEventListener("visibilitychange", alOcultar);
      if (reloj.current) guardarYa(false);
      montado.current = false;
    };
    // Sólo al entrar: lo demás se lee de las referencias.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Al tocar Armar sin poder: el cursor va al cuadro, donde está el motivo.
  useEffect(() => {
    if (motivo) cuadros.current[motivo.id]?.focus();
  }, [motivo]);

  useEffect(() => {
    if (error) avisoError.current?.focus();
  }, [error]);

  function cambiarGuion(id, cambio) {
    const nuevaLista = ultimo.current.lista.map((g) => (g.id === id ? cambio(g) : g));
    return nuevaLista;
  }

  function escribir(id, texto) {
    if (armandoYa.current) return;
    const nuevaLista = cambiarGuion(id, (g) => {
      // Escribir después de deshacer descarta lo de adelante. Una sola versión "a mano" que se va actualizando.
      let versiones = g.versiones.slice(0, g.actual + 1);
      const v = { texto, palabras: contarPalabras(texto), origen: "a-mano" };
      versiones = versiones.at(-1).origen === "a-mano" ? [...versiones.slice(0, -1), v] : [...versiones, v];
      return { ...g, versiones, actual: versiones.length - 1 };
    });
    if (motivo?.id === id) setMotivo(null);
    aplicar(nuevaLista, ultimo.current.elegido, PAUSA_ESCRITURA);
  }

  function deshacer(id) {
    if (armandoYa.current) return;
    const nuevaLista = cambiarGuion(id, (g) => ({ ...g, actual: Math.max(0, g.actual - 1) }));
    if (motivo?.id === id) setMotivo(null);
    aplicar(nuevaLista, ultimo.current.elegido);
  }

  async function cambiar(id, accion) {
    if (ocupados[id] || armandoYa.current) return;
    const g = ultimo.current.lista.find((x) => x.id === id);
    const texto = g.versiones[g.actual].texto;
    setOcupados((o) => ({ ...o, [id]: accion }));
    setFallas((f) => ({ ...f, [id]: null }));
    const r = await pedir("/api/guiones/cambiar", { nota, largo, enfoque: g.enfoque, texto, accion });
    if (!montado.current) return;
    setOcupados((o) => ({ ...o, [id]: null }));
    if (r.error || !r.version) {
      setFallas((f) => ({ ...f, [id]: accion }));
      return;
    }
    const nuevaLista = cambiarGuion(id, (x) => {
      const versiones = [...x.versiones.slice(0, x.actual + 1), r.version];
      return { ...x, versiones, actual: versiones.length - 1 };
    });
    if (motivo?.id === id) setMotivo(null);
    aplicar(nuevaLista, ultimo.current.elegido);
  }

  function elegir(id) {
    if (id === ultimo.current.elegido || armandoYa.current) return;
    setMotivo(null);
    aplicar(ultimo.current.lista, id);
  }

  const sinVoces = Boolean(cupo && cupo.voces.quedan <= 0);

  // Mientras el guion elegido espera "Más corto", "Más simple" o "Escribir otro", no se arma: saldría el texto viejo.
  const elegidoOcupado = Boolean(elegido && ocupados[elegido]);

  async function armar() {
    if (armandoYa.current || elegidoOcupado) return;
    setError(null);
    // El guion vacío o que no entra en el largo no se arma, y el motivo queda en el guion. (Antes lo frenaba el
    // aviso noEntra de Revisar, que mandaba de vuelta al guion; ahora ya se está ahí.)
    const g = lista.find((x) => x.id === elegido);
    const palabras = contarPalabras(g.versiones[g.actual].texto);
    if (palabras === 0) return setMotivo({ id: g.id, tipo: "vacio", vez: Date.now() });
    if (!entraEnLargo(palabras, largo)) return setMotivo({ id: g.id, tipo: "largo", vez: Date.now() });
    guardarYa(false);
    if (sinVoces) {
      setSinVocesMotivo(true);
      return;
    }
    const b = leerBorrador();
    const cuerpo = armadoDelBorrador(b);
    if (!cuerpo) return setError({ codigo: "DESCONOCIDO", salida: "reintentar" });
    armandoYa.current = true;
    setArmando(true);
    const huella = JSON.stringify(cuerpo);
    // El mismo pedido lleva el mismo encargo (otro toque después de un corte); si cambió algo, uno nuevo. Se guarda
    // antes de mandarlo: si la página se cierra mientras arma, al volver a los guiones se encuentra el video.
    const encargo = encargoDe(b, huella) || nuevoEncargo();
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
      // Si la persona ya se fue de los guiones, no se la mueve ni se borra el borrador: al volver, la lleva al video.
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

  // "Volver al guion" de un error del armado (el guion no sirve o no hubo clips): ya se está en los guiones, así que
  // lleva el cursor al guion elegido para corregirlo.
  function volverAlGuion() {
    setError(null);
    cuadros.current[elegido]?.focus();
  }

  function teclaPestana(e, i) {
    const n = lista.length;
    const destino = { ArrowRight: (i + 1) % n, ArrowLeft: (i - 1 + n) % n, Home: 0, End: n - 1 }[e.key];
    if (destino === undefined) return;
    e.preventDefault();
    elegir(lista[destino].id);
    pestanas.current[destino]?.focus();
  }

  if (!cargado) {
    return (
      <main className="contenido" aria-busy="true">
        <Pasos actual={2} />
        <p className="solo-lectores">{GUION.cargando}</p>
        <Esqueleto />
      </main>
    );
  }

  if (!nota) {
    return (
      <main className="contenido">
        <Pasos actual={2} />
        <header className="encabezado">
          <h1 className="titulo">{GUION.titulo}</h1>
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

  const textoError = error ? errorDe(error.codigo) : null;

  const tarjeta = (g, panel) => (
    <TarjetaGuion
      key={g.id}
      guion={g}
      elegido={g.id === elegido}
      angosto={angosto}
      largo={largo}
      ocupado={ocupados[g.id] || null}
      falla={fallas[g.id] || null}
      motivo={motivo?.id === g.id ? motivo.tipo : null}
      refCuadro={(el) => {
        cuadros.current[g.id] = el;
      }}
      onEscribir={(texto) => escribir(g.id, texto)}
      onCambiar={(accion) => cambiar(g.id, accion)}
      onDeshacer={() => deshacer(g.id)}
      onElegir={() => elegir(g.id)}
      armando={armando}
      panel={panel}
    />
  );

  return (
    <main
      className="contenido"
      data-listo={lista && cupoListo ? "si" : undefined}
      aria-busy={escribiendo ? "true" : undefined}
    >
      <Pasos actual={2} />
      <header className="encabezado">
        <h1 className="titulo">{GUION.titulo}</h1>
        <p className="bajada">{GUION.bajada}</p>
        <p className="guion-de-la-nota">
          <span>{GUION.deLaNota}:</span> {nota.titular}
        </p>
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

      {errorCarga ? (
        <Aviso
          titulo={errorDe(errorCarga).titulo}
          acciones={
            <button type="button" className="boton boton-secundario boton-chico" onClick={() => escribirGuiones(nota, largo)}>
              {SALIDAS.reintentar}
            </button>
          }
        >
          <p>{errorDe(errorCarga).texto}</p>
        </Aviso>
      ) : null}

      {escribiendo ? (
        <>
          <p className="solo-lectores" role="status">
            {revisandoGuiones ? GUION.revisando : GUION.escribiendo}
          </p>
          <Esqueleto />
        </>
      ) : null}

      {lista && angosto ? (
        <div className="guiones-pestanas">
          <div className="guion-pestanas" role="tablist" aria-label={GUION.pestanas}>
            {lista.map((g, i) => {
              const sel = g.id === elegido;
              return (
                <button
                  key={g.id}
                  ref={(el) => {
                    pestanas.current[i] = el;
                  }}
                  type="button"
                  role="tab"
                  id={`pestana-${g.enfoque}`}
                  className="guion-pestana"
                  aria-selected={sel}
                  aria-controls={`guion-${g.enfoque}`}
                  tabIndex={sel ? 0 : -1}
                  aria-disabled={armando ? "true" : undefined}
                  onClick={() => elegir(g.id)}
                  onKeyDown={(e) => teclaPestana(e, i)}
                >
                  {sel ? <IconoCheck /> : null}
                  <span>{GUION.enfoques[g.enfoque].nombre}</span>
                </button>
              );
            })}
          </div>
          {lista.map((g) =>
            tarjeta(g, {
              role: "tabpanel",
              "aria-labelledby": `pestana-${g.enfoque}`,
              hidden: g.id !== elegido,
            }),
          )}
        </div>
      ) : null}

      {lista && !angosto ? <div className="guiones">{lista.map((g) => tarjeta(g, null))}</div> : null}

      {lista ? (
        <div className="guion-armar">
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
      ) : null}

      {textoError ? (
        <div ref={avisoError} tabIndex={-1} className="aviso-envoltura">
          <Aviso
            titulo={textoError.titulo}
            acciones={
              error.salida === "volver-al-guion" ? (
                <button type="button" className="boton boton-secundario boton-chico" onClick={volverAlGuion}>
                  {SALIDAS["volver-al-guion"]}
                </button>
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

      <div className="barra-acciones barra-guion">
        {lista ? (
          <button
            type="button"
            className="boton boton-principal"
            aria-busy={armando ? "true" : undefined}
            aria-describedby={sinVocesMotivo ? "armar-motivo" : undefined}
            disabled={elegidoOcupado && !armando}
            onClick={armar}
          >
            {armando ? REVISAR.armando : REVISAR.armar}
          </button>
        ) : null}
        <Link
          className="enlace"
          href="/"
          aria-disabled={armando ? "true" : undefined}
          onClick={armando ? frenar : undefined}
        >
          {GUION.volver}
        </Link>
        <p className="guion-guardado" aria-live="polite">
          {guardado ? (
            <>
              <IconoCheck />
              <span>{GUION.guardado}</span>
            </>
          ) : null}
        </p>
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

function Esqueleto() {
  return (
    <div className="guiones guiones-esqueleto" aria-hidden="true">
      {ENFOQUES.map((e) => (
        <div key={e} className="guion">
          <div className="esqueleto" style={{ height: 22, width: "45%" }} />
          <div className="esqueleto" style={{ height: 14, width: "75%" }} />
          <div className="esqueleto" style={{ height: 220, width: "100%" }} />
          <div className="esqueleto" style={{ height: 14, width: "35%" }} />
          <div className="esqueleto" style={{ height: 104, width: "100%" }} />
        </div>
      ))}
    </div>
  );
}
