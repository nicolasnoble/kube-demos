"""Tests for the topic aggregator service."""

import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Add the parent directory to sys.path to allow imports from app.api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.api.topic_aggregator import TopicAggregator


@pytest.fixture
def topic_aggregator():
    """Create a TopicAggregator instance for testing."""
    return TopicAggregator("Test Topic")


def test_topic_aggregator_initialization(topic_aggregator):
    """Test that TopicAggregator initializes correctly."""
    assert topic_aggregator.topic == "Test Topic"
    assert topic_aggregator.line_count == 0
    assert topic_aggregator.word_count == 0
    assert topic_aggregator.char_count == 0
    assert topic_aggregator.doc_count == 0


@patch('app.api.topic_aggregator.analyze_content')
def test_process_content(mock_analyze_content, topic_aggregator):
    """Test processing content."""
    mock_analyze_content.return_value = {
        "line_count": 10,
        "word_count": 50,
        "char_count": 200
    }
    
    topic_aggregator.process_content("Test content")
    
    # Verify analyze_content was called
    mock_analyze_content.assert_called_once_with("Test content")
    
    # Verify metrics were updated
    assert topic_aggregator.line_count == 10
    assert topic_aggregator.word_count == 50
    assert topic_aggregator.char_count == 200
    assert topic_aggregator.doc_count == 1


def test_get_metrics(topic_aggregator):
    """Test getting metrics."""
    # Set some metrics
    topic_aggregator.line_count = 10
    topic_aggregator.word_count = 50
    topic_aggregator.char_count = 200
    topic_aggregator.doc_count = 2
    
    metrics = topic_aggregator.get_metrics()
    
    # Verify returned metrics
    assert metrics["topic"] == "Test Topic"
    assert metrics["line_count"] == 10
    assert metrics["word_count"] == 50
    assert metrics["char_count"] == 200
    assert metrics["doc_count"] == 2


@patch('app.api.topic_aggregator.zmq.Context')
def test_start_server(mock_context, topic_aggregator):
    """Test starting the topic aggregator server."""
    # Setup mock sockets
    mock_sub_socket = MagicMock()
    mock_rep_socket = MagicMock()
    mock_context.return_value.socket.side_effect = [mock_sub_socket, mock_rep_socket]
    
    # Mock the poll method to return once and then raise an exception to exit the loop
    mock_poller = MagicMock()
    mock_poller.poll.side_effect = [
        [(mock_sub_socket, 1)],  # First poll - sub socket has a message
        [(mock_rep_socket, 1)],  # Second poll - rep socket has a message
        KeyboardInterrupt        # Third poll - exit the loop
    ]
    
    # Setup socket responses
    mock_sub_socket.recv_multipart.return_value = [b"Test Topic", b"Test content"]
    mock_rep_socket.recv_json.return_value = {"action": "get_metrics"}
    
    # Patch ZMQ Poller class
    with patch('app.api.topic_aggregator.zmq.Poller', return_value=mock_poller):
        # Instead of expecting KeyboardInterrupt, we'll check if the code processes messages
        try:
            topic_aggregator.start_server()
        except KeyboardInterrupt:
            pass
        
        # Verify socket bindings and subscriptions
        assert mock_sub_socket.connect.called
        assert mock_sub_socket.setsockopt.called  # For setting the subscription
        assert mock_rep_socket.bind.called
        
        # Verify message processing
        assert mock_sub_socket.recv_multipart.called
        assert mock_rep_socket.recv_json.called
        assert mock_rep_socket.send_json.called