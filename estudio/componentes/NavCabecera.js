"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CABECERA } from "@/lib/textos";

const ENLACES = [
  { href: "/", texto: CABECERA.nuevo },
  { href: "/mis-videos", texto: CABECERA.misVideos },
  { href: "/ajustes", texto: CABECERA.ajustes },
];

/** Los lugares del Estudio. El de la pantalla abierta queda marcado (también para lectores de pantalla). */
export default function NavCabecera() {
  const ruta = usePathname();
  return (
    <nav className="cabecera-nav" aria-label={CABECERA.navegacion}>
      {ENLACES.map((e) => (
        <Link key={e.href} className="cabecera-enlace" href={e.href} aria-current={ruta === e.href ? "page" : undefined}>
          {e.texto}
        </Link>
      ))}
    </nav>
  );
}
