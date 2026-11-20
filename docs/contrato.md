# El contrato | cómo se pasan los datos el Estudio y el motor

El **Estudio** (la web de los 3 pasos, en `estudio/`) y el **motor** (lo que lee la nota, escribe los guiones y
arma el video) hablan con formas fijas. Esas formas son "el contrato": mientras las dos partes las respeten, se
puede cambiar una sin romper la otra. Hay dos fuentes que cumplen lo mismo: los **datos de ejemplo**
inventados (Fase 4, para probar las pantallas sin gastar) y el **motor de verdad** (Fase 5, conectado el
2026-11-18), que entró sin tocar las pantallas.

- Las formas viven en `estudio/lib/contrato.js` (el archivo que las define y las comprueba). Si cambia algo ahí,
  cambia acá en el mismo viaje.
- Quién contesta se elige con `PORTAVOZ_FUENTE`: `ejemplos` (sin nada) o `motor`. Los dos están en
  `estudio/lib/fuente/`. Con el motor: `npm run real` (en la PC) o `npm run real-celular` (en el wifi de la casa).
  Ver "Conexión con el motor" más abajo.
- **Regla de fondo:** el motor devuelve **códigos** (por ejemplo `MURO_DE_PAGO`) y la pantalla pone las
  palabras, que viven todas en `estudio/lib/textos.js`. Así los textos se aprueban en un solo lugar.
- Cada forma tiene su comprobación (`revisarPedido`, `revisarNota`, etc.) y la prueba `npm run contrato` las
  corre sobre todo lo que contestan los ejemplos.

## Los números que salen de acá
| Qué | Valor | Cajón (sección 2.1) |
|---|---|---|
| Largos del video | 15, 30 o 60 segundos; viene marcado el de 30 | decidido |
| Palabras por segundo de la voz | 2,5 (unas 150 por minuto) | **se estima**; se mide en la Fase 5 |
| Margen para que un guion "entre" en el largo | 10 % (un video de 30 deja hasta unos 33 s) | **se estima**; decidido por el asistente |
| Palabras mínimas de una nota | 60 | decidido por el asistente |
| Voces gratis por día | 10 | sale del tope de Google; se mide en la Fase 5 |
| Largo de las etiquetas de YouTube | 500 letras contando las comas | **no comprobado**: no está en las páginas de ayuda de YouTube que se abrieron; se deja porque es más estricto |
| Topes de cada red | ver la tabla de abajo | **se mide**: cada uno con su página oficial |

### Los topes de cada red (`TOPES_REDES` en `contrato.js`)
Sólo los que están escritos en una página oficial, abierta el 2026-11-17. Lo que no se pudo comprobar **no tiene
tope** (no se pone de memoria). `revisarResultado` los aplica a los textos para publicar.

| Red | Tope | Fuente |
|---|---|---|
| TikTok | texto: 2.200 | developers.tiktok.com/doc/content-posting-api-reference-direct-post (documentación para programas) |
| Instagram | texto: 2.200 y 30 hashtags | developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media (documentación para programas) |
| YouTube | título: 100, descripción: 5.000, hashtags: 60 (con más, los ignora todos) | support.google.com/youtube/answer/57407 y answer/6390658 |
| Facebook | **sin tope comprobado** | no se encontró en ninguna página oficial |
| X | 280, con peso: lo común vale 1, otros alfabetos y emojis 2, cada link 23 (los signos pegados al final, como un punto o un paréntesis, cuentan aparte; un dominio suelto como `ejemplo.com/nota` cuenta como un link o más) (`largoX`) | docs.x.com/fundamentals/counting-characters |
| LinkedIn | texto: 3.000 | linkedin.com/help/linkedin/answer/a528176 |

La lista de hashtags del resultado se puede pegar en cualquier red, así que va con el tope más chico: 30.

## Las formas, en el orden del recorrido

**Pedido** (lo que manda la persona en el Paso 1): el link **o** el texto pegado, y el largo.

**Nota** (lo que se leyó): un identificador, el titular, el texto, de dónde salió (link o texto pegado), el
medio, la fecha (o "sin fecha"), el tema (general, política, policiales o tragedia), si es un **tema delicado**
(los tres últimos), cuántas palabras tiene y si es de ejemplo.

**Guion** (Paso 2): son tres, uno por enfoque: **el dato**, **qué te cambia** y **para debatir**. Cada uno
guarda todas sus versiones (la propuesta, "más corto", "más simple", "otro" y lo escrito a mano) y cuál se está
mostrando. **Deshacer** es volver a la versión anterior; escribir después de deshacer descarta las que venían
después. Lo escrito a mano es una sola versión que se va actualizando, no una por tecla.
Lo que **propone** el Estudio (los tres guiones y lo que devuelven "más corto", "más simple" y "otro") entra en
el largo **sin el margen**: nunca dice "unos 16 s de 15". El margen queda sólo para lo que escribe la persona.
Cada versión que propone el motor (los tres guiones, "otro", "más corto" y "más simple") puede traer
**`revision`**, lo que encontró la revisión del guion (`motor/revisar_guion.py`, desde el 2026-11-18). Lo escrito a
mano no la trae. Su forma (`revisarRevision` en `contrato.js`):
- `puntos`: lista de textos, uno por problema ("C2 (marca) tramo 2: ..."), como mucho los del código más 6 del
  revisor. Puede venir vacía.
- `arreglado`: `true` si un segundo pedido arregló el guion y el arreglo pasó los controles; el texto de la versión
  ya es el arreglado.
- `aviso`: `null` o uno de **`AVISOS_REVISION`** (en `contrato.js` y `motor/contrato.py`): `DATO_NO_ESTA` (dice
  algo que la nota no dice: un número, un nombre o un hecho) o `VERBO_CAMBIADO` (cuenta como hecho algo que la nota
  dice que va a pasar). Va sólo cuando quedó un problema grave sin arreglar; si hay de los dos, va `DATO_NO_ESTA`.
- `quien`: `claude-sonnet`, `google` (si el revisor fue Google) o `codigo` (si sólo miró el código: "más corto" y
  "más simple" siempre, y los demás cuando el revisor no contestó o no quedaba tiempo).
- `antes`: sólo cuando `arreglado` es `true`, el texto completo del guion antes del arreglo.
- `arreglados`: sólo cuando `arreglado` es `true`, la lista de textos de los puntos que se mandaron a arreglar (con
  la misma forma que `puntos`). Al arreglo van los puntos `marca` y los `importante` del revisor; un guion que sólo
  tiene `importante` se arregla sólo si sobra tiempo, y si no queda como está, sin aviso. Los `menor` no se arreglan.
  Después de un arreglo, los puntos del revisor que quedan en `puntos` empiezan con "Antes del arreglo: ", porque
  hablan del texto de antes y de sus tramos.
Los campos posibles son **`CAMPOS_REVISION`** (en `contrato.js` y `motor/contrato.py`); uno que no esté ahí no pasa.
La revisión nunca frena los guiones: si falla, salen como antes, con lo que vio el código.

**Las fotos de la nota** (Tanda B, etapa 2, 2026-11-20; las constantes están en `contrato.js` y `motor/contrato.py`
y una prueba compara que digan lo mismo). Todo es **opcional**: una nota, un guion o un trabajo de antes, sin
fotos, pasa igual que siempre.
- **`nota.medios`**: las fotos que se juntaron de la página de la nota (`motor/medios_pagina.py`), hasta
  **`MAXIMO_FOTOS`** (8). Cada una es `{ n, archivo, ancho, alto, pie, alt, credito, mirada? }`: `n` va de 1 a 8 sin
  repetir, `archivo` es ese número con dos cifras (`01.jpg`; nunca una ruta), ancho y alto son enteros, y pie, alt y
  crédito son textos (pueden estar vacíos). La foto está en `motor/cache/medios/<id de la nota>/`, con una copia
  chica (`01-chica.jpg`) para que la mire Claude. Si no hay fotos, el campo **no viene**. Una nota con fotos
  necesita su link. Los campos posibles son **`CAMPOS_FOTO`**.
- **`mirada`** (lo que vio Claude en la foto): `{ sirve, encuadre, centro }`. `sirve` es sí o no; `encuadre` es uno
  de **`ENCUADRES`** (`acercamiento`, `recorrido` de costado o `entera`); `centro` es dónde está lo importante, de 0
  (izquierda) a 1 (derecha). Los campos posibles son **`CAMPOS_MIRADA`**.
- **El tramo de un guion** puede traer **`foto`**: el número de la foto sugerida para esa parte, o nada. Cada foto
  va una sola vez por versión, y como mucho en la mitad de los tramos (redondeando para abajo).
- **`guiones.py`** devuelve `{ guiones, fotos }`: `fotos` es la lista de miradas `[{ n, sirve, encuadre, centro }]`,
  una por foto mirada. El Estudio sólo la deja pasar si cada `n` es una foto de la nota. Si no se miró nada, `fotos`
  no viene. **Guardar las miradas en el borrador** (`nota.medios[].mirada`) es la etapa 4.
- **"Más corto" y "Más simple"** pueden mandar al motor los tramos de la versión de antes (`--tramos`, sólo texto y
  foto), para que cada foto siga con la parte que dice lo mismo. La pantalla los manda desde la etapa 4.
- **El trabajo** puede guardar **`imagenes`**: las fotos aprobadas, `[{ tramo, foto, credito }]` (un tramo con foto
  una sola vez, cada foto de la nota una sola vez, el crédito hasta 120 letras), y **`pie`**: `{ mostrar, fuente,
  ilustrativas }` (si se ve el pie del video y lo que dice; cada texto hasta 120 letras). Los campos posibles del
  pie son **`CAMPOS_PIE`**. Los usan las etapas 4 (la pantalla) y 5 (el video).
- Un campo que no está en el contrato no pasa, en ninguna de estas formas.

**Trabajo** (lo que queda guardado al tocar "Armar mi video"): un identificador que arma el servidor (fecha,
hora y cuatro letras al azar, nunca un nombre que mande la pantalla), cuándo se creó, el largo, la nota, el
guion elegido (enfoque y texto, que tiene que entrar en el largo) y el estado: **armando**, **listo** o **no
salió**. Cada trabajo es una carpeta con su `trabajo.json`. La carpeta de los trabajos de ejemplo es
`estudio/datos/trabajos-de-ejemplo/` (o la que diga `PORTAVOZ_TRABAJOS`); las pruebas usan otra, temporal y
nueva cada vez, para no ensuciar "Mis videos". Al crearse el trabajo, lo que estaba en el navegador se limpia.
Una carpeta rota o con otro nombre se saltea al listar.
Al leer un trabajo guardado se hace una **revisión liviana** (`revisarTrabajoGuardado`): la forma y el estado,
pero no si el guion entra en el largo con la cuenta de hoy. Así un video ya hecho no desaparece de "Mis videos" si
cambia una cuenta que se estima (como las palabras por segundo), y uno que falló con un código de otra versión se
muestra como una falla del armado, con el código `DESCONOCIDO` (la pantalla sólo recibe códigos que conoce). "Volver a probar" sí revisa todo: un guion que ya no entra pide corregirlo
(`GUION_A_CORREGIR`). Una nota cuyo identificador es un nombre que JavaScript ya trae puesto (`constructor`,
`__proto__`) es una nota más.
Además puede guardar, si vienen: el **pedido** del Paso 1 (se revisa como un pedido), los **tres guiones** del
Paso 2 (la forma de `lib/borrador.js`: de qué nota son, la lista y cuál se eligió; el elegido, en su versión
actual, tiene que ser el mismo texto y enfoque que el guion del trabajo), **reintentoDe** (el trabajo que falló y
que éste vuelve a probar), **reintentadoEn** (en uno que no salió, el trabajo que lo volvió a probar), **encargo**
(la marca que la pantalla le pone a cada "Armar mi video": de 16 a 64 letras de la a a la f y números) y el
**error** (sólo en uno que no salió, con la forma de los errores de abajo).
**Una sola vez** (decidido por el asistente, no por Lucio, el 2026-11-18, al arreglar lo que encontró la revisión):
- "Armar mi video" guarda el encargo en el navegador **antes** de mandarlo. Si llega dos veces (la página se cerró
  mientras armaba, se cortó la respuesta, dos toques), el Estudio devuelve el trabajo que ya creó ese encargo, sin
  gastar otra voz. Al volver a Revisar con el mismo borrador, la pantalla busca ese trabajo y lleva al video. Si
  la persona cambió algo (el guion, el largo), el encargo es otro.
- "Volver a probar" se hace una vez por trabajo: en el que no salió queda `reintentadoEn`, y otro pedido (Atrás,
  otra pestaña, Mis videos) devuelve ése. Si no quedó anotado, se busca por `reintentoDe`. Si el reintento
  tampoco salió, se vuelve a probar desde el reintento.
- Dos pedidos a la vez con el mismo encargo, o dos "Volver a probar" del mismo trabajo, reciben el mismo.

**Avance** (Paso 3): las cinco etapas en orden (clips, voz, tiempos, armado y textos: el orden en que las hace
el motor, que busca los clips antes de gastar la voz), cada una en espera,
haciéndose, lista o fallada; el porcentaje (nunca 100 hasta que está listo); `restante`, los segundos que se
estima que faltan (un entero, 0 al terminar; con `PORTAVOZ_VELOCIDAD=rapida` se dice como si fuera a velocidad
normal, para que una barra recién empezada no diga "Ya casi está"); `fila`, cuántos videos hay antes esperando su turno (un entero de
1 en adelante, sólo mientras espera: si no viene, no está esperando o la fuente no lo sabe), y el error si falló.
Los nombres de las etapas están en `textos.js` (`ETAPAS`). La pantalla del video (`/video/<id>`) lo pide cada
segundo mientras se arma, y deja de pedirlo cuando termina o falla.

**Resultado** (cuando el video está listo; queda en `resultado.json`): las direcciones para pedir el video y la
portada (`/api/trabajos/<id>/video` y `.../portada`) y los textos para publicar: título, descripción, hashtags,
etiquetas de YouTube y un texto por red (TikTok, Instagram, YouTube, Facebook, X y LinkedIn; los nombres, en
`textos.js`, `REDES`). Todo dentro de los topes de arriba. **"Pedir otro"** cambia uno de esos textos por su
versión siguiente y lo guarda (cada uno tiene al menos tres). Dos "Pedir otro" a la vez (por ejemplo título y
descripción) no se pisan: se lee, se cambia y se guarda sin ninguna espera en el medio.

**Cupo**: cuántas voces quedan hoy (tope, usadas y quedan) y cuántos videos van en el mes. Las voces usadas son
los trabajos de hoy que no fallaron; **lo que falla no cuenta** como video del mes. La voz se cuenta otra vez
justo antes de guardar el trabajo: dos pedidos (o dos "Volver a probar" de trabajos distintos) a la vez con una
sola voz libre dan un trabajo y un `SIN_VOCES_HOY`.

## El armado de ejemplo (Fase 4)
Con los datos de ejemplo el video **se arma de verdad**, pero sin voz ni clips:
`estudio/herramientas/armar_video_ejemplo.py` pone el guion como subtítulo, palabra por palabra, sobre un fondo
de prueba, con el cartel "IMAGEN DE EJEMPLO" y el pie (la fuente y "Imágenes ilustrativas"). Necesita Python y
FFmpeg en la PC.
- Video vertical de 1080x1920 a 30 cuadros, con una pista de audio muda, que dura lo que el guion a la velocidad
  de la voz (`PALABRAS_POR_SEGUNDO`) más medio segundo; imagen y sonido duran lo mismo. La velocidad se la pasa
  el Estudio a Python (`--palabras-por-segundo=2.5`): Python no tiene una copia propia, y sin ella no arma. Un
  tema delicado sale con la letra **Sobria**. La portada es un cuadro del primer segundo, de 540x960. Con
  `PORTAVOZ_VELOCIDAD=rapida` (las pruebas) sale de 540x960 a 10 cuadros.
- **Color**: libass pinta con la receta de color de los videos comunes, y el navegador lee un video alto como el
  nuestro con la de alta definición (bt709). Por eso el video se pasa a esa receta y queda marcado así, y la
  portada se pasa a la de las fotos. El celeste del resaltado (#7DD3DF) se mide en el video y en la portada.
- **Subtítulo** (decisiones de Lucio del 2026-11-17): los emojis no se dibujan ni cuentan como palabra (la voz
  tampoco los lee); una palabra que era sólo un emoji le pasa su tiempo a la de antes. Un link que no entra en el
  ancho sale partido en pedazos que entran (cortando en / . -), uno detrás del otro, cada uno solo y a tamaño
  normal, con el tiempo de la palabra repartido según el largo de cada pedazo; no se agrega ningún texto nuevo.
  Las letras de otros alfabetos que la letra de la marca no tiene se quedan (libass pone otra en su lugar) y se
  anotan en el registro del armado.
- Los tres fondos (60 s cada uno) se arman solos la primera vez en `estudio/datos/fondos-de-ejemplo/` (no se
  sube) y tardan unos minutos. Después, un video de 15 s tarda unos 16 s en esta PC. Un candado por fondo
  (`fondo-<nombre>[-rapida].lock`) evita que dos armados hagan el mismo a la vez: vale mientras el programa que
  lo tomó siga vivo, y 2 minutos como mucho. El que llega espera hasta 150 s, antes de que el Estudio corte el
  armado. Si el que lo tomó se murió (un armado cortado), el candado se pisa y el fondo se hace.
- Hay **una sola fila** para todo el Estudio: un video por vez. Cada trabajo tiene un candado, `armando.lock`
  (quién lo arma y desde cuándo), que nunca se borra: al terminar queda "libre". Un candado de más de 10
  minutos, o de un programa que ya no existe, se da por muerto. Un trabajo está **una sola vez** en la fila,
  aunque se lea muchas veces a la vez.
- Si un trabajo está "armando", sin video y sin nadie armándolo (por ejemplo, después de cerrar el Estudio), al
  leerlo vuelve a la fila. Si Python tarda más de 8 minutos, se corta (con FFmpeg incluido) y el trabajo no sale
  (`FALLO_ARMADO`). Una falla de verdad de Python también deja el trabajo en "no salió" con `FALLO_ARMADO`
  (el detalle, sin la carpeta personal de quien usa la PC): no gasta la voz y no vuelve a la fila.
- Las etapas siguen el reloj desde que se creó el trabajo; el armado espera al video y la portada: mientras no
  está el video, el armado no se da por terminado, los textos no arrancan y lo que falta nunca sube. Al terminar
  se escribe `resultado.json` y el trabajo pasa a listo. Si los textos para publicar no se pueden armar, el
  trabajo no sale (`FALLO_ARMADO`) en vez de quedar "armando" para siempre.
- Las fallas de ejemplo `sin-clips` y `falla-armado` fallan en su etapa sin armar nada y sin gastar una voz.
  "Volver a probar" crea un trabajo nuevo con los mismos datos y `reintentoDe`, que **gasta una voz**; el
  reintento de `falla-armado` sale bien. Sólo se puede volver a probar un trabajo que no salió, y una sola vez
  (ver "Una sola vez" arriba).
- Los textos para publicar salen de `estudio/datos/ejemplos/textos.json`: escritos para cada nota de ejemplo, y
  plantillas (una general y una sobria, sin emojis) para un texto pegado.

Lo que queda en la carpeta de cada trabajo: `trabajo.json`, `armando.lock`, `subtitulos.ass`, `armado.json` (el
registro del armado: segundos, palabras, estilo, fondo, `letras_reemplazadas`, las letras que la marca no tiene, y
`mirada`, si Claude miró los clips, quién, cuántas vueltas, cuánto tardó, cuántos **tramos** usan un clip
prestado de otro tramo (`prestados` cuenta tramos, no tomas) y cuáles sacó y por qué; si hubo tercera vuelta, para
qué tramos y cuántos clips nuevos trajo; en `busquedas_repetidas` lo que Claude volvió a escribir y ya se había
buscado (no se busca de nuevo), y en `vueltas_fallidas` cada vuelta que no se pudo mirar, con su motivo; detalle en
`motor/clips.py`, `elegir_clips`; `rechazados_ultimo_recurso`, los tramos donde entró un clip "no tiene que ver"
porque no quedaba ningún otro, ni prestado. En `tomas`, una por toma del video: `mirado` (lo que dijo Claude de ese
clip, o `null` si no lo miró), `origen` (`propio`, `prestado` o `rechazado_ultimo_recurso`) y, si es prestada,
`prestado_de`, el tramo de donde salió el clip. Ojo con la numeración: en `tomas` el `tramo` y `prestado_de` cuentan desde 1, como
se ven en el video; en `mirada` los tramos cuentan desde 0. Desde el 2026-11-20, `duracion` es lo que dura el video
con los bordes mudos de la voz recortados (unas décimas menos que `voz.mp3`), y `vuelta` dice cómo quedó la unión
del final con el principio: `recorte` (desde y hasta qué segundo de la voz se usó), `ganancia_ultima` (cuántos dB
subió la última frase), y medido en el video terminado `silencio` (segundos mudos en la vuelta), `salto` (dB de
diferencia entre el último medio segundo con voz y el primero) y `avisos`; si algo no se pudo medir, `fallo`),
`video.mp4`, `portada.jpg`, `resultado.json` y, sólo si el armado falló, `armado-error.txt`. Python escribe su
salida siempre en UTF-8, que es como la lee el Estudio.

## Las direcciones de un trabajo
Todas comprueban el id con su forma exacta y nunca arman una ruta con lo que manda la pantalla. Un trabajo que
no existe da 404 (no está); un pedido que no se puede cumplir (por ejemplo, volver a probar uno que salió bien)
da 422 con su error.

| Dirección | Qué devuelve |
|---|---|
| `GET /api/trabajos/<id>` | `{ trabajo, avance }`, y `resultado` cuando está listo; 404 si no existe |
| `GET /api/trabajos/<id>/video` | el video; por partes si el navegador lo pide (para adelantar); con `?bajar=1`, para bajar con un nombre simple (el titular corto sin tildes y la fecha) y también con tildes; el corte nunca parte una letra (las letras de adorno pasan a las comunes) y las tildes que vienen separadas de su letra se juntan |
| `GET /api/trabajos/<id>/portada` | la portada |
| `POST /api/trabajos/<id>/otro` | `{ campo, red? }`: "Pedir otro" de ese texto; devuelve el resultado entero ya cambiado |
| `POST /api/trabajos/<id>/reintentar` | "Volver a probar": devuelve el trabajo nuevo, o el que ya lo volvió a probar |
| `POST /api/trabajos` | crea el trabajo; además de nota, largo y guion acepta `pedido`, `guiones`, `reintentoDe` y `encargo` (con un encargo que ya creó un trabajo, devuelve ése) |

Las prueba `npm run rutas` con el Estudio prendido de verdad.

## Los errores y qué camino ofrece la pantalla
| Código | Qué pasó | Qué ofrece la pantalla |
|---|---|---|
| `LINK_INVALIDO` | el link está incompleto | corregirlo |
| `LINK_NO_ABRE` | la página no abre | pegar el texto ahí mismo |
| `NOTA_SIN_TEXTO` | la página no tiene una nota (una portada, una de videos) | pegar el texto |
| `MURO_DE_PAGO` | la nota es sólo para suscriptores | pegar el texto |
| `NOTA_MUY_CORTA` | la nota no alcanza para un video | corregir |
| `SIN_VOCES_HOY` | se terminaron las voces del día | dejarlo para mañana; el guion queda guardado |
| `GUION_A_CORREGIR` | al armar, el guion llegó vacío o más largo que el video | volver al guion |
| `SIN_CLIPS` | no hay imágenes para ese guion | volver al guion, que queda intacto |
| `FALLO_VOZ`, `FALLO_ARMADO` | falló la voz o el armado | probar de nuevo |
| `SIN_CONEXION` | se cortó la conexión | probar de nuevo |
| `DESCONOCIDO` | cualquier otra cosa | probar de nuevo |

Ningún error gasta nada ni cuenta como video del mes.

## Dónde falla
- La duración de un guion es una **cuenta de palabras**, no la voz de verdad: una voz más lenta o un texto con
  muchos números puede durar más. Se mide en la Fase 5.
- Los guiones de ejemplo y sus cambios ("más corto", "más simple") están **escritos a mano**: prueban las
  pantallas, no lo bien que escribe el motor.
- Lo que la persona está haciendo antes de armar (la nota y los guiones) se guarda **sólo en su navegador**: en
  otra computadora, o en una ventana privada al cerrarla, no está.
- El video de ejemplo **no tiene voz ni imágenes de verdad**: prueba el camino entero y los tiempos, no cómo se
  ve un video final.
- El tiempo que falta (`restante`) es una **estimación** con lo medido en esta PC; con la PC cargada, el video
  tarda más y la cuenta se queda esperando.
- X cuenta los emojis y otros alfabetos con rangos aproximados. Los links los reconoce sin saber qué
  terminaciones de dominio existen: "EE.UU." cuenta como un link (23, así "EE.UU. y más" da 30), y un dominio
  suelto con una terminación rara o muy nueva puede contar menos de lo que cuenta X.
- En el subtítulo, un link ocupa el lugar de una palabra (0,4 s): partido en pedazos, cada pedazo pasa rápido.
  Un emoji al principio del guion pierde su tiempo (no hay palabra de antes): la pantalla arranca vacía ese
  instante.
- La cuenta de voces es segura dentro de un Estudio. Dos Estudios abiertos a la vez sobre la misma carpeta de
  trabajos podrían pasarse del tope por una voz. Lo mismo con "una sola vez": dos pedidos con el mismo encargo,
  o dos "Volver a probar" del mismo trabajo, que llegan a la vez a dos Estudios distintos, arman dos.
- El encargo vive en el navegador: si la página se cierra mientras arma y se vuelve desde otro navegador, no se
  sabe que ya se tocó "Armar mi video". Si la persona se fue de Revisar mientras armaba (Atrás) y después cambió
  el guion, el borrador ya no coincide y no la lleva al video que salió (está en Mis videos).
- El motor de verdad hace "una sola vez" igual que los ejemplos (mismo encargo, mismo reintento) y además con
  leer la nota, los guiones y cada cambio: dos toques seguidos esperan al primero y no gastan dos pedidos.
- Un fondo cortado a la mitad deja un `fondo-*.parcial.mp4` que no se borra (se pisa en el próximo).
- Facebook no tiene tope comprobado, y el de las etiquetas de YouTube no se encontró en su ayuda.
- Si el Estudio se cierra mientras Python arma un video, el candado sigue a nombre de Python hasta que termina;
  recién ahí el trabajo puede volver a la fila.
- `fila` lo da la fuente de ejemplo, que tiene una sola fila para todo el Estudio. Un video que espera por otro
  motivo (otro Estudio abierto sobre la misma carpeta) no lo dice: se ve con el armado "haciéndose".
- "Volver al guion" en un video viejo, guardado sin sus tres guiones, devuelve sólo el elegido; los otros dos
  vuelven vacíos, para escribirlos a mano o pedir otro.

## Conexión con el motor (Fase 5, 2026-11-18)

`estudio/lib/fuente/motor.js` llama a los programas de `motor/` (Python), sin ventana, con tope de tiempo. Cada
programa contesta una línea con lo pedido o con `{ error }` y su código; el Estudio rearma el error con
`crearError` y le saca la carpeta personal.

| Lo que pide la pantalla | Programa | Pedidos (a Claude; Google si Claude no anda) | Voces |
|---|---|---|---|
| Leer la nota | `leer_nota.py` | 1 (elegir los párrafos; si Jina no la lee, 1 más para leerla). Si la nota tiene link, además baja la página y sus fotos (`medios_pagina.py`, ningún pedido) | 0 |
| Los tres guiones | `guiones.py --duracion` | 1 (con los tramos: qué clips buscar para cada parte y, si la nota trae fotos, qué foto va en cada una), más 1 que mira las fotos **al mismo tiempo** (sólo con fotos; 90 s como mucho). Devuelve `{ guiones, fotos }` | 0 |
| **Más corto** o **Más simple** | `guiones.py --cambiar corto\|simple [--tramos]` | **1 cada uno** (devuelve la versión con sus tramos). Con `--tramos` (las partes de antes con su foto) cada foto pasa a la parte nueva que dice lo mismo; las fotos no se vuelven a mirar | 0 |
| Escribir otro | `guiones.py --enfoque --evitar` | 1. Sugiere sólo las fotos que ya se miraron y sirven (`nota.medios[].mirada`); sin eso, sale sin fotos | 0 |
| Armar el video | `armar.py` | 0 si el guion trae sus tramos (si se corrigió a mano, 1 para elegir los clips), más 1 de los textos | 1 (0 si ese mismo guion ya tenía su voz guardada) |
| Pedir otro texto | `otro_texto.py` | 0 mientras queden versiones guardadas; 1 cuando se acaban | 0 |

Google reintenta solo cuando está saturado y **cada reintento cuenta como pedido**. `PORTAVOZ_INTENTOS_GOOGLE`
pone un techo a los intentos de cada pedido (para pruebas con el cupo contado).

- **Los tramos viajan con el guion:** el Estudio guarda cada versión de los guiones tal como la manda el motor
  (con sus tramos) y la pasa en `guiones` al crear el trabajo. Si el texto elegido es el mismo, el motor usa esos
  tramos y no vuelve a pedirle a Google qué buscar.
- **Las voces del día** se cuentan desde los trabajos: el `vocesGastadas` que anota el motor en cada uno, también
  en los que fallaron después de grabar la voz. Uno que se está armando y todavía no anotó nada guarda una. El día
  es el de la hora del Pacífico (Google renueva el tope a esa medianoche). Las voces que gasta `motor/prueba.py`
  por fuera del Estudio no entran en esta cuenta.
- **La fila** es la misma de los ejemplos (`lib/fuente/fila.js`): un video por vez, `fila` dice cuántos hay
  antes. El avance sale de `avance.json`, que el motor escribe etapa por etapa; mientras espera su turno, se
  estima con `motor/medidas.json` (o con los valores iniciales de `armar.py` si todavía no hay medidas).
- **El estado** lo pone el Estudio: el motor no lo toca. Si `armar.py` termina bien queda "listo"; si no, "fallo"
  con el código que mandó (o el de `avance.json`, o el de `armado-error.txt`). Si el Estudio se apagó en el medio,
  al prender: si el motor llegó a terminar queda listo, si dejó un error falla con ése, y si no vuelve a la fila
  (hasta tres veces).
- **Pedir otro** va de a uno por trabajo: el motor reescribe `resultado.json` y dos a la vez se pisarían.
- Los trabajos van en `PORTAVOZ_TRABAJOS` o, sin nada, en `trabajos/` (al lado de `estudio/`; no se sube).
- La prueba `npm run conexion` lo prueba todo por las direcciones de la pantalla con un **motor de mentira** que
  no sale a internet; `npm run motor` prueba el motor sin gastar. Las dos corren en `npm run verificar`.
- **Dónde falla:** si los textos para publicar no salen (Google saturado), el trabajo queda en "fallo" aunque el
  video esté hecho; "Volver a probar" reusa la voz y los clips guardados y sólo gasta el pedido de los textos.
