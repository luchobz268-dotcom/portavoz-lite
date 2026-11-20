import { PASOS } from "@/lib/textos";

/** "Paso N de 3" con las tres etapas: la nota, el guion, el video. */
export default function Pasos({ actual }) {
  const total = PASOS.nombres.length;
  return (
    <nav className="pasos" aria-label={PASOS.etiqueta}>
      <p className="pasos-numero">{PASOS.de(actual, total)}</p>
      <ol className="pasos-lista">
        {PASOS.nombres.map((nombre, i) => {
          const n = i + 1;
          const estado = n < actual ? "hecho" : n === actual ? "actual" : "falta";
          return (
            <li key={nombre} className="paso" data-estado={estado} aria-current={estado === "actual" ? "step" : undefined}>
              {nombre}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
