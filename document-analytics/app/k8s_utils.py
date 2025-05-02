"""Kubernetes Utilities for Document Analytics.

This module provides reusable functions for creating and managing Kubernetes deployments
and services for the document analytics application.
"""

import logging
import time
from kubernetes import client
from kubernetes.client.rest import ApiException

# Configure logger
logger = logging.getLogger("k8s_utils")

def create_deployment(
    name,
    component,
    image="document-analytics:latest",
    replicas=1,
    command=None,
    ports=None,
    env_vars=None,
    resource_requests=None,
    resource_limits=None,
    volume_mounts=None,
    volumes=None,
    labels=None,
    namespace="default",
    readiness_probe_port=None,
    liveness_probe_port=None
):
    """Create a Kubernetes deployment.
    
    Args:
        name: Deployment name
        component: Component type (worker-queue, doc-processor, etc.)
        image: Container image to use
        replicas: Number of replicas
        command: Container command
        ports: List of container ports as dicts with container_port and name
        env_vars: List of environment variables as dicts with name and value
        resource_requests: Dict with resource requests (cpu, memory)
        resource_limits: Dict with resource limits (cpu, memory)
        volume_mounts: List of volume mounts
        volumes: List of volumes
        labels: Additional labels to add
        namespace: Kubernetes namespace
        readiness_probe_port: Port to use for readiness probe
        liveness_probe_port: Port to use for liveness probe
    
    Returns:
        The created deployment or None if failed
    """
    # Default values
    if ports is None:
        ports = []
    if env_vars is None:
        env_vars = []
    if resource_requests is None:
        resource_requests = {"cpu": "100m", "memory": "128Mi"}
    if resource_limits is None:
        resource_limits = {"cpu": "500m", "memory": "256Mi"}
    if volume_mounts is None:
        volume_mounts = []
    if volumes is None:
        volumes = []
    
    # Base labels
    base_labels = {
        "app": "document-analytics",
        "component": component
    }
    
    # Add additional labels
    if labels:
        base_labels.update(labels)
    
    # Create API client
    apps_v1_api = client.AppsV1Api()
    
    # Prepare container ports
    container_ports = []
    for port in ports:
        container_port = port["container_port"]
        port_name = port.get("name")
        cp = client.V1ContainerPort(container_port=container_port)
        if port_name:
            cp.name = port_name
        container_ports.append(cp)
    
    # Prepare environment variables
    container_env = []
    for env_var in env_vars:
        container_env.append(
            client.V1EnvVar(
                name=env_var["name"],
                value=env_var["value"]
            )
        )
    
    # Prepare probes
    readiness_probe = None
    liveness_probe = None
    
    if readiness_probe_port:
        readiness_probe = client.V1Probe(
            tcp_socket=client.V1TCPSocketAction(port=readiness_probe_port),
            initial_delay_seconds=5,
            period_seconds=10
        )
    
    if liveness_probe_port:
        liveness_probe = client.V1Probe(
            tcp_socket=client.V1TCPSocketAction(port=liveness_probe_port),
            initial_delay_seconds=15,
            period_seconds=20
        )
    
    # Create container template
    container = client.V1Container(
        name=component,
        image=image,
        image_pull_policy="IfNotPresent",
        ports=container_ports,
        env=container_env,
        resources=client.V1ResourceRequirements(
            requests=resource_requests,
            limits=resource_limits
        ),
        volume_mounts=[client.V1VolumeMount(**vm) for vm in volume_mounts]
    )
    
    # Set command if provided
    if command:
        container.command = command
    
    # Set probes if provided
    if readiness_probe:
        container.readiness_probe = readiness_probe
    
    if liveness_probe:
        container.liveness_probe = liveness_probe
    
    # Create deployment
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=base_labels
        ),
        spec=client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(
                match_labels=base_labels
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels=base_labels
                ),
                spec=client.V1PodSpec(
                    containers=[container],
                    volumes=[client.V1Volume(**vol) for vol in volumes]
                )
            )
        )
    )
    
    # Create deployment
    try:
        logger.info(f"Creating {component} deployment: {name}")
        return apps_v1_api.create_namespaced_deployment(
            namespace=namespace,
            body=deployment
        )
        
    except ApiException as e:
        logger.error(f"Exception when creating {component} deployment: {e}")
        return None


def create_service(
    name,
    component,
    ports,
    labels=None,
    namespace="default"
):
    """Create a Kubernetes service.
    
    Args:
        name: Service name
        component: Component type (worker-queue, doc-processor, etc.)
        ports: List of ports as dicts with port and name
        labels: Additional labels to add
        namespace: Kubernetes namespace
    
    Returns:
        The created service or None if failed
    """
    # Base labels
    base_labels = {
        "app": "document-analytics",
        "component": component
    }
    
    # Add additional labels
    if labels:
        base_labels.update(labels)
    
    # Create API client
    core_v1_api = client.CoreV1Api()
    
    # Prepare service ports
    service_ports = []
    for port in ports:
        port_num = port["port"]
        port_name = port.get("name")
        sp = client.V1ServicePort(port=port_num)
        if port_name:
            sp.name = port_name
        service_ports.append(sp)
    
    # Create service
    service = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=base_labels
        ),
        spec=client.V1ServiceSpec(
            selector=base_labels,
            ports=service_ports
        )
    )
    
    # Create service
    try:
        logger.info(f"Creating {component} service: {name}")
        return core_v1_api.create_namespaced_service(
            namespace=namespace,
            body=service
        )
        
    except ApiException as e:
        logger.error(f"Exception when creating {component} service: {e}")
        return None


def wait_for_deployment_ready(deployment_name, namespace="default", timeout=60):
    """Wait for a deployment to be ready.
    
    Args:
        deployment_name: Name of the deployment
        namespace: Kubernetes namespace
        timeout: Timeout in seconds
        
    Returns:
        True if deployment is ready, False otherwise
    """
    apps_v1_api = client.AppsV1Api()
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Get deployment status
            deployment = apps_v1_api.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            
            # Check if deployment is ready
            if (deployment.status.ready_replicas is not None and
                deployment.status.ready_replicas == deployment.status.replicas):
                logger.info(f"Deployment {deployment_name} is ready!")
                return True
            
            logger.info(f"Waiting for deployment {deployment_name} to be ready: "
                       f"{deployment.status.ready_replicas or 0}/{deployment.status.replicas} replicas ready")
            
            time.sleep(5)
            
        except ApiException as e:
            logger.error(f"Error checking deployment status: {e}")
            time.sleep(5)
    
    logger.error(f"Timeout waiting for deployment {deployment_name} to be ready")
    return False


def delete_deployment(name, namespace="default"):
    """Delete a Kubernetes deployment.
    
    Args:
        name: Deployment name
        namespace: Kubernetes namespace
        
    Returns:
        True if successful, False otherwise
    """
    apps_v1_api = client.AppsV1Api()
    
    try:
        logger.info(f"Deleting deployment: {name}")
        apps_v1_api.delete_namespaced_deployment(
            name=name,
            namespace=namespace
        )
        return True
        
    except ApiException as e:
        logger.error(f"Exception when deleting deployment: {e}")
        return False


def delete_service(name, namespace="default"):
    """Delete a Kubernetes service.
    
    Args:
        name: Service name
        namespace: Kubernetes namespace
        
    Returns:
        True if successful, False otherwise
    """
    core_v1_api = client.CoreV1Api()
    
    try:
        logger.info(f"Deleting service: {name}")
        core_v1_api.delete_namespaced_service(
            name=name,
            namespace=namespace
        )
        return True
        
    except ApiException as e:
        logger.error(f"Exception when deleting service: {e}")
        return False


def list_pods_by_labels(component, labels=None, namespace="default"):
    """List pods matching specified labels.
    
    Args:
        component: Component type (worker-queue, doc-processor, etc.)
        labels: Additional labels to filter by
        namespace: Kubernetes namespace
        
    Returns:
        List of pods matching the labels
    """
    # Base labels
    selector = f"app=document-analytics,component={component}"
    
    # Add additional labels
    if labels:
        for key, value in labels.items():
            selector += f",{key}={value}"
    
    # Create API client
    core_v1_api = client.CoreV1Api()
    
    try:
        return core_v1_api.list_namespaced_pod(
            namespace=namespace,
            label_selector=selector
        ).items
        
    except ApiException as e:
        logger.error(f"Exception when listing pods: {e}")
        return []


def get_pod_logs(pod_name, namespace="default"):
    """Get logs from a pod.
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        
    Returns:
        Pod logs as string
    """
    core_v1_api = client.CoreV1Api()
    
    try:
        return core_v1_api.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace
        )
        
    except ApiException as e:
        logger.error(f"Exception when getting pod logs: {e}")
        return f"Error getting logs: {str(e)}"