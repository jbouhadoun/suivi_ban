# Suivi BAN - Application de suivi des Bases Adresses Locales

Application web de suivi et de visualisation des Bases Adresses Locales (BAL) en France.

## Architecture

- **Backend**: FastAPI (Python)
- **Frontend**: Streamlit (Python)
- **Base de données**: MongoDB
- **Déploiement**: Docker / Kubernetes

## Prérequis

- Python 3.12+
- MongoDB 7.0+
- Docker (optionnel, pour le déploiement)

## Installation

### Développement local

#### Setup initial (première fois)

```bash
# 1. Cloner le dépôt
git clone <repository-url>
cd suivi_ban

# 2. Lancer le setup automatique
./setup.sh
```

Le script `setup.sh` va :
- Créer l'environnement virtuel Python
- Installer les dépendances
- Démarrer MongoDB localement
- Initialiser la base de données (restaure le dump si présent)

#### Obtenir les données

Le dump de données peut être fourni sous deux formats :

**Format compressé (recommandé)** :
- Placer `suivi_ban_dump.tar.gz` dans `data/dump/`
- Le script `init_db.py` décompressera automatiquement le fichier

**Format non compressé** :
- Placer les fichiers dans `data/dump/suivi_ban/` :
  ```
  data/dump/suivi_ban/
  ├── communes.bson
  ├── communes.metadata.json
  ├── revisions.bson
  ├── revisions.metadata.json
  └── update_logs.bson
  ```

Le script `init_db.py` restaurera automatiquement le dump si la base est vide.

#### Démarrer l'application

```bash
./start.sh
```

L'application sera accessible sur:
- Frontend: http://localhost:8501
- API: http://localhost:8000

#### Configuration

Les variables d'environnement sont gérées via un fichier `.env`. Le script `setup.sh` crée automatiquement ce fichier depuis `.env.example` si il n'existe pas.

Pour personnaliser la configuration, modifiez le fichier `.env` :

```bash
# Exemple de .env
MONGODB_URI=mongodb://admin:admin123@localhost:27017/suivi_ban?authSource=admin
MONGODB_DATABASE=suivi_ban
API_URL=http://localhost:8000
```

Toutes les variables sont documentées dans `.env.example`.

## Déploiement

### Création d'un dump MongoDB

Pour créer un dump de la base de données (utilise Python, pas besoin de mongodump):

```bash
python scripts/create_dump.py
```

Le script crée :
1. Les fichiers BSON dans `data/dump/suivi_ban/`
2. Un fichier compressé `data/dump/suivi_ban_dump.tar.gz` (recommandé pour le partage)

Le fichier tar.gz peut être partagé avec les développeurs. Il sera automatiquement décompressé lors de l'initialisation.

### Image Docker

1. **Construire l'image**
```bash
docker build -t suivi-ban:latest .
```

2. **Lancer le conteneur**
```bash
docker run -d \
  -p 8501:8501 \
  -p 8000:8000 \
  -e MONGODB_URI="mongodb://host.docker.internal:27017" \
  -e MONGODB_DATABASE="suivi_ban" \
  -v $(pwd)/data/dump:/app/data/dump \
  suivi-ban:latest
```

### Kubernetes

Le déploiement Kubernetes est configuré dans `k8s/` avec Kustomize.

**Variables d'environnement requises:**
- `MONGODB_URI`: URI de connexion MongoDB
- `MONGODB_DATABASE`: Nom de la base de données (défaut: `suivi_ban`)
- `API_URL`: URL de l'API pour le frontend (vide en K8s pour utiliser les chemins relatifs)

**Initialisation automatique:**
L'application vérifie automatiquement si la base est vide au démarrage. Si un dump est présent dans `/app/data/dump`, il sera restauré automatiquement.

## Structure du projet

```
suivi_ban/
├── backend/
│   └── api/
│       └── main.py          # API FastAPI
├── db/
│   └── mongo.py             # Accès MongoDB
├── collectors/
│   └── smart_collector.py   # Collecte incrémentale
├── scripts/
│   ├── init_db.py           # Initialisation de la base
│   └── create_dump.py       # Création de dump
├── config.py                # Configuration centralisée
├── app.py                   # Application Streamlit
├── Dockerfile               # Image Docker
├── setup.sh                 # Setup initial
├── start.sh                 # Script de démarrage local
└── requirements.txt         # Dépendances Python
```

## Architecture

### Backend (FastAPI)
- Fichier: `backend/api/main.py`
- Port: 8000
- Endpoints: `/api/*`
- Base de données: MongoDB

### Frontend (Streamlit)
- Fichier: `app.py`
- Port: 8501
- Interface: Application web interactive

### Base de données
- Type: MongoDB
- Collections principales:
  - `communes`: Données des communes
  - `revisions`: Historique des révisions
  - `update_logs`: Logs de mise à jour
  - `config`: Configuration et métadonnées

### Collecte de données
- Script: `collectors/smart_collector.py`
- Stratégie: Mise à jour incrémentale (seulement les communes modifiées)
- Fréquence: Quotidienne via CronJob Kubernetes (2h du matin)

## Collections MongoDB

- **communes**: Données principales des communes
- **revisions**: Historique des révisions BAL
- **update_logs**: Logs de mise à jour
- **config**: Configuration et métadonnées

## Scripts utiles

### Initialisation de la base
```bash
python scripts/init_db.py
```
Vérifie si la base est vide et restaure un dump si disponible. S'exécute automatiquement au démarrage.

### Création de dump (production uniquement)
```bash
python scripts/create_dump.py
```
Crée un dump de la base de données dans `data/dump/suivi_ban/`. Utilisé pour partager les données avec les développeurs.

## Configuration

Les variables d'environnement sont définies dans le fichier `.env` (créé automatiquement depuis `.env.example` lors du setup).

Variables principales :
- `MONGODB_URI`: URI de connexion MongoDB
- `MONGODB_DATABASE`: Nom de la base de données
- `API_URL`: URL de l'API (pour le frontend)
- `API_HOST`: Host de l'API (défaut: 0.0.0.0)
- `API_PORT`: Port de l'API (défaut: 8000)
- `STREAMLIT_PORT`: Port de Streamlit (défaut: 8501)
- `COLLECT_WINDOW_DAYS`: Fenêtre de collecte en jours (défaut: 7)
- `COLLECT_WORKERS`: Nombre de workers pour la collecte (défaut: 10)

Le fichier `.env` est ignoré par git. Utilisez `.env.example` comme référence.

## API Endpoints

- `GET /api` - Informations sur l'API
- `GET /api/health` - Health check
- `GET /api/departements` - Liste des départements (GeoJSON)
- `GET /api/departement/{code}/communes` - Communes d'un département
- `GET /api/stats/global` - Statistiques globales
- `GET /api/stats/departements` - Statistiques par département
- `GET /api/producteurs` - Liste des producteurs
- `GET /api/producteur/{nom}/departements` - Stats d'un producteur
- `GET /api/search?q={query}` - Recherche de communes
- `GET /api/commune/{code}` - Détails d'une commune

## Maintenance

### Mise à jour quotidienne

Un CronJob Kubernetes est configuré dans `k8s/cronjob.yaml` pour exécuter la collecte quotidienne à 2h du matin (heure de Paris).

Le CronJob utilise `collectors/smart_collector.py` qui met à jour uniquement les communes modifiées dans les 7 derniers jours, ce qui rend la collecte beaucoup plus rapide.

Le CronJob est déployé automatiquement avec `kubectl apply -k k8s/`.

## Support

Pour toute question ou problème, consulter la documentation ou ouvrir une issue.
