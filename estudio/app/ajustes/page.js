import Aviso from "@/componentes/Aviso";
import PantallaAjustes from "@/componentes/PantallaAjustes";
import { leerAjustes } from "@/lib/ajustes";
import { AJUSTES, MARCA } from "@/lib/textos";

export const dynamic = "force-dynamic";
export const metadata = { title: `${AJUSTES.titulo} | ${MARCA.titulo}` };

export default async function Ajustes() {
  const ajustes = await leerAjustes();
  return (
    <main className="contenido" data-listo="si">
      <header className="encabezado">
        <h1 className="titulo">{AJUSTES.titulo}</h1>
        <p className="bajada">{AJUSTES.bajada}</p>
      </header>
      {ajustes ? <PantallaAjustes inicial={ajustes} /> : <Aviso titulo={AJUSTES.falla} />}
    </main>
  );
}
