"""
Collecteur intelligent pour Suivi BAN
Recupere uniquement les communes modifiees dans les N derniers jours
"""

import requests
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    API_GEO, API_BAN_LOOKUP, API_BAL_DEPOT,
    COLLECT_WINDOW_DAYS, API_TIMEOUT, COLLECT_WORKERS
)
from db.mongo import (
    upsert_commune, upsert_revision, get_collection, log_update
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_communes_to_update(since_date):
    """Determine les communes a mettre a jour"""
    from db.mongo import get_collection
    
    communes = get_collection("communes")
    
    # Strategie 1: Chercher les communes avec date_revision plus recente que celle en base
    # On compare date_revision de l'API BAN avec celle qu'on a stockee
    
    # Pour l'instant, on va verifier toutes les communes mais de facon optimisee:
    # - On recupere toutes les communes depuis MongoDB
    # - Pour chaque commune, on appelle l'API BAN lookup qui donne dateRevision
    # - On compare avec date_revision stockee
    # - On met a jour seulement si different
    
    # Pour la premiere execution, on retourne toutes les communes
    # Pour les executions suivantes, on peut filtrer par date_revision en base
    
    cursor = communes.find(
        {},
        {"code_insee": 1, "date_revision": 1}
    )
    
    all_communes = [(doc["code_insee"], doc.get("date_revision")) for doc in cursor]
    
    if not all_communes:
        logger.info("Aucune commune en base, collecte complete necessaire")
        return None
    
    logger.info(f"{len(all_communes)} communes en base, verification des mises a jour...")
    return all_communes


def get_commune_geo(code_insee):
    """Recupere les infos geographiques d'une commune"""
    try:
        url = f"{API_GEO}/communes/{code_insee}"
        params = {
            "fields": "nom,code,centre,departement,region,codesPostaux,population,contour",
            "format": "json",
            "geometry": "contour"
        }
        
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            return response.json()
        return None
        
    except Exception as e:
        logger.debug(f"Erreur geo {code_insee}: {e}")
        return None


def get_ban_lookup(code_insee):
    """Recupere les donnees BAN d'une commune"""
    try:
        url = f"{API_BAN_LOOKUP}/{code_insee}"
        response = requests.get(url, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            return response.json()
        return None
        
    except Exception as e:
        logger.debug(f"Erreur BAN {code_insee}: {e}")
        return None


def get_current_revision(code_insee):
    """Recupere la revision courante d'une commune"""
    try:
        url = f"{API_BAL_DEPOT}/communes/{code_insee}/current-revision"
        response = requests.get(url, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            return response.json()
        return None
        
    except Exception as e:
        logger.debug(f"Erreur current-revision {code_insee}: {e}")
        return None


def get_revision_details(revision_id):
    """Recupere les details d'une revision"""
    try:
        url = f"{API_BAL_DEPOT}/revisions/{revision_id}"
        response = requests.get(url, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            return response.json()
        return None
        
    except Exception as e:
        logger.debug(f"Erreur revision {revision_id}: {e}")
        return None


def determine_statut(ban_data):
    """Determine le statut couleur d'une commune"""
    if not ban_data:
        return "gris"
    
    with_ban_id = ban_data.get("withBanId", False)
    
    if with_ban_id:
        return "vert"
    
    # Verifier si des voies ont un banId
    voies = ban_data.get("voies", [])
    has_voie_with_banid = any(v.get("banId") for v in voies)
    
    if has_voie_with_banid:
        return "orange"
    
    # Assemblage n'est plus un statut couleur, c'est un type de composition
    # Si pas d'ID, c'est rouge (avec ou sans assemblage)
    return "rouge"


def collect_commune(code_insee, revision_data=None):
    """Collecte toutes les donnees d'une commune"""
    try:
        # Donnees geographiques
        geo_data = get_commune_geo(code_insee)
        if not geo_data:
            return None
        
        # Donnees BAN
        ban_data = get_ban_lookup(code_insee)
        
        # Statut couleur
        statut = determine_statut(ban_data)
        
        # Construire le document
        doc = {
            "code_insee": code_insee,
            "nom": geo_data.get("nom"),
            "departement_code": geo_data.get("departement", {}).get("code"),
            "departement_nom": geo_data.get("departement", {}).get("nom"),
            "region_code": geo_data.get("region", {}).get("code"),
            "region_nom": geo_data.get("region", {}).get("nom"),
            "population": geo_data.get("population", 0),
            "codes_postaux": geo_data.get("codesPostaux", []),
            "centre_lat": geo_data.get("centre", {}).get("coordinates", [None, None])[1],
            "centre_lon": geo_data.get("centre", {}).get("coordinates", [None, None])[0],
            "with_ban_id": ban_data.get("withBanId", False) if ban_data else False,
            "nb_numeros": ban_data.get("nbNumeros", 0) if ban_data else 0,
            "nb_numeros_certifies": ban_data.get("nbNumerosCertifies", 0) if ban_data else 0,
            "nb_voies": ban_data.get("nbVoies", 0) if ban_data else 0,
            "nb_lieux_dits": ban_data.get("nbLieuxDits", 0) if ban_data else 0,
            "type_composition": ban_data.get("typeComposition") if ban_data else None,
            "date_revision": ban_data.get("dateRevision") if ban_data else None,
            "statut_couleur": statut,
            "collected_at": datetime.utcnow()
        }
        
        # Ajouter la geometrie
        contour = geo_data.get("contour")
        if contour:
            doc["geometry"] = contour
        
        # Ajouter les infos de revision
        if revision_data:
            doc["producteur"] = revision_data.get("client", {}).get("nom")
            doc["organisation"] = revision_data.get("context", {}).get("organisation")
            doc["date_publication"] = revision_data.get("publishedAt")
            doc["has_bal"] = True
            
            validation = revision_data.get("validation", {})
            doc["validation_valid"] = validation.get("valid", False)
            doc["validation_errors"] = len(validation.get("errors", []))
            doc["validation_warnings"] = len(validation.get("warnings", []))
        
        return doc
        
    except Exception as e:
        logger.error(f"Erreur collecte {code_insee}: {e}")
        return None


def process_commune(code_commune, stored_date_revision=None):
    """Traite une commune et met a jour ses donnees si necessaire"""
    try:
        # D'abord, recuperer les donnees BAN (plus rapide que revision)
        ban_data = get_ban_lookup(code_commune)
        
        if not ban_data:
            # Pas de donnees BAN, on peut skip si on a deja une date
            if stored_date_revision:
                return None, "Pas de changement (pas de donnees BAN)"
            # Sinon on collecte quand meme pour avoir les infos de base
        else:
            # Comparer dateRevision avec celle stockee
            api_date_revision = ban_data.get("dateRevision")
            if stored_date_revision and api_date_revision == stored_date_revision:
                # Pas de changement, on skip
                return None, "Pas de changement"
        
        # Il y a un changement ou premiere collecte, on continue
        # Recuperer la revision courante
        revision_info = get_current_revision(code_commune)
        
        revision_details = None
        if revision_info and revision_info.get("id"):
            revision_details = get_revision_details(revision_info["id"])
        
        # Collecter les donnees de la commune
        doc = collect_commune(code_commune, revision_details)
        
        if doc:
            upsert_commune(doc)
            
            # Sauvegarder aussi la revision
            if revision_details:
                rev_doc = {
                    "revision_id": revision_details.get("id"),
                    "code_commune": code_commune,
                    "created_at": revision_details.get("createdAt"),
                    "updated_at": revision_details.get("updatedAt"),
                    "published_at": revision_details.get("publishedAt"),
                    "is_current": True,
                    "status": revision_details.get("status"),
                    "client_id": revision_details.get("client", {}).get("id"),
                    "client_nom": revision_details.get("client", {}).get("nom"),
                    "organisation": revision_details.get("context", {}).get("organisation"),
                    "validation_valid": revision_details.get("validation", {}).get("valid"),
                    "collected_at": datetime.utcnow()
                }
                upsert_revision(rev_doc)
            
            return code_commune, None
        
        return None, f"Echec collecte {code_commune}"
    
    except Exception as e:
        return None, f"Erreur {code_commune}: {str(e)}"


def run_smart_collect():
    """Execute la collecte intelligente"""
    start_time = datetime.now()
    
    # Calculer la date de debut
    since_date = datetime.utcnow() - timedelta(days=COLLECT_WINDOW_DAYS)
    
    logger.info(f"Collecte des revisions depuis {since_date.date()}")
    
    # Recuperer les communes a verifier avec leur date_revision
    communes_to_check = get_communes_to_update(since_date)
    
    if communes_to_check is None:
        logger.info("Premiere collecte: verification de toutes les communes")
        # Pour la premiere fois, on doit recuperer la liste depuis l'API Geo
        # Mais c'est trop long, on va utiliser celles qu'on a deja en base
        from db.mongo import get_collection
        communes = get_collection("communes")
        communes_to_check = [(doc["code_insee"], doc.get("date_revision")) for doc in communes.find({}, {"code_insee": 1, "date_revision": 1})]
        logger.info(f"Verification de {len(communes_to_check)} communes existantes")
    elif not communes_to_check:
        logger.info("Aucune commune a verifier")
        log_update(start_time, datetime.now(), 0, 0, "success")
        return True
    
    logger.info(f"{len(communes_to_check)} communes a verifier")
    
    # Traiter en parallele
    updated = 0
    skipped = 0
    errors = 0
    
    with ThreadPoolExecutor(max_workers=COLLECT_WORKERS) as executor:
        futures = {
            executor.submit(process_commune, code, stored_date): code
            for code, stored_date in communes_to_check
        }
        
        for future in as_completed(futures):
            code, error = future.result()
            if code:
                updated += 1
            elif error and "Pas de changement" in error:
                skipped += 1
            else:
                errors += 1
                if error and "Pas de changement" not in error:
                    logger.debug(error)
            
            total_processed = updated + skipped + errors
            if total_processed % 100 == 0:
                logger.info(f"Progression: {total_processed}/{len(communes_to_check)} (mises a jour: {updated}, skip: {skipped}, erreurs: {errors})")
    
    # Enregistrer le log
    finished_time = datetime.now()
    duration = (finished_time - start_time).total_seconds()
    
    log_update(start_time, finished_time, updated, errors, "success" if errors == 0 else "partial")
    
    logger.info(f"Collecte terminee en {duration:.1f}s")
    logger.info(f"  - {updated} communes mises a jour")
    logger.info(f"  - {skipped} communes sans changement")
    logger.info(f"  - {errors} erreurs")
    
    return errors == 0


if __name__ == "__main__":
    success = run_smart_collect()
    exit(0 if success else 1)

