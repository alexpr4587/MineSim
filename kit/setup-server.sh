#!/usr/bin/env bash
# One-time setup of the build server for DigScript (Ubuntu/Debian).
set -euo pipefail

echo '==> System packages (git, unzip, curl, Qt offscreen libraries, fonts)'
sudo apt-get update
sudo apt-get install -y git unzip curl ca-certificates \
  libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libxcb-cursor0 fonts-dejavu-core

echo '==> uv (Python package manager)'
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv --version

echo '==> Python 3.12 (managed by uv)'
uv python install 3.12

echo
echo 'Done. Close and reopen the terminal, then run: cd ~/digscript && opencode'
