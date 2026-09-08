#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.python"
export XDG_CACHE_HOME="$PWD/.cache"
export CAD_FONT_PATH="$PWD/assets/fonts/NotoSans-Bold.ttf"
command_name="${1:-help}"
if [[ $# -gt 0 ]]; then shift; fi
python_bin="$PWD/.venv311/bin/python"
if [[ "$command_name" == install ]]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
  fi
  if [[ ! -x "$python_bin" ]]; then uv venv --python 3.11 .venv311; fi
  uv pip install --python "$python_bin" -r requirements.txt
  exit 0
fi
case "$command_name" in
 help|-h|--help)
  cat <<'EOF'
Equestria Atelier CAD collection

The exported models are ready to open; Python is only needed to regenerate them.

  ./build.sh install          Download the local Python toolchain and dependencies
  ./build.sh models [ID]      Rebuild all nine models, or one ID
  ./build.sh render [ID]      Render all nine plus the full cast, or one ID
  ./build.sh verify           Check the delivered geometry and checksums
  ./build.sh test             Run CAD primitive and emblem acceptance tests
  ./build.sh all              Rebuild models, render, and verify

IDs are listed in README.md. Editable geometry: source/design.py and emblems.py.
EOF
  exit 0;;
esac
if [[ ! -x "$python_bin" ]]; then echo 'Run ./build.sh install first.' >&2; exit 1; fi
case "$command_name" in
 models)
  "$python_bin" source/design.py
  if [[ $# -gt 0 ]]; then "$python_bin" source/export_cad.py --only "$1"; else "$python_bin" source/export_cad.py; fi;;
 render)
  if [[ $# -gt 0 ]]; then "$python_bin" source/render_studio.py --only "$1"; else
    "$python_bin" source/render_studio.py --all --orthographic --pair
    "$python_bin" source/make_catalog.py
  fi;;
 verify) "$python_bin" source/verify_collection.py;;
 test) "$python_bin" -m unittest discover -s source -p 'test_*.py';;
 all) "$0" models; "$0" render; "$0" verify;;
 *) echo "Unknown command: $command_name. Run ./build.sh help." >&2; exit 2;;
esac
