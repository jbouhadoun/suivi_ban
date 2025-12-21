"""
Script d'initialisation de la base de données MongoDB
Restaure un dump si la base est vide (première utilisation)
Utilise pymongo pour éviter la dépendance à mongorestore
"""

import os
import sys
import bson
import tarfile
import shutil
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MONGODB_URI, MONGODB_DATABASE, COLLECTIONS


def check_database_status():
    """Vérifie l'état de la base de données et retourne ce qui doit être restauré"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGODB_DATABASE]
        
        # Vérifier les communes
        communes = db[COLLECTIONS["communes"]]
        communes_count = communes.count_documents({})
        
        # Vérifier les départements
        departements = db[COLLECTIONS["departements"]]
        departements_count = departements.count_documents({})
        
        client.close()
        
        EXPECTED_COMMUNES = 35011
        
        # Vérifier si la base est vide (pas de communes)
        if communes_count == 0:
            print("[INFO] Database is empty (no communes)")
            return "full_restore"
        
        # Vérifier si on a le bon nombre de communes
        communes_ok = (communes_count == EXPECTED_COMMUNES)
        
        # Vérifier si les départements sont présents (au moins 90 départements français)
        departements_ok = (departements_count >= 90)
        
        if not communes_ok:
            print(f"[WARN] Database contains {communes_count} communes, expected {EXPECTED_COMMUNES}")
            print("[WARN] Database appears incomplete, will reinitialize...")
            return "full_restore"
        
        if not departements_ok:
            if departements_count == 0:
                print(f"[WARN] Database has {communes_count} communes but no départements")
            else:
                print(f"[WARN] Database has only {departements_count} départements, expected at least 90")
            print("[INFO] Will restore only départements collection...")
            return "departements_only"
        
        print(f"[INFO] Database check: {communes_count} communes, {departements_count} départements - OK")
        return "ok"
    except ConnectionFailure as e:
        print(f"[ERROR] Cannot connect to MongoDB: {e}")
        print("[INFO] Make sure MongoDB is running:")
        print("      docker-compose -f docker-compose.dev.yml up -d mongodb")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error checking database: {e}")
        sys.exit(1)


def find_and_extract_dump():
    """Trouve et décompresse le dump si nécessaire"""
    # Chemins où chercher le dump (lecture seule)
    read_paths = [
        Path("/app/data/dump"),
        Path("data/dump"),
        Path("dump"),
        Path("/dump"),
    ]
    
    # Chemin d'extraction (écriture possible avec readOnlyRootFilesystem)
    extract_path = Path("/tmp/dump")
    
    # Chercher d'abord un fichier tar.gz
    for base_path in read_paths:
        archive_path = base_path / f"{MONGODB_DATABASE}_dump.tar.gz"
        if archive_path.exists():
            print(f"[INFO] Found compressed dump: {archive_path}")
            dump_path = extract_path / MONGODB_DATABASE
            
            # Décompresser dans /tmp si le répertoire n'existe pas ou est vide
            if not dump_path.exists() or not (dump_path / "communes.bson").exists():
                print(f"[INFO] Extracting dump to {dump_path}...")
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                
                with tarfile.open(archive_path, "r:gz") as tar:
                    # filter='data' pour compatibilité Python 3.14+ (extraction sécurisée)
                    tar.extractall(path=extract_path, filter='data')
                
                print(f"[INFO] Dump extracted successfully")
            
            if dump_path.exists() and (dump_path / "communes.bson").exists():
                return dump_path
    
    # Chercher un répertoire de dump non compressé (dans les chemins en lecture)
    for base_path in read_paths:
        dump_path = base_path / MONGODB_DATABASE
        if dump_path.exists() and (dump_path / "communes.bson").exists():
            return dump_path
    
    return None


def restore_collection(dump_path, collection_name):
    """Restaure une collection spécifique depuis le dump"""
    try:
        bson_file = dump_path / f"{collection_name}.bson"
        
        if not bson_file.exists():
            print(f"[WARN] File {bson_file.name} not found in dump")
            return False
        
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DATABASE]
        collection = db[collection_name]
        
        print(f"[INFO] Restoring collection: {collection_name}")
        
        # Supprimer la collection existante
        collection.drop()
        
        # Lire le fichier BSON et insérer les documents
        with open(bson_file, 'rb') as f:
            data = f.read()
            if not data:
                client.close()
                return False
            
            # Parser tous les documents BSON
            inserted = 0
            offset = 0
            while offset < len(data):
                try:
                    # Lire la longueur du document (4 premiers bytes, little-endian)
                    if offset + 4 > len(data):
                        break
                    doc_length = int.from_bytes(data[offset:offset+4], 'little', signed=False)
                    
                    # Vérifier la validité de la longueur
                    if doc_length < 5 or doc_length > len(data) - offset:
                        break
                    
                    # Extraire le document
                    doc_data = data[offset:offset+doc_length]
                    doc = bson.decode(doc_data)
                    
                    # Insérer le document
                    collection.insert_one(doc)
                    inserted += 1
                    
                    # Passer au document suivant
                    offset += doc_length
                except Exception as e:
                    print(f"[WARN] Error parsing document at offset {offset}: {e}")
                    break
        
        client.close()
        print(f"[INFO] Restored {inserted} documents to {collection_name}")
        return inserted > 0
        
    except Exception as e:
        print(f"[ERROR] Error restoring collection {collection_name}: {e}")
        return False


def restore_dump(dump_path, collections_to_restore=None):
    """Restaure le dump MongoDB en utilisant pymongo (sans mongorestore)
    
    Args:
        dump_path: Chemin vers le répertoire du dump
        collections_to_restore: Liste des collections à restaurer (None = toutes)
    """
    try:
        print(f"[INFO] Restoring dump from: {dump_path}")
        
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DATABASE]
        
        # Parcourir tous les fichiers .bson dans le dump
        bson_files = list(dump_path.glob("*.bson"))
        
        if not bson_files:
            print(f"[WARN] No BSON files found in {dump_path}")
            client.close()
            return False
        
        restored_count = 0
        for bson_file in bson_files:
            collection_name = bson_file.stem  # Nom sans extension
            
            # Ignorer les collections système et metadata
            if collection_name.startswith("system.") or collection_name.endswith(".metadata"):
                continue
            
            # Si on a spécifié des collections à restaurer, ne restaurer que celles-là
            if collections_to_restore and collection_name not in collections_to_restore:
                continue
            
            print(f"[INFO] Restoring collection: {collection_name}")
            
            collection = db[collection_name]
            
            # Supprimer la collection existante
            collection.drop()
            
            # Lire le fichier BSON et insérer les documents
            with open(bson_file, 'rb') as f:
                data = f.read()
                if not data:
                    continue
                
                # Parser tous les documents BSON
                inserted = 0
                offset = 0
                while offset < len(data):
                    try:
                        # Lire la longueur du document (4 premiers bytes, little-endian)
                        if offset + 4 > len(data):
                            break
                        doc_length = int.from_bytes(data[offset:offset+4], 'little', signed=False)
                        
                        # Vérifier la validité de la longueur
                        if doc_length < 5 or doc_length > len(data) - offset:
                            break
                        
                        # Extraire le document BSON
                        doc_data = data[offset:offset+doc_length]
                        
                        # Décoder le document BSON
                        doc = bson.decode_all(doc_data)[0]
                        
                        # Insérer le document
                        collection.insert_one(doc)
                        inserted += 1
                        offset += doc_length
                    except (bson.errors.InvalidBSON, IndexError, ValueError) as e:
                        print(f"[WARN] Error parsing document at offset {offset}: {e}")
                        # Essayer de trouver le prochain document valide
                        offset += 1
                        if offset >= len(data):
                            break
                    except Exception as e:
                        print(f"[WARN] Unexpected error at offset {offset}: {e}")
                        offset += 1
                        if offset >= len(data):
                            break
                
                print(f"[INFO] Restored {inserted} documents to {collection_name}")
                restored_count += inserted
        
        client.close()
        
        if restored_count > 0:
            print(f"[INFO] Dump restored successfully ({restored_count} documents total)")
            return True
        else:
            print("[WARN] No documents restored")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error during restore: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_indexes():
    """Crée les index MongoDB"""
    try:
        from db.mongo import init_indexes
        print("[INFO] Creating indexes...")
        init_indexes()
        print("[INFO] Indexes created successfully")
    except Exception as e:
        print(f"[WARN] Error creating indexes: {e}")


def init_departements():
    """Vérifie et met à jour les stats des départements si nécessaire"""
    try:
        from db.mongo import get_collection, update_departements_stats
        
        departements = get_collection("departements")
        count = departements.count_documents({})
        
        if count == 0:
            print("[WARN] No départements in database. They should be restored from dump.")
            return
        
        print(f"[INFO] {count} départements in database")
        
        # Vérifier si les stats sont à jour, sinon les recalculer
        dept_without_stats = departements.count_documents({"stats": {"$exists": False}})
        if dept_without_stats > 0:
            print(f"[INFO] {dept_without_stats} départements without stats, calculating...")
            update_departements_stats()
        else:
            print("[INFO] All départements have statistics")
    except Exception as e:
        print(f"[WARN] Error checking départements: {e}")


def main():
    """Fonction principale"""
    print("[INFO] Checking database initialization...")
    
    status = check_database_status()
    
    if status == "ok":
        print("[INFO] Database already contains all data. Skipping restore.")
        # Vérifier quand même les stats des départements
        init_departements()
        return 0
    
    # Chercher le dump
    dump_path = find_and_extract_dump()
    
    if not dump_path:
        print("[WARN] No dump found. Database will remain incomplete.")
        print("[INFO] To initialize with data:")
        print("  1. Get the dump from the team")
        print("  2. Place it in data/dump/ as:")
        print("     - suivi_ban_dump.tar.gz (compressed, recommended)")
        print("     - OR data/dump/suivi_ban/*.bson (uncompressed)")
        print("  3. Run: python scripts/init_db.py")
        print("")
        print("[INFO] Expected files:")
        print("  data/dump/suivi_ban_dump.tar.gz")
        print("  OR")
        print("  data/dump/suivi_ban/")
        print("  ├── communes.bson")
        print("  ├── revisions.bson")
        print("  ├── departements.bson")
        print("  └── update_logs.bson")
        return 0
    
    # Restaurer selon le statut
    if status == "departements_only":
        # Restaurer seulement les départements
        print("[INFO] Restoring only départements collection...")
        if restore_collection(dump_path, "departements"):
            init_departements()
            print("[INFO] Départements restoration completed")
            return 0
        else:
            print("[ERROR] Départements restoration failed")
            return 1
    elif status == "full_restore":
        # Restaurer tout le dump
        print("[INFO] Restoring full database from dump...")
        if restore_dump(dump_path):
            create_indexes()
            init_departements()
            print("[INFO] Database initialization completed")
            return 0
        else:
            print("[ERROR] Database initialization failed")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

