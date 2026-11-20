import { IconoAviso, IconoInfo } from "./Iconos";

/** Aviso con ícono y título: nunca dice algo sólo con el color. tipo "aviso" (algo falló) o "info". */
export default function Aviso({ tipo = "aviso", titulo, children, acciones, id, enfocable = false }) {
  return (
    <div
      className="aviso"
      data-tipo={tipo}
      role={tipo === "aviso" ? "alert" : "status"}
      id={id}
      tabIndex={enfocable ? -1 : undefined}
    >
      {tipo === "aviso" ? <IconoAviso /> : <IconoInfo />}
      <p className="aviso-titulo">{titulo}</p>
      <div className="aviso-texto">{children}</div>
      {acciones ? <div className="aviso-acciones">{acciones}</div> : null}
    </div>
  );
}
