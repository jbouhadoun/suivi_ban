#!/usr/bin/env python3
"""
Script pour charger les départements dans MongoDB
Peut être utilisé indépendamment de l'initialisation complète

Usage:
    python scripts/load_departements.py          # Charge ou met à jour les départements
    python scripts/load_departements.py --force # Force le rechargement
    python scripts/load_departements.py --stats # Recalcule seulement les stats
"""

import sys
import argparse
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.mongo import (
    get_collection,
    load_departements_from_geojson_file,
    load_departements_from_api,
    update_departements_stats
)

def main():
    """Charge les départements dans MongoDB"""
    parser = argparse.ArgumentParser(description="Load départements into MongoDB")
    parser.add_argument("--force", action="store_true", help="Force reload even if départements exist")
    parser.add_argument("--stats", action="store_true", help="Only recalculate statistics")
    args = parser.parse_args()
    
    print("[INFO] Loading départements into MongoDB...")
    
    departements = get_collection("departements")
    count = departements.count_documents({})
    
    # Si on veut juste recalculer les stats
    if args.stats:
        if count == 0:
            print("[ERROR] No départements in database. Load them first.")
            return 1
        print("[INFO] Recalculating départements statistics...")
        updated = update_departements_stats()
        print(f"[INFO] Stats updated for {updated} départements")
        return 0
    
    # Si départements existent et pas de force
    if count > 0 and not args.force:
        print(f"[INFO] {count} départements already in database")
        print("[INFO] Use --force to reload them, or --stats to recalculate statistics")
        # Vérifier si les stats sont à jour
        dept_without_stats = departements.count_documents({"stats": {"$exists": False}})
        if dept_without_stats > 0:
            print(f"[INFO] {dept_without_stats} départements without stats, calculating...")
            update_departements_stats()
        return 0
    
    # Forcer le rechargement si demandé
    if args.force and count > 0:
        print(f"[INFO] Force reloading {count} départements...")
        departements.drop()
    
    # Essayer d'abord de charger depuis le fichier GeoJSON s'il existe
    print("[INFO] Trying to load départements from GeoJSON file...")
    loaded = load_departements_from_geojson_file()
    
    if loaded == 0:
        # Si pas de fichier, charger depuis l'API
        print("[INFO] Loading départements from API...")
        loaded = load_departements_from_api()
        
        # Après chargement depuis l'API, calculer les stats
        if loaded > 0:
            print("[INFO] Calculating départements statistics...")
            update_departements_stats()
    
    if loaded > 0:
        print(f"[INFO] {loaded} départements loaded successfully")
        return 0
    else:
        print("[ERROR] No départements loaded")
        return 1

if __name__ == "__main__":
    sys.exit(main())

