#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv-build}"
DIST_DIR="${DIST_DIR:-$ROOT_DIR/linux_dist}"
BUILD_DIR="${BUILD_DIR:-$ROOT_DIR/build_linux}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

log() {
  printf '\n[build] %s\n' "$*"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '[error] Missing command: %s\n' "$1" >&2
    exit 1
  fi
}

build_one() {
  local name="$1"
  local script="$2"
  local mode="$3"
  shift 3

  log "Compiling $name"
  "$VENV_DIR/bin/python" -m PyInstaller \
    --clean \
    --noconfirm \
    --onefile \
    --name "$name" \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR/work/$name" \
    --specpath "$BUILD_DIR/specs" \
    "$mode" \
    "$@" \
    "$script"
}

cd "$ROOT_DIR"
need_cmd "$PYTHON_BIN"

log "Creating build virtualenv: $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-linux-build.txt"

rm -rf "$DIST_DIR" "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR/work" "$BUILD_DIR/specs"

build_one "ultimater_multi" \
  "$ROOT_DIR/ultimater_multi.py" \
  "--console" \
  --hidden-import socks \
  --hidden-import urllib3.contrib.socks

build_one "google_dork_auditor" \
  "$ROOT_DIR/google_dork_auditor/google_dork_auditor.py" \
  "--windowed" \
  --add-data "$ROOT_DIR/google_dork_auditor/dorks_seed.txt:."

build_one "opendir_downloader" \
  "$ROOT_DIR/opendir_downloader/opendir_downloader.py" \
  "--console" \
  --paths "$ROOT_DIR/opendir_downloader"

build_one "opendir_downloader_gui" \
  "$ROOT_DIR/opendir_downloader/opendir_downloader_gui.py" \
  "--windowed" \
  --paths "$ROOT_DIR/opendir_downloader" \
  --add-data "$ROOT_DIR/opendir_downloader/opendir_downloader.ico:."

build_one "opendir_downloader_pro" \
  "$ROOT_DIR/opendir_downloader_pro/opendir_downloader_pro.py" \
  "--windowed" \
  --paths "$ROOT_DIR/opendir_downloader_pro" \
  --add-data "$ROOT_DIR/opendir_downloader_pro/opendir_downloader_pro.ico:."

log "Done. Linux binaries:"
find "$DIST_DIR" -maxdepth 1 -type f -printf '  %f\n' | sort
