# DigScript — kit de arranque

Este kit deja todo listo para que OpenCode construya la v0.1 en tu servidor.

## Qué trae
- `AGENTS.md` (raíz del proyecto): las reglas fijas. OpenCode lo lee solo en cada sesión.
- `kit/prompts/00…08`: los 9 prompts, en orden.
- `kit/setup-server.sh`: instala lo que necesita el servidor (una sola vez).
- `kit/START-HERE.md`: esta guía.

## A. Preparar el servidor (una sola vez)
1. Pasá el zip al servidor. Desde tu PC: `scp digscript-kit.zip usuario@servidor:~/`
2. En el servidor:

       mkdir -p ~/digscript && cd ~/digscript
       unzip ~/digscript-kit.zip
       bash kit/setup-server.sh

   Si falta unzip: `sudo apt install unzip`. Después cerrá y volvé a abrir la terminal para que `uv` quede en el PATH.
3. En GitHub creá un repo vacío (público, sin README ni licencia) y guardá su URL. Para hacer push desde el servidor necesitás una clave SSH o un token de GitHub.

## B. Prompt 0 (crea el proyecto)
4. `cd ~/digscript && opencode`
5. Escribí: `Read kit/prompts/00-bootstrap.md and do exactly what it says.`
6. Cuando termine, el reporte tiene que mostrar ruff, pytest y la captura en verde. Después, en la terminal:

       git branch -M main
       git remote add origin URL-DEL-REPO
       git push -u origin main

   Entrá a la pestaña Actions del repo: el CI debe quedar en verde en Linux y Windows. Es tu único test en Windows, así que no lo saltees.

## C. Prompts 1 a 8 (repetir para cada uno)
7. En OpenCode abrí una sesión nueva con `/new`.
8. Escribí: `Read kit/prompts/NN-nombre.md and do exactly what it says.`
9. Revisá el reporte final (comandos de VERIFY en verde), hacé `git push` y esperá el CI en verde antes de pasar al siguiente.

Archivos, en orden: `01-world`, `02-miner-engine-economy`, `03-player-scripts`, `04-progression-saves`, `05-ui-world-view`, `06-ui-editor-and-run`, `07-ui-achievements-upgrades`, `08-release`.

## D. Ver y jugar
- El servidor no tiene pantalla. Para ver la interfaz, bajá las capturas que genera OpenCode: `scp usuario@servidor:~/digscript/artifacts/ui_main.png .`
- Para jugar, en tu PC (Windows o Linux): `git clone URL-DEL-REPO`, `cd digscript`, `uv sync`, `uv run digscript`.
  - Windows: instalá uv con `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
  - Linux: `sudo apt install libxcb-cursor0`.
- Probá a mano los prompts 05, 06 y 07 en tu PC: son los que más cambian lo que ves.

## E. Publicar la v0.1.0
Después del prompt 08: `git tag v0.1.0 && git push --tags`. GitHub Actions arma las descargas de Windows y Linux en la pestaña Releases.

## Si algo sale mal
- Dice «listo» sin correr los comandos: `Run the VERIFY commands and show me the output.`
- Se queda en un bucle de errores: cortalo, abrí `/new` y escribí `Run the tests, read the first failing error and fix only that.`
- Quiere cambiar la arquitectura: `Follow AGENTS.md and do not change the architecture.`
- Qt: error de plugin xcb → `sudo apt install libxcb-cursor0`; error `libEGL.so.1` → `sudo apt install libegl1`.
- Si no se arregla, pegame el error en el chat.

## Consejos
- Un prompt por sesión; no los mezcles.
- Los prompts 03 y 06 son los más difíciles: usá ahí tu mejor modelo de OpenRouter. Para el resto alcanza uno más barato.
- El Prompt 0 de este kit no vuelve a crear AGENTS.md (ya viene incluido); es la única diferencia con el documento.
