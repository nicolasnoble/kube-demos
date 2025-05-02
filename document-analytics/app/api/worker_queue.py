"""Worker Queue Service for Document Analytics.

This service is responsible for distributing documents to document processors.
"""

import zmq
import logging
import time
import random
import os
from typing import List, Dict, Any, Optional

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


class WorkerQueue:
    """Worker Queue distributes documents to Document Processors."""
    
    def __init__(self, rep_address: str = "tcp://*:5555"):
        """Initialize the Worker Queue service.
        
        Args:
            rep_address: ZMQ REP socket address to bind to
        """
        self.rep_address = rep_address
        self.documents = []  # List of document paths to process
        self.workers = []    # List of available document processors
    
    def register_documents(self, documents: List[str]) -> None:
        """Register documents to be processed.
        
        Args:
            documents: List of document file paths
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
    
    def register_worker(self, worker: Dict[str, str]) -> None:
        """Register a document processor worker.
        
        Args:
            worker: Dictionary with worker details (id, address)
        """
        logger.info(f"Registering worker: {worker['id']} at {worker['address']}")
        self.workers.append(worker)
    
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
        context = zmq.Context()
        
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
            
            # Send document to worker using REQ socket
            socket = context.socket(zmq.REQ)
            socket.connect(worker["address"])
            
            # Send process request
            try:
                socket.send_json({
                    "action": "process",
                    "filepath": document
                })
                
                # Wait for response
                response = socket.recv_json()
                
                if response.get("status") == "success":
                    processed_count += 1
                    logger.info(f"Document {document} processed successfully")
                    logger.info(f"Worker reported topics: {response.get('topics', [])}")
                else:
                    error_count += 1
                    logger.error(f"Failed to process document {document}: {response.get('message', 'Unknown error')}")
            
            except Exception as e:
                error_count += 1
                logger.error(f"Error communicating with worker for document {document}: {str(e)}")
            
            finally:
                socket.close()
        
        logger.info(f"Distribution completed. Successfully processed: {processed_count}, Errors: {error_count}")
        
        return {
            "status": "completed",
            "processed": processed_count,
            "errors": error_count
        }
    
    def start_server(self) -> None:
        """Start the Worker Queue server.
        
        This method starts a REP socket to receive commands.
        """
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(self.rep_address)
        
        logger.info(f"Worker Queue server started at {self.rep_address}")
        
        try:
            while True:
                # Wait for next request from client
                message = socket.recv_json()
                logger.info(f"Received request: {message}")
                
                action = message.get("action")
                response = {"status": "error", "message": "Invalid action"}
                
                if action == "register_documents":
                    self.register_documents(message.get("documents", []))
                    response = {"status": "success"}
                    
                elif action == "register_worker":
                    self.register_worker(message.get("worker", {}))
                    response = {"status": "success"}
                    
                elif action == "distribute":
                    response = self.distribute_work()
                
                # Send reply back to client
                socket.send_json(response)
                
        except KeyboardInterrupt:
            logger.info("Shutting down Worker Queue server...")
        finally:
            socket.close()
            context.term()


if __name__ == "__main__":
    worker_queue = WorkerQueue()
    worker_queue.start_server()