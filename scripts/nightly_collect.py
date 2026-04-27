#!/usr/bin/env python3
"""
Orchestrateur nocturne:
1) Collecteur principal Suivi BAN
2) Collecteur Déploiement BAL
"""

import sys
import logging
from pathlib import Path

# Ajouter la racine projet au PYTHONPATH pour l'exécution directe du script.
sys.path.insert(0, str(Path(__file__).parent.parent))

from collectors.smart_collector import run_smart_collect
from collectors.deploiement_bal_collector import run_deploiement_bal_collect

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        ok2 = run_deploiement_bal_collect()
    except Exception as e:
        logger.exception("Echec run_deploiement_bal_collect: %s", e)
        ok2 = False

    try:
        ok1 = run_smart_collect()
    except Exception as e:
        logger.exception("Echec run_smart_collect: %s", e)
        ok1 = False

    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    raise SystemExit(main())

