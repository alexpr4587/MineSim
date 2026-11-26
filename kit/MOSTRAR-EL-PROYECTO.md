# Cómo mostrar MineSim (lista práctica)

## 1. Antes de publicar nada (una tarde)
- Release limpio con descargas para Windows y Linux. Probá el zip de Windows desde cero, en una máquina sin Python.
- README con una frase arriba, imagen, botón de descarga y cómo correrlo (el prompt 37 lo deja hecho).
- GitHub: descripción corta, topics (python, game, programming-game, automation, idle-game, pyside6, open-source), imagen social (sale de `docs/press/`) y Discussions activadas.
- itch.io: página gratis con descarga, capturas y tags (programming, automation, idle, python, cozy). El texto está en `docs/press/itch-page.md`. Los devlogs de itch sirven para avisar de cada versión.

## 2. Los primeros 5 minutos deciden todo
- Que el primer script corra en menos de un minuto desde que abre el juego (la guía de la v0.5 va a eso).
- Pedile a 3 personas que lo prueben 10 minutos sin ayudarlas. Anotá dónde se traban: ahí está lo próximo a arreglar.
- Dejá el enlace de feedback a un clic (menú Help).

## 3. Contenido: clips cortos y verticales
- Formato: 15 a 40 segundos, 9:16, gancho en los primeros 2 segundos (mostrá el resultado, no lo expliques), sonido encendido, en inglés para llegar a más gente.
- Ideas que funcionan con este juego:
  1. «I made a game where you automate mining with real Python»: script corto, un minero, después diez.
  2. Antes y después: la misma semilla con un script torpe y con uno optimizado (dinero por minuto).
  3. Enjambre: pasar de 1 a 10 mineros y ver crecer los números.
  4. El bot del mercado: un script que vende cuando el precio está alto, con el gráfico.
  5. Probabilidades en vivo: estimar la chance de minar un ruby con datos (cruza ciencia de datos y juego).
  6. Versión cozy sin hablar: lluvia, lámparas, sonidos suaves y mineros trabajando.
  7. «Can you beat my script?»: misma semilla, tu código en el comentario o en la carpeta `community/` del repo.
  8. Fallos graciosos: mineros que se sobrecalientan, se quedan sin batería y los rescatan.
  9. Devlog semanal: una sola novedad por clip.
- Frecuencia: 3 a 5 clips por semana durante 8 a 12 semanas antes de juzgar. El mismo clip va a TikTok, Shorts y Reels. Un video largo por mes en YouTube con el devlog.
- La v0.5 trae `capture_clip`: genera los clips desde un replay, con sonido, en tu servidor y siempre iguales.

## 4. Dónde compartirlo (sin spamear)
- Reddit: comunidades de Python, de juegos incrementales y de desarrollo indie. Leé las reglas de autopromoción de cada una y publicá algo útil (un clip, un truco, una pregunta), no solo el enlace.
- Hacker News: «Show HN» funciona mejor con algo que se pueda probar ya y un texto honesto y corto. Estate disponible para responder.
- Discords y comunidades de juegos de programar (los fans de este género son tu público natural): participá antes de mostrar nada.
- Redes de desarrolladores indie: el sábado de capturas (#screenshotsaturday) y Bluesky o Mastodon.
- No mandes mensajes directos masivos ni publiques lo mismo en diez lugares el mismo día.

## 5. Cómo medirlo
- En clips: retención de los primeros 3 segundos y cuántos lo guardan o lo comparten; los likes importan menos.
- En el juego: estrellas de GitHub, descargas de itch.io y de Releases, y los issues de feedback.
- Mirá qué idea de clip trae más descargas y repetila con variaciones.

## 6. Expectativas realistas
- Las primeras publicaciones casi no se ven. Lo que mueve la aguja es la constancia, un gancho claro y responder cada comentario.
- Un juego pequeño y bien pulido que alguien entiende en 5 segundos se comparte mucho más que uno enorme que hay que explicar.
