import { IconoAviso, IconoCheck, IconoReloj } from "./Iconos";
import { MIS_VIDEOS } from "@/lib/textos";

const ICONOS = { armando: IconoReloj, listo: IconoCheck, fallo: IconoAviso };

/** El estado de un trabajo con ícono y palabra: nunca sólo con el color. */
export default function EstadoTrabajo({ estado }) {
  const Icono = ICONOS[estado] || IconoReloj;
  return (
    <span className="estado-trabajo" data-estado={estado}>
      <Icono tam={14} />
      <span>{MIS_VIDEOS.estados[estado] || estado}</span>
    </span>
  );
}
