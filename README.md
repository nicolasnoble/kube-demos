# Kubernetes Demonstration Projects (kube-demos)

This repository contains a collection of demonstration projects for learning and showcasing Kubernetes concepts. Each example presents different aspects of Kubernetes deployment, service orchestration, and microservice architecture with increasing levels of complexity.

## Available Examples

### 1. [Adder Example](./adder-example/)

A simple Kubernetes deployment demonstrating:
- Basic REST API service using Flask
- Kubernetes deployment and service configuration
- Containerization with Docker
- CLI client for service interaction
- Unit testing

This example is perfect for beginners to understand the fundamentals of deploying a simple service to Kubernetes.

**Key features:**
- Single service architecture
- RESTful API endpoints
- Stateless application design
- Kubernetes deployment with replicas
- Service exposure via NodePort

### 2. [Document Analytics](./document-analytics/)

A more complex Kubernetes project demonstrating:
- Dynamic microservice creation and management
- Inter-service communication using ZeroMQ
- Worker pool pattern for distributed processing
- Kubernetes API integration for pod management
- ConfigMap usage for configuration

This intermediate example shows how to build and deploy a distributed system that processes Markdown documents to calculate metrics (line count, word count, character count) across different topics.

**Key features:**
- Multi-service architecture
- Dynamic resource provisioning
- Message-based communication
- Kubernetes RBAC implementation
- Worker queue distribution pattern

### 3. [Python Distributed Guide](./python-distributed-guide/)

A comprehensive documentation resource on:
- Best practices for Python in distributed environments
- Implementation patterns for Kubernetes deployments
- Practical advice for real-world distributed systems

This guide serves as a reference for developers looking to write robust, scalable Python applications for distributed environments like Kubernetes.

**Key topics:**
- State management in distributed systems
- Inter-service communication patterns
- Resilience and error handling
- Resource allocation and management
- Security considerations for distributed applications
- Testing distributed systems

## Prerequisites

To run these examples, you'll need:

- Docker
- Kubernetes cluster (Minikube, Kind, or cloud provider)
- Python 3.9+
- kubectl command-line tool

## Getting Started

1. Clone this repository
2. Navigate to the example you want to explore
3. Follow the README instructions within that example

## Learning Path

These examples are designed to provide a progressive learning path for Kubernetes:

1. Start with the **Adder Example** to understand basic Kubernetes concepts
2. Move to the **Document Analytics** example to learn advanced patterns and techniques

Each example includes detailed documentation on:
- Project structure
- Deployment instructions
- Architecture overview
- Testing procedures
- CLI usage

## Contributing

Contributions are welcome! If you'd like to add another example or improve existing ones, please submit a pull request.

## License

This project is open source and available under the [MIT License](LICENSE).