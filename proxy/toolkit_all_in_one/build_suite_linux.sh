#!/usr/bin/env bash
set -Eeuo pipefail

SUITE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROXY_ROOT="$(cd "$SUITE_DIR/.." && pwd)"
VENV_DIR="${VENV_DIR:-$PROXY_ROOT/.venv-build}"
OUT_DIR="${OUT_DIR:-$SUITE_DIR/suite_dist}"
TOOLS_DIR="$OUT_DIR/tools"

cd "$PROXY_ROOT"
./build_all_linux.sh

cd "$SUITE_DIR"
"$VENV_DIR/bin/python" -m PyInstaller --clean --noconfirm toolkit_launcher.spec

rm -rf "$OUT_DIR"
mkdir -p "$TOOLS_DIR"
cp "$SUITE_DIR/dist/proxy_security_toolkit" "$OUT_DIR/"
cp "$PROXY_ROOT/linux_dist/"* "$TOOLS_DIR/"

printf '\n[OK] Suite created at:\n  %s\n\n' "$OUT_DIR"
find "$OUT_DIR" -maxdepth 2 -type f -printf '  %P\n' | sort
