// Todos los textos que ve la persona en el Estudio. BORRADORES del asistente: Lucio todavía no los aprobó.
// Reglas del autor: sin rayas largas, sin jerga, sin números escritos a mano
// (salen de lib/contrato.js), tuteo neutro ("Pega", "Elige"), "video" sin tilde y nunca "créditos".
// scripts/revisar.mjs lee este archivo y falla si algo de eso se cuela.

import { PALABRAS_MINIMAS_NOTA, TOPE_VOCES_DIA } from "./contrato.js";

export const MARCA = {
  nombre: "PORTAVOZ",
  producto: "LITE",
  app: "Estudio",
  titulo: "Estudio | Portavoz Lite",
  descripcion: "Pega el link de una noticia y sale un video vertical para redes.",
  // La firma del autor: la licencia pide que quede a la vista en las pantallas, también en una copia cambiada.
  firma: "Lucio B. - lucio@lidr.ar",
};

export const CABECERA = {
  inicio: "Ir al inicio del Estudio",
  nuevo: "Nuevo video",
  misVideos: "Mis videos",
  ajustes: "Ajustes",
  ejemplo: "Datos de ejemplo",
  ejemploAyuda: "Las noticias y los videos de esta versión son inventados, para probar las pantallas.",
  navegacion: "Secciones del Estudio",
};

export const PASOS = {
  de: (n, total) => `Paso ${n} de ${total}`,
  nombres: ["La nota", "El guion", "El video"],
  etiqueta: "En qué paso estás",
};

export const PEGAR = {
  titulo: "Pega la nota",
  bajada: "Copia el link de la noticia, pégalo aquí y la leemos por ti.",
  etiquetaLink: "Link de la nota",
  ejemploLink: "https://tudiario.com/la-noticia",
  botonPegar: "Pegar",
  pegarNoSe: "Tu navegador no deja pegar con este botón. Mantén apretado el cuadro y elige Pegar.",
  aTexto: "Prefiero pegar el texto",
  aLink: "Prefiero pegar el link",
  etiquetaTexto: "Texto de la nota",
  ayudaTexto: "Pega la nota completa. La primera línea se usa como título.",
  largoTitulo: "¿Qué largo quieres?",
  largos: {
    15: { nombre: "Corto", para: "Un dato o un titular" },
    30: { nombre: "Medio", para: "Lo más visto en redes" },
    60: { nombre: "Largo", para: "Para contar con contexto" },
  },
  segundos: (s) => `${s} segundos`,
  palabras: (n) => `unas ${n} palabras`,
  boton: "Leer la nota",
  leyendo: "Leyendo la nota",
  nadaSeGasta: "Hasta que aprietes Armar mi video, no se gasta nada.",
  faltaLink: "Pega el link de la nota para seguir.",
  faltaTexto: "Pega el texto de la nota para seguir.",
  quedanVoces: "Voces para hoy",
  aMedio: "Tienes un video a medio hacer",
  seguir: "Seguir",
};

export const COMO_SIGUE = {
  titulo: "Cómo sigue",
  pasos: [
    { nombre: "La nota", texto: "Pegas el link de la noticia o, si no abre, su texto." },
    { nombre: "El guion", texto: "Te proponemos tres guiones. Eliges uno y lo corriges si quieres." },
    {
      nombre: "El video",
      texto: "Lo armamos con imágenes de archivo reales, voz y subtítulos. Lo bajas con los textos para cada red.",
    },
  ],
  nuncaIA: "Nunca usamos video inventado por inteligencia artificial.",
};

export const CONFIRMAR = {
  titulo: "¿Es esta la nota?",
  bajada: "Revisa que sea la noticia correcta antes de escribir los guiones.",
  medio: "Medio",
  fecha: "Fecha",
  largoNota: "Largo de la nota",
  palabras: (n) => `${n} palabras`,
  sinFecha: "Sin fecha",
  textoPegado: "Texto pegado",
  verTodo: "Ver la nota completa",
  verMenos: "Ver menos",
  abrirOriginal: "Abrir la nota original",
  video: "Tu video",
  largoElegido: (s) => `${s} segundos`,
  cambiarLargo: "Cambiar el largo",
  si: "Sí, escribir los guiones",
  no: "No, es otra nota",
  sensibleTitulo: "Es un tema delicado",
  sensibleTexto:
    "Usamos solo imágenes de ambiente, sin personas que se puedan reconocer, y un subtítulo más sobrio.",
  temas: { politica: "Política", crimen: "Policiales", tragedia: "Tragedia" },
  tema: "Tema",
  cargando: "Cargando la nota",
  sinNota: "No hay ninguna nota cargada. Empieza pegando el link.",
  volverAlInicio: "Pegar una nota",
};

export const GUION = {
  titulo: "Elige y corrige el guion",
  bajada: "Te proponemos tres guiones para la misma nota. Elige uno y cámbialo como quieras: es lo que va a decir la voz del video.",
  deLaNota: "De la nota",
  escribiendo: "Escribiendo tres guiones",
  // Aparece en la espera, un rato después de "Escribiendo tres guiones" o de "Escribiendo otro guion".
  revisando: "Revisando los guiones",
  // El mismo aviso cuando se revisa uno solo (después de "Escribir otro").
  revisandoUno: "Revisando el guion",
  cargando: "Cargando los guiones",
  pestanas: "Los tres guiones",
  enfoques: {
    dato: { nombre: "El dato", que: "Lo más importante de la nota, directo." },
    "te-cambia": { nombre: "Qué te cambia", que: "Qué cambia para quien mira." },
    debate: { nombre: "Para debatir", que: "Termina con una pregunta para que comenten." },
  },
  // Las fotos de la nota en el video (etapa 4). El resto de los textos de esta parte llega con la pantalla de fotos.
  fotos: {
    formas: { pantalla: "Pantalla completa", encima: "Encima del clip" },
  },
  elegido: "Elegido",
  elegir: "Elegir este",
  elegirEste: (nombre) => `Elegir ${nombre}`,
  cuadro: (nombre) => `Texto del guion: ${nombre}`,
  duracion: (s, largo) => `unos ${s} s de ${largo}`,
  sePasa: (s, largo) => `Se pasa: unos ${s} s de ${largo}`,
  masCorto: "Más corto",
  masSimple: "Más simple",
  deshacer: "Deshacer",
  escribirOtro: "Escribir otro",
  cambiando: {
    corto: "Acortando el guion",
    simple: "Simplificando el guion",
    otro: "Escribiendo otro guion",
  },
  fallaCambio: {
    titulo: "No se pudo cambiar este guion",
    texto: "Tu texto quedó como estaba.",
  },
  errorLargo: (s, largo) =>
    `Este guion dura unos ${s} s y tu video es de ${largo}. Toca Más corto o borra algunas frases.`,
  errorVacio: "Escribe el guion para seguir. También puedes tocar Escribir otro.",
  // Una línea en el guion cuando la revisión encontró algo que no pudo arreglar sola (AVISOS_REVISION en contrato.js).
  avisos: {
    DATO_NO_ESTA: "Revisa este guion: dice algo que no encontramos en la nota.",
    VERBO_CAMBIADO: "Revisa este guion: cuenta como hecho algo que la nota dice que va a pasar.",
  },
  // Desde el 2026-11-18 no hay pantalla de la nota: lleva al paso 1, con el link todavía escrito.
  volver: "Cambiar la nota",
  guardado: "Guardado",
};

export const REVISAR = {
  titulo: "Revisa antes de armar",
  bajada: "Así va a salir tu video. Si algo no te convence, todavía lo puedes cambiar.",
  cargando: "Cargando lo que preparaste",
  laNota: "La nota",
  largo: "Largo del video",
  segundos: (s) => `${s} segundos`,
  elGuion: "El guion",
  cambiarGuion: "Cambiar el guion",
  pie: "Al pie del video",
  fuente: (medio) => `Fuente: ${medio}`,
  sinFuente: "Sin fuente: pegaste el texto de la nota",
  ilustrativas: "Imágenes ilustrativas",
  voces: "Voces",
  siFalla: "Si falla, no cuenta.",
  armar: "Armar mi video",
  armando: "Armando…",
  volver: "Volver al guion",
  sinVocesMotivo: "Hoy ya no quedan voces. Tu guion queda guardado para mañana.",
  noEntra: {
    titulo: "El guion dura más que el video",
    texto: "Vuelve al guion y toca Más corto, o borra algunas frases.",
  },
  sinGuion: "Todavía no elegiste un guion. Vuelve al guion para elegir uno.",
  irAlGuion: "Ir al guion",
};

export const VIDEO = {
  armando: "Estamos armando tu video",
  listo: "Tu video está listo",
  fallo: "Tu video no salió",
  bajada: "Ya quedó guardado en Mis videos.",
  puedesCerrar: "Puedes cerrar esta página: queda en Mis videos.",
  avance: "Cómo va tu video",
  faltan: (s) => (s <= 5 ? "Ya casi está" : s < 90 ? `Faltan unos ${s} segundos` : `Faltan unos ${Math.round(s / 60)} minutos`),
  fila: (n) =>
    n === 1
      ? "Hay un video antes que el tuyo. El tuyo arranca apenas termine."
      : `Hay ${n} videos antes que el tuyo. El tuyo arranca apenas terminen.`,
  estadosEtapa: { espera: "En espera", haciendo: "Haciéndose", listo: "Listo", fallo: "No salió" },
  sinConexion: "Se cortó la conexión. Lo seguimos intentando y no se pierde nada.",
  reproductor: (titular) => `Tu video: ${titular}`,
  bajar: "Bajar el video",
  textos: "Textos para publicar",
  textosBajada: "Uno para cada red. Copia el que necesites y pégalo al publicar.",
  redes: "Redes",
  campos: { texto: "Texto", hashtags: "Hashtags", titulo: "Título", descripcion: "Descripción", etiquetas: "Etiquetas" },
  contador: (n, tope) => `${n} de ${tope}`,
  copiar: "Copiar",
  copiado: "Copiado",
  copiarAMano: "Mantén apretado el texto y elige Copiar.",
  pedirOtro: "Pedir otro",
  llegoOtro: (texto) => `Llegó otro texto: ${texto}`,
  noLlegoOtro: "No pudimos traer otro. Prueba de nuevo en un rato.",
  anuncioListo: "Tu video está listo. Ya puedes verlo y bajarlo.",
  anuncioFallo: "Tu video no salió.",
  probando: "Probando de nuevo…",
  irAMisVideos: "Ir a Mis videos",
  otro: "Hacer otro video",
  noEncontrado: "No encontramos ese video",
  noEncontradoTexto: "Puede que el link esté incompleto. Todos tus videos están en Mis videos.",
};

export const MIS_VIDEOS = {
  titulo: "Mis videos",
  mes: "Videos este mes",
  noCuentan: "Los que fallan no cuentan.",
  vacio: "Todavía no hay videos",
  vacioTexto: "Cuando toques Armar mi video, tu video aparece aquí.",
  primero: "Hacer mi primer video",
  lista: "Tus videos",
  largo: (s) => `${s} segundos`,
  estados: { armando: "Armando", listo: "Listo", fallo: "No salió" },
  falla: {
    titulo: "No pudimos mostrar tus videos",
    texto: "Siguen guardados. Prueba de nuevo en un rato.",
  },
};

export const ERRORES = {
  LINK_INVALIDO: {
    titulo: "Ese link no parece completo",
    texto: "Revisa que empiece con https:// y que esté entero.",
  },
  LINK_NO_ABRE: {
    titulo: "No pudimos abrir esa página",
    texto: "Puede estar caída o pedir que inicies sesión. Pega el texto de la nota aquí abajo y seguimos.",
  },
  NOTA_SIN_TEXTO: {
    titulo: "En esa página no hay una nota para leer",
    texto: "Puede ser una portada o una página de videos. Pega el texto de la nota aquí abajo y seguimos.",
  },
  MURO_DE_PAGO: {
    titulo: "Esa nota es solo para suscriptores",
    texto: "No la podemos leer desde afuera. Si la tienes abierta, copia el texto y pégalo aquí abajo.",
  },
  NOTA_MUY_CORTA: {
    titulo: "La nota es muy corta para un video",
    texto: `Necesitamos por lo menos ${PALABRAS_MINIMAS_NOTA} palabras. Pega el texto completo de la nota.`,
  },
  SIN_VOCES_HOY: {
    titulo: "Hoy ya no quedan voces",
    texto: `Se pueden grabar ${TOPE_VOCES_DIA} voces por día. Puedes preparar la nota y el guion ahora y armar el video mañana.`,
  },
  GUION_A_CORREGIR: {
    titulo: "Hay que revisar el guion",
    texto: "Está vacío o dura más que el video. Vuelve al guion para corregirlo. No se gastó nada.",
  },
  SIN_CLIPS: {
    titulo: "No encontramos imágenes para este guion",
    texto: "No se gastó nada y tu guion está guardado. Prueba con otro guion o con palabras más generales.",
  },
  FALLO_VOZ: {
    titulo: "No se pudo grabar la voz",
    texto: "No se gastó nada y tu guion está guardado. Prueba de nuevo en un rato.",
  },
  FALLO_ARMADO: {
    titulo: "El video no se pudo armar",
    texto: "No se gastó nada y tu guion está guardado. Prueba de nuevo.",
  },
  SIN_CONEXION: {
    titulo: "Se cortó la conexión",
    texto: "Revisa el wifi y prueba de nuevo. No se perdió nada.",
  },
  DESCONOCIDO: {
    titulo: "Algo salió mal",
    texto: "No se gastó nada. Prueba de nuevo en un rato.",
  },
};

export const SALIDAS = {
  corregir: "Corregir",
  "pegar-texto": "Pegar el texto",
  reintentar: "Probar de nuevo",
  "volver-al-guion": "Volver al guion",
  manana: "Entendido",
};

export const CUPO = {
  voces: (quedan, tope) => `Quedan ${quedan} de ${tope} voces hoy`,
};

export const EJEMPLOS = {
  titulo: "Probar con un ejemplo",
  bajada: "En esta versión las noticias son inventadas. Toca una para cargar su link.",
  notas: "Noticias de ejemplo",
  errores: "Para ver qué pasa cuando algo falla",
  sensible: "Tema delicado",
  cualquierLink: "Con cualquier otro link vas a ver una de estas noticias de ejemplo.",
  sinVoces: "Simular que hoy ya no quedan voces",
  fallas: {
    "muro-de-pago": "Nota para suscriptores",
    "no-abre": "Página que no abre",
    "sin-texto": "Página sin nota",
    "sin-clips": "Sin imágenes para el guion",
    "falla-armado": "Falla al armar el video",
  },
};

// Las etapas del armado, en el orden de ETAPAS en lib/contrato.js.
export const ETAPAS = {
  clips: "Buscando imágenes",
  voz: "Grabando la voz",
  tiempos: "Acomodando los subtítulos",
  armado: "Armando el video",
  textos: "Escribiendo los textos",
};

// Los nombres de las redes, en el orden de REDES en lib/contrato.js.
export const REDES = {
  tiktok: "TikTok",
  instagram: "Instagram",
  youtube: "YouTube",
  facebook: "Facebook",
  x: "X",
  linkedin: "LinkedIn",
};

// Lo que dice la ventanita del arranque (scripts/arrancar.mjs), la que abre el ícono del escritorio.
export const ARRANQUE = {
  yaPrendido: "Portavoz Lite ya estaba prendido. Te abro el navegador.",
  puertoAjeno: "Otro programa está usando el lugar donde se prende Portavoz Lite. Ciérralo y vuelve a intentar.",
  buscando: "Buscando novedades...",
  sinInternet: "No pude buscar novedades (¿hay internet?). Sigo con la versión que tienes.",
  alDia: "Tienes la última versión.",
  cambiosPropios:
    "No actualicé porque hay archivos del programa cambiados en esta carpeta. No toqué nada tuyo. Si no los cambiaste a propósito, pídele a Claude: \"Revisa mi Portavoz Lite\".",
  desviada:
    "No actualicé porque esta copia tiene cambios guardados que no están en la versión publicada. No toqué nada tuyo. Pídele a Claude: \"Revisa mi Portavoz Lite\".",
  versionMala: "Hay una versión nueva, pero la última vez no arrancó. Sigo con la que anda y espero la próxima.",
  actualizando: "Hay una versión nueva. La preparo, puede tardar un par de minutos...",
  actualizada: "Listo, ya tienes la versión nueva.",
  fallo: "La versión nueva no arrancó. Volví a la que andaba y la próxima vez espero una más nueva.",
  noSePudo: "No pude traer la versión nueva. Sigo con la que tienes.",
  primeraVez: "Preparando Portavoz Lite por primera vez, puede tardar un par de minutos...",
  sinArmado: "No pude preparar Portavoz Lite. Pídele a Claude: \"Revisa mi Portavoz Lite\".",
  faltanLlaves: (que) => `Faltan llaves: ${que}. Te abro Ajustes para ponerlas.`,
  faltaGoogle: "la de Google (para la voz)",
  faltaPexels: "la de Pexels (para los clips)",
  prendiendo: "Prendiendo Portavoz Lite...",
  prendido: (link) => `Portavoz Lite está prendido en ${link}\nPara apagarlo, cierra esta ventana.`,
  noPrendio: "Portavoz Lite no se pudo prender. Pídele a Claude: \"Revisa mi Portavoz Lite\".",
  cerrar: "Aprieta Enter para cerrar esta ventana.",
};

// La pantalla Ajustes (app/ajustes): quién escribe los guiones y las llaves. Las llaves nunca se muestran enteras.
export const AJUSTES = {
  titulo: "Ajustes",
  bajada: "Quién escribe los guiones y tus llaves. Las llaves quedan guardadas sólo en esta computadora.",
  escribeTitulo: "Quién escribe los guiones",
  escribeAhora: (quien) => `Ahora los escribe ${quien}.`,
  quien: {
    claude: "Claude, con tu Claude Code",
    anthropic: "Claude, con tu llave de Anthropic",
    google: "Google",
  },
  opciones: {
    "": { nombre: "El primero que ande", ayuda: "Primero Claude Code, después la llave de Anthropic, al final Google." },
    claude: { nombre: "Claude Code", ayuda: "Usa tu suscripción de Claude. Es lo que mejor escribe." },
    anthropic: { nombre: "Llave de Anthropic", ayuda: "Para cuando no tienes Claude Code. Se paga aparte, por uso." },
    google: { nombre: "Google", ayuda: "Usa la misma llave de la voz." },
  },
  sinClaudeCode: "No encontramos Claude Code en esta computadora.",
  llavesTitulo: "Tus llaves",
  llaves: {
    google: {
      nombre: "Google",
      para: "La voz y lo que dice cada segundo.",
      sacar: "Sacar una llave de Google",
      link: "https://aistudio.google.com/apikey",
      nota: "Crea un proyecto nuevo para Portavoz Lite: el tope de voces por día es por proyecto.",
    },
    pexels: {
      nombre: "Pexels",
      para: "Los clips de fondo.",
      sacar: "Sacar una llave de Pexels",
      link: "https://www.pexels.com/api/",
      nota: "Es gratis. Te pide una cuenta de Pexels.",
    },
    anthropic: {
      nombre: "Anthropic",
      para: "Que Claude escriba sin Claude Code.",
      sacar: "Sacar mi llave de Claude",
      link: "https://console.anthropic.com/settings/keys",
      nota: "Si tienes Claude Max, tu plan trae dinero para esto todos los meses. Se conecta desde la facturación de claude.ai.",
      notaLink: "https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers",
      notaLinkTexto: "Cómo se conecta",
    },
  },
  terminaEn: (fin) => `Guardada, termina en ${fin}`,
  sinLlave: "Sin llave",
  prestadas: "Usa las llaves prestadas de esta computadora.",
  cambiar: "Cambiar",
  poner: "Poner la llave",
  rotuloNueva: (nombre) => `Llave nueva de ${nombre}`,
  guardar: "Probar y guardar",
  cancelar: "Cancelar",
  probando: "Probando la llave...",
  guardada: "Listo, la llave anda y quedó guardada.",
  mala: "Esa llave no anda. Fíjate que la copiaste entera.",
  sinInternet: "No pude probarla porque parece que no hay internet. Vuelve a intentar en un rato.",
  vacia: "Pega la llave para seguir.",
  guardadoEscribe: "Listo, quedó guardado.",
  soloMirar: "Desde aquí sólo se puede mirar. Los cambios se hacen abriendo Portavoz Lite con el ícono de la computadora.",
  falla: "No pude leer los ajustes. Vuelve a intentar en un rato.",
  noGuardo: "No pude guardar el cambio. Vuelve a intentar en un rato.",
};
