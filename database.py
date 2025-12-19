"""
Gestion de la base de données SQLite pour le suivi BAN
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import json

DB_PATH = Path("data/suivi_ban.db")
DB_PATH.parent.mkdir(exist_ok=True)


def init_database():
    """Initialise la structure de la base de données"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table communes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS communes (
            code_insee TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            departement_code TEXT,
            departement_nom TEXT,
            region_code TEXT,
            region_nom TEXT,
            population INTEGER,
            codes_postaux TEXT,
            centre_lat REAL,
            centre_lon REAL,
            contour TEXT,
            with_ban_id BOOLEAN DEFAULT 0,
            nb_numeros INTEGER DEFAULT 0,
            nb_numeros_certifies INTEGER DEFAULT 0,
            nb_voies INTEGER DEFAULT 0,
            nb_voies_avec_banid INTEGER DEFAULT 0,
            nb_lieux_dits INTEGER DEFAULT 0,
            type_composition TEXT,
            date_revision TEXT,
            has_bal BOOLEAN DEFAULT 0,
            statut_couleur TEXT,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table revisions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revisions (
            revision_id TEXT PRIMARY KEY,
            code_commune TEXT NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            published_at TIMESTAMP,
            is_current BOOLEAN DEFAULT 1,
            status TEXT,
            client_id TEXT,
            client_nom TEXT,
            client_mandataire TEXT,
            client_chef_de_file TEXT,
            client_email TEXT,
            organisation TEXT,
            validation_valid BOOLEAN,
            validation_errors INTEGER DEFAULT 0,
            validation_warnings INTEGER DEFAULT 0,
            validation_infos INTEGER DEFAULT 0,
            validation_rows_count INTEGER DEFAULT 0,
            validator_version TEXT,
            file_size INTEGER,
            FOREIGN KEY (code_commune) REFERENCES communes(code_insee)
        )
    """)
    
    # Table voies
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS voies (
            id TEXT PRIMARY KEY,
            code_commune TEXT NOT NULL,
            id_voie TEXT,
            ban_id TEXT,
            nom_voie TEXT,
            nb_numeros INTEGER DEFAULT 0,
            nb_numeros_certifies INTEGER DEFAULT 0,
            has_ban_id BOOLEAN DEFAULT 0,
            FOREIGN KEY (code_commune) REFERENCES communes(code_insee)
        )
    """)
    
    # Table producteurs (stats agrégées)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS producteurs (
            client_nom TEXT PRIMARY KEY,
            client_id TEXT,
            nb_communes INTEGER DEFAULT 0,
            nb_communes_vertes INTEGER DEFAULT 0,
            nb_communes_oranges INTEGER DEFAULT 0,
            nb_communes_rouges INTEGER DEFAULT 0,
            nb_communes_grises INTEGER DEFAULT 0,
            nb_voies_total INTEGER DEFAULT 0,
            nb_numeros_total INTEGER DEFAULT 0,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table departements (stats agrégées)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departements (
            code TEXT PRIMARY KEY,
            nom TEXT,
            nb_communes_total INTEGER DEFAULT 0,
            nb_communes_vertes INTEGER DEFAULT 0,
            nb_communes_oranges INTEGER DEFAULT 0,
            nb_communes_rouges INTEGER DEFAULT 0,
            nb_communes_grises INTEGER DEFAULT 0,
            taux_couverture REAL DEFAULT 0,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table logs de mise à jour
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS update_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            duration_seconds INTEGER,
            communes_updated INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            status TEXT,
            error_message TEXT
        )
    """)
    
    # Index pour améliorer les performances
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_communes_dept ON communes(departement_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_communes_statut ON communes(statut_couleur)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_revisions_commune ON revisions(code_commune)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_revisions_client ON revisions(client_nom)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_voies_commune ON voies(code_commune)")
    
    conn.commit()
    conn.close()
    
    print("✅ Base de données initialisée")


def get_connection():
    """Retourne une connexion à la base de données"""
    return sqlite3.connect(DB_PATH)


def insert_commune(conn, data):
    """Insère ou met à jour une commune"""
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO communes (
            code_insee, nom, departement_code, departement_nom, 
            region_code, region_nom, population, codes_postaux,
            centre_lat, centre_lon, contour,
            with_ban_id, nb_numeros, nb_numeros_certifies, nb_voies, 
            nb_voies_avec_banid, nb_lieux_dits, type_composition, 
            date_revision, has_bal, statut_couleur, last_update
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('code_insee'),
        data.get('nom'),
        data.get('departement_code'),
        data.get('departement_nom'),
        data.get('region_code'),
        data.get('region_nom'),
        data.get('population'),
        json.dumps(data.get('codes_postaux', [])),
        data.get('centre_lat'),
        data.get('centre_lon'),
        json.dumps(data.get('contour')),
        data.get('with_ban_id', False),
        data.get('nb_numeros', 0),
        data.get('nb_numeros_certifies', 0),
        data.get('nb_voies', 0),
        data.get('nb_voies_avec_banid', 0),
        data.get('nb_lieux_dits', 0),
        data.get('type_composition'),
        data.get('date_revision'),
        data.get('has_bal', False),
        data.get('statut_couleur'),
        datetime.now().isoformat()
    ))


def insert_revision(conn, data):
    """Insère ou met à jour une révision"""
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO revisions (
            revision_id, code_commune, created_at, updated_at, published_at,
            is_current, status, client_id, client_nom, client_mandataire,
            client_chef_de_file, client_email, organisation,
            validation_valid, validation_errors, validation_warnings,
            validation_infos, validation_rows_count, validator_version, file_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('revision_id'),
        data.get('code_commune'),
        data.get('created_at'),
        data.get('updated_at'),
        data.get('published_at'),
        data.get('is_current', True),
        data.get('status'),
        data.get('client_id'),
        data.get('client_nom'),
        data.get('client_mandataire'),
        data.get('client_chef_de_file'),
        data.get('client_email'),
        data.get('organisation'),
        data.get('validation_valid', False),
        data.get('validation_errors', 0),
        data.get('validation_warnings', 0),
        data.get('validation_infos', 0),
        data.get('validation_rows_count', 0),
        data.get('validator_version'),
        data.get('file_size', 0)
    ))


def insert_voie(conn, data):
    """Insère ou met à jour une voie"""
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT OR REPLACE INTO voies (
            id, code_commune, id_voie, ban_id, nom_voie,
            nb_numeros, nb_numeros_certifies, has_ban_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('id'),
        data.get('code_commune'),
        data.get('id_voie'),
        data.get('ban_id'),
        data.get('nom_voie'),
        data.get('nb_numeros', 0),
        data.get('nb_numeros_certifies', 0),
        data.get('has_ban_id', False)
    ))


def get_all_communes(conn):
    """Récupère toutes les communes"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code_insee, nom, departement_code, departement_nom,
               centre_lat, centre_lon, contour, statut_couleur,
               with_ban_id, nb_numeros, nb_voies, has_bal
        FROM communes
        ORDER BY nom
    """)
    return cursor.fetchall()


def get_stats_by_departement(conn):
    """Récupère les stats par département"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            departement_code,
            departement_nom,
            COUNT(*) as total,
            SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) as vertes,
            SUM(CASE WHEN statut_couleur = 'orange' THEN 1 ELSE 0 END) as oranges,
            SUM(CASE WHEN statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouges,
            SUM(CASE WHEN statut_couleur = 'gris' THEN 1 ELSE 0 END) as grises,
            ROUND(100.0 * SUM(CASE WHEN has_bal THEN 1 ELSE 0 END) / COUNT(*), 1) as taux_bal
        FROM communes
        GROUP BY departement_code, departement_nom
        ORDER BY departement_code
    """)
    return cursor.fetchall()


def get_stats_by_producteur(conn):
    """Récupère les stats par producteur"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            r.client_nom,
            COUNT(DISTINCT r.code_commune) as nb_communes,
            SUM(c.nb_numeros) as nb_numeros_total,
            SUM(c.nb_voies) as nb_voies_total,
            SUM(CASE WHEN c.statut_couleur = 'vert' THEN 1 ELSE 0 END) as vertes,
            SUM(CASE WHEN c.statut_couleur = 'orange' THEN 1 ELSE 0 END) as oranges,
            SUM(CASE WHEN c.statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouges
        FROM revisions r
        JOIN communes c ON r.code_commune = c.code_insee
        WHERE r.is_current = 1
        GROUP BY r.client_nom
        ORDER BY nb_communes DESC
    """)
    return cursor.fetchall()


def get_stats_globales(conn):
    """Récupère les statistiques globales"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN statut_couleur = 'vert' THEN 1 ELSE 0 END) as vertes,
            SUM(CASE WHEN statut_couleur = 'orange' THEN 1 ELSE 0 END) as oranges,
            SUM(CASE WHEN statut_couleur = 'rouge' THEN 1 ELSE 0 END) as rouges,
            SUM(CASE WHEN statut_couleur = 'gris' THEN 1 ELSE 0 END) as grises,
            SUM(CASE WHEN has_bal THEN 1 ELSE 0 END) as avec_bal,
            SUM(nb_numeros) as total_numeros,
            SUM(nb_voies) as total_voies
        FROM communes
    """)
    return cursor.fetchone()


if __name__ == "__main__":
    print("Initialisation de la base de données...")
    init_database()
    print("✅ Terminé !")










