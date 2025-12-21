"""
API FastAPI pour Suivi BAN
"""

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_DIR, GEOJSON_DIR
from db.mongo import (
    get_db, get_collection,
    get_stats_global, get_stats_departements,
    get_communes_by_departement, get_producteurs,
    search_communes, get_departements_geojson
)

app = FastAPI(title="Suivi BAN API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache memoire
_cache = {}


@app.get("/api")
def api_root():
    """Endpoint racine"""
    return {"status": "ok", "message": "API Suivi BAN v2 - MongoDB"}


@app.get("/api/health")
def health_check():
    """Verification de sante"""
    try:
        get_db().command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.get("/api/departements")
def api_departements_geojson():
    """Retourne le GeoJSON des departements depuis MongoDB"""
    if "departements" not in _cache:
        try:
            geojson = get_departements_geojson()
            _cache["departements"] = geojson
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Erreur récupération départements: {str(e)}"}
            )
    
    return _cache["departements"]


@app.get("/api/departement/{code}/communes")
def get_communes_dept(code: str):
    """Retourne le GeoJSON des communes d'un departement"""
    # Essayer d'abord depuis MongoDB
    try:
        result = get_communes_by_departement(code)
        if result and result.get("features"):
            return result
    except Exception:
        pass
    
    # Fallback sur le fichier cache
    cache_key = f"communes_{code}"
    if cache_key not in _cache:
        geojson_path = GEOJSON_DIR / f"{code}.geojson"
        if not geojson_path.exists():
            return JSONResponse(status_code=404, content={"error": f"Departement {code} non trouve"})
        
        with open(geojson_path, 'r', encoding='utf-8') as f:
            _cache[cache_key] = json.load(f)
    
    return _cache[cache_key]


@app.get("/api/stats/global")
def api_stats_global():
    """Statistiques globales"""
    stats = get_stats_global()
    
    if not stats:
        return {"total": 0, "vert": 0, "orange": 0, "rouge": 0, "jaune": 0, "gris": 0}
    
    total = stats.get("total", 1) or 1
    
    return {
        "total": stats.get("total", 0),
        "vert": stats.get("vert", 0),
        "orange": stats.get("orange", 0),
        "rouge": stats.get("rouge", 0),
        "jaune": stats.get("jaune", 0),
        "gris": stats.get("gris", 0),
        "numeros": stats.get("numeros", 0),
        "voies": stats.get("voies", 0),
        "pct_vert": round(stats.get("vert", 0) / total * 100, 1),
        "pct_orange": round(stats.get("orange", 0) / total * 100, 1),
        "pct_rouge": round(stats.get("rouge", 0) / total * 100, 1)
    }


@app.get("/api/stats/departements")
def api_stats_departements():
    """Stats par departement"""
    return get_stats_departements()


@app.get("/api/producteurs")
def api_producteurs():
    """Liste des producteurs"""
    return get_producteurs()


@app.get("/api/producteur/{nom}/departements")
def api_producteur_departements(nom: str):
    """Stats d'un producteur par departement"""
    communes = get_collection("communes")
    
    pipeline = [
        {"$match": {"producteur": nom}},
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
                "numeros": {"$sum": "$nb_numeros"},
                "voies": {"$sum": "$nb_voies"}
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
                "numeros": doc.get("numeros", 0) or 0,
                "voies": doc.get("voies", 0) or 0,
                "pct_vert": round(doc["vert"] / total * 100, 1)
            }
    
    return results


@app.get("/api/producteur/{nom}/stats")
def api_producteur_stats(nom: str):
    """Stats globales d'un producteur (numéros, voies, etc.)"""
    communes = get_collection("communes")
    
    pipeline = [
        {"$match": {"producteur": nom}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "numeros": {"$sum": "$nb_numeros"},
                "voies": {"$sum": "$nb_voies"}
            }
        }
    ]
    
    result = list(communes.aggregate(pipeline))
    if result:
        return {
            "total": result[0].get("total", 0),
            "numeros": result[0].get("numeros", 0) or 0,
            "voies": result[0].get("voies", 0) or 0
        }
    return {"total": 0, "numeros": 0, "voies": 0}


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=2)):
    """Recherche de communes"""
    return search_communes(q, limit=20)


@app.get("/api/commune/{code}")
def api_commune(code: str):
    """Details d'une commune"""
    communes = get_collection("communes")
    
    doc = communes.find_one({"code_insee": code})
    
    if not doc:
        return JSONResponse(status_code=404, content={"error": "Commune non trouvee"})
    
    return {
        "code": doc.get("code_insee"),
        "nom": doc.get("nom"),
        "dept": doc.get("departement_code"),
        "dept_nom": doc.get("departement_nom"),
        "region": doc.get("region_code"),
        "region_nom": doc.get("region_nom"),
        "population": doc.get("population"),
        "statut": doc.get("statut_couleur", "gris"),
        "lat": doc.get("centre_lat"),
        "lon": doc.get("centre_lon"),
        "with_ban_id": doc.get("with_ban_id", False),
        "nb_numeros": doc.get("nb_numeros", 0),
        "nb_numeros_certifies": doc.get("nb_numeros_certifies", 0),
        "nb_voies": doc.get("nb_voies", 0),
        "nb_lieux_dits": doc.get("nb_lieux_dits", 0),
        "type_composition": doc.get("type_composition"),
        "date_revision": doc.get("date_revision"),
        "producteur": doc.get("producteur"),
        "organisation": doc.get("organisation"),
        "has_bal": doc.get("has_bal", False)
    }


if __name__ == "__main__":
    import uvicorn
    from config import API_HOST, API_PORT
    uvicorn.run(app, host=API_HOST, port=API_PORT)


