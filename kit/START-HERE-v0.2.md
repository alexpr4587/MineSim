# DigScript v0.2 — kit de arranque

Seis prompts nuevos (09 a 14). Se usan igual que los anteriores.

## Qué hace cada uno
- 09: terreno con relieve y luz (el look «un poco 3D»).
- 10: skins del minero, sprites y edificio de la base.
- 11: motor de logros ampliado (contadores, detección de rasgos del script, recompensas nuevas).
- 12: librería ampliada: 7 funciones nuevas, ayudantes de minerlib, 4 módulos y 8 scripts de ejemplo.
- 13: contenido: 26 logros nuevos (41 en total, 5 pestañas) y la cadena de desbloqueos.
- 14: release v0.2.0.

## Pasos
1. En el servidor: `cd ~/digscript && unzip -o ~/digscript-kit-v0.2.zip` (agrega los archivos a `kit/prompts`).
2. Si todavía no etiquetaste la v0.1: `git tag v0.1.0 && git push --tags` (con el CI en verde).
3. Trabajá en una rama: `git switch -c v0.2 && git push -u origin v0.2`
4. Por cada prompt, de 09 a 14: abrí `opencode`, escribí `/new` y después `Read kit/prompts/NN-nombre.md and do exactly what it says.` Revisá el reporte, `git push` y esperá el CI en verde.
5. Después del 10 ya vas a ver el cambio visual: en tu PC `git pull`, `uv sync`, `uv run digscript`.
6. Después del 14: abrí un Pull Request de `v0.2` a `main` en GitHub, mergealo con el CI en verde y recién ahí, parado en `main`, `git tag v0.2.0 && git push --tags`.

Archivos: `09-terrain-lit-renderer`, `10-skins-sprites`, `11-progression-engine-ext`, `12-library-expansion`, `13-v02-content-wiring`, `14-release-v02`.

## Consejos
- Los más difíciles son el 09 y el 11: usá ahí tu mejor modelo de OpenRouter.
- Si renombraste el proyecto a MineSim, corré esto antes de empezar: `sed -i 's/DigScript/MineSim/g; s/digscript/minesim/g' kit/prompts/09-*.md kit/prompts/1*.md`
- Las skins no necesitan arte: son cambios de color sobre los mismos sprites. Si después dibujás los tuyos (Aseprite, Piskel), guardá un PNG por skin en `assets/skins/` y el juego lo usa solo.
- Para v0.3, ideas que encajan con un juego de programar: mercado con precios que cambian, refinería (hornos), varios drones programables, contratos y eventos.
