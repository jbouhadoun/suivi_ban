#!/bin/bash
# Script de setup pour les développeurs
# Usage: ./setup.sh

set -e

echo "=========================================="
echo "   Setup Suivi BAN - Development"
echo "=========================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv venv
fi

echo "[INFO] Installing dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "[INFO] Starting MongoDB..."
docker compose -f docker-compose.dev.yml up -d mongodb

echo "[INFO] Waiting for MongoDB to be ready..."
sleep 5

if [ ! -f ".env" ]; then
    echo "[INFO] Creating .env file from .env.example..."
    cp .env.example .env
fi

echo "[INFO] Initializing database..."
python scripts/init_db.py

echo ""
echo "[INFO] Setup completed"
echo ""
echo "To start the application:"
echo "  ./start.sh"
echo ""
echo "To get the data dump:"
echo "  Contact the team or place it in data/dump/suivi_ban/"
echo ""

