import { redirect } from "next/navigation";

// "¿Es esta la nota?" salió del recorrido el 2026-11-18: el link lleva directo a los guiones. La dirección queda
// para los borradores y enlaces viejos, y lleva a los guiones (PasoConfirmar.js queda guardado sin usar).
export default function Nota() {
  redirect("/guion");
}
