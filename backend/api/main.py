"""
API FastAPI pour Suivi BAN — stats JSON + tuiles vectorielles PBF pour la carte.
"""

import json
import logging
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import GEOJSON_DIR
from db.mongo import (
    get_collection,
    get_db,
    get_producteurs,
    get_stats_departements,
    get_stats_global,
    init_indexes,
    search_communes,
)
from backend.api.tiles_routes import router as tiles_router

logger = logging.getLogger(__name__)

_API_CACHE_HEADERS = {"Cache-Control": "public, max-age=21600"}
_STATS_GLOBAL_CACHE_TTL_SECONDS = 21600
_PRODUCTEURS_CACHE_TTL_SECONDS = 21600


def _prewarm_bal_index() -> None:
    """
    Préchauffe en tâche de fond, sans bloquer le démarrage :
      1. l'index BAL en mémoire (lecture Mongo + projection + simplification),
      2. les tuiles PBF bas zoom couvrant la France (z=4 à 7) dans le cache LRU.
    Activé par défaut pour éviter les tuiles bas-zoom lentes après reboot.
    En développement, on peut le désactiver avec PREWARM_BAL_INDEX=0 pour
    éviter de relancer un préchauffage long à chaque reload.
    """
    if os.getenv("PREWARM_BAL_INDEX", "1") not in ("1", "true", "TRUE", "yes"):
        return
    try:
        from backend.api.tiles_routes import tile_deploiement_bal, _get_bal_index

        logger.info("Préchauffage index BAL (background)")
        _get_bal_index()
        logger.info("Préchauffage index BAL terminé")

        # Tuiles couvrant la France métropolitaine et l'outre-mer proche
        # pour les zooms les plus coûteux à encoder dynamiquement.
        # x/y XYZ approximés pour englober la France ; les tuiles vides
        # sont encodées rapidement (réponse 0 octet, sans coût Python notable).
        france_ranges = {
            4: (range(7, 9), range(5, 6)),
            5: (range(15, 18), range(10, 12)),
            6: (range(30, 36), range(20, 24)),
            7: (range(60, 72), range(40, 47)),
        }
        for z, (xs, ys) in france_ranges.items():
            for x in xs:
                for y in ys:
                    try:
                        tile_deploiement_bal(z=z, x=x, y=y)
                    except Exception as e:
                        logger.debug("Préchauffe tuile z=%s x=%s y=%s: %s", z, x, y, e)
        logger.info("Préchauffage tuiles BAL bas zoom terminé")
    except Exception as e:
        logger.warning("Préchauffage BAL ignoré: %s", e)


def _build_global_stats_response(stats: Optional[dict]) -> dict:
    stats = stats or {}
    total = stats.get("total", 0)
    total_safe = total or 1
    return {
        "total": total,
        "vert": stats.get("vert", 0),
        "orange": stats.get("orange", 0),
        "rouge": stats.get("rouge", 0),
        "jaune": stats.get("jaune", 0),
        "gris": stats.get("gris", 0),
        "numeros": stats.get("numeros", 0),
        "voies": stats.get("voies", 0),
        "numeros_certifies": stats.get("numeros_certifies", 0),
        "numeros_fiabilises": stats.get("numeros_fiabilises", 0),
        "numeros_non_fiabilises": stats.get("numeros_non_fiabilises", 0),
        "pct_vert": round(stats.get("vert", 0) / total_safe * 100, 1),
        "pct_orange": round(stats.get("orange", 0) / total_safe * 100, 1),
        "pct_rouge": round(stats.get("rouge", 0) / total_safe * 100, 1),
        "pct_numeros_certifies": stats.get("pct_numeros_certifies", 0),
        "pct_numeros_fiabilises": stats.get("pct_numeros_fiabilises", 0),
    }


def _refresh_stats_global_cache() -> None:
    _cache["stats_global"] = {
        "value": _build_global_stats_response(get_stats_global()),
        "updated_at": time.time(),
    }


def _get_stats_global_cached() -> dict:
    cached = _cache.get("stats_global")
    now = time.time()
    if cached and now - cached.get("updated_at", 0) < _STATS_GLOBAL_CACHE_TTL_SECONDS:
        return cached.get("value", {})
    try:
        _refresh_stats_global_cache()
    except Exception as e:
        logger.warning("Refresh cache stats global impossible: %s", e)
        if cached:
            return cached.get("value", {})
        return _build_global_stats_response(None)
    return _cache.get("stats_global", {}).get("value", {})


def _prewarm_stats_cache() -> None:
    try:
        _refresh_stats_global_cache()
        logger.info("Préchauffage cache stats global terminé")
    except Exception as e:
        logger.warning("Préchauffage cache stats global ignoré: %s", e)


def _refresh_producteurs_cache() -> None:
    _cache["producteurs"] = {
        "value": get_producteurs(),
        "updated_at": time.time(),
    }


def _get_producteurs_cached() -> list:
    cached = _cache.get("producteurs")
    now = time.time()
    if cached and now - cached.get("updated_at", 0) < _PRODUCTEURS_CACHE_TTL_SECONDS:
        return cached.get("value", [])
    try:
        _refresh_producteurs_cache()
    except Exception as e:
        logger.warning("Refresh cache producteurs impossible: %s", e)
        if cached:
            return cached.get("value", [])
        return []
    return _cache.get("producteurs", {}).get("value", [])


def _prewarm_producteurs_cache() -> None:
    try:
        _refresh_producteurs_cache()
        logger.info("Préchauffage cache producteurs terminé")
    except Exception as e:
        logger.warning("Préchauffage cache producteurs ignoré: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_indexes()
    except Exception as e:
        logger.warning("init_indexes au démarrage ignorée: %s", e)
    threading.Thread(
        target=_prewarm_bal_index, name="prewarm-bal-index", daemon=True
    ).start()
    threading.Thread(
        target=_prewarm_stats_cache, name="prewarm-stats-cache", daemon=True
    ).start()
    threading.Thread(
        target=_prewarm_producteurs_cache, name="prewarm-producteurs-cache", daemon=True
    ).start()
    yield


app = FastAPI(
    title="Suivi BAN — API",
    version="2.0.0",
    lifespan=lifespan,
    description="""
**Statistiques et recherche** en JSON classique.

**Carte** : géométries servies uniquement en **tuiles vectorielles PBF (MVT)** — pas de gros GeoJSON côté navigateur.

- Tuiles départements : `/api/tiles/departements/{z}/{x}/{y}.pbf` (couche `departements`)
- Tuiles communes : `/api/tiles/departement/{code}/{z}/{x}/{y}.pbf` (couche `communes`)
- Liste communes (sans géométrie) : `/api/departement/{code}/communes-meta`
- Emprise carte : `/api/departement/{code}/bounds`
    """,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tiles_router)

_cache: dict = {}


@app.get("/api")
def api_root():
    return {
        "status": "ok",
        "message": "API Suivi BAN v2 - MongoDB",
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "openapi": "/api/openapi.json",
    }


@app.get("/api/health")
def health_check():
    try:
        get_db().command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )


@app.get("/api/departement/{code}/communes")
def get_communes_dept_geojson_legacy(code: str):
    """
    **Obsolète** — renvoie du GeoJSON lourd (RAM navigateur).
    Préférer `/api/tiles/departement/{code}/{z}/{x}/{y}.pbf` + `/api/departement/{code}/communes-meta`.
    """
    from db.mongo import get_communes_by_departement

    try:
        result = get_communes_by_departement(code)
        if result and result.get("features"):
            return result
    except Exception:
        pass

    cache_key = f"communes_{code}"
    if cache_key not in _cache:
        path = GEOJSON_DIR / f"{code}.geojson"
        if not path.exists():
            return JSONResponse(status_code=404, content={"error": f"Département {code} non trouvé"})
        with open(path, encoding="utf-8") as f:
            _cache[cache_key] = json.load(f)
    return _cache[cache_key]


@app.get("/api/departements")
def api_departements_geojson_legacy():
    """
    **Obsolète** — GeoJSON national lourd.
    Préférer `/api/tiles/departements/{z}/{x}/{y}.pbf` et `/api/stats/departements` pour les chiffres.
    """
    from db.mongo import get_departements_geojson

    if "departements" not in _cache:
        try:
            _cache["departements"] = get_departements_geojson()
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": f"Erreur récupération départements: {str(e)}"},
            )
    return _cache["departements"]


@app.get("/api/stats/global")
def api_stats_global():
    return JSONResponse(
        content=_get_stats_global_cached(),
        headers=_API_CACHE_HEADERS,
    )


@app.get("/api/stats/departements")
def api_stats_departements():
    return JSONResponse(
        content=get_stats_departements(),
        headers=_API_CACHE_HEADERS,
    )


@app.get("/api/producteurs")
def api_producteurs():
    return JSONResponse(
        content=_get_producteurs_cached(),
        headers=_API_CACHE_HEADERS,
    )


@app.get("/api/producteur/{nom}/departements")
def api_producteur_departements(nom: str):
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
                "voies": {"$sum": "$nb_voies"},
            }
        },
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
                "pct_vert": round(doc["vert"] / total * 100, 1),
            }

    return JSONResponse(
        content=results,
        headers=_API_CACHE_HEADERS,
    )


@app.get("/api/producteur/{nom}/stats")
def api_producteur_stats(nom: str):
    communes = get_collection("communes")

    pipeline = [
        {"$match": {"producteur": nom}},
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "numeros": {"$sum": "$nb_numeros"},
                "voies": {"$sum": "$nb_voies"},
            }
        },
    ]

    result = list(communes.aggregate(pipeline))
    if result:
        return JSONResponse(
            content={
                "total": result[0].get("total", 0),
                "numeros": result[0].get("numeros", 0) or 0,
                "voies": result[0].get("voies", 0) or 0,
            },
            headers=_API_CACHE_HEADERS,
        )
    return JSONResponse(
        content={"total": 0, "numeros": 0, "voies": 0},
        headers=_API_CACHE_HEADERS,
    )


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=2)):
    return search_communes(q, limit=20)


@app.get("/api/commune/{code}")
def api_commune(code: str):
    communes = get_collection("communes")

    doc = communes.find_one({"code_insee": code})

    if not doc:
        return JSONResponse(status_code=404, content={"error": "Commune non trouvée"})

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
        "has_bal": doc.get("has_bal", False),
    }


if __name__ == "__main__":
    import uvicorn
    from config import API_HOST, API_PORT

    uvicorn.run(app, host=API_HOST, port=API_PORT)
