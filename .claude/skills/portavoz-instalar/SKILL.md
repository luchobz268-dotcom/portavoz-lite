---
name: portavoz-instalar
description: Instala Portavoz Lite en Windows o en Mac, lo abre y rehace su ícono. Usala cuando la persona pegue la frase de instalación de Portavoz Lite, o pida "abrí Portavoz Lite", "rehacé el ícono", "cambiá mis llaves de Portavoz Lite" o "¿por qué no anda Portavoz Lite?".
---

# Instalar y abrir Portavoz Lite

Portavoz Lite convierte el link de una noticia en un video corto para redes. Se usa desde el navegador de la propia
computadora. Quien te habla probablemente no programa: **hablale en su idioma, corto y sin tecnicismos** (nada de
"repositorio", "dependencias", "variable de entorno", "PATH" ni "terminal"). Decí qué vas a hacer y para qué, no cómo.

## Reglas que no se negocian

- **Antes de instalar cada pieza que falte, pedí permiso con una pregunta de botón**, diciendo qué es en una línea y
  cuánto tarda más o menos. Si dice que no, no la instales y explicá qué no va a andar sin ella.
- **Nunca pises lo que ya tiene la persona.** No borres archivos suyos, no cambies programas que ya tiene, no toques el
  `.env` salvo las líneas de Portavoz Lite (los pasos de abajo ya lo cuidan).
- **Las llaves no se muestran nunca enteras**, ni en la charla ni en un resumen. Para confirmar alcanza con sus últimos 4
  caracteres. No las mandes a ningún lado que no sea el `.env` de la carpeta de Portavoz Lite.
- **No mandes datos de la persona** (correo, nombre) a ningún servicio.
- Si algo falla dos veces, frená y explicá en criollo qué pasó y qué podría hacer la persona.

## Dónde vive

- Windows: `%USERPROFILE%\PortavozLite` (nunca adentro de OneDrive: si la carpeta del usuario está en OneDrive, usá
  `C:\PortavozLite` y avisá por qué).
- Mac: `~/PortavozLite`.

Si la carpeta todavía no está, bajala con `git clone https://github.com/luchobz268-dotcom/portavoz-lite.git <carpeta>`.
Si ya está, no la vuelvas a bajar: el propio Portavoz Lite se actualiza solo cada vez que se abre.

## Los pasos (todos devuelven una línea de JSON)

En Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File instalar\windows.ps1 <paso>`.
En Mac: `bash instalar/mac.sh <paso>`. Siempre parado en la carpeta de Portavoz Lite.

1. **Avisá** qué vas a hacer: revisar qué tiene la computadora, instalar lo que falte (con su permiso), pedirle dos
   llaves gratis y dejar un ícono en el escritorio. Entre diez y veinte minutos, casi todo esperando descargas.
2. **`revisar`**. Mirá qué dice `false`:
   - `git`, `node`, `python`, `ffmpeg`/`ffprobe`: piezas que faltan. Por cada una, pregunta de botón y después
     `traer <pieza>` (`node`, `python`, `ffmpeg`, `git`). Explicalas así: Node "lo que hace andar la pantalla",
     Python "lo que arma los videos", FFmpeg "lo que corta y junta audio y video", git "lo que trae las
     actualizaciones".
   - En Windows, si `winget` es `false`, decí que hace falta el "Instalador de aplicación" de la tienda de Microsoft
     y dale el link `ms-windows-store://pdp/?productid=9NBLGGH4NNS1`.
   - En Mac, `traer git` abre una ventanita de Apple: pedile que toque "Instalar", esperá a que termine y volvé a
     `revisar`. Es el único clic que se le pide.
   - Si `traer ffmpeg` en Mac contesta `sin-firma`, **frená**: no busques otro FFmpeg por tu cuenta. Decí que hubo un
     problema con una pieza y que lo revise quien le pasó Portavoz Lite.
3. **Las llaves.** Abrile cada página con el navegador y pedile que pegue la llave en la charla:
   - **Google** (la voz): https://aistudio.google.com/apikey. Que cree **un proyecto nuevo** para Portavoz Lite: el
     tope de voces gratis por día es por proyecto, y si comparte uno con otra cosa se lo comen entre los dos.
   - **Pexels** (los clips de fondo): https://www.pexels.com/api/ . Es gratis, pide una cuenta.
   - Guardalas en el `.env` de la carpeta como `GEMINI_API_KEY=` y `PEXELS_API_KEY=`, cambiando sólo esas líneas.
4. **Quién escribe los guiones.** Si tiene Claude Code (vos estás corriendo ahí, así que casi seguro sí), escribe
   Claude con su suscripción: no hace falta nada más. Si prefiere otra cosa, `PORTAVOZ_TEXTO=anthropic` con
   `ANTHROPIC_API_KEY=` (sacala en https://console.anthropic.com/settings/keys; con Claude Max el plan trae crédito
   todos los meses: https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers) o
   `PORTAVOZ_TEXTO=google` con la misma llave de Google. Todo esto también se cambia después en la pantalla Ajustes.
5. **`preparar`**: deja todo listo para arrancar (puede tardar unos minutos).
6. **`probar-llaves`**: cada llave tiene que decir `anda`. Si una dice `mala`, pedile que la copie de nuevo entera. Si
   dice `sin-internet`, probá otra vez en un rato.
7. **`icono`**: deja "Portavoz Lite" en el escritorio.
8. **`abrir`**: se abre el navegador con Portavoz Lite. Contale que hay una ventanita minimizada que lo mantiene
   prendido, que **cerrarla lo apaga**, y que de ahora en más lo abre con doble clic en el ícono.

## Otros pedidos

- **"Abrí Portavoz Lite"**: `abrir`. Si contesta `sin-icono`, hacé `icono` primero.
- **"Rehacé el ícono"**: `icono`.
- **"Cambiá mis llaves"**: mandalo a la pantalla Ajustes (arriba a la derecha en Portavoz Lite), que prueba la llave
  antes de guardarla.
- **"No anda"**: `revisar` y `probar-llaves`, y contale en criollo qué falta.
