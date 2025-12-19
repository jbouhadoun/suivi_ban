#!/bin/bash
# Script de démarrage rapide du dashboard

echo "=========================================="
echo "   🗺️  Dashboard Suivi BAN"
echo "=========================================="
echo ""

# Vérifier si venv existe
if [ ! -d "venv" ]; then
    echo "❌ Environnement virtuel non trouvé"
    echo "Exécutez: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activer venv
source venv/bin/activate

# Vérifier si la base existe
if [ ! -f "data/suivi_ban.db" ]; then
    echo "⚠️  Base de données non trouvée"
    echo ""
    read -p "Voulez-vous collecter les données maintenant ? (15-30 min) (o/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[OoYy]$ ]]; then
        python collect_data.py
        if [ $? -ne 0 ]; then
            echo "❌ Échec de la collecte"
            exit 1
        fi
    else
        echo "❌ Collecte annulée. Lancez 'python collect_data.py' pour collecter les données."
        exit 0
    fi
fi

echo ""
echo "🚀 Lancement du dashboard..."
echo "📍 URL: http://localhost:8501"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter"
echo ""

streamlit run app.py










