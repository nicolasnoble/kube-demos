"""Tests for the document processor service."""

import pytest
from unittest.mock import MagicMock, patch
import os
import sys
import tempfile

# Add the parent directory to sys.path to allow imports from app.api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.api.doc_processor import DocumentProcessor


@pytest.fixture
def doc_processor():
    """Create a DocumentProcessor instance for testing."""
    return DocumentProcessor()


def test_document_processor_initialization(doc_processor):
    """Test that DocumentProcessor initializes correctly."""
    assert doc_processor.pub_address == "tcp://*:5556"


@patch('app.api.doc_processor.zmq.Context')
def test_start_server(mock_context, doc_processor):
    """Test starting the document processor server."""
    # Setup mock sockets
    mock_rep_socket = MagicMock()
    mock_pub_socket = MagicMock()
    mock_context.return_value.socket.side_effect = [mock_rep_socket, mock_pub_socket]
    
    # Mock the poll method to return once and then raise an exception to exit the loop
    mock_poller = MagicMock()
    mock_poller.poll.side_effect = [[(mock_rep_socket, 1)], KeyboardInterrupt]
    mock_rep_socket.recv_json.return_value = {"action": "process", "filepath": "/path/to/doc.md"}
    
    # Patch ZMQ Poller class
    with patch('app.api.doc_processor.zmq.Poller', return_value=mock_poller):
        # Patch the process_document method
        with patch.object(doc_processor, 'process_document', return_value={"status": "success"}):
            # Instead of expecting KeyboardInterrupt, we'll check if the code processes the message
            try:
                doc_processor.start_server()
            except KeyboardInterrupt:
                pass
            
            # Verify socket bindings
            assert mock_rep_socket.bind.called
            assert mock_pub_socket.bind.called
            
            # Verify message processing
            assert mock_rep_socket.recv_json.called
            assert mock_rep_socket.send_json.called
            mock_rep_socket.send_json.assert_called_with({"status": "success"})


@patch('app.api.doc_processor.extract_topics')
def test_process_document(mock_extract_topics, doc_processor):
    """Test processing a document."""
    # Create a temporary file
    content = """# Topic 1
Content for topic 1.

# Topic 2
Content for topic 2."""
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
        temp_file.write(content)
        filepath = temp_file.name
    
    try:
        # Mock extract_topics to return predefined topics
        mock_extract_topics.return_value = {
            "Topic 1": "# Topic 1\nContent for topic 1.",
            "Topic 2": "# Topic 2\nContent for topic 2."
        }
        
        # Mock the publish_topic method
        with patch.object(doc_processor, 'publish_topic', return_value=None) as mock_publish:
            result = doc_processor.process_document(filepath)
            
            # Verify extract_topics was called with file content
            mock_extract_topics.assert_called_once()
            
            # Verify publish_topic was called for each topic
            assert mock_publish.call_count == 2
            
            # Verify result
            assert result["status"] == "success"
            assert result["topics_found"] == 2
    finally:
        os.unlink(filepath)


@patch('app.api.doc_processor.zmq.Context')
def test_publish_topic(mock_context, doc_processor):
    """Test publishing a topic."""
    # Setup mock socket
    mock_socket = MagicMock()
    doc_processor.pub_socket = mock_socket
    
    # Call publish_topic
    doc_processor.publish_topic("Test Topic", "Test content")
    
    # Verify socket publish
    mock_socket.send_multipart.assert_called_once()