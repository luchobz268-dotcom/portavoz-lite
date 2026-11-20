// Se ESTIMA si una nota es de un tema delicado (política, policiales, tragedia), buscando palabras.
// Acierta la mayoría de las veces pero se equivoca: una nota de un club que "ganó la elección de comisión"
// cae en política. Por eso la pantalla lo muestra y la persona lo ve antes de seguir.
// En la Fase 5 el motor lo decide con más cuidado; esto queda para pegar texto y para los ejemplos.

const PALABRAS = {
  tragedia: ["choque", "chocó", "accidente", "incendio", "inundación", "derrumbe", "víctima", "víctimas", "herido", "heridos", "murió", "muerte", "fallec", "tragedia"],
  crimen: ["asesin", "homicid", "robo", "robaron", "detenid", "policía", "delito", "crimen", "secuestr", "narco", "disparo", "baleado", "fiscal"],
  politica: ["gobierno", "presidente", "presidenta", "diputad", "senador", "ministr", "elecci", "intendente", "gobernador", "congreso", "partido", "campaña", "votación"],
};

/** Devuelve "politica", "crimen", "tragedia" o "general". Gana el tema con más coincidencias. */
export function estimarTema(texto) {
  const t = String(texto || "").toLowerCase();
  let mejor = "general";
  let puntos = 0;
  for (const [tema, lista] of Object.entries(PALABRAS)) {
    const p = lista.reduce((n, raiz) => n + (t.split(raiz).length - 1), 0);
    if (p > puntos) {
      mejor = tema;
      puntos = p;
    }
  }
  return puntos >= 2 ? mejor : "general";
}
