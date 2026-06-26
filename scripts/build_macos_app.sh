#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-./venv/bin/python}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python ortamı bulunamadı: $PYTHON_BIN"
  echo "Önce sanal ortamı oluşturun veya PYTHON_BIN ile yolu verin."
  exit 1
fi

if ! "$PYTHON_BIN" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller kurulu değil."
  echo "Kurulum: $PYTHON_BIN -m pip install -r requirements.txt"
  exit 1
fi

"$PYTHON_BIN" -m PyInstaller Jarvis.spec --noconfirm --clean

echo
echo "Hazır: dist/JARVIS.app"
