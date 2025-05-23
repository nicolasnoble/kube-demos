# Kubernetes Document Analytics Demo

This project demonstrates a complex Kubernetes deployment with multiple microservices that analyze Markdown documents to count lines, words, and characters by topic. It includes a CLI tool to interact with the deployed services. The services will be automatically created and managed by the API service, which will also handle the distribution of work among the services.

## Project Structure

```
.
├── Dockerfile                 # Container image definition
├── README.md                  # This documentation file
├── requirements.txt           # Python dependencies
├── deploy.sh                  # Deployment script for Kubernetes
├── doc_analytics_lib/         # Core document analytics functionality as a reusable package
│   └── __init__.py            # Document analytics library implementation
├── app/                       # API service code
│   ├── __init__.py            # Package marker
│   ├── app.py                 # Main application entry point
│   ├── k8s_deployments.py     # Kubernetes deployment management
│   ├── k8s_utils.py           # Kubernetes utilities
│   ├── process_utils.py       # Process utilities
│   ├── api/                   # API endpoints
│   │   ├── __init__.py        # Package marker
│   │   ├── worker_queue.py    # Worker queue service
│   │   ├── doc_processor.py   # Document processor service
│   │   └── topic_aggregator.py# Topic aggregator service
│   └── tests/                 # Unit tests
│       ├── __init__.py        # Package marker
│       ├── test_doc_analytics_lib.py # Tests for analytics library
│       ├── test_worker_queue.py     # Tests for worker queue
│       ├── test_doc_processor.py    # Tests for document processor
│       └── test_topic_aggregator.py # Tests for topic aggregator
├── cli/                       # Command-line client
│   └── document_analytics.py  # CLI tool to process documents
├── data/                      # Sample data files
│   └── documents/             # Markdown documents for testing
│       ├── sample1.md         # Sample document 1
│       ├── sample2.md         # Sample document 2
│       └── sample3.md         # Sample document 3
├── kubernetes/                # Kubernetes configurations
│   ├── api.yaml               # API service deployment
│   ├── rbac.yaml              # RBAC permissions for K8s API access
│   └── README.md              # Kubernetes deployment instructions
```

## Overview

This document analytics system processes Markdown files and calculates metrics (line count, word count, character count) for different topics within those documents. Topics are defined by H1 headers (`# Topic Name`) in the Markdown files.

### Architecture

The system consists of several microservices:

1. **Worker Queue**: A singleton service that distributes markdown files to Document Processors.
2. **Document Processors**: A worker pool that processes individual markdown files and broadcasts content by topic.
3. **Topic Aggregators**: Services that listen for content from specific topics and calculate metrics.

The API service orchestrates the entire process, dynamically creating and managing the Worker Queue, Document Processors, and Topic Aggregators as needed. It communicates with the Kubernetes API to create and manage these components. The Document Processors and Topic Aggregators are implemented as separate microservices, allowing for scalability and flexibility in deployment.

#### Communication Architecture

The system uses a hybrid approach for inter-service communication:

- **HTTP REST API**: Used for Worker Queue to Document Processor communication (RESTful API endpoints)
- **ZeroMQ PUB/SUB**: Used for Document Processor to Topic Aggregator communication (efficient topic-based messaging)

## Prerequisites

- Docker
- Kubernetes cluster (Minikube or Kind)
- Python 3.9+
- kubectl command-line tool

## Local Development Setup

### Setting up a Virtual Environment

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

```bash
pip install -r requirements.txt
```

### Running Tests

```bash
cd document-analytics && python -m pytest app/tests -v
```

## Building and Deploying

### 1. Build the Docker image

```bash
docker build -t document-analytics:latest .
```

### 2. Load the image into your Kubernetes cluster

If you're using Kind:
```bash
kind load docker-image document-analytics:latest --name your-cluster-name
```

For Minikube:
```bash
minikube image load document-analytics:latest
```

### 3. Deploy to Kubernetes

Use the included deployment script which creates the necessary ConfigMap from your local sample documents and deploys the API service:

```bash
# Make the script executable if needed
chmod +x deploy.sh

# Run the deployment script
./deploy.sh
```

The script will:
1. Create a ConfigMap from the documents in the data/documents folder
2. Deploy the API service using kubernetes/api.yaml
3. Wait for the pod to become ready

### 4. Running the CLI Tool

The CLI tool can be used in two modes:
- Local mode: Processes files directly on your machine
- Kubernetes mode: Sends requests to the deployed API service

```bash
# Local mode
./cli/document_analytics.py --topic=Sport --topic=Music --documents=data/documents/*.md --local

# Kubernetes mode (when services are deployed)
./cli/document_analytics.py --topic=Sport --topic=Music --documents=data/documents/*.md
```

When running in Kubernetes mode, the CLI tool will send requests to the API service, which will then distribute the work to the Document Processors and Topic Aggregators. It may be necessary to forward the API service port to access it locally:

```bash
kubectl port-forward service/document-analytics-api 8080:80
```

#### Important Note About Document Glob Patterns

When using glob patterns with the `--documents` parameter, always enclose the pattern in quotes to prevent shell expansion:

```bash
# CORRECT: Use quotes around glob patterns to prevent shell expansion
./cli/document_analytics.py --topic=Sport --documents="data/documents/*.md"

# INCORRECT: Without quotes, the shell will expand the glob before passing to the script
./cli/document_analytics.py --topic=Sport --documents=data/documents/*.md
```

If you don't use quotes, your shell might expand the glob pattern before passing it to the script, which can lead to unexpected behavior, as the script will receive the expanded list of files instead of the pattern itself, causing argument parsing failure since the script expects a single pattern.

## Architecture Details

The system is implemented using a dynamic pod deployment approach. The main API service (deployed via api.yaml) uses the Kubernetes API to create and manage the following components:

### Worker Queue

The Worker Queue is responsible for:
- Registering documents for processing
- Distributing documents to Document Processors via HTTP requests
- Tracking processing progress

The Worker Queue is dynamically created by the API service when analysis is requested and provides RESTful API endpoints for communication.

### Document Processor

Document Processors:
- Parse Markdown files to identify topics (H1 headers)
- Extract content for each topic
- Broadcast content to Topic Aggregators based on topic names using ZeroMQ PUB/SUB

Multiple Document Processor pods are dynamically created by the API service based on workload requirements. Each Document Processor exposes a Flask REST API for receiving processing requests from the Worker Queue.

### Topic Aggregator

Topic Aggregators:
- Subscribe to content for specific topics via ZeroMQ
- Count lines, words, and characters in the content
- Aggregate results for reporting
- Expose metrics via a REST API

One Topic Aggregator pod is created dynamically for each topic being analyzed.

### Dynamic Resource Management

The API service automatically creates and manages all required microservices:
- Creates the Worker Queue, Document Processors, and Topic Aggregators on demand
- Registers Document Processors with the Worker Queue
- Sets up proper communication between all components
- Cleans up resources when analysis is complete

## Communication Details

This project uses a hybrid communication approach:

- **HTTP REST APIs**: Used for:
  - CLI to API service communication
  - Worker Queue to Document Processor task distribution
  - API service to Topic Aggregator metrics collection

- **ZeroMQ PUB/SUB**: Used for:
  - Document Processor to Topic Aggregator content distribution
  - Efficient topic-based message delivery

## Security Considerations

This demo focuses on functionality, but in a production environment, consider:
- Adding authentication and authorization
- Using TLS for secure communication
- Implementing network policies
- Setting up proper resource quotas
- Using Kubernetes Secrets for sensitive information