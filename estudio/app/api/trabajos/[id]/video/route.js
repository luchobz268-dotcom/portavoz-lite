import { NextResponse } from "next/server";
import { crearError, esIdTrabajo } from "@/lib/contrato";
import { fuente } from "@/lib/fuente";
import { nombreDescarga, servirArchivo } from "@/lib/servir";

export const dynamic = "force-dynamic";

// GET -> el video, por partes si se pide "Range" (206). Con ?bajar=1, se baja con un nombre que se entiende.
export async function GET(request, { params }) {
  const { id } = await params;
  if (!esIdTrabajo(id)) return NextResponse.json(crearError("DESCONOCIDO", "el id del trabajo tiene una forma rara"), { status: 404 });
  const a = await fuente().archivo(id, "video");
  if (a.error) return NextResponse.json(a, { status: 404 });
  const bajar = new URL(request.url).searchParams.get("bajar") === "1";
  return servirArchivo(request, a.archivo, bajar ? nombreDescarga(a.archivo.trabajo) : null);
}
