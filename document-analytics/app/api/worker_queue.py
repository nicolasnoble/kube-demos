"""Worker Queue Service for Document Analytics.

This service is responsible for distributing documents to document processors.
"""

import logging
import time
import random
import os
import requests
from typing import List, Dict, Any, Optional
from flask import Flask, request, jsonify

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'DEBUG')
numeric_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.DEBUG

logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker_queue")

# Initialize Flask application
app = Flask(__name__)

# Global WorkerQueue instance
worker_queue = None


class WorkerQueue:
    """Worker Queue distributes documents to Document Processors."""
    
    def __init__(self):
        """Initialize the Worker Queue service."""
        self.documents = []  # List of document paths to process
        self.workers = []    # List of available document processors
    
    def register_documents(self, documents: List[str]) -> Dict[str, Any]:
        """Register documents to be processed.
        
        Args:
            documents: List of document file paths
            
        Returns:
            Status response
        """
        logger.info(f"Registering {len(documents)} documents")
        
        # Log each document path for debugging
        for i, doc in enumerate(documents):
            logger.info(f"Document {i+1}: {doc}")
            
            # Check if document uses /documents path format
            if doc.startswith('/documents/'):
                logger.info(f"Document {i+1} already uses ConfigMap path format")
            elif os.path.basename(doc) != doc:
                # For absolute paths, check if file might be available in ConfigMap
                alt_path = f"/documents/{os.path.basename(doc)}"
                logger.info(f"Document {i+1} might be available at ConfigMap path: {alt_path}")
        
        self.documents = documents
        return {"status": "success"}
    
    def register_worker(self, worker: Dict[str, str]) -> Dict[str, Any]:
        """Register a document processor worker.
        
        Args:
            worker: Dictionary with worker details (id, url or address)
            
        Returns:
            Status response
        """
        worker_id = worker['id']
        # Handle both 'url' and 'address' keys for backward compatibility
        if 'url' in worker:
            worker_url = worker['url']
        elif 'address' in worker:
            # Convert ZMQ address to HTTP URL if needed
            zmq_address = worker['address']
            if zmq_address.startswith('tcp://'):
                parts = zmq_address.replace('tcp://', '').split(':')
                if len(parts) == 2:
                    host, port = parts
                    worker_url = f"http://{host}:5555"  # Assuming HTTP port is 5555
                else:
                    worker_url = f"http://{zmq_address.replace('tcp://', '')}"
            else:
                worker_url = zmq_address
        else:
            logger.error(f"Worker data missing url or address: {worker}")
            return {"status": "error", "message": "Worker data missing url or address"}
            
        logger.info(f"Registering worker: {worker_id} at {worker_url}")
        self.workers.append({
            "id": worker_id,
            "url": worker_url
        })
        return {"status": "success"}
    
    def pick_idle_worker(self) -> Optional[Dict[str, str]]:
        """Pick an idle worker from the pool.
        
        In a real-world scenario, we would track worker status.
        For simplicity, we'll randomly select a worker.
        
        Returns:
            Worker details or None if no workers available
        """
        if not self.workers:
            return None
        return random.choice(self.workers)
    
    def distribute_work(self) -> Dict[str, Any]:
        """Distribute documents to document processors.
        
        Returns:
            Status of the distribution process
        """
        if not self.documents:
            logger.info("No documents to process")
            return {"status": "completed", "processed": 0}
        
        if not self.workers:
            logger.error("No workers available")
            return {"status": "error", "message": "No workers available"}
        
        logger.info(f"Starting document distribution with {len(self.documents)} documents and {len(self.workers)} workers")
        
        processed_count = 0
        error_count = 0
        
        for doc_index, document in enumerate(self.documents):
            worker = self.pick_idle_worker()
            if not worker:
                logger.error("No workers available")
                break
            
            logger.info(f"Distributing document [{doc_index+1}/{len(self.documents)}]: {document} to worker {worker['id']}")
            
            # Check if the document path might need adjustment for Kubernetes pods
            if not document.startswith('/documents/') and os.path.basename(document) != document:
                alt_path = f"/documents/{os.path.basename(document)}"
                logger.info(f"Original path: {document}")
                logger.info(f"Possible ConfigMap path: {alt_path}")
            
            # Send document to worker using HTTP request
            try:
                logger.info(f"Sending HTTP request to worker at {worker['url']}/process")
                response = requests.post(
                    f"{worker['url']}/process",
                    json={"filepath": document},
                    timeout=30  # Longer timeout for document processing
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "success":
                        processed_count += 1
                        logger.info(f"Document {document} processed successfully")
                        logger.info(f"Worker reported topics: {result.get('topics', [])}")
                    else:
                        error_count += 1
                        logger.error(f"Failed to process document {document}: {result.get('message', 'Unknown error')}")
                else:
                    error_count += 1
                    logger.error(f"Failed to process document {document}: HTTP {response.status_code} - {response.text}")
            
            except Exception as e:
                error_count += 1
                logger.error(f"Error communicating with worker for document {document}: {str(e)}")
        
        logger.info(f"Distribution completed. Successfully processed: {processed_count}, Errors: {error_count}")
        
        return {
            "status": "completed",
            "processed": processed_count,
            "errors": error_count
        }


# Flask routes for the Worker Queue API
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})


@app.route('/register_documents', methods=['POST'])
def register_documents_api():
    """API endpoint to register documents."""
    global worker_queue
    data = request.json
    documents = data.get('documents', [])
    result = worker_queue.register_documents(documents)
    return jsonify(result)


@app.route('/register_worker', methods=['POST'])
def register_worker_api():
    """API endpoint to register a worker."""
    global worker_queue
    data = request.json
    worker = data.get('worker', {})
    result = worker_queue.register_worker(worker)
    return jsonify(result)


@app.route('/distribute', methods=['POST'])
def distribute_api():
    """API endpoint to distribute documents to workers."""
    global worker_queue
    result = worker_queue.distribute_work()
    return jsonify(result)


if __name__ == "__main__":
    # Create WorkerQueue instance
    worker_queue = WorkerQueue()
    
    # Run Flask app
    port = int(os.environ.get("PORT", 5555))
    logger.info(f"Starting Worker Queue Flask server on port {port}")
    app.run(host='0.0.0.0', port=port)