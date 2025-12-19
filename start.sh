#!/bin/bash
# Script de démarrage - Lance l'API et l'app Streamlit

echo "🚀 Démarrage Suivi BAN..."
echo ""

# Activer l'environnement virtuel si présent
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Environnement virtuel activé"
fi

# Vérifier que uvicorn est installé
if ! command -v uvicorn &> /dev/null; then
    echo "📦 Installation de uvicorn..."
    pip install uvicorn fastapi
fi

# Lancer l'API en arrière-plan
echo "🔌 Démarrage de l'API sur http://localhost:8000..."
uvicorn api:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
echo "   PID: $API_PID"

# Attendre que l'API soit prête
sleep 2

# Lancer Streamlit
echo ""
echo "🗺️ Démarrage de l'application sur http://localhost:8501..."
echo ""
streamlit run app.py --server.headless true

# Quand Streamlit s'arrête, arrêter aussi l'API
kill $API_PID 2>/dev/null
echo ""
echo "👋 Application arrêtée"


