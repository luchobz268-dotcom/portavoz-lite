import { cookies } from "next/headers";
import PasoPegar from "@/componentes/PasoPegar";
import { esEjemplo, fuente } from "@/lib/fuente";

export const dynamic = "force-dynamic";

export default async function Inicio({ searchParams }) {
  const ejemplo = esEjemplo();
  const sinVoces = ejemplo && (await cookies()).get("simular")?.value === "sin-voces";
  const respuesta = await fuente().cupo({ sinVoces });
  const vitrina = ejemplo ? fuente().vitrina() : null;
  // Por si se apretó "Leer la nota" antes de que cargara la página: el navegador manda el link en la dirección.
  const q = await searchParams;
  const inicial = typeof q?.link === "string" ? { link: q.link.slice(0, 2000), largo: Number(q.largo) } : null;
  return <PasoPegar ejemplo={ejemplo} vitrina={vitrina} cupo={respuesta.cupo ?? null} sinVoces={sinVoces} inicial={inicial} />;
}
