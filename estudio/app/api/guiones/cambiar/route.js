import { NextResponse } from "next/server";
import { crearError } from "@/lib/contrato";
import { fuente } from "@/lib/fuente";

// POST { nota, largo, enfoque, texto, accion } -> 200 { version } o 422 { error }.
// accion es "corto", "simple" u "otro" (CAMBIOS en lib/contrato.js).
export async function POST(request) {
  let pedido;
  try {
    pedido = await request.json();
  } catch {
    return NextResponse.json(crearError("DESCONOCIDO", "el pedido no es JSON"), { status: 400 });
  }
  const respuesta = await fuente().cambiarGuion(pedido);
  return NextResponse.json(respuesta, { status: respuesta.error ? 422 : 200 });
}
