#!/bin/bash
# Script pour configurer le cron de mise à jour nocturne

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_PATH="$SCRIPT_DIR/venv/bin/python"
UPDATE_SCRIPT="$SCRIPT_DIR/update_nightly.py"

# Vérifier que le script existe
if [ ! -f "$UPDATE_SCRIPT" ]; then
    echo "❌ Script update_nightly.py introuvable"
    exit 1
fi

# Rendre le script exécutable
chmod +x "$UPDATE_SCRIPT"

# Créer la ligne cron (tous les jours à 2h du matin)
CRON_LINE="0 2 * * * cd $SCRIPT_DIR && $PYTHON_PATH $UPDATE_SCRIPT >> $SCRIPT_DIR/logs/cron.log 2>&1"

# Vérifier si la tâche existe déjà
if crontab -l 2>/dev/null | grep -q "$UPDATE_SCRIPT"; then
    echo "⚠️  Une tâche cron existe déjà pour ce script"
    read -p "Voulez-vous la remplacer ? (o/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[OoYy]$ ]]; then
        echo "❌ Installation annulée"
        exit 0
    fi
    # Supprimer l'ancienne ligne
    (crontab -l 2>/dev/null | grep -v "$UPDATE_SCRIPT") | crontab -
fi

# Ajouter la nouvelle tâche cron
(crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -

echo "✅ Tâche cron configurée avec succès !"
echo ""
echo "📅 Planification : Tous les jours à 2h du matin"
echo "📝 Logs : $SCRIPT_DIR/logs/cron.log"
echo ""
echo "Pour voir les tâches cron :"
echo "  crontab -l"
echo ""
echo "Pour supprimer la tâche :"
echo "  crontab -e"
echo "  (puis supprimer la ligne contenant 'update_nightly.py')"










