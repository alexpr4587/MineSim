# v0.3.1 y v0.4 — kit de arranque

Once prompts nuevos (26 a 36). Los dos primeros son tus pedidos y salen como v0.3.1; los otros nueve son la v0.4 «Bajo tierra».

## Parte 1: v0.3.1 (prompts 26 y 27)
- 26: «drones» pasa a «mineros» en todo el juego: textos, API, logros y guardados. Los nombres viejos de la API siguen funcionando como alias. El panel de mineros pasa de la tecla D a la T (de Team).
- 27: las pestañas del editor se cierran sin borrar el archivo (x, clic del medio, Ctrl+W), hay un «Abrir...» con buscador, renombrar y duplicar, y borrar manda a una papelera recuperable. También arregla el texto del botón de velocidad seleccionado.

Pasos:
1. En el servidor, en la carpeta del proyecto: `unzip -o ~/minesim-kit-v0.4.zip`
2. Con `main` al día y el CI en verde: `git switch -c v0.3.1 && git push -u origin v0.3.1`
3. Prompts 26 y 27, uno por sesión: `opencode`, `/new` y `Read kit/prompts/NN-nombre.md and do exactly what it says.` Revisá el reporte, `git push` y esperá el CI en verde.
4. Pull Request de `v0.3.1` a `main`, merge y, parado en `main`, `git tag v0.3.1 && git push --tags`.

## Parte 2: v0.4 «Bajo tierra» (prompts 28 a 36)
- 28 y 29: capas (Superficie, Galerías, Nivel profundo y Roca abisal) con pozo en la base y una estación en cada capa.
- 30: energía: cada minero tiene batería, se carga en la base o en las estaciones y, si se queda sin carga, lo rescatan perdiendo el inventario.
- 31: calor y ventilación compartida: el aire alcanza para un número de mineros; si hay de más, todos se calientan más rápido.
- 32: muelle de descarga compartido con cola.
- 33: librería: ayudantes de energía, capas, clima y muelle, y los ayudantes viejos pasan a tener en cuenta la batería. 8 ejemplos nuevos.
- 34 y 35: contadores y 17 logros nuevos (86 en 10 pestañas).
- 36: release v0.4.0.

Pasos:
1. `git switch main && git pull && git switch -c v0.4 && git push -u origin v0.4`
2. Prompts 28 a 36, uno por sesión, igual que arriba.
3. Se puede jugar en tu PC (`git pull`, `uv sync`, `uv run minesim`) después del 29 (capas), 30 (energía), 31 (calor) y 32 (muelle).
4. Después del 36: Pull Request de `v0.4` a `main`, merge y `git tag v0.4.0 && git push --tags` desde `main`.

## Consejos
- El 28 (capas) y el 30 (energía) son los más difíciles: usá ahí tu mejor modelo. El 28 empieza con un test de oro que garantiza que la superficie no cambia.
- La energía está activa desde el principio; las funciones para mirarla (`battery()` y compañía) se desbloquean con logros. Los scripts viejos que ignoran la batería se van a quedar sin carga: eso es a propósito y el primer logro de la pestaña Engineering lo explica.
- Cuando termines el 35, pasame `docs/BALANCE.md` y ajusto costos y tiempos.

## Para la v0.5 (todavía sin prompts)
Trenes de carga con horario, maquinaria pesada (tuneladora) con combustible, agua y bombas, eventos por capa y un minimapa.
