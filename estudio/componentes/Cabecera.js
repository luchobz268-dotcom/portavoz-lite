import Link from "next/link";
import { IconoMarca } from "./Iconos";
import NavCabecera from "./NavCabecera";
import { CABECERA, MARCA } from "@/lib/textos";

export default function Cabecera({ ejemplo }) {
  return (
    <header className="cabecera">
      <div className="cabecera-dentro">
        <Link className="identidad" href="/" aria-label={CABECERA.inicio}>
          <IconoMarca />
          <span className="marca">{MARCA.nombre}</span>
          <span className="marca-producto">/&nbsp;&nbsp;{MARCA.producto}</span>
          <span className="marca-app">{MARCA.app}</span>
        </Link>
        <NavCabecera />
        <div className="cabecera-der">
          {ejemplo ? (
            <span className="sello-ejemplo" title={CABECERA.ejemploAyuda}>
              {CABECERA.ejemplo}
            </span>
          ) : null}
        </div>
      </div>
    </header>
  );
}
