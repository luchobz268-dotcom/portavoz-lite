import { NextResponse } from "next/server";
import { crearError, esIdTrabajo } from "@/lib/contrato";
import { fuente } from "@/lib/fuente";
import { servirArchivo } from "@/lib/servir";

export const dynamic = "force-dynamic";

// GET -> la portada del video (un cuadro del primer segundo).
export async function GET(request, { params }) {
  const { id } = await params;
  if (!esIdTrabajo(id)) return NextResponse.json(crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara"), { status: 404 });
  const a = await fuente().archivo(id, "portada");
  if (a.error) return NextResponse.json(a, { status: 404 });
  return servirArchivo(request, a.archivo);
}
