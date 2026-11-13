# v0.3 — kit de arranque

Doce prompts nuevos (15 a 25 y uno opcional, R). Se usan igual que los anteriores.

## Qué entra en la v0.3
- Flota de drones: cada dron corre su propio script y comparten memoria (15, 20, 21).
- Almacén y mercado dinámico con historial de precios (16, 18).
- Refinería con 6 recetas y contratos (17, 18).
- Eventos del mundo: vetas ricas, zonas lentas y noticias de mercado (19).
- Librería nueva: rutas, trading, datos y clases (POO) (22).
- 28 logros nuevos en 3 pestañas nuevas: Trading, Industry y Fleet (23, 24).
- Release v0.3.0 (25).

## Orden y puntos de control
1. En el servidor: `cd ~/minesim && unzip -o ~/minesim-kit-v0.3.zip`
2. Con el CI en verde, etiquetá la v0.2 si todavía no lo hiciste: `git tag v0.2.0 && git push --tags` (desde `main`).
3. Rama nueva: `git switch -c v0.3 && git push -u origin v0.3`
4. Opcional: si el juego se va a llamar MineSim, corré primero `R-rename-to-minesim.md`.
5. Prompts 15 a 25, uno por sesión: `opencode`, `/new` y `Read kit/prompts/NN-nombre.md and do exactly what it says.` Revisá el reporte, `git push` y esperá el CI en verde.
6. Puntos donde conviene jugar en tu PC (`git pull`, `uv sync`, `uv run minesim`):
   - después del 18: ya podés vender, refinar y entregar contratos a mano;
   - después del 19: se ven los eventos;
   - después del 21: flota de drones.
7. Después del 25: Pull Request de `v0.3` a `main`, merge con el CI en verde y, parado en `main`, `git tag v0.3.0 && git push --tags`.

## Consejos
- El 15 (refactor de la flota) y el 20 (manager de scripts) son los más difíciles: usá ahí tu mejor modelo. El 15 va primero a propósito, para que cualquier problema aparezca temprano.
- Si algo falla, pegame el error. Cuando termines el 24, pasame `docs/BALANCE.md` y ajusto los números (precios, costos, tiempos).
- El archivo `15-multi-drone-core.md` agrega dos reglas a `AGENTS.md` (numpy solo en `ui/`, aritmética simple en `core/`) para que los resultados sean idénticos en Windows y Linux.

## Para la v0.4 (todavía sin prompts)
Infraestructura y entorno: energía y batería de los drones (primero), capacidad del muelle de descarga, aire y calor por capas, trenes y estratos geológicos. Dependen de que la flota ya exista.
