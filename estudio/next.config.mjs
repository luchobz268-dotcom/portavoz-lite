/** El Estudio corre con servidor (lee notas, guarda trabajos). Nunca se publica: anda en la PC de Lucio
 *  y, cuando se prende con `npm run celular`, en el wifi de la casa. */
// PORTAVOZ_ARMADO: la carpeta donde se arma. El arranque (scripts/arrancar.mjs) arma una versión nueva en
// .next-nuevo y sólo si sale bien la pone en lugar de .next, así una actualización rota no deja sin Estudio.
const config = {
  distDir: process.env.PORTAVOZ_ARMADO || ".next",
  poweredByHeader: false,
  reactStrictMode: true,
};
export default config;
