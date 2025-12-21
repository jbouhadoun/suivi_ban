# Guide de développement

## Workflow de données

### Pour les développeurs

1. Obtenir le dump de données depuis l'équipe
2. Placer le dump dans `data/dump/suivi_ban/`
3. Lancer `./setup.sh` qui restaurera automatiquement le dump
4. La base est prête, vous pouvez développer

### Pour la production

1. Créer le dump depuis la base de production :
   ```bash
   python scripts/create_dump.py
   ```

2. Le dump est créé dans `data/dump/suivi_ban/`

3. Partager le dump avec les développeurs

## Développement local

### Première installation

```bash
./setup.sh
```

### Démarrer l'application

```bash
./start.sh
```

### Démarrer MongoDB uniquement

```bash
docker-compose -f docker-compose.dev.yml up -d mongodb
```

### Vérifier l'état de la base

```bash
python scripts/init_db.py
```

Le script vérifie si la base est vide et restaure le dump si nécessaire.

### Connexion MongoDB

```bash
mongosh "mongodb://admin:admin123@localhost:27017/suivi_ban?authSource=admin"
```

### Commandes utiles

```bash
# Voir les collections
docker exec -it suivi-ban-mongodb-dev mongosh -u admin -p admin123 --authenticationDatabase admin --eval "use suivi_ban; show collections"

# Compter les communes
docker exec -it suivi-ban-mongodb-dev mongosh -u admin -p admin123 --authenticationDatabase admin --eval "use suivi_ban; db.communes.countDocuments()"

# Arrêter MongoDB
docker-compose -f docker-compose.dev.yml down
```

## Structure des données

### Collections MongoDB

- `communes` : Données principales des communes
- `revisions` : Historique des révisions BAL
- `update_logs` : Logs de mise à jour
- `config` : Configuration et métadonnées

### Format du dump

Le dump peut être fourni sous deux formats :

**Format compressé (recommandé)** :
- `suivi_ban_dump.tar.gz` : archive compressée contenant tous les fichiers BSON
- Décompression automatique lors de l'initialisation

**Format non compressé** :
- `communes.bson` + `communes.metadata.json`
- `revisions.bson` + `revisions.metadata.json`
- `update_logs.bson` + `update_logs.metadata.json`

Le script `create_dump.py` crée automatiquement les deux formats.

## Configuration

Les variables d'environnement sont gérées via le fichier `.env`. Le fichier `.env.example` contient les valeurs par défaut pour le développement local.

Pour personnaliser, copiez `.env.example` vers `.env` et modifiez les valeurs :

```bash
cp .env.example .env
# Éditer .env selon vos besoins
```

En production, ces variables sont configurées via Kubernetes Secrets ou variables d'environnement du conteneur.

## Scripts disponibles

- `setup.sh` : Setup initial pour les développeurs
- `start.sh` : Démarrage de l'application (API + Frontend)
- `scripts/init_db.py` : Initialisation automatique de la base
- `scripts/create_dump.py` : Création de dump (production)

## Architecture

- Backend : FastAPI (`backend/api/main.py`)
- Frontend : Streamlit (`app.py`)
- Base de données : MongoDB (`db/mongo.py`)
- Collecteur : `collectors/smart_collector.py` (mise à jour incrémentale)
