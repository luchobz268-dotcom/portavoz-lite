import { NextResponse } from "next/server";
import { crearError } from "@/lib/contrato";
import { fuente } from "@/lib/fuente";

// POST { nota, largo } -> 200 { guiones: [3] } o 422 { error }. El error trae un código, nunca palabras.
export async function POST(request) {
  let pedido;
  try {
    pedido = await request.json();
  } catch {
    return NextResponse.json(crearError("DESCONOCIDO", "el pedido no es JSON"), { status: 400 });
  }
  const respuesta = await fuente().guiones(pedido);
  return NextResponse.json(respuesta, { status: respuesta.error ? 422 : 200 });
}
