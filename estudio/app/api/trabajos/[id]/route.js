import { NextResponse } from "next/server";
import { crearError, esIdTrabajo } from "@/lib/contrato";
import { fuente } from "@/lib/fuente";

export const dynamic = "force-dynamic";

const noEsta = (detalle) => NextResponse.json(crearError("DESCONOCIDO", detalle), { status: 404 });

// GET -> { trabajo, avance, resultado? }: cómo va un video. resultado sólo cuando está listo. 404 { error } si no existe.
export async function GET(_request, { params }) {
  const { id } = await params;
  if (!esIdTrabajo(id)) return noEsta("el id del trabajo tiene una forma rara");
  let a = await fuente().avance(id);
  if (a.error) return NextResponse.json(a, { status: 404 });
  const t = await fuente().trabajo(id);
  if (t.error) return NextResponse.json(t, { status: 404 });
  // Si justo terminó o falló entre las dos lecturas, el avance se vuelve a pedir para que digan lo mismo.
  if (t.trabajo.estado !== "armando") a = await fuente().avance(id);
  if (a.error) return NextResponse.json(a, { status: 404 });
  const r = t.trabajo.estado === "listo" ? await fuente().resultado(id) : null;
  return NextResponse.json({ trabajo: t.trabajo, avance: a.avance, ...(r?.resultado ? { resultado: r.resultado } : {}) });
}
