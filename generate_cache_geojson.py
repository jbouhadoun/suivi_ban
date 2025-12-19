#!/usr/bin/env python3
"""
Génère des fichiers GeoJSON par département pour le cache
"""

import json
from pathlib import Path
from database import get_connection

CACHE_DIR = Path("cache/geojson")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def generate_department_geojson():
    """Génère un fichier GeoJSON par département"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("🗺️ Génération des fichiers GeoJSON par département...")
    
    # Récupérer la liste des départements
    cursor.execute("""
        SELECT DISTINCT departement_code, departement_nom
        FROM communes
        WHERE departement_code IS NOT NULL
        ORDER BY departement_code
    """)
    
    departements = cursor.fetchall()
    
    for dept_code, dept_nom in departements:
        print(f"  📍 {dept_code} - {dept_nom}...", end=" ")
        
        # Récupérer toutes les communes du département
        cursor.execute("""
            SELECT 
                c.code_insee, c.nom, c.centre_lat, c.centre_lon,
                c.statut_couleur, c.contour, c.population,
                c.nb_numeros, c.nb_voies, c.type_composition,
                c.with_ban_id, c.nb_voies_avec_banid, c.nb_numeros_certifies,
                r.client_nom, r.organisation, r.published_at,
                r.validation_valid, r.validation_errors, r.validation_warnings
            FROM communes c
            LEFT JOIN revisions r ON c.code_insee = r.code_commune AND r.is_current = 1
            WHERE c.departement_code = ?
            AND c.contour IS NOT NULL
        """, (dept_code,))
        
        features = []
        for row in cursor.fetchall():
            code, nom, lat, lon, statut, contour_json, pop, nb_num, nb_voies, type_comp, \
            with_ban, nb_voies_banid, nb_num_cert, prod, org, pub_date, val_valid, val_err, val_warn = row
            
            if contour_json:
                contour = json.loads(contour_json)
                
                # Déterminer la couleur
                color_map = {
                    'vert': '#00cc00',
                    'orange': '#ff8800',
                    'rouge': '#cc0000',
                    'jaune': '#ffdd00',
                    'gris': '#666666'
                }
                
                feature = {
                    "type": "Feature",
                    "geometry": contour,
                    "properties": {
                        "code": code,
                        "nom": nom,
                        "statut": statut,
                        "couleur": color_map.get(statut, '#666666'),
                        "population": pop,
                        "nb_numeros": nb_num,
                        "nb_numeros_certifies": nb_num_cert,
                        "nb_voies": nb_voies,
                        "nb_voies_avec_banid": nb_voies_banid,
                        "type_composition": type_comp,
                        "with_ban_id": with_ban,
                        "producteur": prod,
                        "organisation": org,
                        "date_publication": pub_date[:10] if pub_date else None,
                        "validation_valid": val_valid,
                        "validation_errors": val_err,
                        "validation_warnings": val_warn
                    }
                }
                features.append(feature)
        
        # Créer le GeoJSON
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        # Sauvegarder
        output_file = CACHE_DIR / f"{dept_code}.geojson"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False)
        
        print(f"✅ {len(features)} communes")
    
    conn.close()
    
    print(f"\n✅ {len(departements)} fichiers GeoJSON générés dans {CACHE_DIR}")
    print(f"📦 Taille totale: {sum(f.stat().st_size for f in CACHE_DIR.glob('*.geojson')) / 1024 / 1024:.1f} Mo")


def generate_national_markers():
    """Génère un fichier JSON léger avec juste les marqueurs pour la vue nationale"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n🎯 Génération du fichier de marqueurs nationaux...")
    
    cursor.execute("""
        SELECT 
            code_insee, nom, centre_lat, centre_lon,
            statut_couleur, population, nb_numeros, departement_code
        FROM communes
        WHERE centre_lat IS NOT NULL AND centre_lon IS NOT NULL
    """)
    
    markers = []
    for row in cursor.fetchall():
        code, nom, lat, lon, statut, pop, nb_num, dept = row
        
        color_map = {
            'vert': '#00cc00',
            'orange': '#ff8800',
            'rouge': '#cc0000',
            'jaune': '#ffdd00',
            'gris': '#666666'
        }
        
        markers.append({
            "code": code,
            "nom": nom,
            "lat": lat,
            "lon": lon,
            "statut": statut,
            "couleur": color_map.get(statut, '#666666'),
            "population": pop,
            "nb_numeros": nb_num,
            "departement": dept
        })
    
    output_file = CACHE_DIR.parent / "markers_national.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(markers, f, ensure_ascii=False)
    
    print(f"✅ {len(markers)} marqueurs sauvegardés")
    print(f"📦 Taille: {output_file.stat().st_size / 1024:.1f} Ko")
    
    conn.close()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🗺️ Génération des caches GeoJSON".center(70))
    print("="*70 + "\n")
    
    generate_department_geojson()
    generate_national_markers()
    
    print("\n✅ Cache généré ! Le dashboard sera maintenant ULTRA rapide ! 🚀")








