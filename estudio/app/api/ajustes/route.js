import { NextResponse } from "next/server";
import { elegirQuienEscribe, leerAjustes, ponerLlave, soloMirar } from "@/lib/ajustes";

export const dynamic = "force-dynamic";

// GET  -> { ajustes }: quién escribe y qué llaves hay (sólo los últimos 4 caracteres de cada una).
// POST { llave, valor } -> { resultado: "guardada" | "mala" | "sin-internet" | "vacia" }: prueba la llave y la guarda.
// POST { escribe }      -> { resultado: "guardado" }: quién escribe los guiones ("", "claude", "anthropic", "google").
// Los cambios se aceptan sólo desde esta misma compu: nunca con el Estudio abierto al wifi, nunca desde otra página
// (el pedido tiene que venir de la propia pantalla de Ajustes, 127.0.0.1 o localhost) y sólo como JSON.

export async function GET() {
  const ajustes = await leerAjustes();
  if (!ajustes) return NextResponse.json({ error: "sin-ajustes" }, { status: 503 });
  return NextResponse.json({ ajustes });
}

function deEstaCompu(pedido) {
  const origen = pedido.headers.get("origin");
  if (!origen) return false;
  try {
    const { hostname } = new URL(origen);
    return hostname === "127.0.0.1" || hostname === "localhost";
  } catch {
    return false;
  }
}

export async function POST(pedido) {
  if (soloMirar() || !deEstaCompu(pedido)) return NextResponse.json({ error: "solo-mirar" }, { status: 403 });
  if (!(pedido.headers.get("content-type") || "").includes("application/json")) {
    return NextResponse.json({ error: "pedido-raro" }, { status: 400 });
  }
  let cuerpo;
  try {
    cuerpo = await pedido.json();
  } catch {
    return NextResponse.json({ error: "pedido-raro" }, { status: 400 });
  }
  if (cuerpo && typeof cuerpo.llave === "string") {
    const resultado = await ponerLlave(cuerpo.llave, typeof cuerpo.valor === "string" ? cuerpo.valor : "");
    return NextResponse.json({ resultado }, { status: resultado === "guardada" ? 200 : 422 });
  }
  if (cuerpo && typeof cuerpo.escribe === "string") {
    return elegirQuienEscribe(cuerpo.escribe)
      ? NextResponse.json({ resultado: "guardado" })
      : NextResponse.json({ error: "pedido-raro" }, { status: 400 });
  }
  return NextResponse.json({ error: "pedido-raro" }, { status: 400 });
}
