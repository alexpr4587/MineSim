# v0.5 «Cozy» — kit de arranque

Diez prompts nuevos (37 a 46). Se usan igual que los anteriores.

## Qué entra
- 37: repo listo para mostrar: README nuevo con botón de descarga, capturas automáticas, kit de prensa, página de itch.io y textos para publicar, menú de ayuda y plantillas de issues. Hacelo primero: ya podés empezar a compartir.
- 38 y 39: sonido. Todo se sintetiza por código (no hay archivos de audio, así que no hay problemas de licencias): efectos suaves para cada acción, música de fondo muy tranquila que cambia con la capa, panel de opciones (tecla O) con volúmenes y apagado, y botón de parlante en el HUD (silenciar todo: Ctrl+Shift+M).
- 40: efectos visuales de satisfacción: polvo al picar, números flotantes, ráfaga de monedas al vender, contador de dinero que sube, combos y confeti cada cinco logros. Con opción «reducir movimiento».
- 41: ambiente acogedor: luz cálida, hora del día, lluvia suave, luciérnagas, lámparas de los mineros y sonidos de ambiente por capa.
- 42: objetivos siempre a la vista (próximos 3 logros con barra), guía de primera partida, Diario (tecla J) con ores, productos, biomas y récords personales.
- 43: ver tu código corriendo (línea resaltada con una insignia por minero), resumen al terminar un script y medidor de ingresos por minuto.
- 44: herramientas para mostrar el juego: semillas compartibles, replays, modo showcase (F9), captura de pantalla (F12) y `capture_clip`, que genera clips verticales con sonido sin grabar la pantalla.
- 45: logros de colección (97 en total) y 4 skins nuevas.
- 46: release v0.5.0.

## Pasos
1. En el servidor, en la carpeta del proyecto: `unzip -o ~/minesim-kit-v0.5.zip`
2. Con `main` al día y el CI en verde, etiquetá la v0.4 si todavía no lo hiciste: `git tag v0.4.0 && git push --tags`
3. Rama nueva: `git switch -c v0.5 && git push -u origin v0.5`
4. Prompts 37 a 46, uno por sesión: `opencode`, `/new` y `Read kit/prompts/NN-nombre.md and do exactly what it says.` Revisá el reporte, `git push` y esperá el CI en verde.
5. Después del 46: Pull Request de `v0.5` a `main`, merge y `git tag v0.5.0 && git push --tags` desde `main`.

## Puntos de control para jugar en tu PC (`git pull`, `uv sync`, `uv run minesim`)
- Después del 37: abrí el README como lo vería alguien nuevo.
- Después del 39: escuchalo con auriculares. El sonido lo genera código y yo no puedo oírlo: decime qué cambiar (más grave, menos brillante, más lento, menos repetitivo) y ajusto las recetas.
- Después del 41: jugalo un rato al atardecer y con lluvia.
- Después del 44: generá tu primer clip con `capture_clip`.

## Consejos
- El 38 (motor de audio) y el 44 (replays y captura) son los más difíciles: usá ahí tu mejor modelo.
- Si algún día querés música propia, dejala en la carpeta `audio/override` de los datos del usuario y reemplaza a la sintetizada (revisá la licencia de lo que uses).
- En la guía `MOSTRAR-EL-PROYECTO.md` está la lista de pasos para dar a conocer el juego.

## Para la v0.6 (todavía sin prompts)
Trenes de carga con horario, maquinaria pesada con combustible, agua y bombas, eventos por capa, minimapa y retos semanales con semilla compartida.
