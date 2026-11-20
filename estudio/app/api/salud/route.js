import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// GET -> { portavoz: "lite" }: el arranque (scripts/arrancar.mjs) pregunta acá si el que está en el lugar 3100 es
// Portavoz Lite (doble clic repetido: sólo abre el navegador) o es otro programa.
export function GET() {
  return NextResponse.json({ portavoz: "lite" });
}
