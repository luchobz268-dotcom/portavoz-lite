import localFont from "next/font/local";
import "./globals.css";
import Cabecera from "@/componentes/Cabecera";
import { esEjemplo } from "@/lib/fuente";
import { MARCA } from "@/lib/textos";

// La cabecera dice si el Estudio anda con ejemplos o con el motor, y eso se elige al prenderlo (PORTAVOZ_FUENTE), no al
// armarlo: ninguna página se guarda hecha de antemano con lo que había al armar.
export const dynamic = "force-dynamic";

// Las mismas tres letras de la landing, guardadas adentro: no se piden a Google al abrir la página.
const inter = localFont({ src: "./fonts/Inter-variable.ttf", weight: "100 900", variable: "--letra-pantalla", display: "swap" });
const cormorant = localFont({
  src: "./fonts/CormorantGaramond-variable.ttf",
  weight: "300 700",
  variable: "--letra-titulos",
  display: "swap",
});
const mono = localFont({ src: "./fonts/IBMPlexMono-Bold.ttf", weight: "700", variable: "--letra-numeros", display: "swap" });

export const metadata = {
  title: MARCA.titulo,
  description: MARCA.descripcion,
  // El Estudio no se publica nunca: que ningún buscador lo muestre aunque alguien lo abra en el wifi.
  robots: { index: false, follow: false },
};

export const viewport = {
  themeColor: "#181b24",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es" className={`${inter.variable} ${cormorant.variable} ${mono.variable}`}>
      <body>
        <Cabecera ejemplo={esEjemplo()} />
        {children}
        <footer className="firma">{MARCA.firma}</footer>
      </body>
    </html>
  );
}
