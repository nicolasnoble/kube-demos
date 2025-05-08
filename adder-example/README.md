# Kubernetes Adder Service Demo

This project demonstrates a simple Kubernetes deployment of a Python API service that adds two numbers together. It includes a CLI tool to interact with the deployed service and a reusable adder library that can be used independently.

## Project Structure

```
.
├── Dockerfile             # Container image definition
├── README.md              # This documentation file
├── adder_lib/             # Core adder functionality as a reusable package
│   └── __init__.py        # Adder library implementation
├── app/                   # API service code
│   ├── api/               # API endpoints
│   │   └── adder_service.py  # Flask service that adds numbers
│   ├── app.py             # Main application entry point
│   └── tests/             # Unit tests
│       └── test_adder_service.py  # Tests for adder service
├── cli/                   # Command-line client
│   └── adder_client.py    # CLI tool to interact with service
├── kubernetes/            # Kubernetes configurations
│   ├── deployment.yaml    # Deployment definition
│   └── service.yaml       # Service definition
└── requirements.txt       # Python dependencies
```

## Prerequisites

- Docker
- Kubernetes cluster (Minikube, Docker Desktop, or a cloud provider)
- Python 3.9+
- kubectl command-line tool

## Local Development Setup

### Setting up a Virtual Environment

It's recommended to use a virtual environment for local development to ensure dependency isolation:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### Installing Dependencies

Install the required packages within your virtual environment:

```bash
pip install -r requirements.txt
```

**Note:** When using Flask 2.2.3 (specified in requirements.txt), ensure you're using a compatible version of Werkzeug. If you encounter import errors with `werkzeug.urls` or `url_quote`, you might need to downgrade Werkzeug:

```bash
pip install werkzeug==2.2.3
```

### Running Tests

After setting up the virtual environment and installing dependencies, you can run the tests:

```bash
cd app && python -m pytest -v
```

## Setting up a Local Kubernetes Environment

This project requires a running Kubernetes cluster. You can use either Minikube or Kind for local development:

### Option 1: Minikube

Minikube is a tool that lets you run Kubernetes locally, creating a single-node cluster in a virtual machine.

#### Installation

##### Linux:
```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```

##### macOS:
```bash
brew install minikube
# OR
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-darwin-amd64
sudo install minikube-darwin-amd64 /usr/local/bin/minikube
```

##### Windows:
```bash
# With chocolatey
choco install minikube

# OR download the installer:
# https://storage.googleapis.com/minikube/releases/latest/minikube-installer.exe
```

#### Starting Minikube

```bash
# Start with default settings (requires a hypervisor like Docker, VirtualBox, or Hyper-V)
minikube start

# OR specify the driver explicitly
minikube start --driver=docker
```

Verify installation:
```bash
minikube status
```

For more information, visit the [Minikube documentation](https://minikube.sigs.k8s.io/docs/start/).

### Option 2: Kind (Kubernetes in Docker)

Kind runs Kubernetes clusters using Docker containers as nodes.

#### Installation

##### Linux/macOS:
```bash
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
# OR for macOS: curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-darwin-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

##### With Homebrew (macOS/Linux):
```bash
brew install kind
```

##### Windows:
```bash
# With chocolatey
choco install kind

# OR with PowerShell
curl.exe -Lo kind-windows-amd64.exe https://kind.sigs.k8s.io/dl/v0.20.0/kind-windows-amd64
Move-Item .\kind-windows-amd64.exe c:\some-dir-in-your-PATH\kind.exe
```

#### Creating a Cluster

```bash
kind create cluster --name adder-demo
```

Verify installation:
```bash
kubectl cluster-info --context kind-adder-demo
```

#### Loading Docker Images into Kind

When using Kind, you need to explicitly load your locally built Docker images into the Kind cluster:

```bash
# After building your Docker image
docker build -t adder-service:latest .

# Load the image into the Kind cluster
kind load docker-image adder-service:latest --name adder-demo
```

This step is necessary because the Kind cluster runs in its own Docker context and doesn't automatically have access to images in your local Docker daemon.

For more information, visit the [Kind documentation](https://kind.sigs.k8s.io/docs/user/quick-start/).

### Pointing kubectl to Your Cluster

Both Minikube and Kind will automatically configure kubectl to communicate with your new cluster. You can verify this with:

```bash
kubectl get nodes
```

## Setup Instructions

### 1. Build the Docker image

```bash
docker build -t adder-service:latest .

# only necessary for MiniKube
minikube image load adder-service:latest
```

### 2. Deploy to Kubernetes

```bash
# Apply Kubernetes configurations
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml

# Verify deployment
kubectl get pods
kubectl get services
```

### 3. Access the service

#### Using port-forwarding

```bash
# Forward the service to localhost
kubectl port-forward svc/adder-service 8080:80
```

The service will be available at http://localhost:8080

#### Using Minikube

```bash
# Get the URL if using Minikube
minikube service adder-service --url
```

### 4. Using the CLI Tool

Install the required Python dependencies to use the CLI tool:

```bash
pip install click requests
```

#### Check service health

```bash
./cli/adder_client.py health --url http://localhost:8080
```

#### Add two numbers using the API

```bash
./cli/adder_client.py add --url http://localhost:8080 --a 5 --b 10
```

#### Add two numbers using the local adder library (without API)

The adder functionality is also available as a standalone library that can be used without the API:

```bash
./cli/adder_client.py add --a 5 --b 10 --local
```

## Using the Adder Library

The core adder functionality has been extracted into a reusable library that can be used in various contexts:

### 1. Direct Python Import

```python
from adder_lib import add, AdderException

try:
    result = add(5, 3)
    print(f"5 + 3 = {result}")
except AdderException as e:
    print(f"Error: {e}")
```

### 2. Through the CLI Client

```bash
# Using the local library directly
./cli/adder_client.py add --a 5 --b 3 --local

# Using the API service
./cli/adder_client.py add --url http://localhost:8080 --a 5 --b 3
```

### 3. Through HTTP Requests

```bash
curl -X POST http://localhost:8080/add \
  -H "Content-Type: application/json" \
  -d '{"a": 5, "b": 3}'
```

## API Documentation

### Health Check

```
GET /health
```

Response:
```json
{
  "status": "healthy"
}
```

### Add Numbers

```
POST /add
Content-Type: application/json

{
  "a": <number>,
  "b": <number>
}
```

Response:
```json
{
  "result": <number>
}
```

Error Response:
```json
{
  "error": <error message>
}
```

## Testing

Run the unit tests:

```bash
cd app && python -m pytest
```

## Error Handling

The service handles various error cases:
- Missing parameters
- Invalid parameter types (non-numeric)
- Server errors

All errors are returned with appropriate HTTP status codes and error messages in JSON format.

## Kubernetes Configuration Details

### Deployment

- 2 replicas for high availability
- Resource limits and requests defined
- Health checks configured (readiness and liveness probes)
- Rolling update strategy

### Service

- NodePort service type for external access
- Maps port 80 to container port 5000

## Security Considerations

This demo focuses on functionality, but in a production environment, consider:
- Adding authentication and authorization
- Using HTTPS
- Implementing network policies
- Setting up proper resource quotas
- Using secrets for sensitive configuration
