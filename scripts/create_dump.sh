#!/bin/bash
# Script wrapper pour créer un dump MongoDB (utilise create_dump.py)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Utiliser le script Python (pas besoin de mongodump)
python scripts/create_dump.py "$@"

