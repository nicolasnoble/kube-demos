# Document Analytics Kubernetes Configuration

This directory contains Kubernetes configuration files required to deploy the Document Analytics system. These manifests define the API service deployment, service exposure, and the necessary RBAC (Role-Based Access Control) permissions for dynamic pod management.

## Files Overview

- `api.yaml`: Defines the API service and deployment
- `rbac.yaml`: Contains RBAC configurations for the API service to manage other Kubernetes resources

## api.yaml

This file contains two main Kubernetes resources:

### 1. Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: document-analytics-api
  labels:
    app: document-analytics
    component: api
spec:
  type: NodePort
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30080
    name: http
  selector:
    app: document-analytics
    component: api
```

**Purpose:**
- Exposes the Document Analytics API application to external traffic
- Makes the API accessible at port 30080 on the Kubernetes node's IP address
- Routes traffic to port 8080 of pods with labels `app: document-analytics, component: api`
- Uses NodePort type to allow external access for demonstration purposes

### 2. Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: document-analytics-api
  labels:
    app: document-analytics
    component: api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: document-analytics
      component: api
  template:
    metadata:
      labels:
        app: document-analytics
        component: api
    spec:
      serviceAccountName: document-analytics-api
      containers:
      - name: api
        image: document-analytics:latest
        # ... configuration continues
```

**Purpose:**
- Deploys the main API container that orchestrates the document analytics system
- Uses the `serviceAccountName: document-analytics-api` to grant permissions for the API to manage other resources
- Sets up health checks via readiness and liveness probes
- Configures two volume mounts:
  - `shared-documents`: An emptyDir volume for temporary document storage
  - `sample-documents`: A ConfigMap volume containing sample documents for testing

**Key Features:**
- Resource limits and requests ensure appropriate CPU and memory allocation
- Health probe endpoints confirm the API is functioning correctly
- Volumes provide necessary data access for document processing
- Log level can be configured via environment variables

## rbac.yaml

This file defines three RBAC (Role-Based Access Control) resources:

### 1. ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: document-analytics-api
  labels:
    app: document-analytics
```

**Purpose:**
- Creates a dedicated identity for the API service
- Used by the API deployment to authenticate with the Kubernetes API

### 2. Role

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: document-analytics-api-role
  labels:
    app: document-analytics
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps", "pods/log"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

**Purpose:**
- Defines the specific permissions granted to the API service
- Allows the API service to dynamically create, manage, and monitor:
  - Worker Queue pods
  - Document Processor pods
  - Topic Aggregator pods
  - Associated services and configurations

**Permissions Explanation:**
- **Pod Management**: Create and manage worker pods for document processing
- **Service Management**: Create services for inter-component communication
- **ConfigMap Access**: Read configuration data and sample documents
- **Deployment Management**: Create and manage deployments for scaling components
- **Pod Logs**: Access logs from worker pods for monitoring and troubleshooting

### 3. RoleBinding

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: document-analytics-api-role-binding
  labels:
    app: document-analytics
subjects:
- kind: ServiceAccount
  name: document-analytics-api
  namespace: default
roleRef:
  kind: Role
  name: document-analytics-api-role
  apiGroup: rbac.authorization.k8s.io
```

**Purpose:**
- Links the Role to the ServiceAccount
- Activates the permissions defined in the Role for the API service
- Associates the permissions with the default namespace

## Deployment Architecture

The Kubernetes configurations support the following architecture:

1. **API Service (Singleton)**
   - Deployed via api.yaml
   - Serves as the entry point and orchestrator for the system
   - Dynamically creates other components based on analysis requests

2. **Dynamically Created Components**
   - Worker Queue (created by the API when analysis is requested)
   - Document Processors (dynamically scaled based on workload)
   - Topic Aggregators (one per topic being analyzed)

## Usage Notes

1. **Applying the Configurations**

   Apply the RBAC configuration first to ensure the service account exists:
   ```bash
   kubectl apply -f rbac.yaml
   ```

   Then apply the API deployment:
   ```bash
   kubectl apply -f api.yaml
   ```

2. **ConfigMap Requirement**

   The deployment expects a ConfigMap named `sample-documents` to exist. This is typically created by the `deploy.sh` script in the parent directory:
   ```bash
   # Example of how the ConfigMap might be created
   kubectl create configmap sample-documents --from-file=../data/documents/
   ```

3. **Port Forwarding**

   To access the API service locally:
   ```bash
   kubectl port-forward service/document-analytics-api 8080:80
   ```

4. **Checking Deployment Status**

   ```bash
   kubectl get pods -l app=document-analytics
   kubectl get services -l app=document-analytics
   ```

## Security Considerations

- The RBAC permissions granted are quite broad for demonstration purposes
- In a production environment, the permissions should be scoped more tightly
- Consider using Kubernetes Network Policies to restrict communication between components
- For production use, implement proper authentication and TLS for API access