"""
Gestion de la connexion MongoDB pour Suivi BAN
"""

from pymongo import MongoClient, ASCENDING, GEOSPHERE, UpdateOne
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
    # Tuiles MVT : filtre par bbox + département.
    # Les index 2dsphere sont nativement sparse (docs sans le champ exclus automatiquement).
    # Ne pas mettre sparse=True : incompatible avec les index 2dsphere composés sur certaines versions.
    try:
        communes.create_index(
            [("departement_code", ASCENDING), ("geometry", GEOSPHERE)],
            name="dept_code_geometry_2dsphere",
        )
        communes.create_index(
            [("departement_code", ASCENDING), ("geometry_raw", GEOSPHERE)],
            name="dept_code_geometry_raw_2dsphere",
        )
        logger.info("Index geospatial 2dsphere communes crees (geometry + geometry_raw)")
    except Exception as e:
        logger.warning("Creation index geospatial communes ignoree: %s", e)
    
    # Index revisions
    revisions = db[COLLECTIONS["revisions"]]
    revisions.create_index("revision_id", unique=True)
    revisions.create_index("code_commune")
    revisions.create_index("client_nom")
    revisions.create_index("published_at")
    # Index partiel pour optimiser les requêtes sur is_current=True
    revisions.create_index([("code_commune", ASCENDING), ("is_current", ASCENDING)])
    
    # Index voies
    voies = db[COLLECTIONS["voies"]]
    voies.create_index("code_commune")
    voies.create_index("ban_id")
    
    # Index departements
    departements = db[COLLECTIONS["departements"]]
    departements.create_index("code", unique=True)

    # Index deploiement BAL
    deploiement_bal = db[COLLECTIONS["deploiement_bal_features"]]
    deploiement_bal.create_index("code_insee", unique=True)
    deploiement_bal.create_index([("geometry", GEOSPHERE)], name="geometry_2dsphere")
    deploiement_bal.create_index("properties.statusBals")
    deploiement_bal.create_index(
        [("properties.statusBals", ASCENDING), ("code_insee", ASCENDING)],
        name="status_code_insee_1",
    )
    
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
    
    # Si on insere/met a jour une revision avec is_current=True,
    # mettre toutes les autres revisions de la meme commune a is_current=False
    if data.get("is_current") is True and data.get("code_commune"):
        revisions.update_many(
            {
                "code_commune": data["code_commune"],
                "is_current": True,
                "revision_id": {"$ne": data["revision_id"]}  # Exclure la revision actuelle
            },
            {"$set": {"is_current": False, "updated_at": datetime.utcnow()}}
        )
    
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


def aggregate_stats_departements_from_communes():
    """
    Agrège les stats par département sur toute la collection communes.
    Réservé au cron (update_departements_stats) — coûteux, ne pas appeler par requête HTTP.
    """
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
                "gris": {"$sum": {"$cond": [{"$eq": ["$statut_couleur", "gris"]}, 1, 0]}},
            }
        }
    ]

    results: dict = {}
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
                "pct_vert": round(doc["vert"] / total * 100, 1),
            }

    return results


def get_stats_departements():
    """
    Statistiques par département pour l'API / le front.
    Lit les champs matérialisés ``departements.stats`` (alimentés par le cron), pas d'agrégation
    sur toute la collection ``communes`` — aligné sur les tuiles PBF.
    """
    departements = get_collection("departements")
    results: dict = {}
    for doc in departements.find({}, {"code": 1, "nom": 1, "stats": 1}):
        code = doc.get("code")
        if not code:
            continue
        st = doc.get("stats") or {}
        total = int(st.get("total", 0) or 0)
        vert = int(st.get("vert", 0) or 0)
        t = total or 1
        results[code] = {
            "code": code,
            "nom": doc.get("nom", f"Département {code}"),
            "total": total,
            "vert": vert,
            "orange": int(st.get("orange", 0) or 0),
            "rouge": int(st.get("rouge", 0) or 0),
            "jaune": int(st.get("jaune", 0) or 0),
            "gris": int(st.get("gris", 0) or 0),
            "pct_vert": round(vert / t * 100, 1) if st.get("pct_vert") is None else float(st["pct_vert"]),
        }

    return results


def update_departements_stats():
    """Met à jour les statistiques des départements dans la collection departements"""
    departements = get_collection("departements")
    stats = aggregate_stats_departements_from_communes()

    ops = []
    now = datetime.utcnow()
    for code, stat_data in stats.items():
        if not code:
            continue

        total = stat_data.get("total", 0) or 1
        vert = stat_data.get("vert", 0)
        orange = stat_data.get("orange", 0)
        rouge = stat_data.get("rouge", 0)
        jaune = stat_data.get("jaune", 0)
        gris = stat_data.get("gris", 0)

        pct_vert = round(vert / total * 100, 1)
        pct_orange = round(orange / total * 100, 1)
        pct_rouge = round(rouge / total * 100, 1)
        pct_jaune = round(jaune / total * 100, 1)

        max_count = max(orange, vert, rouge, jaune, gris)
        if orange == max_count:
            couleur_majoritaire, couleur_hex = "orange", "#ff8800"
        elif vert == max_count:
            couleur_majoritaire, couleur_hex = "vert", "#00A86B"
        elif rouge == max_count:
            couleur_majoritaire, couleur_hex = "rouge", "#DC143C"
        elif jaune == max_count:
            couleur_majoritaire, couleur_hex = "jaune", "#FFD700"
        else:
            couleur_majoritaire, couleur_hex = "gris", "#808080"

        ops.append(UpdateOne(
            {"code": code},
            {
                "$set": {
                    "nom": stat_data.get("nom") or f"Département {code}",
                    "stats": {
                        "total": stat_data.get("total", 0),
                        "vert": vert,
                        "orange": orange,
                        "rouge": rouge,
                        "jaune": jaune,
                        "gris": gris,
                        "pct_vert": pct_vert,
                        "pct_orange": pct_orange,
                        "pct_rouge": pct_rouge,
                        "pct_jaune": pct_jaune,
                        "couleur_majoritaire": couleur_majoritaire,
                        "couleur_hex": couleur_hex,
                    },
                    "stats_updated_at": now,
                }
            },
            upsert=True,
        ))

    if not ops:
        logger.info("Aucun département à mettre à jour")
        return 0

    result = departements.bulk_write(ops, ordered=False)
    updated = result.modified_count + result.upserted_count
    logger.info(f"Stats mises à jour pour {updated} départements ({len(ops)} opérations)")
    return updated


def get_communes_meta_by_departement(code_dept):
    """
    Liste légère des communes d'un département (sans géométrie) — pour UI / filtres.
    """
    communes = get_collection("communes")
    cursor = communes.find(
        {"departement_code": code_dept},
        {
            "code_insee": 1,
            "nom": 1,
            "statut_couleur": 1,
            "nb_numeros": 1,
            "nb_voies": 1,
            "type_composition": 1,
            "with_ban_id": 1,
            "producteur": 1,
            "centre_lat": 1,
            "centre_lon": 1,
            "population": 1,
            "date_revision": 1,
        },
    )
    out = []
    for doc in cursor:
        out.append(
            {
                "code": doc.get("code_insee"),
                "nom": doc.get("nom"),
                "statut": doc.get("statut_couleur", "gris"),
                "nb_numeros": doc.get("nb_numeros", 0) or 0,
                "nb_voies": doc.get("nb_voies", 0) or 0,
                "type_composition": doc.get("type_composition") or "",
                "with_ban_id": bool(doc.get("with_ban_id", False)),
                "producteur": doc.get("producteur") or "",
                "lat": doc.get("centre_lat"),
                "lon": doc.get("centre_lon"),
                "population": doc.get("population") or 0,
                "date_revision": doc.get("date_revision"),
            }
        )
    return out


def get_departement_bounds_leaflet(code: str):
    """BBox du département pour fitBounds Leaflet [[lat,lon],[lat,lon]] ou None."""
    from backend.api.tile_utils import geometry_bounds_leaflet

    dept = get_collection("departements").find_one({"code": code}, {"geometry": 1})
    if not dept:
        return None
    return geometry_bounds_leaflet(dept.get("geometry"))


def _doc_to_commune_feature(doc: dict) -> dict:
    """Construit une Feature GeoJSON commune à partir d'un document (géométrie déjà résolue)."""
    return {
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
            "lon": doc.get("centre_lon"),
        },
        "geometry": doc.get("geometry"),
    }


def get_communes_by_departement(code_dept):
    """Retourne les communes d'un departement en GeoJSON"""
    communes = get_collection("communes")
    pipeline = [
        {"$match": {"departement_code": code_dept}},
        {
            "$project": {
                "_id": 0,
                "code_insee": 1,
                "nom": 1,
                "statut_couleur": 1,
                "nb_numeros": 1,
                "nb_voies": 1,
                "type_composition": 1,
                "with_ban_id": 1,
                "producteur": 1,
                "centre_lat": 1,
                "centre_lon": 1,
                "geometry": {"$ifNull": ["$geometry", "$geometry_raw"]},
            }
        },
    ]
    features = [_doc_to_commune_feature(doc) for doc in communes.aggregate(pipeline)]
    return {"type": "FeatureCollection", "features": features}


def _bbox_polygon_geojson(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def get_communes_geojson_in_bbox(
    code_dept: str,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> dict:
    """
    Communes d'un département dont la géométrie intersecte la bbox (tuile XYZ).

    Deux requêtes séparées (geometry puis geometry_raw) pour que chacune exploite
    son propre index 2dsphere — évite le plan OR_PLAN moins efficace d'un $or.
    En cas d'échec (index manquant, géométrie invalide), repli sur scan département.
    """
    from backend.api.tile_utils import bbox_intersects, feature_bbox

    poly = _bbox_polygon_geojson(min_lon, min_lat, max_lon, max_lat)
    geo_clause = {"$geoIntersects": {"$geometry": poly}}
    communes = get_collection("communes")

    base_proj = {
        "code_insee": 1,
        "nom": 1,
        "statut_couleur": 1,
        "nb_numeros": 1,
        "nb_voies": 1,
        "type_composition": 1,
        "with_ban_id": 1,
        "producteur": 1,
        "centre_lat": 1,
        "centre_lon": 1,
    }
    tile_bbox = (min_lon, min_lat, max_lon, max_lat)
    try:
        seen: dict[str, dict] = {}

        # Requête 1 : via geometry → index dept_code_geometry_2dsphere
        for doc in communes.find(
            {"departement_code": code_dept, "geometry": geo_clause},
            {**base_proj, "geometry": 1},
            hint="dept_code_geometry_2dsphere",
        ):
            code = doc.get("code_insee")
            if code:
                seen[code] = {**doc, "geometry": doc.get("geometry")}

        # Requête 2 : via geometry_raw → index dept_code_geometry_raw_2dsphere
        # On ne filtre pas sur la présence de geometry:
        # certaines communes peuvent avoir geometry présent mais non exploitable,
        # tandis que geometry_raw est valide. Le dict "seen" gère la déduplication.
        for doc in communes.find(
            {
                "departement_code": code_dept,
                "geometry_raw": geo_clause,
            },
            {**base_proj, "geometry_raw": 1},
            hint="dept_code_geometry_raw_2dsphere",
        ):
            code = doc.get("code_insee")
            if code and code not in seen:
                seen[code] = {**doc, "geometry": doc.get("geometry_raw")}

        features = [_doc_to_commune_feature(d) for d in seen.values() if d.get("geometry")]
        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        logger.warning(
            "get_communes_geojson_in_bbox geo query dept=%s: %s — fallback scan departement",
            code_dept,
            e,
        )
        fc = get_communes_by_departement(code_dept)
        out = [
            f
            for f in fc.get("features", [])
            if isinstance(f, dict) and f.get("geometry") and bbox_intersects(feature_bbox(f), tile_bbox)
        ]
        return {"type": "FeatureCollection", "features": out}


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


def load_departements_from_geojson_file():
    """Charge les départements depuis le fichier departements_with_stats.geojson s'il existe"""
    from config import CACHE_DIR
    import json
    
    geojson_path = CACHE_DIR / "departements_with_stats.geojson"
    
    if not geojson_path.exists():
        return 0
    
    try:
        departements = get_collection("departements")
        
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        loaded = 0
        for feature in geojson_data.get("features", []):
            props = feature.get("properties", {})
            code = props.get("code")
            if not code:
                continue
            
            # Extraire les stats depuis les properties
            stats = {
                "total": props.get("total_communes", 0),
                "vert": props.get("communes_vertes", 0),
                "orange": props.get("communes_oranges", 0),
                "rouge": props.get("communes_rouges", 0),
                "jaune": props.get("communes_jaunes", 0),
                "gris": props.get("communes_grises", 0),
                "pct_vert": props.get("pct_vert", 0),
                "pct_orange": props.get("pct_orange", 0),
                "pct_rouge": props.get("pct_rouge", 0),
                "pct_jaune": props.get("pct_jaune", 0),
                "couleur_majoritaire": props.get("couleur_majoritaire", "gris"),
                "couleur_hex": props.get("couleur_hex", "#808080")
            }
            
            # Stocker dans MongoDB
            departements.update_one(
                {"code": code},
                {
                    "$set": {
                        "code": code,
                        "nom": props.get("nom", f"Département {code}"),
                        "geometry": feature.get("geometry"),
                        "stats": stats,
                        "loaded_at": datetime.utcnow(),
                        "loaded_from": "geojson_file"
                    }
                },
                upsert=True
            )
            loaded += 1
        
        logger.info(f"{loaded} départements chargés depuis {geojson_path}")
        return loaded
    except Exception as e:
        logger.warning(f"Erreur chargement depuis fichier GeoJSON: {e}")
        return 0


def load_departements_from_api():
    """Charge les départements depuis l'API geo.api.gouv.fr et les stocke dans MongoDB"""
    import requests
    from config import API_GEO
    
    departements = get_collection("departements")
    
    try:
        # Récupérer la liste des départements
        response = requests.get(f"{API_GEO}/departements", timeout=30)
        response.raise_for_status()
        depts_data = response.json()
        
        loaded = 0
        for dept in depts_data:
            code = dept.get("code")
            if not code:
                continue
            
            # Récupérer le contour du département
            try:
                dept_response = requests.get(
                    f"{API_GEO}/departements/{code}",
                    params={"fields": "nom,code,contour"},
                    timeout=30
                )
                dept_response.raise_for_status()
                dept_detail = dept_response.json()
                
                # Stocker dans MongoDB (sans stats, elles seront calculées après)
                departements.update_one(
                    {"code": code},
                    {
                        "$set": {
                            "code": code,
                            "nom": dept_detail.get("nom", dept.get("nom", f"Département {code}")),
                            "geometry": dept_detail.get("contour"),
                            "loaded_at": datetime.utcnow(),
                            "loaded_from": "api"
                        }
                    },
                    upsert=True
                )
                loaded += 1
            except Exception as e:
                logger.warning(f"Erreur chargement département {code}: {e}")
                continue
        
        logger.info(f"{loaded} départements chargés dans MongoDB depuis l'API")
        return loaded
    except Exception as e:
        logger.error(f"Erreur chargement départements: {e}")
        return 0


def get_departements_geojson():
    """Retourne le GeoJSON des départements depuis MongoDB avec les stats dans les properties"""
    departements = get_collection("departements")
    
    features = []
    for doc in departements.find({}, {"code": 1, "nom": 1, "geometry": 1, "stats": 1}):
        if not doc.get("code"):
            continue
        
        # Récupérer les stats si elles existent
        stats = doc.get("stats", {})
        
        # Construire les properties au format GeoJSON avec les stats
        properties = {
            "code": doc.get("code"),
            "nom": doc.get("nom", f"Département {doc.get('code')}"),
            "total_communes": stats.get("total", 0),
            "communes_vertes": stats.get("vert", 0),
            "communes_oranges": stats.get("orange", 0),
            "communes_rouges": stats.get("rouge", 0),
            "communes_jaunes": stats.get("jaune", 0),
            "communes_grises": stats.get("gris", 0),
            "pct_vert": stats.get("pct_vert", 0),
            "pct_orange": round(stats.get("orange", 0) / (stats.get("total", 1) or 1) * 100, 1),
            "pct_rouge": round(stats.get("rouge", 0) / (stats.get("total", 1) or 1) * 100, 1),
            "pct_jaune": round(stats.get("jaune", 0) / (stats.get("total", 1) or 1) * 100, 1)
        }
        
        # Déterminer la couleur majoritaire
        if stats.get("total", 0) > 0:
            max_count = max(
                stats.get("orange", 0),
                stats.get("vert", 0),
                stats.get("rouge", 0),
                stats.get("jaune", 0),
                stats.get("gris", 0)
            )
            if stats.get("orange", 0) == max_count:
                properties["couleur_majoritaire"] = "orange"
                properties["couleur_hex"] = "#ff8800"
            elif stats.get("vert", 0) == max_count:
                properties["couleur_majoritaire"] = "vert"
                properties["couleur_hex"] = "#00A86B"
            elif stats.get("rouge", 0) == max_count:
                properties["couleur_majoritaire"] = "rouge"
                properties["couleur_hex"] = "#DC143C"
            elif stats.get("jaune", 0) == max_count:
                properties["couleur_majoritaire"] = "jaune"
                properties["couleur_hex"] = "#FFD700"
            else:
                properties["couleur_majoritaire"] = "gris"
                properties["couleur_hex"] = "#808080"
        else:
            properties["couleur_majoritaire"] = "gris"
            properties["couleur_hex"] = "#808080"
        
        feature = {
            "type": "Feature",
            "properties": properties,
            "geometry": doc.get("geometry")
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


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


def replace_deploiement_bal_features(features: list[dict], source_stats: dict | None = None) -> int:
    """
    Remplace le snapshot de déploiement BAL.
    Les index sont conservés (deleteMany + insert_many).
    """
    coll = get_collection("deploiement_bal_features")
    meta = get_collection("deploiement_bal_meta")
    coll.delete_many({})
    inserted = 0
    if features:
        res = coll.insert_many(features, ordered=False)
        inserted = len(res.inserted_ids)
    meta.update_one(
        {"_id": "latest"},
        {
            "$set": {
                "updated_at": datetime.utcnow(),
                "features_count": inserted,
                "source_stats": source_stats or {},
            }
        },
        upsert=True,
    )
    return inserted


def get_deploiement_bal_stats(codes_commune: list[str] | None = None) -> dict:
    """Retourne la FeatureCollection déploiement BAL (optionnellement filtrée par codes INSEE)."""
    if not codes_commune:
        return {"type": "FeatureCollection", "features": []}
    coll = get_collection("deploiement_bal_features")
    query = {}
    query = {"code_insee": {"$in": codes_commune}}
    cursor = coll.find(query, {"_id": 0, "type": 1, "properties": 1, "geometry": 1})
    return {"type": "FeatureCollection", "features": list(cursor)}


def _doc_to_deploiement_feature(doc: dict) -> dict:
    return {
        "type": "Feature",
        "properties": doc.get("properties") or {},
        "geometry": doc.get("geometry"),
    }


def get_deploiement_bal_geojson_in_bbox(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> dict:
    """
    Features déploiement BAL intersectant la bbox (tuile XYZ).
    """
    poly = _bbox_polygon_geojson(min_lon, min_lat, max_lon, max_lat)
    coll = get_collection("deploiement_bal_features")
    cursor = coll.find(
        {
            "geometry": {
                "$geoIntersects": {"$geometry": poly}
            }
        },
        {
            "_id": 0,
            "properties": 1,
            "geometry": 1,
        },
    )
    features = []
    for doc in cursor:
        if doc.get("geometry"):
            features.append(_doc_to_deploiement_feature(doc))
    return {"type": "FeatureCollection", "features": features}

