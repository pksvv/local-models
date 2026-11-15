#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo 'Install Python 3.10+ from python.org, then rerun this script.'; exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ is required"'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
if [[ $# -eq 0 ]]; then
  echo 'Usage: bash setup.sh "/Volumes/Your External Volume"'; exit 1
fi
.venv/bin/python vault.py setup --volume "$1"
