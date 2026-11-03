#!/usr/bin/env bash
# Starts the API (port 8000) and the dashboard (port 5173). Ctrl+C stops both.
cd "$(dirname "$0")"
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --port 8000) &
(cd frontend && npm run dev) &
wait
