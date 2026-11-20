import { cookies } from "next/headers";
import Link from "next/link";
import Aviso from "@/componentes/Aviso";
import EstadoTrabajo from "@/componentes/EstadoTrabajo";
import { IconoMarca } from "@/componentes/Iconos";
import RefrescoMisVideos from "@/componentes/RefrescoMisVideos";
import { esEjemplo, fuente } from "@/lib/fuente";
import { CUPO, MARCA, MIS_VIDEOS } from "@/lib/textos";

export const dynamic = "force-dynamic";
export const metadata = { title: `${MIS_VIDEOS.titulo} | ${MARCA.titulo}` };

/** "17 nov, 14:05": la fecha corta en castellano, con la hora de la PC donde anda el Estudio. */
function fechaCorta(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default async function MisVideos() {
  const sinVoces = esEjemplo() && (await cookies()).get("simular")?.value === "sin-voces";
  const [rt, rc] = await Promise.all([fuente().trabajos(), fuente().cupo({ sinVoces })]);
  const lista = rt.trabajos ?? null;
  const cupo = rc.cupo ?? null;
  const hayArmando = Boolean(lista?.some((t) => t.estado === "armando"));

  return (
    <main className="contenido" data-listo="si">
      <header className="encabezado">
        <h1 className="titulo">{MIS_VIDEOS.titulo}</h1>
      </header>
      <RefrescoMisVideos activo={hayArmando} />

      {cupo ? (
        <div className="mis-cupo">
          <div className="mis-caja mis-mes">
            <p className="mis-rotulo">{MIS_VIDEOS.mes}</p>
            <p className="mis-numero">{cupo.videosMes}</p>
            <p className="nota-chica">{MIS_VIDEOS.noCuentan}</p>
          </div>
          <div className="mis-caja mis-voces">
            <p className="voces-quedan" data-sin={cupo.voces.quedan <= 0 ? "si" : undefined}>
              {CUPO.voces(cupo.voces.quedan, cupo.voces.tope)}
            </p>
          </div>
        </div>
      ) : null}

      {!lista ? (
        <Aviso titulo={MIS_VIDEOS.falla.titulo}>
          <p>{MIS_VIDEOS.falla.texto}</p>
        </Aviso>
      ) : lista.length === 0 ? (
        <section className="mis-vacio" aria-labelledby="mis-vacio">
          <span className="tarjeta-portada" aria-hidden="true">
            <IconoMarca />
          </span>
          <h2 className="mis-vacio-titulo" id="mis-vacio">
            {MIS_VIDEOS.vacio}
          </h2>
          <p className="nota-chica">{MIS_VIDEOS.vacioTexto}</p>
          <Link className="boton boton-principal" href="/">
            {MIS_VIDEOS.primero}
          </Link>
        </section>
      ) : (
        <ul className="mis-lista" aria-label={MIS_VIDEOS.lista}>
          {lista.map((t) => (
            <li key={t.id}>
              <Link className="tarjeta-video" href={`/video/${t.id}`} data-estado={t.estado}>
                <span className="tarjeta-portada" aria-hidden="true" data-con-imagen={t.estado === "listo" ? "si" : undefined}>
                  {t.estado === "listo" ? (
                    // eslint-disable-next-line @next/next/no-img-element -- la portada la sirve el Estudio tal cual, sin pasar por el optimizador
                    <img src={`/api/trabajos/${t.id}/portada`} alt="" loading="lazy" decoding="async" />
                  ) : (
                    <IconoMarca />
                  )}
                </span>
                <span className="tarjeta-cuerpo">
                  <EstadoTrabajo estado={t.estado} />
                  <span className="tarjeta-titular">{t.nota.titular}</span>
                  <span className="tarjeta-datos">
                    {fechaCorta(t.creado)} · {MIS_VIDEOS.largo(t.largo)}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
