import Link from "next/link";
import VideoTrabajo from "@/componentes/VideoTrabajo";
import { fuente } from "@/lib/fuente";
import { MARCA, VIDEO } from "@/lib/textos";

export const dynamic = "force-dynamic";

// El título de la pestaña dice cómo va desde que se abre la página (después lo sigue cambiando la pantalla).
export async function generateMetadata({ params }) {
  const { id } = await params;
  const t = (await fuente().trabajo(id)).trabajo;
  const nombre = !t ? VIDEO.noEncontrado : t.estado === "listo" ? VIDEO.listo : t.estado === "fallo" ? VIDEO.fallo : VIDEO.armando;
  return { title: `${nombre} | ${MARCA.titulo}` };
}

// Paso 3, "El video": cómo va el armado, el video terminado con sus textos, o por qué no salió.
// Llega ya con lo que hay ahora; mientras se arma, la pantalla sigue preguntando sola (componentes/VideoTrabajo.js).
export default async function Video({ params }) {
  const { id } = await params;
  // trabajo() comprueba la forma del id antes de buscar nada en la carpeta.
  const r = await fuente().trabajo(id);
  const t = r.trabajo;

  if (!t) {
    return (
      <main className="contenido" data-listo="si">
        <header className="encabezado">
          <h1 className="titulo">{VIDEO.noEncontrado}</h1>
          <p className="bajada">{VIDEO.noEncontradoTexto}</p>
        </header>
        <div className="acciones">
          <Link className="boton boton-principal" href="/mis-videos">
            {VIDEO.irAMisVideos}
          </Link>
        </div>
      </main>
    );
  }

  const a = await fuente().avance(id);
  const res = t.estado === "listo" ? await fuente().resultado(id) : null;
  // key: al pasar de un video a otro (por ejemplo, "Probar de nuevo"), la pantalla arranca de cero.
  return <VideoTrabajo key={t.id} inicial={{ trabajo: t, avance: a.avance ?? null, resultado: res?.resultado ?? null }} />;
}
