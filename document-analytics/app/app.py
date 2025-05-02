"""Main Application Entry Point for Document Analytics.

This module provides Flask API endpoints to interact with the document analytics services.
It can use either Kubernetes API to deploy microservices or local processes for a hybrid approach.
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
from app import process_utils

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

# Deployment mode (kubernetes or process)
DEPLOYMENT_MODE = os.environ.get('DEPLOYMENT_MODE', 'kubernetes')

# Initialize Kubernetes client if in kubernetes mode
if DEPLOYMENT_MODE == 'kubernetes':
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
else:
    logger.info(f"Running in {DEPLOYMENT_MODE} mode, Kubernetes client not initialized")


# Deployment factory functions
def create_worker_queue():
    """Create a worker queue service based on deployment mode.
    
    Returns:
        dict: Service details
    """
    if DEPLOYMENT_MODE == 'kubernetes':
        return create_worker_queue_deployment()
    else:
        return process_utils.create_worker_queue_process()


def create_doc_processor(num_replicas=2):
    """Create document processor services based on deployment mode.
    
    Args:
        num_replicas: Number of document processor replicas (only used in k8s mode)
        
    Returns:
        dict: Service details
    """
    if DEPLOYMENT_MODE == 'kubernetes':
        return create_doc_processor_deployment(num_replicas)
    else:
        # For process mode, we create just one doc processor for simplicity
        # This could be extended to create multiple processors if desired
        return process_utils.create_doc_processor_process("1")


def create_topic_aggregator(topic):
    """Create a topic aggregator service based on deployment mode.
    
    Args:
        topic: The topic to aggregate
        
    Returns:
        dict: Service details
    """
    if DEPLOYMENT_MODE == 'kubernetes':
        return create_topic_aggregator_deployment(topic)
    else:
        return process_utils.create_topic_aggregator_process(topic)


def register_workers_with_queue(worker_queue_url):
    """Register document processor workers with the worker queue.
    
    Args:
        worker_queue_url: URL of the worker queue service
    """
    if DEPLOYMENT_MODE == 'kubernetes':
        # K8s implementation (existing code)
        logger.info("Registering document processors with worker queue (k8s mode)")
        
        # Get the list of document processor pods
        pods = k8s_utils.list_pods_by_labels("doc-processor")
        
        # Register each pod with the worker queue using HTTP requests
        import requests
        
        for pod in pods:
            pod_ip = pod.status.pod_ip
            if pod_ip:
                worker_id = f"processor-{pod.metadata.name}"
                worker_url = f"http://{pod_ip}:5555"  # Using HTTP URL instead of ZeroMQ address
                
                try:
                    # Register worker using HTTP POST request with the HTTP URL
                    logger.info(f"Registering worker {worker_id} at {worker_url}")
                    response = requests.post(
                        f"{worker_queue_url}/register_worker",
                        json={
                            "worker": {
                                "id": worker_id,
                                "url": worker_url  # Use 'url' instead of 'address' for HTTP communication
                            }
                        },
                        timeout=10
                    )
                    
                    # Check response
                    if response.status_code == 200:
                        logger.info(f"Registration response: {response.json()}")
                    else:
                        logger.error(f"Error registering worker {worker_id}: HTTP {response.status_code} - {response.text}")
                
                except Exception as e:
                    logger.error(f"Error registering worker {worker_id}: {e}")
    else:
        # Process implementation
        logger.info("Registering document processors with worker queue (process mode)")
        process_utils.register_workers_with_queue(worker_queue_url, [doc_processor_pods])


def cleanup_resources():
    """Clean up all created resources."""
    logger.info(f"Cleaning up resources in {DEPLOYMENT_MODE} mode")
    
    if DEPLOYMENT_MODE == 'kubernetes':
        # K8s cleanup
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
    else:
        # Process cleanup
        process_utils.cleanup_processes()


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
            logger.debug("Starting worker queue")
            worker_queue_service = create_worker_queue()
            if not worker_queue_service:
                logger.error("Failed to create worker queue")
                deployment_status["status"] = "error"
                deployment_status["message"] = "Failed to create worker queue"
                return
            logger.info(f"Started worker queue at {worker_queue_service['url']}")
            deployment_status["worker_queue_ready"] = True
            deployment_status["completed_steps"].append("worker_queue")
            deployment_status["pending_steps"].remove("worker_queue")
        
        # Create document processors if not already started
        if not doc_processor_pods:
            logger.debug(f"Starting document processor with {num_processors} replicas")
            doc_processor_pods = create_doc_processor(num_replicas=num_processors)
            if not doc_processor_pods:
                logger.error("Failed to create document processor")
                deployment_status["status"] = "error"
                deployment_status["message"] = "Failed to create document processor"
                return
            
            # In process mode, we get a single processor, not a list of processors
            if DEPLOYMENT_MODE != 'kubernetes':
                logger.info(f"Started document processor at {doc_processor_pods['http_url']}")
            else:
                logger.info(f"Started document processors at {doc_processor_pods['http_url']}")
            
            # Register document processors with worker queue
            register_workers_with_queue(worker_queue_service["url"])
            deployment_status["doc_processors_ready"] = True
            deployment_status["completed_steps"].append("doc_processors")
            deployment_status["pending_steps"].remove("doc_processors")
        
        # Create topic aggregators for each topic
        for topic in topics:
            if topic not in topic_aggregator_pods:
                logger.debug(f"Starting topic aggregator for topic: {topic}")
                aggregator = create_topic_aggregator(topic)
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
            import requests
            
            # Register documents with worker queue using HTTP
            logger.debug(f"Registering {len(documents)} documents with worker queue")
            try:
                register_response = requests.post(
                    f"{worker_queue_service['url']}/register_documents",
                    json={"documents": documents},
                    timeout=10
                )
                
                if register_response.status_code == 200:
                    logger.debug(f"Registration response: {register_response.json()}")
                else:
                    logger.error(f"Error registering documents: HTTP {register_response.status_code} - {register_response.text}")
                    deployment_status["status"] = "error"
                    deployment_status["message"] = f"Error registering documents with worker queue"
                    return
                
                # Trigger document distribution
                logger.debug("Triggering document distribution")
                distribute_response = requests.post(
                    f"{worker_queue_service['url']}/distribute",
                    json={},
                    timeout=30  # Longer timeout for distribution which could take time
                )
                
                if distribute_response.status_code == 200:
                    distribution_result = distribute_response.json()
                    logger.info(f"Document distribution response: {distribution_result}")
                else:
                    logger.error(f"Error distributing documents: HTTP {distribute_response.status_code} - {distribute_response.text}")
                    deployment_status["status"] = "error"
                    deployment_status["message"] = f"Error distributing documents to workers"
                    return
                
            except Exception as e:
                logger.error(f"Error communicating with worker queue: {str(e)}")
                deployment_status["status"] = "error"
                deployment_status["message"] = f"Error communicating with worker queue: {str(e)}"
                return
        
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


@app.route('/set_mode', methods=['POST'])
def set_mode():
    """Set the deployment mode (kubernetes or process)."""
    global DEPLOYMENT_MODE
    data = request.json
    mode = data.get('mode', 'kubernetes')
    
    if mode not in ['kubernetes', 'process']:
        return jsonify({"status": "error", "message": "Invalid mode. Use 'kubernetes' or 'process'"}), 400
    
    DEPLOYMENT_MODE = mode
    logger.info(f"Deployment mode set to: {DEPLOYMENT_MODE}")
    
    return jsonify({
        "status": "success",
        "message": f"Deployment mode set to {DEPLOYMENT_MODE}"
    })


@app.route('/start', methods=['POST'])
def start_services():
    """Start the document analytics services.
    
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
        deployment_mode = data.get('mode', DEPLOYMENT_MODE)
        
        # Set the deployment mode if specified
        global DEPLOYMENT_MODE
        if deployment_mode in ['kubernetes', 'process']:
            DEPLOYMENT_MODE = deployment_mode
            logger.info(f"Deployment mode set to: {DEPLOYMENT_MODE}")
        
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
            "message": f"Preparing to deploy services in {DEPLOYMENT_MODE} mode",
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
            "message": f"Deployment started in the background (mode: {DEPLOYMENT_MODE})",
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
        "deployment_status": deployment_status,
        "mode": DEPLOYMENT_MODE
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
    """Clean up all resources."""
    global worker_queue_service, doc_processor_pods, topic_aggregator_pods
    
    try:
        cleanup_resources()
        
        # Reset global state
        worker_queue_service = None
        doc_processor_pods = []
        topic_aggregator_pods = {}
        
        return jsonify({
            "status": "success",
            "message": f"All resources cleaned up successfully (mode: {DEPLOYMENT_MODE})"
        })
    
    except Exception as e:
        logger.error(f"Error cleaning up resources: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/logs', methods=['GET'])
def get_pod_logs():
    """Get logs from all document analytics pods."""
    try:
        logs = {}
        
        if DEPLOYMENT_MODE == 'kubernetes':
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
        else:
            logs["message"] = "Log retrieval not implemented in process mode"
        
        return jsonify({
            "status": "success",
            "logs": logs
        })
    
    except Exception as e:
        logger.error(f"Error getting pod logs: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 8080))
    
    # Log deployment mode
    logger.info(f"Starting Document Analytics API in {DEPLOYMENT_MODE} mode on port {port}")
    
    # Run the Flask application
    app.run(host='0.0.0.0', port=port)