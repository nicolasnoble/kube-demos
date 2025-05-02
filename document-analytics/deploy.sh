#!/bin/bash
# deploy.sh - Script to deploy the document-analytics system to Kubernetes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="${SCRIPT_DIR}/data/documents"

echo "Creating ConfigMap from documents directory..."
if kubectl get configmap sample-documents &> /dev/null; then
    echo "ConfigMap sample-documents already exists, deleting..."
    kubectl delete configmap sample-documents
fi

# Create the ConfigMap from the local documents directory
kubectl create configmap sample-documents --from-file="${DOCS_DIR}"
echo "ConfigMap created successfully."

echo "Deploying RBAC configuration..."
kubectl apply -f "${SCRIPT_DIR}/kubernetes/rbac.yaml"
echo "RBAC configuration applied."

echo "Deploying document-analytics API..."
kubectl apply -f "${SCRIPT_DIR}/kubernetes/api.yaml"
echo "Deployment completed."

echo "Waiting for pod to become ready..."
kubectl wait --for=condition=ready pod -l app=document-analytics,component=api --timeout=120s
echo "Pod is ready!"

echo "Document Analytics system has been deployed successfully."
echo "You can access the API via NodePort 30080."