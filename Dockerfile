# Dockerfile pour Suivi BAN - Version MongoDB
# Compatible Kyverno (non-root, read-only filesystem)

FROM python:3.12-slim AS builder

WORKDIR /build

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/build/deps -r requirements.txt

# ===========================================
FROM python:3.12-slim

# Installer curl pour healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Copier les dépendances Python
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages/

# Copier l'application (structure propre)
COPY --chown=appuser:appgroup config.py ./
COPY --chown=appuser:appgroup db/ ./db/
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup collectors/ ./collectors/
COPY --chown=appuser:appgroup app.py ./

# Créer les répertoires nécessaires
RUN mkdir -p /app/.streamlit /app/cache /app/data /app/data/dump && \
    chown -R appuser:appgroup /app

# Configuration Streamlit
RUN echo '[server]\n\
headless = true\n\
address = "0.0.0.0"\n\
port = 8501\n\
enableCORS = false\n\
enableXsrfProtection = false\n\
\n\
[browser]\n\
gatherUsageStats = false\n\
' > /app/.streamlit/config.toml && chown appuser:appgroup /app/.streamlit/config.toml

# Copier les scripts
COPY --chown=appuser:appgroup scripts/ ./scripts/

# Copier le dump MongoDB (inclus dans data/)
COPY --chown=appuser:appgroup data/dump/ /app/data/dump/

# Script de démarrage
RUN echo '#!/bin/sh\n\
set -e\n\
echo "[INFO] Starting Suivi BAN application..."\n\
\n\
# Initialiser la base de données si nécessaire\n\
echo "[INFO] Checking database initialization..."\n\
python scripts/init_db.py || echo "[WARN] Database initialization failed (check logs above)"\n\
\n\
# Lancer l API en arrière-plan\n\
echo "[INFO] Starting API on port 8000..."\n\
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 &\n\
\n\
# Lancer Streamlit (en foreground, c est le processus principal)\n\
echo "[INFO] Starting Streamlit on port 8501..."\n\
exec python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501\n\
' > /app/start.sh && chmod +x /app/start.sh && chown appuser:appgroup /app/start.sh

# Passer à l'utilisateur non-root
USER appuser

# Exposer les ports
EXPOSE 8501 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Commande de démarrage
CMD ["/app/start.sh"]
