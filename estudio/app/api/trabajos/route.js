import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { crearError } from "@/lib/contrato";
import { esEjemplo, fuente } from "@/lib/fuente";

export const dynamic = "force-dynamic";

// Con datos de ejemplo, el interruptor "Simular que hoy ya no quedan voces" deja esta galletita.
const simulaSinVoces = async () => esEjemplo() && (await cookies()).get("simular")?.value === "sin-voces";

// GET -> { trabajos, cupo }: lo que muestra Mis videos. Si algo no se puede leer, 503 { error }.
export async function GET() {
  const [t, c] = await Promise.all([fuente().trabajos(), fuente().cupo({ sinVoces: await simulaSinVoces() })]);
  if (t.error) return NextResponse.json(t, { status: 503 });
  if (c.error) return NextResponse.json(c, { status: 503 });
  return NextResponse.json({ trabajos: t.trabajos, cupo: c.cupo });
}

// POST { nota, largo, guion: { enfoque, texto }, pedido?, guiones?, reintentoDe?, encargo? } -> 200 { trabajo } o 422 { error }.
// El id lo arma el Estudio. pedido es lo del Paso 1 y guiones los tres del Paso 2 (la forma de lib/borrador.js):
// el elegido, en su versión actual, tiene que ser el mismo guion que `guion`. encargo es la marca que pone la
// pantalla: si ya creó un trabajo, se devuelve ése (ver esEncargo en lib/contrato.js).
export async function POST(request) {
  let pedido;
  try {
    pedido = await request.json();
  } catch {
    return NextResponse.json(crearError("DESCONOCIDO", "el pedido no es JSON"), { status: 400 });
  }
  const respuesta = await fuente().crearTrabajo({
    nota: pedido?.nota,
    largo: pedido?.largo,
    guion: pedido?.guion,
    ...(pedido?.pedido !== undefined ? { pedido: pedido.pedido } : {}),
    ...(pedido?.guiones !== undefined ? { guiones: pedido.guiones } : {}),
    ...(pedido?.reintentoDe !== undefined ? { reintentoDe: pedido.reintentoDe } : {}),
    ...(pedido?.encargo !== undefined ? { encargo: pedido.encargo } : {}),
    sinVoces: await simulaSinVoces(),
  });
  return NextResponse.json(respuesta, { status: respuesta.error ? 422 : 200 });
}
