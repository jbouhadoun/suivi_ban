#!/usr/bin/env python3
"""
Script de collecte des données BAN pour toutes les communes de France
"""

import requests
import time
from datetime import datetime
from database import init_database, get_connection, insert_commune, insert_revision, insert_voie
import json

# URLs des APIs
API_GEO = "https://geo.api.gouv.fr"
API_BAN_LOOKUP = "https://plateforme.adresse.data.gouv.fr/lookup"
API_BAL_DEPOT = "https://plateforme-bal.adresse.data.gouv.fr/api-depot"


def get_all_communes_geo():
    """Récupère toutes les communes depuis l'API Géo"""
    print("📥 Récupération de la liste des communes...")
    try:
        # Récupérer sans les contours (trop lourd)
        url = f"{API_GEO}/communes?fields=nom,code,centre,departement,region,codesPostaux,population&format=json"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            communes = response.json()
            print(f"✅ {len(communes)} communes récupérées")
            return communes
        else:
            print(f"❌ Erreur HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None


def get_commune_contour(code_insee):
    """Récupère le contour d'une commune spécifique"""
    try:
        url = f"{API_GEO}/communes/{code_insee}?fields=contour&format=json&geometry=contour"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('contour')
        return None
    except Exception:
        return None


def get_ban_lookup_data(code_insee):
    """Récupère les données BAN via l'API lookup"""
    try:
        url = f"{API_BAN_LOOKUP}/{code_insee}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def get_current_revision(code_insee):
    """Récupère la révision courante d'une commune"""
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
    """
    Détermine le statut couleur d'une commune
    - vert: withBanId = true
    - orange: withBanId = false MAIS des voies ont un banId
    - rouge: withBanId = false ET aucune voie avec banId
    - gris: pas de données BAN
    """
    if not ban_data:
        return 'gris'
    
    with_ban_id = ban_data.get('withBanId', False)
    
    if with_ban_id:
        return 'vert'
    
    # Si pas withBanId, vérifier si les voies ont des banId
    if voies_data:
        has_voie_with_banid = any(v.get('banId') for v in voies_data)
        return 'orange' if has_voie_with_banid else 'rouge'
    
    return 'rouge'


def count_voies_avec_banid(voies):
    """Compte le nombre de voies avec un banId"""
    if not voies:
        return 0
    return sum(1 for v in voies if v.get('banId'))


def collect_commune_data(commune_geo, conn):
    """Collecte toutes les données d'une commune et les insère dans la DB"""
    code_insee = commune_geo['code']
    
    # 1. Récupérer le contour
    contour = get_commune_contour(code_insee)
    
    # 2. Récupérer les données BAN (lookup)
    ban_data = get_ban_lookup_data(code_insee)
    
    # 3. Récupérer la révision courante
    revision_info = get_current_revision(code_insee)
    
    has_bal = revision_info is not None
    revision_details = None
    
    if revision_info and 'id' in revision_info:
        revision_details = get_revision_details(revision_info['id'])
    
    # 4. Extraire les voies
    voies = ban_data.get('voies', []) if ban_data else []
    nb_voies_avec_banid = count_voies_avec_banid(voies)
    
    # 5. Déterminer le statut couleur
    statut_couleur = determine_statut_couleur(ban_data, voies)
    
    # 6. Préparer les données commune
    commune_data = {
        'code_insee': code_insee,
        'nom': commune_geo.get('nom'),
        'departement_code': commune_geo.get('departement', {}).get('code'),
        'departement_nom': commune_geo.get('departement', {}).get('nom'),
        'region_code': commune_geo.get('region', {}).get('code'),
        'region_nom': commune_geo.get('region', {}).get('nom'),
        'population': commune_geo.get('population', 0),
        'codes_postaux': commune_geo.get('codesPostaux', []),
        'centre_lat': commune_geo.get('centre', {}).get('coordinates', [None, None])[1] if commune_geo.get('centre') else None,
        'centre_lon': commune_geo.get('centre', {}).get('coordinates', [None, None])[0] if commune_geo.get('centre') else None,
        'contour': contour,
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
    }
    
    # 7. Insérer la commune
    insert_commune(conn, commune_data)
    
    # 8. Insérer la révision si elle existe
    if revision_details:
        revision_data = {
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
        insert_revision(conn, revision_data)
    
    # 9. Insérer les voies (limiter pour ne pas surcharger)
    for voie in voies[:50]:  # Limiter à 50 voies principales
        voie_data = {
            'id': voie.get('id'),
            'code_commune': code_insee,
            'id_voie': voie.get('idVoie'),
            'ban_id': voie.get('banId'),
            'nom_voie': voie.get('nomVoie'),
            'nb_numeros': voie.get('nbNumeros', 0),
            'nb_numeros_certifies': voie.get('nbNumerosCertifies', 0),
            'has_ban_id': voie.get('banId') is not None
        }
        insert_voie(conn, voie_data)
    
    return statut_couleur


def main():
    """Fonction principale"""
    print("\n" + "="*70)
    print("🗺️  Collecte des données BAN - Toutes les communes de France".center(70))
    print("="*70 + "\n")
    
    start_time = datetime.now()
    
    # 1. Initialiser la base de données
    print("1️⃣  Initialisation de la base de données...")
    init_database()
    
    # 2. Récupérer toutes les communes
    print("\n2️⃣  Récupération des communes...")
    communes = get_all_communes_geo()
    
    if not communes:
        print("❌ Impossible de récupérer les communes")
        return False
    
    total = len(communes)
    print(f"✅ {total} communes à traiter\n")
    
    # 3. Traiter chaque commune
    print("3️⃣  Collecte des données BAN...")
    print("-" * 70)
    
    stats = {
        'total': total,
        'vert': 0,
        'orange': 0,
        'rouge': 0,
        'gris': 0,
        'erreurs': 0
    }
    
    conn = get_connection()
    
    try:
        for idx, commune in enumerate(communes, 1):
            try:
                statut = collect_commune_data(commune, conn)
                stats[statut] += 1
                
                # Afficher la progression tous les 50 communes
                if idx % 50 == 0:
                    pct = (idx / total) * 100
                    elapsed = (datetime.now() - start_time).total_seconds()
                    eta = (elapsed / idx) * (total - idx)
                    print(f"  [{idx:>5}/{total}] {pct:>5.1f}% | {commune['nom']:<30} | ETA: {eta/60:.0f}min")
                
                # Commit tous les 100 communes
                if idx % 100 == 0:
                    conn.commit()
                
            except Exception as e:
                stats['erreurs'] += 1
                print(f"  ⚠️  Erreur pour {commune.get('nom', commune.get('code'))}: {e}")
        
        # Commit final
        conn.commit()
        
    finally:
        conn.close()
    
    # 4. Afficher les résultats
    duration = (datetime.now() - start_time).total_seconds()
    
    print("\n" + "="*70)
    print("✅ Collecte terminée !".center(70))
    print("="*70)
    
    print(f"\n⏱️  Durée totale: {duration/60:.1f} minutes")
    print(f"\n📊 Statistiques:\n")
    print(f"   Total communes  : {stats['total']:>6,}")
    print(f"   🟢 Vertes       : {stats['vert']:>6,} ({stats['vert']/stats['total']*100:>5.1f}%)")
    print(f"   🟠 Oranges      : {stats['orange']:>6,} ({stats['orange']/stats['total']*100:>5.1f}%)")
    print(f"   🔴 Rouges       : {stats['rouge']:>6,} ({stats['rouge']/stats['total']*100:>5.1f}%)")
    print(f"   ⚫ Grises       : {stats['gris']:>6,} ({stats['gris']/stats['total']*100:>5.1f}%)")
    print(f"   ⚠️  Erreurs      : {stats['erreurs']:>6,}")
    
    print(f"\n💾 Base de données : data/suivi_ban.db")
    print("\n✨ Vous pouvez maintenant lancer le dashboard !")
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

