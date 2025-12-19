"""
API FastAPI pour le suivi BAN
Sert les données GeoJSON à la demande pour une app fluide
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json
from pathlib import Path
from typing import Optional
import sqlite3

app = FastAPI(title="API Suivi BAN", version="1.0")

# CORS pour permettre les appels depuis Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chemins
CACHE_DIR = Path("cache")
GEOJSON_DIR = CACHE_DIR / "geojson"
DEPT_GEOJSON = CACHE_DIR / "departements_with_stats.geojson"
DB_PATH = Path("data/suivi_ban.db")

# Cache en mémoire pour les données fréquentes
_cache = {}


def get_db():
    """Connexion SQLite"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def root():
    return {"status": "ok", "message": "API Suivi BAN"}


@app.get("/api")
def api_root():
    return {"status": "ok", "message": "API Suivi BAN - /api endpoint"}


@app.get("/api/departements")
def get_departements():
    """Retourne le GeoJSON des départements avec stats"""
    if "departements" not in _cache:
        with open(DEPT_GEOJSON, 'r', encoding='utf-8') as f:
            _cache["departements"] = json.load(f)
    return _cache["departements"]


@app.get("/api/departement/{code}/communes")
def get_communes_departement(code: str):
    """Retourne le GeoJSON des communes d'un département"""
    cache_key = f"communes_{code}"
    
    if cache_key not in _cache:
        geojson_path = GEOJSON_DIR / f"{code}.geojson"
        if not geojson_path.exists():
            return JSONResponse(
                status_code=404,
                content={"error": f"Département {code} non trouvé"}
            )
        
        with open(geojson_path, 'r', encoding='utf-8') as f:
            _cache[cache_key] = json.load(f)
    
    return _cache[cache_key]


@app.get("/api/stats/global")
def get_stats_global():
    """Statistiques globales"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) as vert,
            SUM(CASE WHEN statut_couleur = 'orange' THEN 1 ELSE 0 END) as orange,
            SUM(CASE WHEN statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouge,
            SUM(CASE WHEN statut_couleur = 'jaune' THEN 1 ELSE 0 END) as jaune,
            SUM(CASE WHEN statut_couleur = 'gris' OR statut_couleur IS NULL THEN 1 ELSE 0 END) as gris,
            SUM(nb_numeros) as numeros,
            SUM(nb_voies) as voies
        FROM communes
    """)
    row = cursor.fetchone()
    conn.close()
    
    total = row['total'] or 1
    return {
        "total": row['total'] or 0,
        "vert": row['vert'] or 0,
        "orange": row['orange'] or 0,
        "rouge": row['rouge'] or 0,
        "jaune": row['jaune'] or 0,
        "gris": row['gris'] or 0,
        "numeros": row['numeros'] or 0,
        "voies": row['voies'] or 0,
        "pct_vert": round((row['vert'] or 0) / total * 100, 1),
        "pct_orange": round((row['orange'] or 0) / total * 100, 1),
        "pct_rouge": round((row['rouge'] or 0) / total * 100, 1),
        "pct_jaune": round((row['jaune'] or 0) / total * 100, 1),
        "pct_gris": round((row['gris'] or 0) / total * 100, 1),
    }


@app.get("/api/stats/departements")
def get_stats_departements():
    """Stats par département"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            departement_code as code,
            departement_nom as nom,
            COUNT(*) as total,
            SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) as vert,
            SUM(CASE WHEN statut_couleur = 'orange' THEN 1 ELSE 0 END) as orange,
            SUM(CASE WHEN statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouge,
            SUM(CASE WHEN statut_couleur = 'jaune' THEN 1 ELSE 0 END) as jaune,
            SUM(CASE WHEN statut_couleur = 'gris' OR statut_couleur IS NULL THEN 1 ELSE 0 END) as gris
        FROM communes
        WHERE departement_code IS NOT NULL
        GROUP BY departement_code, departement_nom
    """)
    
    result = {}
    for row in cursor.fetchall():
        total = row['total'] or 1
        result[row['code']] = {
            "code": row['code'],
            "nom": row['nom'],
            "total": row['total'],
            "vert": row['vert'] or 0,
            "orange": row['orange'] or 0,
            "rouge": row['rouge'] or 0,
            "jaune": row['jaune'] or 0,
            "gris": row['gris'] or 0,
            "pct_vert": round((row['vert'] or 0) / total * 100, 1),
        }
    
    conn.close()
    return result


@app.get("/api/producteurs")
def get_producteurs():
    """Liste des producteurs avec stats"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            r.client_nom as nom,
            COUNT(DISTINCT r.code_commune) as nb_communes,
            COUNT(DISTINCT c.departement_code) as nb_depts,
            GROUP_CONCAT(DISTINCT c.departement_code) as depts,
            SUM(CASE WHEN c.statut_couleur = 'vert' THEN 1 ELSE 0 END) as vert,
            SUM(CASE WHEN c.statut_couleur = 'orange' THEN 1 ELSE 0 END) as orange,
            SUM(CASE WHEN c.statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouge
        FROM revisions r
        JOIN communes c ON r.code_commune = c.code_insee
        WHERE r.is_current = 1 AND r.client_nom IS NOT NULL AND r.client_nom != ''
        GROUP BY r.client_nom
        ORDER BY nb_communes DESC
    """)
    
    result = []
    for row in cursor.fetchall():
        result.append({
            "nom": row['nom'],
            "nb_communes": row['nb_communes'],
            "nb_depts": row['nb_depts'],
            "depts": row['depts'].split(',') if row['depts'] else [],
            "vert": row['vert'] or 0,
            "orange": row['orange'] or 0,
            "rouge": row['rouge'] or 0,
        })
    
    conn.close()
    return result


@app.get("/api/producteur/{nom}/departements")
def get_producteur_departements(nom: str):
    """Stats par département pour un producteur"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.departement_code as code,
            c.departement_nom as nom,
            COUNT(*) as total,
            SUM(CASE WHEN c.statut_couleur = 'vert' THEN 1 ELSE 0 END) as vert,
            SUM(CASE WHEN c.statut_couleur = 'orange' THEN 1 ELSE 0 END) as orange,
            SUM(CASE WHEN c.statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouge,
            SUM(CASE WHEN c.statut_couleur = 'jaune' THEN 1 ELSE 0 END) as jaune,
            SUM(CASE WHEN c.statut_couleur = 'gris' OR c.statut_couleur IS NULL THEN 1 ELSE 0 END) as gris
        FROM communes c
        JOIN revisions r ON c.code_insee = r.code_commune
        WHERE r.is_current = 1 AND r.client_nom = ?
        GROUP BY c.departement_code, c.departement_nom
    """, (nom,))
    
    result = {}
    for row in cursor.fetchall():
        if row['code']:
            result[row['code']] = {
                "code": row['code'],
                "nom": row['nom'],
                "total": row['total'],
                "vert": row['vert'] or 0,
                "orange": row['orange'] or 0,
                "rouge": row['rouge'] or 0,
                "jaune": row['jaune'] or 0,
                "gris": row['gris'] or 0,
            }
    
    conn.close()
    return result


@app.get("/api/search/communes")
def search_communes(q: str = Query(..., min_length=2)):
    """Recherche de communes par nom ou code INSEE"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Chercher par nom OU par code INSEE
    cursor.execute("""
        SELECT 
            code_insee as code,
            nom,
            departement_code as dept,
            departement_nom as dept_nom,
            statut_couleur as statut,
            population,
            centre_lat as lat,
            centre_lon as lon
        FROM communes
        WHERE nom LIKE ? OR code_insee LIKE ?
        ORDER BY 
            CASE WHEN code_insee = ? THEN 0 ELSE 1 END,
            CASE WHEN code_insee LIKE ? THEN 0 ELSE 1 END,
            population DESC
        LIMIT 20
    """, (f"%{q}%", f"{q}%", q, f"{q}%"))
    
    result = []
    for row in cursor.fetchall():
        result.append({
            "code": row['code'],
            "nom": row['nom'],
            "dept": row['dept'],
            "dept_nom": row['dept_nom'],
            "statut": row['statut'] or 'gris',
            "population": row['population'],
            "lat": row['lat'],
            "lon": row['lon'],
        })
    
    conn.close()
    return result


@app.get("/api/commune/{code}")
def get_commune(code: str):
    """Détails d'une commune"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            c.code_insee as code,
            c.nom,
            c.departement_code as dept,
            c.departement_nom as dept_nom,
            c.statut_couleur as statut,
            c.population,
            c.nb_numeros,
            c.nb_voies,
            c.nb_voies_avec_banid,
            c.type_composition,
            c.centre_lat as lat,
            c.centre_lon as lon,
            c.contour,
            r.client_nom as producteur,
            r.published_at as date_publication
        FROM communes c
        LEFT JOIN revisions r ON c.code_insee = r.code_commune AND r.is_current = 1
        WHERE c.code_insee = ?
    """, (code,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return JSONResponse(status_code=404, content={"error": "Commune non trouvée"})
    
    contour = None
    if row['contour']:
        try:
            contour = json.loads(row['contour'])
        except:
            pass
    
    return {
        "code": row['code'],
        "nom": row['nom'],
        "dept": row['dept'],
        "dept_nom": row['dept_nom'],
        "statut": row['statut'] or 'gris',
        "population": row['population'],
        "nb_numeros": row['nb_numeros'],
        "nb_voies": row['nb_voies'],
        "nb_voies_avec_banid": row['nb_voies_avec_banid'],
        "type_composition": row['type_composition'],
        "lat": row['lat'],
        "lon": row['lon'],
        "contour": contour,
        "producteur": row['producteur'],
        "date_publication": row['date_publication'],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

