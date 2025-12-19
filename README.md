# 🗺️ Dashboard Suivi BAN

Dashboard Streamlit pour le suivi de la couverture BAN (Base Adresse Nationale) sur toutes les communes de France.

## 📊 Fonctionnalités

### Système de couleurs
- 🟢 **VERT** : Commune avec `withBanId = true` (couverture complète)
- 🟠 **ORANGE** : Commune avec BAL mais `withBanId = false` ET certaines voies ont des `banId` (couverture partielle)
- 🔴 **ROUGE** : Commune avec BAL mais aucun identifiant BAN
- ⚫ **GRIS** : Commune sans Base Adresse Locale

### Statistiques
- **Vue globale** : Carte de France avec toutes les communes colorées
- **Par département** : Statistiques agrégées par département
- **Par producteur** : Statistiques par producteur de données (client)
- **Filtres avancés** : Par statut, département, producteur

### Base de données SQLite
Toutes les données sont stockées dans une base SQLite locale incluant :
- Informations des communes
- Révisions BAL avec producteurs
- Détails des voies (avec/sans banId)
- Historique des mises à jour

## 🚀 Installation

### 1. Créer l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

## 📥 Collecte initiale des données

**Important** : La première collecte peut prendre 15-30 minutes car elle interroge l'API pour ~35 000 communes.

```bash
python collect_data.py
```

Cette commande va :
1. Initialiser la base de données SQLite
2. Récupérer toutes les communes de France
3. Pour chaque commune :
   - Données BAN (lookup)
   - Révision courante (si disponible)
   - Détails du producteur
   - Liste des voies avec leurs banId
4. Calculer le statut couleur
5. Tout stocker dans `data/suivi_ban.db`

## 📊 Lancer le dashboard

```bash
streamlit run app.py
```

Le dashboard sera accessible à : http://localhost:8501

## 🔄 Mise à jour automatique nocturne

### Configurer le cron (Linux/Mac)

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

Cette commande configure une tâche cron qui lance automatiquement la mise à jour tous les jours à **2h du matin**.

### Mise à jour manuelle

```bash
python update_nightly.py
```

Les logs sont sauvegardés dans `logs/`.

### Vérifier les mises à jour

```bash
# Voir les tâches cron
crontab -l

# Voir les logs
tail -f logs/cron.log
```

## 📁 Structure du projet

```
suivi_ban/
├── app.py                  # Dashboard Streamlit
├── database.py             # Gestion base SQLite
├── collect_data.py         # Script de collecte initiale
├── update_nightly.py       # Script de mise à jour nocturne
├── setup_cron.sh          # Configuration du cron
├── requirements.txt        # Dépendances Python
├── data/
│   └── suivi_ban.db       # Base de données SQLite
├── logs/                   # Logs des mises à jour
└── venv/                   # Environnement virtuel

```

## 🗄️ Structure de la base de données

### Table `communes`
Informations principales de chaque commune avec statut BAN

### Table `revisions`
Historique des révisions BAL avec informations sur les producteurs

### Table `voies`
Détails des voies par commune (avec/sans banId)

### Table `producteurs`
Statistiques agrégées par producteur

### Table `departements`
Statistiques agrégées par département

### Table `update_logs`
Historique des mises à jour automatiques

## 🔍 APIs utilisées

- **geo.api.gouv.fr** : Liste et contours des communes
- **plateforme.adresse.data.gouv.fr/lookup** : Données BAN de base
- **plateforme-bal.adresse.data.gouv.fr/api-depot** : Révisions et producteurs

## 📊 Exemples de requêtes SQL

### Communes par département
```sql
SELECT departement_nom, COUNT(*) as total,
       SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) as vertes
FROM communes
GROUP BY departement_nom;
```

### Top producteurs
```sql
SELECT client_nom, COUNT(*) as nb_communes
FROM revisions
WHERE is_current = 1
GROUP BY client_nom
ORDER BY nb_communes DESC
LIMIT 10;
```

### Communes sans BAL
```sql
SELECT code_insee, nom, departement_nom
FROM communes
WHERE has_bal = 0
ORDER BY population DESC;
```

## 🐛 Dépannage

### Base de données vide
```bash
# Supprimer et recréer
rm data/suivi_ban.db
python collect_data.py
```

### Erreurs de collecte
- Vérifier la connexion internet
- Les APIs peuvent avoir des limites de débit
- Le script fait des pauses pour éviter la surcharge

### Le dashboard ne s'affiche pas
```bash
# Vérifier que la base existe
ls -lh data/suivi_ban.db

# Vérifier les dépendances
pip install -r requirements.txt
```

## 📝 Notes

- Les données sont mises à jour automatiquement chaque nuit
- Le cache Streamlit est de 1 heure
- La collecte complète prend 15-30 minutes
- La base SQLite pèse environ 100-200 Mo

## 🤝 Contribution

Pour ajouter des fonctionnalités :
1. Modifier `database.py` pour la structure
2. Modifier `collect_data.py` pour la collecte
3. Modifier `app.py` pour l'affichage

## 📄 Licence

Projet open source - Données BAN sous Licence Ouverte Etalab 2.0
