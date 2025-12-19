# 🚀 Guide de démarrage rapide

## ✅ Ce qui a été créé

### 📁 Fichiers principaux

1. **`database.py`** - Gestion de la base SQLite
   - Tables: communes, revisions, voies, producteurs, departements, logs
   - Fonctions d'insertion et de requête

2. **`collect_data.py`** - Collecte des données BAN
   - Récupère TOUTES les communes de France (~35 000)
   - Pour chaque commune : données BAN + révision + producteur + voies
   - Calcule le statut couleur (vert/orange/rouge/gris)
   - Stocke tout dans SQLite

3. **`app.py`** - Dashboard Streamlit
   - Carte interactive avec OpenStreetMap uniquement
   - 4 couleurs de statut
   - Filtres par statut, département, producteur
   - Stats globales, par département, par producteur

4. **`update_nightly.py`** - Mise à jour automatique
   - Lance collect_data.py
   - Enregistre les logs
   - Trace les mises à jour dans la base

5. **`setup_cron.sh`** - Configuration du cron
   - Configure une tâche automatique à 2h du matin

6. **`quickstart.sh`** - Démarrage rapide
   - Vérifie tout et lance le dashboard

## 🎨 Système de couleurs

- 🟢 **VERT** : `withBanId = true` (parfait !)
- 🟠 **ORANGE** : `withBanId = false` MAIS certaines voies ont des `banId`
- 🔴 **ROUGE** : `withBanId = false` ET aucune voie avec `banId`
- ⚫ **GRIS** : Pas de BAL du tout (pas de révision)

## 📊 Statistiques disponibles

### Vue globale
- Total communes par statut (vert/orange/rouge/gris)
- Taux de couverture BAL
- Nombre total de numéros et voies

### Par département
- Nombre de communes par statut
- Taux de BAL par département
- Filtrage possible

### Par producteur (client)
- Qui produit quoi
- Nombre de communes par producteur
- Qualité de la production (nb vertes/oranges/rouges)

## 🚀 Comment démarrer

### Option 1 : Script rapide (recommandé)
```bash
./quickstart.sh
```

### Option 2 : Étape par étape

#### 1. Collecter les données (première fois)
```bash
source venv/bin/activate
python collect_data.py
```
⏱️ **Durée : 15-30 minutes** (interroge l'API pour ~35 000 communes)

#### 2. Lancer le dashboard
```bash
streamlit run app.py
```
🌐 Ouvrez : http://localhost:8501

#### 3. Configurer la mise à jour automatique (optionnel)
```bash
./setup_cron.sh
```
🌙 Met à jour automatiquement chaque nuit à 2h

## 📂 Structure de la base de données

### `communes` - Données principales
- Informations géographiques (contour, centre, département)
- Stats BAN (nb numéros, nb voies)
- Statut couleur calculé
- Nombre de voies avec banId

### `revisions` - Historique BAL
- ID de révision
- Dates (création, mise à jour, publication)
- **Producteur** : nom du client, mandataire, chef de file, email
- Validation : erreurs, warnings, nombre de lignes

### `voies` - Détails des voies
- ID voie, nom, nombre de numéros
- **Présence de banId** (boolean)

### `producteurs` - Stats agrégées
- Nombre de communes par producteur
- Répartition par statut couleur

### `departements` - Stats agrégées
- Statistiques par département
- Taux de couverture

### `update_logs` - Historique mises à jour
- Date, durée, nombre de communes mises à jour
- Erreurs éventuelles

## 🔍 APIs utilisées

1. **geo.api.gouv.fr/communes** 
   - Liste et contours des communes

2. **plateforme.adresse.data.gouv.fr/lookup/{codeInsee}**
   - Données BAN de base (withBanId, nbNumeros, voies, etc.)

3. **plateforme-bal.adresse.data.gouv.fr/api-depot/communes/{codeInsee}/current-revision**
   - Récupération de la révision courante

4. **plateforme-bal.adresse.data.gouv.fr/api-depot/revisions/{revisionId}**
   - Détails de la révision (producteur, validation, etc.)

## 💡 Exemples d'utilisation

### Voir toutes les communes sans BAL
```sql
SELECT code_insee, nom, population 
FROM communes 
WHERE statut_couleur = 'gris' 
ORDER BY population DESC;
```

### Top 10 producteurs
```sql
SELECT client_nom, COUNT(*) as nb_communes
FROM revisions
WHERE is_current = 1
GROUP BY client_nom
ORDER BY nb_communes DESC
LIMIT 10;
```

### Départements avec meilleure couverture
```sql
SELECT departement_nom, 
       COUNT(*) as total,
       SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) as vertes,
       ROUND(100.0 * SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) / COUNT(*), 1) as taux
FROM communes
GROUP BY departement_nom
ORDER BY taux DESC;
```

## 🐛 Résolution de problèmes

### "Base de données non trouvée"
→ Lancez `python collect_data.py`

### "Erreurs lors de la collecte"
→ Vérifiez votre connexion internet
→ Les APIs peuvent avoir des limites de débit (le script fait des pauses)

### "Carte ne s'affiche pas"
→ Vérifiez que Folium ne crée pas d'objets avec `style_function` lambda
→ Tous les GeoJSON utilisent des features simples

### "Trop lent"
→ La collecte initiale est longue (normale)
→ Ensuite le dashboard utilise la base locale (rapide)
→ Cache Streamlit de 1h

## 📅 Maintenance

### Mise à jour manuelle
```bash
python update_nightly.py
```

### Voir les logs
```bash
tail -f logs/cron.log
ls -lh logs/
```

### Réinitialiser la base
```bash
rm data/suivi_ban.db
python collect_data.py
```

## 🎯 Prochaines étapes possibles

- [ ] Ajouter un filtre par région
- [ ] Graphiques de progression dans le temps
- [ ] Export des données en CSV/Excel
- [ ] Alertes sur les communes qui régressent
- [ ] Intégration avec d'autres sources de données

## 📞 Support

Pour toute question, consultez le `README.md` ou examinez le code source des fichiers Python (bien documentés).

Bon suivi de la BAN ! 🗺️✨










