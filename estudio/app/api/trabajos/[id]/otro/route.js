import { NextResponse } from "next/server";
import { crearError, esIdTrabajo } from "@/lib/contrato";
import { fuente } from "@/lib/fuente";

export const dynamic = "force-dynamic";

// POST { campo, red? } -> 200 { resultado } con ese texto cambiado por otro y guardado, o 422 { error }.
// campo: titulo, descripcion, hashtags, etiquetasYoutube o redes (y entonces red dice cuál).
export async function POST(request, { params }) {
  const { id } = await params;
  if (!esIdTrabajo(id)) return NextResponse.json(crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara"), { status: 404 });
  // Un trabajo que no existe es "no está" (404), no un pedido que no se puede cumplir (422).
  const existe = await fuente().trabajo(id);
  if (existe.error) return NextResponse.json(existe, { status: 404 });
  let pedido;
  try {
    pedido = await request.json();
  } catch {
    return NextResponse.json(crearError("DESCONOCIDO", "el pedido no es JSON"), { status: 400 });
  }
  const respuesta = await fuente().otroTexto(id, pedido?.campo, pedido?.red);
  return NextResponse.json(respuesta, { status: respuesta.error ? 422 : 200 });
}
