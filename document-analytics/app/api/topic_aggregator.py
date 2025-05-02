"""Topic Aggregator Service for Document Analytics.

This service subscribes to a specific topic and aggregates metrics for that topic.
"""

import zmq
import logging
import os
from typing import Dict, Any

from doc_analytics_lib import analyze_content

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'DEBUG')
numeric_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_level, int):
    numeric_level = logging.DEBUG

logging.basicConfig(
    level=numeric_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("topic_aggregator")


class TopicAggregator:
    """Topic Aggregator subscribes to a topic and aggregates metrics."""
    
    def __init__(self, topic: str, sub_address: str = "tcp://doc-processor:5556", rep_address: str = "tcp://*:5557"):
        """Initialize the Topic Aggregator service.
        
        Args:
            topic: The topic to subscribe to
            sub_address: ZMQ SUB socket address to connect to
            rep_address: ZMQ REP socket address to bind to for API access
        """
        self.topic = topic
        self.sub_address = sub_address
        self.rep_address = rep_address
        
        # Metric counters
        self.line_count = 0
        self.word_count = 0
        self.char_count = 0
        self.doc_count = 0
    
    def process_content(self, content: str) -> None:
        """Process content and update metrics.
        
        Args:
            content: Content to analyze
        """
        logger.info(f"Processing content for topic: {self.topic}")
        logger.info(f"Content sample for topic '{self.topic}': {content[:100]}...")
        
        # Analyze the content
        metrics = analyze_content(content)
        logger.info(f"Analysis results for topic '{self.topic}': {metrics}")
        
        # Update counters
        self.line_count += metrics["line_count"]
        self.word_count += metrics["word_count"]
        self.char_count += metrics["char_count"]
        self.doc_count += 1
        
        logger.info(f"Updated metrics for topic {self.topic}: lines={self.line_count}, words={self.word_count}, chars={self.char_count}, docs={self.doc_count}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics.
        
        Returns:
            Dictionary with current metrics
        """
        return {
            "topic": self.topic,
            "line_count": self.line_count,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "doc_count": self.doc_count
        }
    
    def start_server(self) -> None:
        """Start the Topic Aggregator server.
        
        This method starts both SUB and REP sockets.
        """
        context = zmq.Context()
        
        # Socket to subscribe for topic content
        sub_socket = context.socket(zmq.SUB)
        sub_socket.connect(self.sub_address)
        
        # Subscribe to specific topic
        topic_filter = self.topic.encode('utf-8')
        sub_socket.setsockopt(zmq.SUBSCRIBE, topic_filter)
        
        # Socket to receive API commands
        rep_socket = context.socket(zmq.REP)
        rep_socket.bind(self.rep_address)
        
        logger.info(f"Topic Aggregator started for topic: {self.topic}")
        logger.info(f"  SUB socket: {self.sub_address}")
        logger.info(f"  REP socket: {self.rep_address}")
        
        # Setup poller to handle multiple sockets
        poller = zmq.Poller()
        poller.register(sub_socket, zmq.POLLIN)
        poller.register(rep_socket, zmq.POLLIN)
        
        try:
            while True:
                # Poll for events with timeout (1000ms)
                socks = dict(poller.poll(1000))
                
                # Handle SUB socket messages (topic content)
                if sub_socket in socks:
                    topic_msg, content_msg = sub_socket.recv_multipart()
                    topic_str = topic_msg.decode('utf-8')
                    content_str = content_msg.decode('utf-8')
                    
                    logger.debug(f"Received content for topic: {topic_str}")
                    if topic_str == self.topic:
                        self.process_content(content_str)
                
                # Handle REP socket messages (API requests)
                if rep_socket in socks:
                    message = rep_socket.recv_json()
                    logger.info(f"Received API request: {message}")
                    
                    action = message.get("action")
                    response = {"status": "error", "message": "Invalid action"}
                    
                    if action == "get_metrics":
                        response = {
                            "status": "success",
                            "metrics": self.get_metrics()
                        }
                    
                    # Send reply back to client
                    rep_socket.send_json(response)
                
        except KeyboardInterrupt:
            logger.info(f"Shutting down Topic Aggregator for topic: {self.topic}")
        finally:
            sub_socket.close()
            rep_socket.close()
            context.term()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python topic_aggregator.py <topic_name>")
        sys.exit(1)
    
    topic = sys.argv[1]
    aggregator = TopicAggregator(topic)
    aggregator.start_server()