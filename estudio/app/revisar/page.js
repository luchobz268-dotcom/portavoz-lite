import { redirect } from "next/navigation";

// "Revisa antes de armar" salió del recorrido el 2026-11-18: "Armar mi video" está abajo de los guiones. La
// dirección queda para los borradores y enlaces viejos, y lleva a los guiones (PasoRevisar.js queda guardado sin usar).
export default function Revisar() {
  redirect("/guion");
}
