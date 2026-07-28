#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python -m py_compile security_toolkit_all_in_one.py
python -m PyInstaller --clean security_toolkit_all_in_one.spec
echo "OK: dist/security_toolkit_all_in_one"
