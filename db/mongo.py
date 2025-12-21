"""
Gestion de la connexion MongoDB pour Suivi BAN
"""

from pymongo import MongoClient, ASCENDING, GEOSPHERE
from pymongo.errors import ConnectionFailure
from datetime import datetime
import logging

from config import MONGODB_URI, MONGODB_DATABASE, COLLECTIONS

logger = logging.getLogger(__name__)

_client = None
_db = None


def get_client():
    """Retourne le client MongoDB (singleton)"""
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
        try:
            _client.admin.command('ping')
            logger.info("Connexion MongoDB etablie")
        except ConnectionFailure as e:
            logger.error(f"Echec connexion MongoDB: {e}")
            raise
    return _client


def get_db():
    """Retourne la base de donnees"""
    global _db
    if _db is None:
        _db = get_client()[MONGODB_DATABASE]
    return _db


def get_collection(name):
    """Retourne une collection par son nom"""
    return get_db()[COLLECTIONS.get(name, name)]


def init_indexes():
    """Initialise les index MongoDB"""
    db = get_db()
    
    # Index communes
    communes = db[COLLECTIONS["communes"]]
    communes.create_index("code_insee", unique=True)
    communes.create_index("departement_code")
    communes.create_index("statut_couleur")
    # Index geospatial cree plus tard apres validation des geometries
    # communes.create_index([("geometry", GEOSPHERE)])
    
    # Index revisions
    revisions = db[COLLECTIONS["revisions"]]
    revisions.create_index("revision_id", unique=True)
    revisions.create_index("code_commune")
    revisions.create_index("client_nom")
    revisions.create_index("published_at")
    
    # Index voies
    voies = db[COLLECTIONS["voies"]]
    voies.create_index("code_commune")
    voies.create_index("ban_id")
    
    logger.info("Index MongoDB crees")


def upsert_commune(data):
    """Insere ou met a jour une commune"""
    communes = get_collection("communes")
    data["updated_at"] = datetime.utcnow()
    
    return communes.update_one(
        {"code_insee": data["code_insee"]},
        {"$set": data},
        upsert=True
    )


def upsert_revision(data):
    """Insere ou met a jour une revision"""
    revisions = get_collection("revisions")
    data["updated_at"] = datetime.utcnow()
    
    return revisions.update_one(
        {"revision_id": data["revision_id"]},
        {"$set": data},
        upsert=True
    )


def upsert_voie(data):
    """Insere ou met a jour une voie"""
    voies = get_collection("voies")
    
    return voies.update_one(
        {"id": data["id"]},
        {"$set": data},
        upsert=True
    )


def get_stats_global():
    """Retourne les statistiques globales"""
    communes = get_collection("communes")
    
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "vert": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "vert"]}, 1, 0]}},
                "orange": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "orange"]}, 1, 0]}},
                "rouge": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "rouge"]}, 1, 0]}},
                "jaune": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "jaune"]}, 1, 0]}},
                "gris": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "gris"]}, 1, 0]}},
                "numeros": {"$sum": "$nb_numeros"},
                "voies": {"$sum": "$nb_voies"}
            }
        }
    ]
    
    result = list(communes.aggregate(pipeline))
    return result[0] if result else {}


def get_stats_departements():
    """Retourne les statistiques par departement"""
    communes = get_collection("communes")
    
    pipeline = [
        {
            "$group": {
                "_id": "$departement_code",
                "nom": {"$first": "$departement_nom"},
                "total": {"$sum": 1},
                "vert": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "vert"]}, 1, 0]}},
                "orange": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "orange"]}, 1, 0]}},
                "rouge": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "rouge"]}, 1, 0]}},
                "jaune": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "jaune"]}, 1, 0]}},
                "gris": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "gris"]}, 1, 0]}}
            }
        }
    ]
    
    results = {}
    for doc in communes.aggregate(pipeline):
        code = doc["_id"]
        if code:
            total = doc["total"] or 1
            results[code] = {
                "code": code,
                "nom": doc["nom"],
                "total": doc["total"],
                "vert": doc["vert"],
                "orange": doc["orange"],
                "rouge": doc["rouge"],
                "jaune": doc["jaune"],
                "gris": doc["gris"],
                "pct_vert": round(doc["vert"] / total * 100, 1)
            }
    
    return results


def get_communes_by_departement(code_dept):
    """Retourne les communes d'un departement en GeoJSON"""
    communes = get_collection("communes")
    
    cursor = communes.find(
        {"departement_code": code_dept},
        {
            "code_insee": 1,
            "nom": 1,
            "statut_couleur": 1,
            "geometry": 1,
            "geometry_raw": 1,
            "nb_numeros": 1,
            "nb_voies": 1,
            "type_composition": 1,
            "with_ban_id": 1,
            "producteur": 1,
            "centre_lat": 1,
            "centre_lon": 1
        }
    )
    
    features = []
    for doc in cursor:
        feature = {
            "type": "Feature",
            "properties": {
                "code": doc.get("code_insee"),
                "nom": doc.get("nom"),
                "statut": doc.get("statut_couleur", "gris"),
                "nb_numeros": doc.get("nb_numeros", 0),
                "nb_voies": doc.get("nb_voies", 0),
                "type_composition": doc.get("type_composition"),
                "with_ban_id": doc.get("with_ban_id", False),
                "producteur": doc.get("producteur"),
                "lat": doc.get("centre_lat"),
                "lon": doc.get("centre_lon")
            },
            "geometry": doc.get("geometry") or doc.get("geometry_raw")
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def get_producteurs():
    """Retourne la liste des producteurs avec leurs stats"""
    revisions = get_collection("revisions")
    communes = get_collection("communes")
    
    pipeline = [
        {"$match": {"is_current": True}},
        {
            "$lookup": {
                "from": COLLECTIONS["communes"],
                "localField": "code_commune",
                "foreignField": "code_insee",
                "as": "commune"
            }
        },
        {"$unwind": "$commune"},
        {
            "$group": {
                "_id": "$client_nom",
                "nb_communes": {"$sum": 1},
                "nb_depts": {"$addToSet": "$commune.departement_code"},
                "vert": {"$sum": {"$cond": [{"$eq": ["$commune.statut_couleur", "vert"]}, 1, 0]}},
                "orange": {"$sum": {"$cond": [{"$eq": ["$commune.statut_couleur", "orange"]}, 1, 0]}},
                "rouge": {"$sum": {"$cond": [{"$eq": ["$commune.statut_couleur", "rouge"]}, 1, 0]}}
            }
        },
        {"$sort": {"nb_communes": -1}}
    ]
    
    results = []
    for doc in revisions.aggregate(pipeline):
        if doc["_id"]:
            results.append({
                "nom": doc["_id"],
                "nb_communes": doc["nb_communes"],
                "nb_depts": len(doc["nb_depts"]),
                "vert": doc["vert"],
                "orange": doc["orange"],
                "rouge": doc["rouge"]
            })
    
    return results


def search_communes(query, limit=20):
    """Recherche de communes par nom ou code INSEE"""
    communes = get_collection("communes")
    
    # Recherche exacte par code
    exact = communes.find_one({"code_insee": query})
    if exact:
        return [{
            "code": exact["code_insee"],
            "nom": exact["nom"],
            "dept": exact.get("departement_code"),
            "dept_nom": exact.get("departement_nom"),
            "statut": exact.get("statut_couleur", "gris"),
            "lat": exact.get("centre_lat"),
            "lon": exact.get("centre_lon")
        }]
    
    # Recherche par nom (regex)
    cursor = communes.find(
        {"nom": {"$regex": query, "$options": "i"}},
        {
            "code_insee": 1,
            "nom": 1,
            "departement_code": 1,
            "departement_nom": 1,
            "statut_couleur": 1,
            "centre_lat": 1,
            "centre_lon": 1
        }
    ).limit(limit)
    
    return [
        {
            "code": doc["code_insee"],
            "nom": doc["nom"],
            "dept": doc.get("departement_code"),
            "dept_nom": doc.get("departement_nom"),
            "statut": doc.get("statut_couleur", "gris"),
            "lat": doc.get("centre_lat"),
            "lon": doc.get("centre_lon")
        }
        for doc in cursor
    ]


def log_update(started_at, finished_at, communes_updated, errors, status, error_message=None):
    """Enregistre un log de mise a jour"""
    logs = get_collection("update_logs")
    
    duration = (finished_at - started_at).total_seconds()
    
    logs.insert_one({
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": int(duration),
        "communes_updated": communes_updated,
        "errors_count": errors,
        "status": status,
        "error_message": error_message
    })

