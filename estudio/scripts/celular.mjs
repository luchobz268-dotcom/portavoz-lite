// Abre el Estudio en el wifi de la casa para probarlo en el celular.
// Arma el Estudio, busca la dirección de esta PC en el wifi y lo prende ahí. Deja escrito el link
// (y lo guarda en capturas/celular-link.txt para el QR de la página de cambios).
// Mientras está prendido, cualquiera conectado al mismo wifi lo puede abrir: se apaga con Ctrl+C.
// La primera vez Windows puede preguntar si deja entrar a Node: marcar "Redes privadas" y "Permitir".
// Uso: npm run celular   (con los ejemplos)
//      npm run real-celular   (con el motor de verdad: gasta pedidos a Google y voces de verdad)
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { networkInterfaces } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("../", import.meta.url));
const PUERTO = 3100;
const NEXT = join(RAIZ, "node_modules", "next", "dist", "bin", "next");

function direccionWifi() {
  const todas = Object.values(networkInterfaces())
    .flat()
    .filter((d) => d && d.family === "IPv4" && !d.internal)
    .map((d) => d.address);
  return todas.find((a) => a.startsWith("192.168.")) || todas.find((a) => a.startsWith("10.")) || todas[0];
}

const ip = direccionWifi();
if (!ip) {
  console.error("No encontré la dirección de esta PC en el wifi. ¿Está conectada?");
  process.exit(1);
}

if (!process.argv.includes("--sin-armar")) {
  console.log("Armando el Estudio...");
  const armado = spawnSync(process.execPath, [NEXT, "build"], { cwd: RAIZ, stdio: "inherit" });
  if (armado.status !== 0) process.exit(armado.status ?? 1);
}

const link = `http://${ip}:${PUERTO}`;
mkdirSync(join(RAIZ, "capturas"), { recursive: true });
writeFileSync(join(RAIZ, "capturas", "celular-link.txt"), `${link}\n`);

const conMotor = process.argv.includes("--motor");
const servidor = spawn(process.execPath, [NEXT, "start", "-H", "0.0.0.0", "-p", String(PUERTO)], {
  cwd: RAIZ,
  env: { ...process.env, PORTAVOZ_FUENTE: conMotor ? "motor" : process.env.PORTAVOZ_FUENTE || "ejemplos", PORTAVOZ_CELULAR: "si" },
  stdio: ["ignore", "pipe", "inherit"],
});
servidor.stdout.on("data", (d) => {
  if (/Ready|started/i.test(String(d))) {
    console.log(`\nListo. En el celular, conectado al mismo wifi, abre:\n\n   ${link}\n\nPara apagarlo: Ctrl+C.`);
  }
});
servidor.on("exit", (codigo) => process.exit(codigo ?? 0));
process.on("SIGINT", () => servidor.kill());
