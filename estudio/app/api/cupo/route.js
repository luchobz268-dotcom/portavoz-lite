import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { esEjemplo, fuente } from "@/lib/fuente";

export const dynamic = "force-dynamic";

// GET -> { cupo }: cuántas voces quedan hoy y cuántos videos van en el mes.
export async function GET() {
  const sinVoces = esEjemplo() && (await cookies()).get("simular")?.value === "sin-voces";
  const respuesta = await fuente().cupo({ sinVoces });
  return NextResponse.json(respuesta, { status: respuesta.error ? 503 : 200 });
}
