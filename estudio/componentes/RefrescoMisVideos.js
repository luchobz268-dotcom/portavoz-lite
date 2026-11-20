"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

const CADA = 3000;

/** Mis videos se pone al día solo cada pocos segundos, pero sólo mientras algún video se está armando. */
export default function RefrescoMisVideos({ activo }) {
  const router = useRouter();
  useEffect(() => {
    if (!activo) return undefined;
    const reloj = setInterval(() => router.refresh(), CADA);
    return () => clearInterval(reloj);
  }, [activo, router]);
  return null;
}
