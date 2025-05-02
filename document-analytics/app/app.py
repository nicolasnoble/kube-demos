"""Main Application Entry Point for Document Analytics.

This module provides Flask API endpoints to interact with the document analytics services.
It uses the Kubernetes API to deploy and manage the document analytics microservices.
"""

import os
import logging
import socket
import json
import threading
import time
import zmq
import uuid
import traceback
from flask import Flask, request, jsonify
from werkzeug.serving import run_simple
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from app import k8s_utils

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
numeric_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.INFO

logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("app")

app = Flask(__name__)

# Global variables to track deployed resources
worker_queue_service = None
doc_processor_pods = []
topic_aggregator_pods = {}
deployment_status = {
    "status": "idle",
    "message": "No deployment in progress",
    "completed_steps": [],
    "pending_steps": [],
    "worker_queue_ready": False,
    "doc_processors_ready": False,
    "topic_aggregators": {}
}

# Initialize Kubernetes client
try:
    # Try to load in-cluster config first (when running as a pod)
    config.load_incluster_config()
    logger.info("Loaded in-cluster Kubernetes configuration")
except config.ConfigException:
    try:
        # Fall back to kubeconfig file
        config.load_kube_config()
        logger.info("Loaded Kubernetes configuration from kubeconfig file")
    except config.ConfigException:
        logger.warning("Could not load Kubernetes configuration. Using a mock client for testing.")


def create_worker_queue_deployment():
    """Create the worker queue deployment and service in Kubernetes.
    
    Returns:
        dict: Service details including cluster IP
    """
    # Define worker queue deployment configuration
    ports = [{"container_port": 5555, "name": "zmq"}]
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
    service_ports = [{"port": 5555, "name": "zmq"}]
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
        "address": f"tcp://{service.spec.cluster_ip}:5555"
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
        {"container_port": 5555, "name": "zmq-rep"},
        {"container_port": 5556, "name": "zmq-pub"}
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
        readiness_probe_port=5555,
        liveness_probe_port=5555
    )
    
    if not deployment:
        logger.error("Failed to create document processor deployment")
        return None
    
    # Create service
    service_ports = [
        {"port": 5555, "name": "zmq-rep"},
        {"port": 5556, "name": "zmq-pub"}
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
        "rep_address": f"tcp://{service.spec.cluster_ip}:5555",
        "pub_address": f"tcp://{service.spec.cluster_ip}:5556"
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


def register_workers_with_queue(worker_queue_address):
    """Register document processor workers with the worker queue.
    
    Args:
        worker_queue_address: Address of the worker queue service
    """
    logger.info("Registering document processors with worker queue")
    
    # Get the list of document processor pods
    pods = k8s_utils.list_pods_by_labels("doc-processor")
    
    context = zmq.Context()
    
    # Register each pod with the worker queue
    for pod in pods:
        pod_ip = pod.status.pod_ip
        if pod_ip:
            worker_id = f"processor-{pod.metadata.name}"
            worker_address = f"tcp://{pod_ip}:5555"
            
            try:
                # Connect to worker queue
                socket = context.socket(zmq.REQ)
                socket.connect(worker_queue_address)
                
                # Register worker
                logger.info(f"Registering worker {worker_id} at {worker_address}")
                socket.send_json({
                    "action": "register_worker",
                    "worker": {
                        "id": worker_id,
                        "address": worker_address
                    }
                })
                
                # Wait for response
                response = socket.recv_json()
                logger.info(f"Registration response: {response}")
                
                socket.close()
            
            except Exception as e:
                logger.error(f"Error registering worker {worker_id}: {e}")


def cleanup_resources():
    """Clean up all created Kubernetes resources."""
    logger.info("Cleaning up Kubernetes resources")
    
    # Delete worker queue
    k8s_utils.delete_deployment("worker-queue")
    k8s_utils.delete_service("worker-queue")
    
    # Delete document processors
    k8s_utils.delete_deployment("doc-processor")
    k8s_utils.delete_service("doc-processor")
    
    # Delete topic aggregators
    for topic, aggregator in topic_aggregator_pods.items():
        deployment_name = aggregator["deployment_name"]
        service_name = aggregator["service_name"]
        
        logger.info(f"Deleting topic aggregator deployment for '{topic}'")
        k8s_utils.delete_deployment(deployment_name)
        
        logger.info(f"Deleting topic aggregator service for '{topic}'")
        k8s_utils.delete_service(service_name)


def deploy_services_async(documents, topics, num_processors):
    """Deploy all services in the background.
    
    Args:
        documents: List of document file paths
        topics: List of topics to process
        num_processors: Number of document processor replicas
    """
    global deployment_status, worker_queue_service, doc_processor_pods, topic_aggregator_pods
    
    deployment_status = {
        "status": "in_progress",
        "message": "Deployment started",
        "completed_steps": [],
        "pending_steps": ["worker_queue", "doc_processors"] + topics,
        "worker_queue_ready": False,
        "doc_processors_ready": False,
        "topic_aggregators": {topic: False for topic in topics}
    }
    
    try:
        # Create worker queue if not already started
        if worker_queue_service is None:
            logger.debug("Starting worker queue deployment")
            worker_queue_service = create_worker_queue_deployment()
            if not worker_queue_service:
                logger.error("Failed to create worker queue deployment")
                deployment_status["status"] = "error"
                deployment_status["message"] = "Failed to create worker queue deployment"
                return
            logger.info(f"Started worker queue at {worker_queue_service['address']}")
            deployment_status["worker_queue_ready"] = True
            deployment_status["completed_steps"].append("worker_queue")
            deployment_status["pending_steps"].remove("worker_queue")
        
        # Create document processors if not already started
        if not doc_processor_pods:
            logger.debug(f"Starting document processor deployment with {num_processors} replicas")
            doc_processor_pods = create_doc_processor_deployment(num_replicas=num_processors)
            if not doc_processor_pods:
                logger.error("Failed to create document processor deployment")
                deployment_status["status"] = "error"
                deployment_status["message"] = "Failed to create document processor deployment"
                return
            logger.info(f"Started document processors at {doc_processor_pods['rep_address']}")
            
            # Register document processors with worker queue
            register_workers_with_queue(worker_queue_service["address"])
            deployment_status["doc_processors_ready"] = True
            deployment_status["completed_steps"].append("doc_processors")
            deployment_status["pending_steps"].remove("doc_processors")
        
        # Create topic aggregators for each topic
        for topic in topics:
            if topic not in topic_aggregator_pods:
                logger.debug(f"Starting topic aggregator for topic: {topic}")
                aggregator = create_topic_aggregator_deployment(topic)
                if aggregator:
                    topic_aggregator_pods[topic] = aggregator
                    logger.info(f"Started topic aggregator for '{topic}' at {aggregator['address']}")
                    deployment_status["topic_aggregators"][topic] = True
                    deployment_status["completed_steps"].append(topic)
                    deployment_status["pending_steps"].remove(topic)
                else:
                    logger.error(f"Failed to create topic aggregator for '{topic}'")
                    deployment_status["status"] = "error"
                    deployment_status["message"] = f"Failed to create topic aggregator for '{topic}'"
                    return
        
        # Register documents with worker queue and trigger distribution
        if documents:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.connect(worker_queue_service["address"])
            
            # Register documents
            logger.debug(f"Registering {len(documents)} documents with worker queue")
            socket.send_json({
                "action": "register_documents",
                "documents": documents
            })
            response = socket.recv_json()
            logger.debug(f"Registration response: {response}")
            
            # Trigger document distribution
            logger.debug("Triggering document distribution")
            socket.send_json({
                "action": "distribute"
            })
            distribution_response = socket.recv_json()
            socket.close()
            
            logger.info(f"Document distribution response: {distribution_response}")
        
        deployment_status["status"] = "completed"
        deployment_status["message"] = "All services deployed successfully"
        
    except Exception as e:
        logger.error(f"Error deploying services: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        deployment_status["status"] = "error"
        deployment_status["message"] = str(e)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route('/start', methods=['POST'])
def start_services():
    """Start the document analytics services using Kubernetes.
    
    This method starts the deployment process in the background and returns immediately.
    """
    global deployment_status
    
    try:
        # Get configuration from request
        data = request.json
        logger.debug(f"Received start request with data: {data}")
        documents = data.get('documents', [])
        topics = data.get('topics', [])
        num_processors = data.get('num_processors', 2)
        
        # Start the deployment process in a separate thread
        if deployment_status["status"] == "in_progress":
            return jsonify({
                "status": "in_progress", 
                "message": "Deployment already in progress",
                "deployment_status": deployment_status
            })
        
        # Reset status for new deployment
        deployment_status = {
            "status": "starting",
            "message": "Preparing to deploy services",
            "completed_steps": [],
            "pending_steps": ["worker_queue", "doc_processors"] + topics,
            "worker_queue_ready": False,
            "doc_processors_ready": False,
            "topic_aggregators": {topic: False for topic in topics}
        }
        
        # Start deployment in background thread
        threading.Thread(
            target=deploy_services_async,
            args=(documents, topics, num_processors),
            daemon=True
        ).start()
        
        return jsonify({
            "status": "accepted",
            "message": "Deployment started in the background",
            "deployment_status": deployment_status
        })
    
    except Exception as e:
        logger.error(f"Error starting services: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/status', methods=['GET'])
def get_deployment_status():
    """Get the status of the deployment process."""
    global deployment_status
    
    return jsonify({
        "status": "success",
        "deployment_status": deployment_status
    })


@app.route('/results', methods=['GET'])
def get_results():
    """Get aggregated results from all topic aggregators."""
    results = {}
    
    try:
        context = zmq.Context()
        
        for topic, aggregator in topic_aggregator_pods.items():
            socket = context.socket(zmq.REQ)
            socket.connect(aggregator["address"])
            socket.send_json({"action": "get_metrics"})
            response = socket.recv_json()
            socket.close()
            
            if response.get("status") == "success":
                results[topic] = response.get("metrics")
        
        return jsonify({
            "status": "success",
            "results": results
        })
    
    except Exception as e:
        logger.error(f"Error getting results: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Clean up all Kubernetes resources."""
    global worker_queue_service, doc_processor_pods, topic_aggregator_pods
    
    try:
        cleanup_resources()
        
        # Reset global state
        worker_queue_service = None
        doc_processor_pods = []
        topic_aggregator_pods = {}
        
        return jsonify({
            "status": "success",
            "message": "All resources cleaned up successfully"
        })
    
    except Exception as e:
        logger.error(f"Error cleaning up resources: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/logs', methods=['GET'])
def get_pod_logs():
    """Get logs from all document analytics pods."""
    try:
        logs = {}
        
        # Get worker queue pod logs
        worker_pods = k8s_utils.list_pods_by_labels("worker-queue")
        for pod in worker_pods:
            pod_name = pod.metadata.name
            pod_logs = k8s_utils.get_pod_logs(pod_name)
            logs[f"worker-queue-{pod_name}"] = pod_logs
        
        # Get document processor pod logs
        processor_pods = k8s_utils.list_pods_by_labels("doc-processor")
        for pod in processor_pods:
            pod_name = pod.metadata.name
            pod_logs = k8s_utils.get_pod_logs(pod_name)
            logs[f"doc-processor-{pod_name}"] = pod_logs
        
        # Get topic aggregator pod logs
        topic_pods = k8s_utils.list_pods_by_labels("topic-aggregator")
        for pod in topic_pods:
            pod_name = pod.metadata.name
            topic_label = pod.metadata.labels.get("topic", "unknown")
            pod_logs = k8s_utils.get_pod_logs(pod_name)
            logs[f"topic-aggregator-{topic_label}-{pod_name}"] = pod_logs
        
        return jsonify({
            "status": "success",
            "logs": logs
        })
    
    except Exception as e:
        logger.error(f"Error getting pod logs: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500