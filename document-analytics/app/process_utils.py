"""Process Utilities for Document Analytics in Hybrid Mode.

This module provides utilities for spawning and managing local processes
for the document analytics application when running in hybrid mode.
"""

import os
import sys
import time
import logging
import subprocess
import socket
import threading
import json
import atexit
import signal
from typing import Dict, List, Any, Optional
import requests

# Configure logger
logger = logging.getLogger("process_utils")

# Global list to track spawned processes
active_processes = []


def get_available_port():
    """Find an available port to bind a process.
    
    Returns:
        int: Available port number
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def spawn_process(
    name: str,
    component: str,
    command: List[str],
    env_vars: Optional[Dict[str, str]] = None,
    service_ports: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Spawn a local process for a service component.
    
    Args:
        name: Name of the process
        component: Component type (worker-queue, doc-processor, etc.)
        command: Command to run the process
        env_vars: Environment variables for the process
        service_ports: List of ports the service will listen on
        
    Returns:
        Dict with process details including PID and ports
    """
    global active_processes
    
    # Set up environment variables
    proc_env = os.environ.copy()
    if env_vars:
        proc_env.update(env_vars)
    
    # Set up ports if needed
    if service_ports is None:
        service_ports = [get_available_port()]
    
    # Add port to environment variables
    for i, port in enumerate(service_ports):
        port_var = f"PORT{i+1}" if i > 0 else "PORT"
        proc_env[port_var] = str(port)
    
    logger.info(f"Starting {component} process: {name} with command: {' '.join(command)}")
    logger.info(f"Using ports: {service_ports}")
    
    # Start the process
    try:
        process = subprocess.Popen(
            command,
            env=proc_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Create a thread to read and log output
        def log_output(process, component, name):
            for line in iter(process.stdout.readline, ''):
                logger.info(f"[{component}][{name}]: {line.strip()}")
        
        threading.Thread(
            target=log_output,
            args=(process, component, name),
            daemon=True
        ).start()
        
        # Wait a moment for process to start
        time.sleep(1)
        
        # Check if process is still running
        if process.poll() is not None:
            logger.error(f"Process {name} failed to start: exit code {process.poll()}")
            return None
        
        # Create process info dictionary
        process_info = {
            "name": name,
            "component": component,
            "pid": process.pid,
            "process": process,
            "ports": service_ports,
            "started_at": time.time()
        }
        
        # Add to active processes list
        active_processes.append(process_info)
        
        # Return process info (without process object which is not JSON serializable)
        return {key: value for key, value in process_info.items() if key != "process"}
        
    except Exception as e:
        logger.error(f"Failed to start {component} process: {e}")
        return None


def create_worker_queue_process():
    """Create a worker queue process.
    
    Returns:
        Dict: Service details including URL
    """
    port = get_available_port()
    command = [sys.executable, "-m", "app.api.worker_queue"]
    env_vars = {"PORT": str(port), "LOG_LEVEL": "INFO"}
    
    worker_queue = spawn_process(
        name="worker-queue-1",
        component="worker-queue",
        command=command,
        env_vars=env_vars,
        service_ports=[port]
    )
    
    if not worker_queue:
        logger.error("Failed to create worker queue process")
        return None
    
    # Wait for the service to be ready
    logger.info("Waiting for worker queue process to be ready")
    if not wait_for_http_service(f"http://localhost:{port}/health"):
        logger.error("Timed out waiting for worker queue process to be ready")
        return None
    
    # Add the URL to the worker queue info
    worker_queue["url"] = f"http://localhost:{port}"
    logger.info(f"Worker queue ready at {worker_queue['url']}")
    
    return worker_queue


def create_doc_processor_process(worker_id, documents_path=None):
    """Create a document processor process.
    
    Args:
        worker_id: Unique identifier for the worker
        documents_path: Path to documents directory
        
    Returns:
        Dict: Service details including URL
    """
    http_port = get_available_port()
    zmq_port = get_available_port()
    
    command = [sys.executable, "-m", "app.api.doc_processor"]
    env_vars = {
        "PORT": str(http_port),
        "ZMQ_PUB_PORT": str(zmq_port),
        "WORKER_ID": worker_id,
        "LOG_LEVEL": "INFO"
    }
    
    if documents_path:
        env_vars["DOCUMENTS_PATH"] = documents_path
    
    processor = spawn_process(
        name=f"doc-processor-{worker_id}",
        component="doc-processor",
        command=command,
        env_vars=env_vars,
        service_ports=[http_port, zmq_port]
    )
    
    if not processor:
        logger.error(f"Failed to create document processor process {worker_id}")
        return None
    
    # Wait for the service to be ready
    logger.info(f"Waiting for document processor {worker_id} to be ready")
    if not wait_for_http_service(f"http://localhost:{http_port}/health"):
        logger.error(f"Timed out waiting for document processor {worker_id} to be ready")
        return None
    
    # Add the URLs to the processor info
    processor["http_url"] = f"http://localhost:{http_port}"
    processor["pub_address"] = f"tcp://localhost:{zmq_port}"
    logger.info(f"Document processor {worker_id} ready at {processor['http_url']}")
    
    return processor


def create_topic_aggregator_process(topic):
    """Create a topic aggregator process.
    
    Args:
        topic: The topic to aggregate
        
    Returns:
        Dict: Service details including address
    """
    # Create a safe name for the topic
    safe_topic_name = topic.lower().replace(' ', '-')
    
    zmq_port = get_available_port()
    command = [sys.executable, "-m", "app.api.topic_aggregator", topic]
    
    # Get the document processor's ZMQ address from active processes
    pub_address = None
    for proc in active_processes:
        if proc["component"] == "doc-processor":
            pub_address = proc.get("pub_address")
            break
    
    if not pub_address:
        logger.error("No document processor found for topic aggregator to subscribe to")
        return None
    
    env_vars = {
        "TOPIC": topic,
        "ZMQ_REP_PORT": str(zmq_port),
        "SUB_ADDRESS": pub_address,
        "LOG_LEVEL": "INFO"
    }
    
    aggregator = spawn_process(
        name=f"topic-aggregator-{safe_topic_name}",
        component="topic-aggregator",
        command=command,
        env_vars=env_vars,
        service_ports=[zmq_port]
    )
    
    if not aggregator:
        logger.error(f"Failed to create topic aggregator process for '{topic}'")
        return None
    
    # Wait a bit for the ZMQ socket to be ready
    time.sleep(2)
    
    # Add the address to the aggregator info
    aggregator["address"] = f"tcp://localhost:{zmq_port}"
    logger.info(f"Topic aggregator for '{topic}' ready at {aggregator['address']}")
    
    return aggregator


def wait_for_http_service(url, timeout=30, check_interval=1):
    """Wait for an HTTP service to be ready.
    
    Args:
        url: URL to check
        timeout: Maximum time to wait in seconds
        check_interval: How often to check in seconds
        
    Returns:
        bool: True if service is ready, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        
        time.sleep(check_interval)
    
    return False


def register_workers_with_queue(worker_queue_url, doc_processors):
    """Register document processor workers with the worker queue.
    
    Args:
        worker_queue_url: URL of the worker queue service
        doc_processors: List of document processor service details
    """
    logger.info("Registering document processors with worker queue")
    
    for processor in doc_processors:
        worker_id = processor.get("name", f"processor-{processor['pid']}")
        worker_url = processor["http_url"]
        
        try:
            # Register worker using HTTP POST request
            logger.info(f"Registering worker {worker_id} at {worker_url}")
            response = requests.post(
                f"{worker_queue_url}/register_worker",
                json={
                    "worker": {
                        "id": worker_id,
                        "url": worker_url
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


def cleanup_processes():
    """Clean up all spawned processes."""
    logger.info("Cleaning up all processes")
    
    for proc_info in active_processes:
        process = proc_info.get("process")
        if process and process.poll() is None:
            logger.info(f"Terminating process: {proc_info['name']} (PID: {proc_info['pid']})")
            try:
                # First try sending SIGTERM
                process.terminate()
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # If termination didn't work, try SIGKILL
                logger.info(f"Process {proc_info['name']} did not terminate, killing it")
                process.kill()
    
    # Clear the active processes list
    active_processes.clear()


# Register cleanup handler for program exit
atexit.register(cleanup_processes)

# Also handle signals
for sig in [signal.SIGINT, signal.SIGTERM]:
    signal.signal(sig, lambda sig, frame: cleanup_processes())