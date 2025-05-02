"""Document Processor Service for Document Analytics.

This service processes Markdown documents and broadcasts content by topic.
"""

import zmq
import logging
import os
from typing import Dict, Any

from doc_analytics_lib import extract_topics, DocumentAnalyticsException

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'DEBUG')
numeric_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.DEBUG

logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("doc_processor")


class DocumentProcessor:
    """Document Processor parses Markdown files and broadcasts content by topic."""
    
    def __init__(self, rep_address: str = "tcp://*:5555", pub_address: str = "tcp://*:5556"):
        """Initialize the Document Processor service.
        
        Args:
            rep_address: ZMQ REP socket address to bind to
            pub_address: ZMQ PUB socket address to bind to for topic broadcasting
        """
        self.rep_address = rep_address
        self.pub_address = pub_address
        self.rep_socket = None
        self.pub_socket = None
    
    def process_document(self, filepath: str) -> Dict[str, Any]:
        """Process a document and broadcast its content by topic.
        
        Args:
            filepath: Path to the document file
            
        Returns:
            Processing status
        """
        logger.info(f"Processing document: {filepath}")
        
        try:
            # Log current working directory for debugging
            logger.info(f"Current working directory: {os.getcwd()}")
            
            # List contents of /documents directory to see if files are available
            if os.path.exists('/documents'):
                logger.info("Contents of /documents directory:")
                for f in os.listdir('/documents'):
                    logger.info(f"  - {f}")
            else:
                logger.info("/documents directory does not exist")
            
            # Try alternative paths for debugging
            alt_path = os.path.join('/documents', os.path.basename(filepath))
            logger.info(f"Checking alternative path: {alt_path}, exists: {os.path.exists(alt_path)}")
            
            # Verify file exists
            if not os.path.exists(filepath):
                logger.error(f"File not found: {filepath}")
                
                # If original path doesn't work, try the filename in /documents
                if os.path.exists(alt_path):
                    logger.info(f"Found file at alternative path: {alt_path}")
                    filepath = alt_path
                else:
                    return {"status": "error", "message": f"File not found: {filepath}"}
            
            # Read the file
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    content = file.read()
                    logger.info(f"Successfully read file: {filepath}, content length: {len(content)} characters")
                    # Log first 100 characters to verify content
                    logger.info(f"File content sample: {content[:100]}...")
            except Exception as e:
                logger.error(f"Error reading file {filepath}: {str(e)}")
                return {"status": "error", "message": f"Error reading file: {str(e)}"}
            
            # Extract topics from the content
            try:
                topics = extract_topics(content)
                logger.info(f"Successfully extracted {len(topics)} topics: {list(topics.keys())}")
                
                # Log detailed information about each extracted topic
                for topic_name, topic_text in topics.items():
                    logger.info(f"Topic '{topic_name}': {len(topic_text)} characters, sample: {topic_text[:50]}...")
            except DocumentAnalyticsException as e:
                logger.error(f"Error extracting topics: {str(e)}")
                return {"status": "error", "message": f"Error extracting topics: {str(e)}"}
            
            # Broadcast each topic
            for topic, topic_content in topics.items():
                logger.info(f"Broadcasting topic: {topic}")
                self.publish_topic(topic, topic_content)
            
            return {
                "status": "success",
                "topics_found": len(topics),
                "filepath": filepath,
                "topics": list(topics.keys())
            }
            
        except Exception as e:
            logger.error(f"Unexpected error processing document: {str(e)}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}
    
    def publish_topic(self, topic: str, content: str) -> None:
        """Publish content for a specific topic.
        
        Args:
            topic: Topic name
            content: Topic content
        """
        if not self.pub_socket:
            logger.error("PUB socket not initialized")
            return
        
        # Send multipart message: [topic, content]
        self.pub_socket.send_multipart([
            topic.encode('utf-8'),
            content.encode('utf-8')
        ])
        logger.debug(f"Published content for topic: {topic}")
    
    def start_server(self) -> None:
        """Start the Document Processor server.
        
        This method starts both REP and PUB sockets.
        """
        context = zmq.Context()
        
        # Socket to receive commands
        self.rep_socket = context.socket(zmq.REP)
        self.rep_socket.bind(self.rep_address)
        
        # Socket to publish topics
        self.pub_socket = context.socket(zmq.PUB)
        self.pub_socket.bind(self.pub_address)
        
        logger.info(f"Document Processor started:")
        logger.info(f"  REP socket: {self.rep_address}")
        logger.info(f"  PUB socket: {self.pub_address}")
        
        # Setup poller to handle multiple sockets
        poller = zmq.Poller()
        poller.register(self.rep_socket, zmq.POLLIN)
        
        try:
            while True:
                # Poll for events with timeout (1000ms)
                socks = dict(poller.poll(1000))
                
                # Handle REP socket messages
                if self.rep_socket in socks:
                    message = self.rep_socket.recv_json()
                    logger.info(f"Received request: {message}")
                    
                    action = message.get("action")
                    response = {"status": "error", "message": "Invalid action"}
                    
                    if action == "process":
                        filepath = message.get("filepath")
                        if filepath:
                            response = self.process_document(filepath)
                        else:
                            response = {"status": "error", "message": "Missing filepath parameter"}
                    
                    # Send reply back to client
                    self.rep_socket.send_json(response)
                
        except KeyboardInterrupt:
            logger.info("Shutting down Document Processor...")
        finally:
            if self.rep_socket:
                self.rep_socket.close()
            if self.pub_socket:
                self.pub_socket.close()
            context.term()


if __name__ == "__main__":
    processor = DocumentProcessor()
    processor.start_server()