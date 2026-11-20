import { NextResponse } from "next/server";
import { esEjemplo } from "@/lib/fuente";

// Sólo con datos de ejemplo: prende o apaga "hoy ya no quedan voces" con una cookie. Con el motor no existe.
export async function POST(request) {
  if (!esEjemplo()) return NextResponse.json({ error: { codigo: "DESCONOCIDO" } }, { status: 404 });
  let cuerpo = {};
  try {
    cuerpo = await request.json();
  } catch {
    // Sin cuerpo: se apaga.
  }
  const respuesta = NextResponse.json({ sinVoces: Boolean(cuerpo.sinVoces) });
  if (cuerpo.sinVoces) respuesta.cookies.set("simular", "sin-voces", { path: "/", sameSite: "lax", httpOnly: true });
  else respuesta.cookies.delete("simular");
  return respuesta;
}
