#!/usr/bin/env bash
# One-time setup: Python venv + deps, model weights, sample videos, frontend deps.
set -e
cd "$(dirname "$0")"
command -v uv >/dev/null || { echo "Install uv first: https://docs.astral.sh/uv/"; exit 1; }
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
PY=.venv/bin/python ./download_models.sh
./download_samples.sh
cd ../frontend && npm install
echo "Setup complete. Run ./run.sh"
