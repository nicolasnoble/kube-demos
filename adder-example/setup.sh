#!/bin/bash
# Setup script for the Kubernetes Adder Service Demo
# This script builds the Docker image and deploys the application to Kubernetes

set -e  # Exit immediately if a command exits with a non-zero status

echo "==== Kubernetes Adder Service Demo Setup ===="
echo "Building Docker image..."
docker build -t adder-service:latest .

echo "Deploying to Kubernetes..."
kubectl apply -f kubernetes/deployment.yaml --validate=false
kubectl apply -f kubernetes/service.yaml

echo "Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=60s deployment/adder-service

echo "Checking pod status..."
kubectl get pods -l app=adder-service

echo "Checking service..."
kubectl get service adder-service

echo "==== Setup Complete ===="
echo ""
echo "Access the service using port forwarding:"
echo "kubectl port-forward svc/adder-service 8080:80"
echo ""
echo "Then use the CLI client:"
echo "./cli/adder_client.py health --url http://localhost:8080"
echo "./cli/adder_client.py add --url http://localhost:8080 --a 5 --b 10"