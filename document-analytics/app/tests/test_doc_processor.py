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
    """Create a DocumentProcessor instance for testing with mocked ZMQ socket."""
    with patch('app.api.doc_processor.zmq.Context') as mock_context:
        # Setup a mock pub socket
        mock_pub_socket = MagicMock()
        mock_context.return_value.socket.return_value = mock_pub_socket
        
        processor = DocumentProcessor()
        # Ensure we're using the mock socket
        assert processor.pub_socket == mock_pub_socket
        return processor


def test_document_processor_initialization(doc_processor):
    """Test that DocumentProcessor initializes correctly."""
    assert doc_processor.pub_address == "tcp://*:5556"


@patch('app.api.doc_processor.zmq.Context')
def test_start_server(mock_context, doc_processor):
    """Test the Flask server initialization instead of the start_server method."""
    # Since DocumentProcessor now uses Flask instead of a start_server method,
    # we'll test that the Flask app is initialized properly
    from app.api.doc_processor import app as flask_app
    
    assert flask_app is not None
    # The app name is actually the module name, so we'll verify it contains 'doc_processor'
    assert 'doc_processor' in flask_app.name
    
    # Test the health_check endpoint
    with flask_app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert b'"status":"healthy"' in response.data


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


def test_publish_topic(doc_processor):
    """Test publishing a topic."""
    # pub_socket is already mocked in the fixture
    
    # Call publish_topic
    doc_processor.publish_topic("Test Topic", "Test content")
    
    # Verify socket publish
    doc_processor.pub_socket.send_multipart.assert_called_once_with([
        b'Test Topic',
        b'Test content'
    ])