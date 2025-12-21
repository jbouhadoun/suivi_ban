"""
Script pour créer un dump MongoDB de la base Suivi BAN
Utilise pymongo pour éviter la dépendance à mongodump
"""

import os
import sys
import bson
import tarfile
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MONGODB_URI, MONGODB_DATABASE, COLLECTIONS


def create_dump(output_dir=None):
    """Crée un dump MongoDB dans le répertoire spécifié"""
    try:
        # Déterminer le répertoire de sortie
        if output_dir is None:
            output_dir = Path("data/dump")
        else:
            output_dir = Path(output_dir)
        
        dump_path = output_dir / MONGODB_DATABASE
        dump_path.mkdir(parents=True, exist_ok=True)
        
        print(f"[INFO] Creating MongoDB dump...")
        print(f"[INFO] Database: {MONGODB_DATABASE}")
        print(f"[INFO] Output directory: {dump_path}")
        
        # Connexion MongoDB
        client = MongoClient(MONGODB_URI)
        db = client[MONGODB_DATABASE]
        
        # Lister toutes les collections
        collection_names = db.list_collection_names()
        
        if not collection_names:
            print("[WARN] No collections found in database")
            client.close()
            return False
        
        total_docs = 0
        for collection_name in collection_names:
            # Ignorer les collections système
            if collection_name.startswith("system."):
                continue
            
            print(f"[INFO] Dumping collection: {collection_name}")
            
            collection = db[collection_name]
            count = collection.count_documents({})
            
            if count == 0:
                print(f"[INFO] Collection {collection_name} is empty, skipping")
                continue
            
            # Créer le fichier BSON
            bson_file = dump_path / f"{collection_name}.bson"
            
            with open(bson_file, 'wb') as f:
                # Parcourir tous les documents
                cursor = collection.find({})
                docs_written = 0
                
                for doc in cursor:
                    # Encoder le document en BSON
                    bson_data = bson.encode(doc)
                    f.write(bson_data)
                    docs_written += 1
                
                print(f"[INFO] Wrote {docs_written} documents to {bson_file.name}")
                total_docs += docs_written
            
            # Créer un fichier metadata (optionnel, pour compatibilité avec mongorestore)
            metadata_file = dump_path / f"{collection_name}.metadata.json"
            with open(metadata_file, 'w') as f:
                import json
                metadata = {
                    "options": {},
                    "indexes": []
                }
                # Récupérer les index
                indexes = collection.list_indexes()
                for index in indexes:
                    if index["name"] != "_id_":  # Ignorer l'index _id par défaut
                        metadata["indexes"].append({
                            "v": index.get("v", 2),
                            "key": index["key"],
                            "name": index["name"]
                        })
                json.dump(metadata, f, indent=2)
        
        client.close()
        
        print(f"[INFO] Dump created successfully")
        print(f"[INFO] Total documents: {total_docs}")
        print(f"[INFO] Location: {dump_path}")
        
        # Compresser le dump en tar.gz
        archive_name = output_dir / f"{MONGODB_DATABASE}_dump.tar.gz"
        print(f"[INFO] Compressing dump to {archive_name.name}...")
        
        with tarfile.open(archive_name, "w:gz") as tar:
            tar.add(dump_path, arcname=MONGODB_DATABASE)
        
        archive_size = archive_name.stat().st_size / (1024 * 1024)
        print(f"[INFO] Archive created: {archive_name.name} ({archive_size:.2f} MB)")
        print(f"[INFO] You can delete the uncompressed directory: {dump_path}")
        
        return True
        
    except ConnectionFailure as e:
        print(f"[ERROR] Cannot connect to MongoDB: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Error creating dump: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create MongoDB dump")
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory (default: data/dump)"
    )
    
    args = parser.parse_args()
    
    success = create_dump(args.output)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


