import PasoGuion from "@/componentes/PasoGuion";
import { GUION, MARCA } from "@/lib/textos";

export const metadata = { title: `${GUION.titulo} | ${MARCA.titulo}` };

export default function Guion() {
  return <PasoGuion />;
}
