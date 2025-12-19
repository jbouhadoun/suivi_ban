#!/usr/bin/env python3
"""
Génère le cache des polygones de départements avec couleur majoritaire
"""

import json
import requests
from pathlib import Path
from database import get_connection

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
DEPT_GEOJSON = CACHE_DIR / "departements_with_stats.geojson"

def get_departements_contours():
    """Télécharge les contours des départements depuis Etalab"""
    print("📥 Téléchargement des contours départements depuis Etalab...")
    
    url = "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/latest/geojson/departements-100m.geojson"
    
    try:
        response = requests.get(url, timeout=120)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {len(data['features'])} départements téléchargés")
            return data
        else:
            print(f"❌ Erreur HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None


def get_dept_stats():
    """Récupère les stats par département depuis la base"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            departement_code,
            departement_nom,
            COUNT(*) as total,
            SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) as vertes,
            SUM(CASE WHEN statut_couleur = 'orange' THEN 1 ELSE 0 END) as oranges,
            SUM(CASE WHEN statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouges,
            SUM(CASE WHEN statut_couleur = 'jaune' THEN 1 ELSE 0 END) as jaunes,
            SUM(CASE WHEN statut_couleur = 'gris' THEN 1 ELSE 0 END) as grises
        FROM communes
        WHERE departement_code IS NOT NULL
        GROUP BY departement_code, departement_nom
    """)
    
    stats = {}
    for row in cursor.fetchall():
        code, nom, total, vert, orange, rouge, jaune, gris = row
        
        # Déterminer couleur majoritaire
        couleurs = {
            'vert': vert,
            'orange': orange,
            'rouge': rouge,
            'jaune': jaune,
            'gris': gris
        }
        couleur_maj = max(couleurs, key=couleurs.get)
        
        stats[code] = {
            'nom': nom,
            'total': total,
            'vert': vert,
            'orange': orange,
            'rouge': rouge,
            'jaune': jaune,
            'gris': gris,
            'couleur_majoritaire': couleur_maj,
            'pct_vert': round(vert / total * 100, 1) if total > 0 else 0,
            'pct_orange': round(orange / total * 100, 1) if total > 0 else 0,
            'pct_rouge': round(rouge / total * 100, 1) if total > 0 else 0,
            'pct_jaune': round(jaune / total * 100, 1) if total > 0 else 0
        }
    
    conn.close()
    return stats


def generate_departements_geojson():
    """Génère le GeoJSON des départements avec stats"""
    print("\n🗺️ Génération du GeoJSON départements...")
    
    # Télécharger les vrais contours
    dept_geo = get_departements_contours()
    if not dept_geo:
        print("❌ Impossible de télécharger les contours")
        return False
    
    # Récupérer stats
    stats = get_dept_stats()
    
    # Mapper couleurs
    color_map = {
        'vert': '#00cc00',
        'orange': '#ff8800',
        'rouge': '#cc0000',
        'jaune': '#ffdd00',
        'gris': '#666666'
    }
    
    # Enrichir le GeoJSON
    features_enriched = []
    
    for feature in dept_geo['features']:
        code = feature['properties']['code']
        
        if code in stats:
            s = stats[code]
            
            feature['properties'].update({
                'total_communes': s['total'],
                'communes_vertes': s['vert'],
                'communes_oranges': s['orange'],
                'communes_rouges': s['rouge'],
                'communes_jaunes': s['jaune'],
                'communes_grises': s['gris'],
                'couleur_majoritaire': s['couleur_majoritaire'],
                'couleur_hex': color_map[s['couleur_majoritaire']],
                'pct_vert': s['pct_vert'],
                'pct_orange': s['pct_orange'],
                'pct_rouge': s['pct_rouge'],
                'pct_jaune': s['pct_jaune']
            })
            
            features_enriched.append(feature)
            print(f"  📍 {code} - {s['nom']}: {s['couleur_majoritaire'].upper()} ({s['total']} communes)")
    
    # Sauvegarder
    geojson_final = {
        'type': 'FeatureCollection',
        'features': features_enriched
    }
    
    with open(DEPT_GEOJSON, 'w', encoding='utf-8') as f:
        json.dump(geojson_final, f, ensure_ascii=False)
    
    print(f"\n✅ {len(features_enriched)} départements sauvegardés")
    print(f"📦 Taille: {DEPT_GEOJSON.stat().st_size / 1024:.1f} Ko")
    print(f"📁 Fichier: {DEPT_GEOJSON}")
    
    return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("🗺️ Génération cache départements".center(70))
    print("="*70)
    
    success = generate_departements_geojson()
    
    if success:
        print("\n✅ Cache départements généré !")
        exit(0)
    else:
        exit(1)

