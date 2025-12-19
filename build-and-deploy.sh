#!/bin/bash
# Script pour builder et déployer suivi-ban

set -e

# Configuration
IMAGE_NAME="ghcr.io/jbouhadoun/suivi-ban"
TAG="${1:-latest}"

echo "🔨 Build de l'image Docker..."
docker build -t ${IMAGE_NAME}:${TAG} .

echo ""
echo "📤 Push vers le registry..."
docker push ${IMAGE_NAME}:${TAG}

echo ""
echo "🚀 Déploiement sur Kubernetes..."
kubectl apply -k k8s/

echo ""
echo "⏳ Attente du rollout..."
kubectl rollout status deployment/suivi-ban -n ban

echo ""
echo "✅ Déploiement terminé !"
echo ""
echo "📍 Pour accéder à l'app:"
echo "   kubectl port-forward svc/suivi-ban 8501:8501 -n ban"
echo "   Puis ouvrir http://localhost:8501"

