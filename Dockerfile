# Dockerfile pour Suivi BAN - Version statique
# Compatible Kyverno (non-root, read-only filesystem)

FROM python:3.12-slim AS builder

WORKDIR /build

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/build/deps -r requirements.txt

# ===========================================
FROM python:3.12-slim

# Installer unzip
RUN apt-get update && apt-get install -y --no-install-recommends unzip && \
    rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Copier les dépendances Python
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages/

# Copier l'application
COPY --chown=appuser:appgroup app.py api.py ./

# Copier et dézipper les données
COPY --chown=appuser:appgroup data.zip ./
RUN unzip data.zip && rm data.zip && chown -R appuser:appgroup data/ cache/

# Créer les répertoires nécessaires pour Streamlit
RUN mkdir -p /app/.streamlit && chown -R appuser:appgroup /app

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

# Script de démarrage
RUN echo '#!/bin/sh\n\
# Lancer l API en arrière-plan\n\
python -m uvicorn api:app --host 0.0.0.0 --port 8000 &\n\
\n\
# Attendre que l API soit prête\n\
sleep 2\n\
\n\
# Lancer Streamlit\n\
exec streamlit run app.py\n\
' > /app/start.sh && chmod +x /app/start.sh && chown appuser:appgroup /app/start.sh

# Passer à l'utilisateur non-root
USER appuser

# Exposer les ports
EXPOSE 8501 8000

# Healthcheck via Python (curl non dispo dans slim)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Commande de démarrage
CMD ["/app/start.sh"]

