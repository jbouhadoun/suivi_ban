#!/usr/bin/env python3
"""
Script de collecte ULTRA-RAPIDE des données BAN
Télécharge les contours en 1 fois, puis collecte en multiprocess
"""

import requests
import time
from datetime import datetime
from database import init_database, get_connection, insert_commune, insert_revision, insert_voie
import json
from multiprocessing import Pool, cpu_count
from pathlib import Path

# URLs des APIs
API_BAN_LOOKUP = "https://plateforme.adresse.data.gouv.fr/lookup"
API_BAL_DEPOT = "https://plateforme-bal.adresse.data.gouv.fr/api-depot"
# Fichier GeoJSON complet des communes
COMMUNES_GEOJSON_URL = "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/latest/geojson/communes-100m.geojson"

# Configuration
NUM_WORKERS = min(cpu_count() * 3, 24)  # Max 24 workers
BATCH_SIZE = 100
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
COMMUNES_FILE = CACHE_DIR / "communes_geojson.json"


def download_communes_geojson():
    """Télécharge le GeoJSON de toutes les communes (1 seul appel !)"""
    print("📥 Téléchargement du GeoJSON des communes...")
    
    if COMMUNES_FILE.exists():
        print(f"✅ Fichier déjà en cache: {COMMUNES_FILE}")
        with open(COMMUNES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    try:
        response = requests.get(COMMUNES_GEOJSON_URL, timeout=120)
        if response.status_code == 200:
            data = response.json()
            
            # Sauvegarder en cache
            with open(COMMUNES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            
            print(f"✅ {len(data.get('features', []))} communes téléchargées")
            return data
        else:
            print(f"❌ Erreur HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None


def build_communes_dict(geojson_data):
    """Construit un dict {code_insee: {infos + contour}}"""
    communes_dict = {}
    
    for feature in geojson_data.get('features', []):
        props = feature.get('properties', {})
        code = props.get('code')
        
        if code:
            communes_dict[code] = {
                'code': code,
                'nom': props.get('nom'),
                'departement_code': code[:2] if len(code) >= 2 else None,
                'departement_nom': None,  # On le récupérera via BAN
                'region_code': None,
                'region_nom': None,
                'population': props.get('population', 0),
                'centre': None,  # On le calculera si besoin
                'contour': feature.get('geometry')
            }
    
    print(f"✅ {len(communes_dict)} communes indexées")
    return communes_dict


def get_ban_lookup_data(code_insee):
    """Récupère les données BAN"""
    try:
        url = f"{API_BAN_LOOKUP}/{code_insee}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def get_current_revision(code_insee):
    """Récupère la révision courante"""
    try:
        url = f"{API_BAL_DEPOT}/communes/{code_insee}/current-revision"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def get_revision_details(revision_id):
    """Récupère les détails d'une révision"""
    try:
        url = f"{API_BAL_DEPOT}/revisions/{revision_id}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def determine_statut_couleur(ban_data, voies_data=None):
    """Détermine le statut couleur"""
    if not ban_data:
        return 'gris'
    
    with_ban_id = ban_data.get('withBanId', False)
    if with_ban_id:
        return 'vert'
    
    if voies_data:
        has_voie_with_banid = any(v.get('banId') for v in voies_data)
        return 'orange' if has_voie_with_banid else 'rouge'
    
    return 'rouge'


def count_voies_avec_banid(voies):
    """Compte les voies avec banId"""
    if not voies:
        return 0
    return sum(1 for v in voies if v.get('banId'))


def collect_commune_worker(code_and_commune):
    """Worker qui collecte les données d'une commune (SEULEMENT 2 appels API max !)"""
    code_insee, commune_geo = code_and_commune
    
    try:
        # 1. Récupérer données BAN (1 appel)
        ban_data = get_ban_lookup_data(code_insee)
        
        # 2. Récupérer révision courante (1 appel)
        revision_info = get_current_revision(code_insee)
        
        has_bal = revision_info is not None
        revision_details = None
        
        # 3. Si révision existe, récupérer détails (1 appel optionnel)
        if revision_info and 'id' in revision_info:
            revision_details = get_revision_details(revision_info['id'])
        
        voies = ban_data.get('voies', []) if ban_data else []
        nb_voies_avec_banid = count_voies_avec_banid(voies)
        statut_couleur = determine_statut_couleur(ban_data, voies)
        
        # Enrichir avec données BAN
        if ban_data:
            commune_geo['departement_nom'] = ban_data.get('departement', {}).get('nom')
            commune_geo['region_code'] = ban_data.get('region', {}).get('code')
            commune_geo['region_nom'] = ban_data.get('region', {}).get('nom')
            if 'displayBBox' in ban_data and ban_data['displayBBox']:
                bbox = ban_data['displayBBox']
                commune_geo['centre'] = {
                    'coordinates': [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
                }
        
        result = {
            'commune': {
                'code_insee': code_insee,
                'nom': commune_geo.get('nom'),
                'departement_code': commune_geo.get('departement_code'),
                'departement_nom': commune_geo.get('departement_nom'),
                'region_code': commune_geo.get('region_code'),
                'region_nom': commune_geo.get('region_nom'),
                'population': commune_geo.get('population', 0),
                'codes_postaux': ban_data.get('codesPostaux', []) if ban_data else [],
                'centre_lat': commune_geo.get('centre', {}).get('coordinates', [None, None])[1] if commune_geo.get('centre') else None,
                'centre_lon': commune_geo.get('centre', {}).get('coordinates', [None, None])[0] if commune_geo.get('centre') else None,
                'contour': commune_geo.get('contour'),
                'with_ban_id': ban_data.get('withBanId', False) if ban_data else False,
                'nb_numeros': ban_data.get('nbNumeros', 0) if ban_data else 0,
                'nb_numeros_certifies': ban_data.get('nbNumerosCertifies', 0) if ban_data else 0,
                'nb_voies': ban_data.get('nbVoies', 0) if ban_data else 0,
                'nb_voies_avec_banid': nb_voies_avec_banid,
                'nb_lieux_dits': ban_data.get('nbLieuxDits', 0) if ban_data else 0,
                'type_composition': ban_data.get('typeComposition') if ban_data else None,
                'date_revision': ban_data.get('dateRevision') if ban_data else None,
                'has_bal': has_bal,
                'statut_couleur': statut_couleur
            },
            'revision': None,
            'voies': [],
            'statut': statut_couleur
        }
        
        # Révision
        if revision_details:
            result['revision'] = {
                'revision_id': revision_details.get('id'),
                'code_commune': code_insee,
                'created_at': revision_details.get('createdAt'),
                'updated_at': revision_details.get('updatedAt'),
                'published_at': revision_details.get('publishedAt'),
                'is_current': revision_details.get('isCurrent', True),
                'status': revision_details.get('status'),
                'client_id': revision_details.get('client', {}).get('id') if revision_details.get('client') else None,
                'client_nom': revision_details.get('client', {}).get('nom') if revision_details.get('client') else None,
                'client_mandataire': revision_details.get('client', {}).get('mandataire') if revision_details.get('client') else None,
                'client_chef_de_file': revision_details.get('client', {}).get('chefDeFile') if revision_details.get('client') else None,
                'client_email': revision_details.get('client', {}).get('chefDeFileEmail') if revision_details.get('client') else None,
                'organisation': revision_details.get('context', {}).get('organisation') if revision_details.get('context') else None,
                'validation_valid': revision_details.get('validation', {}).get('valid', False) if revision_details.get('validation') else False,
                'validation_errors': len(revision_details.get('validation', {}).get('errors', [])) if revision_details.get('validation') else 0,
                'validation_warnings': len(revision_details.get('validation', {}).get('warnings', [])) if revision_details.get('validation') else 0,
                'validation_infos': len(revision_details.get('validation', {}).get('infos', [])) if revision_details.get('validation') else 0,
                'validation_rows_count': revision_details.get('validation', {}).get('rowsCount', 0) if revision_details.get('validation') else 0,
                'validator_version': revision_details.get('validation', {}).get('validatorVersion') if revision_details.get('validation') else None,
                'file_size': revision_details.get('files', [{}])[0].get('size', 0) if revision_details.get('files') else 0
            }
        
        # Voies (limiter à 30 pour être rapide)
        for voie in voies[:30]:
            result['voies'].append({
                'id': voie.get('id'),
                'code_commune': code_insee,
                'id_voie': voie.get('idVoie'),
                'ban_id': voie.get('banId'),
                'nom_voie': voie.get('nomVoie'),
                'nb_numeros': voie.get('nbNumeros', 0),
                'nb_numeros_certifies': voie.get('nbNumerosCertifies', 0),
                'has_ban_id': voie.get('banId') is not None
            })
        
        return result
        
    except Exception as e:
        return {
            'error': str(e),
            'code': code_insee,
            'nom': commune_geo.get('nom')
        }


def write_batch_to_db(batch_results):
    """Écrit un batch de résultats dans la DB"""
    conn = get_connection()
    try:
        for result in batch_results:
            if 'error' in result:
                continue
                
            insert_commune(conn, result['commune'])
            
            if result['revision']:
                insert_revision(conn, result['revision'])
            
            for voie in result['voies']:
                insert_voie(conn, voie)
        
        conn.commit()
        return True
    except Exception as e:
        print(f"  ⚠️  Erreur écriture: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    """Fonction principale"""
    print("\n" + "="*70)
    print("⚡ Collecte ULTRA-RAPIDE - Communes de France".center(70))
    print("="*70 + "\n")
    
    start_time = datetime.now()
    
    # 1. Initialiser la base
    print("1️⃣  Initialisation de la base de données...")
    init_database()
    
    # 2. Télécharger GeoJSON des communes (1 SEUL appel !)
    print("\n2️⃣  Téléchargement des contours...")
    geojson_data = download_communes_geojson()
    
    if not geojson_data:
        print("❌ Impossible de télécharger les contours")
        return False
    
    # 3. Indexer les communes
    print("\n3️⃣  Indexation des communes...")
    communes_dict = build_communes_dict(geojson_data)
    
    total = len(communes_dict)
    print(f"\n✅ {total} communes à traiter")
    print(f"👷 {NUM_WORKERS} workers en parallèle")
    print(f"⚡ 2-3 appels API par commune (au lieu de 5)\n")
    
    # 4. Traiter en parallèle
    print("4️⃣  Collecte des données BAN (multiprocess)...")
    print("-" * 70)
    
    stats = {'vert': 0, 'orange': 0, 'rouge': 0, 'gris': 0, 'erreurs': 0}
    
    processed = 0
    batch = []
    
    with Pool(NUM_WORKERS) as pool:
        for result in pool.imap_unordered(collect_commune_worker, communes_dict.items(), chunksize=20):
            if 'error' in result:
                stats['erreurs'] += 1
            else:
                batch.append(result)
                stats[result['statut']] += 1
            
            processed += 1
            
            # Écrire par batch
            if len(batch) >= BATCH_SIZE:
                write_batch_to_db(batch)
                batch = []
            
            # Afficher progression
            if processed % 500 == 0:
                pct = (processed / total) * 100
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (total - processed) / rate if rate > 0 else 0
                print(f"  [{processed:>5}/{total}] {pct:>5.1f}% | ⚡{rate:>5.1f} c/s | ETA: {eta/60:>4.0f}min | "
                      f"🟢{stats['vert']} 🟠{stats['orange']} 🔴{stats['rouge']} ⚫{stats['gris']}")
    
    # Écrire le dernier batch
    if batch:
        write_batch_to_db(batch)
    
    # 5. Résultats
    duration = (datetime.now() - start_time).total_seconds()
    
    print("\n" + "="*70)
    print("✅ Collecte terminée !".center(70))
    print("="*70)
    
    print(f"\n⏱️  Durée totale: {duration/60:.1f} minutes")
    print(f"⚡ Vitesse moyenne: {total/duration:.1f} communes/seconde")
    print(f"\n📊 Statistiques:\n")
    print(f"   Total communes  : {total:>6,}")
    print(f"   🟢 Vertes       : {stats['vert']:>6,} ({stats['vert']/total*100:>5.1f}%)")
    print(f"   🟠 Oranges      : {stats['orange']:>6,} ({stats['orange']/total*100:>5.1f}%)")
    print(f"   🔴 Rouges       : {stats['rouge']:>6,} ({stats['rouge']/total*100:>5.1f}%)")
    print(f"   ⚫ Grises       : {stats['gris']:>6,} ({stats['gris']/total*100:>5.1f}%)")
    print(f"   ⚠️  Erreurs      : {stats['erreurs']:>6,}")
    
    print(f"\n💾 Base de données : data/suivi_ban.db")
    print(f"💾 Cache contours : {COMMUNES_FILE}")
    print("\n✨ Lancez : streamlit run app.py")
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)










