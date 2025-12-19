#!/usr/bin/env python3
"""
Script de mise à jour nocturne de la base de données BAN
Lance automatiquement collect_data.py et enregistre les logs
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from database import get_connection

LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


def log_update_start(conn):
    """Enregistre le début de la mise à jour"""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO update_logs (started_at, status)
        VALUES (?, 'running')
    """, (datetime.now().isoformat(),))
    conn.commit()
    return cursor.lastrowid


def log_update_finish(conn, log_id, success, communes_updated=0, errors=0, error_msg=None):
    """Enregistre la fin de la mise à jour"""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE update_logs
        SET finished_at = ?,
            duration_seconds = CAST((julianday(?) - julianday(started_at)) * 86400 AS INTEGER),
            communes_updated = ?,
            errors_count = ?,
            status = ?,
            error_message = ?
        WHERE id = ?
    """, (
        datetime.now().isoformat(),
        datetime.now().isoformat(),
        communes_updated,
        errors,
        'success' if success else 'failed',
        error_msg,
        log_id
    ))
    conn.commit()


def main():
    """Fonction principale"""
    log_file = LOGS_DIR / f"update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    print(f"\n{'='*70}")
    print(f"🌙 Mise à jour nocturne BAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    print(f"📝 Log: {log_file}\n")
    
    # Connexion à la base
    conn = get_connection()
    log_id = log_update_start(conn)
    
    try:
        # Lancer le script de collecte
        with open(log_file, 'w') as f:
            f.write(f"Mise à jour BAN - {datetime.now().isoformat()}\n")
            f.write("="*70 + "\n\n")
            
            process = subprocess.Popen(
                [sys.executable, 'collect_data.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Afficher et logger la sortie en temps réel
            for line in process.stdout:
                print(line, end='')
                f.write(line)
            
            process.wait()
            
            if process.returncode == 0:
                print("\n✅ Mise à jour terminée avec succès")
                f.write("\n✅ Mise à jour réussie\n")
                log_update_finish(conn, log_id, success=True)
                return True
            else:
                print(f"\n❌ Échec de la mise à jour (code: {process.returncode})")
                f.write(f"\n❌ Échec (code: {process.returncode})\n")
                log_update_finish(conn, log_id, success=False, error_msg=f"Exit code: {process.returncode}")
                return False
                
    except Exception as e:
        error_msg = f"Erreur: {str(e)}"
        print(f"\n❌ {error_msg}")
        with open(log_file, 'a') as f:
            f.write(f"\n❌ {error_msg}\n")
        log_update_finish(conn, log_id, success=False, error_msg=error_msg)
        return False
    
    finally:
        conn.close()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)










