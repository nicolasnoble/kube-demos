"""Kubernetes Deployment Functions for Document Analytics.

This module provides specialized deployment functions for creating the document analytics
microservices in Kubernetes. It builds upon the basic k8s_utils functionality.
"""

import logging
from app import k8s_utils

# Configure logger
logger = logging.getLogger("k8s_deployments")

def create_worker_queue_deployment():
    """Create the worker queue deployment and service in Kubernetes.
    
    Returns:
        dict: Service details including cluster IP
    """
    # Define worker queue deployment configuration
    ports = [{"container_port": 5555, "name": "http"}]
    command = ["python", "-m", "app.api.worker_queue"]
    
    # Create deployment
    deployment = k8s_utils.create_deployment(
        name="worker-queue",
        component="worker-queue",
        command=command,
        ports=ports,
        resource_requests={"cpu": "100m", "memory": "128Mi"},
        resource_limits={"cpu": "500m", "memory": "256Mi"},
        readiness_probe_port=5555,
        liveness_probe_port=5555
    )
    
    if not deployment:
        logger.error("Failed to create worker queue deployment")
        return None
    
    # Create service
    service_ports = [{"port": 5555, "name": "http"}]
    service = k8s_utils.create_service(
        name="worker-queue",
        component="worker-queue",
        ports=service_ports
    )
    
    if not service:
        logger.error("Failed to create worker queue service")
        # Clean up the deployment since service creation failed
        k8s_utils.delete_deployment("worker-queue")
        return None
    
    # Wait for deployment to be ready
    logger.info("Waiting for worker queue deployment to be ready")
    if not k8s_utils.wait_for_deployment_ready("worker-queue"):
        logger.error("Timed out waiting for worker queue deployment to be ready")
        # Clean up resources
        k8s_utils.delete_deployment("worker-queue")
        k8s_utils.delete_service("worker-queue")
        return None
    
    # Return service details
    return {
        "name": service.metadata.name,
        "cluster_ip": service.spec.cluster_ip,
        "url": f"http://{service.spec.cluster_ip}:5555"
    }


def create_doc_processor_deployment(num_replicas=2):
    """Create document processor deployment and service in Kubernetes.
    
    Args:
        num_replicas: Number of document processor replicas to create
    
    Returns:
        dict: Service details including cluster IP
    """
    # Define document processor deployment configuration
    ports = [
        {"container_port": 5555, "name": "http"},  # HTTP for worker communication
        {"container_port": 5556, "name": "zmq-pub"}  # ZMQ PUB for topic broadcasting
    ]
    command = ["python", "-m", "app.api.doc_processor"]
    volume_mounts = [
        {
            "name": "documents-volume",
            "mount_path": "/documents"
        }
    ]
    volumes = [
        {
            "name": "documents-volume",
            "config_map": {
                "name": "sample-documents"
            }
        }
    ]
    
    # Create deployment
    deployment = k8s_utils.create_deployment(
        name="doc-processor",
        component="doc-processor",
        command=command,
        ports=ports,
        resource_requests={"cpu": "200m", "memory": "256Mi"},
        resource_limits={"cpu": "1000m", "memory": "512Mi"},
        volume_mounts=volume_mounts,
        volumes=volumes,
        replicas=num_replicas,
        readiness_probe_port=5555,  # HTTP port for readiness probe
        liveness_probe_port=5555
    )
    
    if not deployment:
        logger.error("Failed to create document processor deployment")
        return None
    
    # Create service
    service_ports = [
        {"port": 5555, "name": "http"},  # HTTP for worker communication
        {"port": 5556, "name": "zmq-pub"}  # ZMQ PUB for topic broadcasting
    ]
    service = k8s_utils.create_service(
        name="doc-processor",
        component="doc-processor",
        ports=service_ports
    )
    
    if not service:
        logger.error("Failed to create document processor service")
        # Clean up the deployment since service creation failed
        k8s_utils.delete_deployment("doc-processor")
        return None
    
    # Wait for deployment to be ready
    logger.info("Waiting for document processor deployment to be ready")
    if not k8s_utils.wait_for_deployment_ready("doc-processor"):
        logger.error("Timed out waiting for document processor deployment to be ready")
        # Clean up resources
        k8s_utils.delete_deployment("doc-processor")
        k8s_utils.delete_service("doc-processor")
        return None
    
    # Return service details
    return {
        "name": service.metadata.name,
        "cluster_ip": service.spec.cluster_ip,
        "http_url": f"http://{service.spec.cluster_ip}:5555",  # HTTP URL for worker communication
        "pub_address": f"tcp://{service.spec.cluster_ip}:5556"  # ZMQ PUB address for topic broadcasting
    }


def create_topic_aggregator_deployment(topic):
    """Create a topic aggregator deployment and service for a specific topic.
    
    Args:
        topic: The topic to aggregate
    
    Returns:
        dict: Service details including cluster IP
    """
    # Create unique name for this topic aggregator
    safe_topic_name = topic.lower().replace(' ', '-')
    deployment_name = f"topic-aggregator-{safe_topic_name}"
    service_name = f"topic-aggregator-{safe_topic_name}"
    
    # Define topic aggregator deployment configuration
    ports = [{"container_port": 5557, "name": "zmq-rep"}]
    command = ["python", "-m", "app.api.topic_aggregator", topic]
    env_vars = [
        {"name": "TOPIC", "value": topic},
        {"name": "SUB_ADDRESS", "value": "tcp://doc-processor:5556"}
    ]
    labels = {"topic": safe_topic_name}
    
    # Create deployment
    deployment = k8s_utils.create_deployment(
        name=deployment_name,
        component="topic-aggregator",
        command=command,
        ports=ports,
        env_vars=env_vars,
        labels=labels,
        resource_requests={"cpu": "100m", "memory": "128Mi"},
        resource_limits={"cpu": "500m", "memory": "256Mi"},
        readiness_probe_port=5557,
        liveness_probe_port=5557
    )
    
    if not deployment:
        logger.error(f"Failed to create topic aggregator deployment for '{topic}'")
        return None
    
    # Create service
    service_ports = [{"port": 5557, "name": "zmq-rep"}]
    service = k8s_utils.create_service(
        name=service_name,
        component="topic-aggregator",
        ports=service_ports,
        labels=labels
    )
    
    if not service:
        logger.error(f"Failed to create topic aggregator service for '{topic}'")
        # Clean up the deployment since service creation failed
        k8s_utils.delete_deployment(deployment_name)
        return None
    
    # Wait for deployment to be ready
    logger.info(f"Waiting for topic aggregator deployment for '{topic}' to be ready")
    if not k8s_utils.wait_for_deployment_ready(deployment_name):
        logger.error(f"Timed out waiting for topic aggregator deployment for '{topic}' to be ready")
        # Clean up resources
        k8s_utils.delete_deployment(deployment_name)
        k8s_utils.delete_service(service_name)
        return None
    
    # Return service details
    return {
        "topic": topic,
        "deployment_name": deployment_name,
        "service_name": service_name,
        "cluster_ip": service.spec.cluster_ip,
        "address": f"tcp://{service.spec.cluster_ip}:5557"
    }