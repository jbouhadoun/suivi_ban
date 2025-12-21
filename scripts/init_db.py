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


def check_database_empty():
    """Vérifie si la base de données est vide"""
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGODB_DATABASE]
        communes = db[COLLECTIONS["communes"]]
        count = communes.count_documents({})
        client.close()
        return count == 0
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


def restore_dump(dump_path):
    """Restaure le dump MongoDB en utilisant pymongo (sans mongorestore)"""
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


def main():
    """Fonction principale"""
    print("[INFO] Checking database initialization...")
    
    if not check_database_empty():
        print("[INFO] Database already contains data. Skipping restore.")
        return 0
    
    print("[INFO] Database is empty. Looking for dump to restore...")
    
    dump_path = find_and_extract_dump()
    
    if not dump_path:
        print("[WARN] No dump found. Database will remain empty.")
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
        print("  └── update_logs.bson")
        return 0
    
    if restore_dump(dump_path):
        create_indexes()
        print("[INFO] Database initialization completed")
        return 0
    else:
        print("[ERROR] Database initialization failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

