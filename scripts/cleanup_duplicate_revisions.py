"""
Script de nettoyage des révisions en double
Corrige les communes qui ont plusieurs révisions avec is_current=True
en gardant seulement la plus récente et mettant les autres à False
"""

import sys
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.mongo import get_collection, get_db
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def cleanup_duplicate_revisions():
    """Nettoie les révisions en double en gardant seulement la plus récente par commune"""
    revisions = get_collection("revisions")
    
    # Trouver toutes les communes qui ont plusieurs révisions avec is_current=True
    pipeline = [
        {"$match": {"is_current": True}},
        {
            "$group": {
                "_id": "$code_commune",
                "count": {"$sum": 1},
                "revisions": {
                    "$push": {
                        "revision_id": "$revision_id",
                        "published_at": "$published_at",
                        "updated_at": "$updated_at",
                        "created_at": "$created_at",
                        "collected_at": "$collected_at"
                    }
                }
            }
        },
        {"$match": {"count": {"$gt": 1}}}
    ]
    
    duplicates = list(revisions.aggregate(pipeline))
    
    if not duplicates:
        logger.info("Aucun doublon trouvé, tout est correct !")
        return 0
    
    logger.info(f"Trouvé {len(duplicates)} communes avec des révisions en double")
    
    total_fixed = 0
    
    for dup in duplicates:
        code_commune = dup["_id"]
        revs = dup["revisions"]
        
        # Trier par date : published_at → updated_at → created_at → collected_at
        def get_sort_date(rev):
            if rev.get("published_at"):
                return rev["published_at"]
            if rev.get("updated_at"):
                return rev["updated_at"]
            if rev.get("created_at"):
                return rev["created_at"]
            if rev.get("collected_at"):
                return rev["collected_at"]
            return datetime.min
        
        sorted_revs = sorted(revs, key=get_sort_date, reverse=True)
        
        # Garder la plus récente, mettre les autres à False
        keep_revision_id = sorted_revs[0]["revision_id"]
        to_fix = [r["revision_id"] for r in sorted_revs[1:]]
        
        if to_fix:
            result = revisions.update_many(
                {
                    "code_commune": code_commune,
                    "revision_id": {"$in": to_fix},
                    "is_current": True
                },
                {
                    "$set": {
                        "is_current": False,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Commune {code_commune}: {result.modified_count} révisions mises à False (gardé: {keep_revision_id})")
                total_fixed += result.modified_count
    
    logger.info(f"Nettoyage terminé: {total_fixed} révisions corrigées")
    return total_fixed


def show_statistics():
    """Affiche les statistiques avant/après nettoyage"""
    revisions = get_collection("revisions")
    
    # Compter les révisions is_current par commune
    pipeline = [
        {"$match": {"is_current": True}},
        {
            "$group": {
                "_id": "$code_commune",
                "count": {"$sum": 1}
            }
        },
        {
            "$group": {
                "_id": None,
                "total_communes": {"$sum": 1},
                "communes_with_duplicates": {
                    "$sum": {"$cond": [{"$gt": ["$count", 1]}, 1, 0]}
                },
                "total_revisions": {"$sum": "$count"}
            }
        }
    ]
    
    stats = list(revisions.aggregate(pipeline))
    
    if stats:
        s = stats[0]
        logger.info(f"Statistiques:")
        logger.info(f"  - Communes avec révisions is_current: {s['total_communes']}")
        logger.info(f"  - Communes avec doublons: {s['communes_with_duplicates']}")
        logger.info(f"  - Total révisions is_current: {s['total_revisions']}")
        if s['total_communes'] > 0:
            logger.info(f"  - Ratio: {s['total_revisions'] / s['total_communes']:.2f} révisions par commune")
    else:
        logger.info("Aucune révision is_current trouvée")


if __name__ == "__main__":
    logger.info("=== Nettoyage des révisions en double ===")
    
    logger.info("\nStatistiques AVANT nettoyage:")
    show_statistics()
    
    logger.info("\nDébut du nettoyage...")
    fixed = cleanup_duplicate_revisions()
    
    logger.info("\nStatistiques APRÈS nettoyage:")
    show_statistics()
    
    if fixed > 0:
        logger.info(f"\n✅ {fixed} révisions corrigées avec succès")
    else:
        logger.info("\n✅ Aucune correction nécessaire")

