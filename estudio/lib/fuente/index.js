// De dónde salen los datos: de los ejemplos inventados o del motor de verdad.
// Se elige con PORTAVOZ_FUENTE=ejemplos|motor (sin nada, ejemplos). Las dos fuentes cumplen el mismo
// contrato (lib/contrato.js), así la pantalla no sabe ni le importa cuál está andando.
import * as ejemplos from "./ejemplos.js";
import * as motor from "./motor.js";

export const nombreFuente = () => (process.env.PORTAVOZ_FUENTE === "motor" ? "motor" : "ejemplos");
export const fuente = () => (nombreFuente() === "motor" ? motor : ejemplos);
export const esEjemplo = () => nombreFuente() === "ejemplos";
