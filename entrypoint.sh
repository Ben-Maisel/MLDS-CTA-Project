#!/usr/bin/env bash

set -e

echo "Starting extract_data.py (CTA data logger)…"
python src/extract_data.py &

echo "Starting FastAPI server on 0.0.0.0:8000…"
uvicorn src.server_fastapi:app --host 0.0.0.0 --port 8000