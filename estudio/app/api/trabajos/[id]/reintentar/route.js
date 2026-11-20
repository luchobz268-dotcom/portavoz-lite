import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { crearError, esIdTrabajo } from "@/lib/contrato";
import { esEjemplo, fuente } from "@/lib/fuente";

export const dynamic = "force-dynamic";

const simulaSinVoces = async () => esEjemplo() && (await cookies()).get("simular")?.value === "sin-voces";

// POST -> 200 { trabajo } (uno nuevo, con los mismos datos y reintentoDe) o 422 { error }. Gasta una voz.
export async function POST(_request, { params }) {
  const { id } = await params;
  if (!esIdTrabajo(id)) return NextResponse.json(crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara"), { status: 404 });
  // Un trabajo que no existe es "no está" (404), no un pedido que no se puede cumplir (422).
  const existe = await fuente().trabajo(id);
  if (existe.error) return NextResponse.json(existe, { status: 404 });
  const respuesta = await fuente().reintentar(id, { sinVoces: await simulaSinVoces() });
  return NextResponse.json(respuesta, { status: respuesta.error ? 422 : 200 });
}
