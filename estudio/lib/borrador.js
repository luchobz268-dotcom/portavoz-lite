// Lo que se está haciendo antes de "Armar mi video" (pedido, nota y, desde el Entregable 2, los guiones)
// se guarda sólo en el navegador. Si el navegador no deja guardar (ventana privada), la app sigue andando:
// sólo se pierde al cerrar.
//
// Forma del borrador:
//   { pedido: { link?, texto?, largo }, nota, guiones: { notaId, lista: [guion x3], elegido }, pantalla, guardado }
//   - guiones.lista: los tres guiones del contrato ({ id, enfoque, versiones, actual }).
//   - guiones.elegido: el id del guion elegido.
//   - pantalla: la última pantalla abierta ("nota", "guion" o "revisar"), para "Seguir donde quedaste".
// Al tocar "Armar mi video" y crearse el trabajo, el borrador se limpia: lo que sigue vive en el trabajo.
const CLAVE = "portavoz-estudio-borrador";

/**
 * A dónde lleva "Seguir" según la última pantalla abierta. Desde el 2026-11-18 "¿Es esta la nota?" y "Revisa antes
 * de armar" ya no existen (todo pasó a los guiones): un borrador viejo guardado en esas pantallas abre en los guiones.
 */
export const PANTALLAS = { nota: "/guion", guion: "/guion", revisar: "/guion" };

export function leerBorrador() {
  try {
    const crudo = window.localStorage.getItem(CLAVE);
    return crudo ? JSON.parse(crudo) : {};
  } catch {
    return {};
  }
}

export function guardarBorrador(cambios) {
  const nuevo = { ...leerBorrador(), ...cambios, guardado: new Date().toISOString() };
  try {
    window.localStorage.setItem(CLAVE, JSON.stringify(nuevo));
  } catch {
    // Sin lugar para guardar: se sigue igual.
  }
  return nuevo;
}

export function limpiarBorrador() {
  try {
    window.localStorage.removeItem(CLAVE);
  } catch {
    // Sin lugar para guardar: no hay nada que limpiar.
  }
}

/**
 * El guion elegido y el texto que tiene ahora (la versión `actual`), o null si no hay guiones para la
 * nota del borrador. Devuelve { guion, version } con version = { texto, palabras, origen }.
 */
export function elegidoDelBorrador(borrador = leerBorrador()) {
  const g = borrador?.guiones;
  if (!g || !borrador.nota || g.notaId !== borrador.nota.id || !Array.isArray(g.lista)) return null;
  const guion = g.lista.find((x) => x.id === g.elegido);
  const version = guion?.versiones?.[guion.actual];
  return guion && version ? { guion, version } : null;
}
