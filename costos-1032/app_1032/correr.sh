#!/bin/bash
# Arranca la aplicación web en http://127.0.0.1:8000
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
exec python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
