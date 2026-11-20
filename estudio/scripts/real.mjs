// Prende el Estudio con el motor de verdad (lee notas de verdad, escribe con Claude, graba la voz con Google y arma el video).
// Arma el Estudio (salvo con --sin-armar) y lo prende en esta PC: http://127.0.0.1:3100. Se apaga con Ctrl+C.
// Cada video gasta pedidos a Claude (del cupo de la suscripción), pedidos a Google y una voz del día. Los videos quedan en ../trabajos (o en PORTAVOZ_TRABAJOS).
// Uso: npm run real   (npm run real -- --sin-armar para no volver a armarlo)
import { spawn, spawnSync } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = fileURLToPath(new URL("../", import.meta.url));
const PUERTO = 3100;
const NEXT = join(RAIZ, "node_modules", "next", "dist", "bin", "next");

if (!process.argv.includes("--sin-armar")) {
  console.log("Armando el Estudio...");
  const armado = spawnSync(process.execPath, [NEXT, "build"], { cwd: RAIZ, stdio: "inherit" });
  if (armado.status !== 0) process.exit(armado.status ?? 1);
}

const servidor = spawn(process.execPath, [NEXT, "start", "-H", "127.0.0.1", "-p", String(PUERTO)], {
  cwd: RAIZ,
  env: { ...process.env, PORTAVOZ_FUENTE: "motor" },
  stdio: ["ignore", "pipe", "inherit"],
});
servidor.stdout.on("data", (d) => {
  if (/Ready|started/i.test(String(d))) {
    console.log(`\nListo, con el motor de verdad. Abre:\n\n   http://127.0.0.1:${PUERTO}\n\nPara apagarlo: Ctrl+C.`);
  }
});
servidor.on("exit", (codigo) => process.exit(codigo ?? 0));
process.on("SIGINT", () => servidor.kill());
