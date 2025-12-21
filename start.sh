#!/bin/bash
# Script de démarrage - Lance l'API et l'app Streamlit

set -e

echo "[INFO] Starting Suivi BAN application..."
echo ""

if [ -d "venv" ]; then
    source venv/bin/activate
fi

if ! command -v uvicorn &> /dev/null; then
    echo "[WARN] uvicorn not found, installing..."
    pip install uvicorn fastapi
fi

echo "[INFO] Initializing database if needed..."
python scripts/init_db.py || echo "[WARN] Database initialization skipped or failed"

echo "[INFO] Starting API on http://localhost:8000..."
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

sleep 2

echo "[INFO] Starting Streamlit on http://localhost:8501..."
echo ""
python -m streamlit run app.py --server.headless true

kill $API_PID 2>/dev/null || true
echo "[INFO] Application stopped"
