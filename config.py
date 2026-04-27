"""
Configuration centralisee pour Suivi BAN
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# MongoDB
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "suivi_ban")

# Construire l'URI depuis les variables séparées ou utiliser MONGODB_URI directement
MONGODB_USER = os.getenv("MONGODB_USER")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
MONGODB_HOST = os.getenv("MONGODB_HOST")

if MONGODB_USER and MONGODB_PASSWORD and MONGODB_HOST:
    # Construire l'URI depuis les variables séparées (MongoDB Atlas)
    # URL encode le password au cas où il contient des caractères spéciaux
    from urllib.parse import quote_plus
    encoded_password = quote_plus(MONGODB_PASSWORD)
    MONGODB_URI = f"mongodb+srv://{MONGODB_USER}:{encoded_password}@{MONGODB_HOST}"
else:
    # Utiliser MONGODB_URI directement (pour compatibilité locale)
    MONGODB_URI = os.getenv("MONGODB_URI", f"mongodb://admin:admin123@localhost:27017?authSource=admin")

COLLECTIONS = {
    "communes": "communes",
    "revisions": "revisions",
    "voies": "voies",
    "update_logs": "update_logs",
    "config": "config",
    "departements": "departements",
    "deploiement_bal_features": "deploiement_bal_features",
    "deploiement_bal_meta": "deploiement_bal_meta",
}

# APIs externes
API_GEO = "https://geo.api.gouv.fr"
API_BAN_LOOKUP = "https://plateforme.adresse.data.gouv.fr/lookup"
API_BAL_DEPOT = "https://plateforme-bal.adresse.data.gouv.fr/api-depot"
API_BAL_STATS_BASE = os.getenv("BAL_API_URL") or os.getenv("NEXT_PUBLIC_BAL_API_URL", "https://api-bal.adresse.data.gouv.fr/v2")
BAL_TILES_MIN_ZOOM = int(os.getenv("BAL_TILES_MIN_ZOOM", "4"))

# Collecte
COLLECT_WINDOW_DAYS = int(os.getenv("COLLECT_WINDOW_DAYS", "7"))
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
COLLECT_WORKERS = int(os.getenv("COLLECT_WORKERS", "10"))

# Cache
CACHE_DIR = Path(os.getenv("CACHE_DIR", "cache"))
GEOJSON_DIR = CACHE_DIR / "geojson"


# Serveur
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Statuts
STATUT_COLORS = {
    "vert": "#00A86B",
    "orange": "#FF8C00",
    "rouge": "#DC143C",
    "jaune": "#FFD700",
    "gris": "#808080"
}
