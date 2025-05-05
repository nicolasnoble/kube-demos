"""Tests for the worker queue service."""

import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Add the parent directory to sys.path to allow imports from app.api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.api.worker_queue import WorkerQueue


@pytest.fixture
def worker_queue():
    """Create a WorkerQueue instance for testing."""
    return WorkerQueue()


def test_worker_queue_initialization(worker_queue):
    """Test that WorkerQueue initializes correctly."""
    assert worker_queue.documents == []
    assert worker_queue.workers == []


def test_register_documents(worker_queue):
    """Test registering documents with the worker queue."""
    documents = ["/path/to/doc1.md", "/path/to/doc2.md"]
    worker_queue.register_documents(documents)
    assert worker_queue.documents == documents


def test_register_worker(worker_queue):
    """Test registering a worker with the worker queue."""
    # Test with address format
    worker = {"id": "worker1", "address": "tcp://localhost:5555"}
    worker_queue.register_worker(worker)
    
    # Check if the converted worker (with url) is in the workers list
    assert any(w["id"] == "worker1" and w["url"] == "http://localhost:5555" for w in worker_queue.workers)
    
    # Test with url format
    worker2 = {"id": "worker2", "url": "http://localhost:5556"}
    worker_queue.register_worker(worker2)
    assert any(w["id"] == "worker2" and w["url"] == "http://localhost:5556" for w in worker_queue.workers)


@patch('app.api.worker_queue.requests')
def test_distribute_work_no_documents(mock_requests, worker_queue):
    """Test distributing work when there are no documents."""
    result = worker_queue.distribute_work()
    assert result == {"status": "completed", "processed": 0}
    # No HTTP requests should be made
    assert not mock_requests.post.called


@patch('app.api.worker_queue.requests')
def test_distribute_work_no_workers(mock_requests, worker_queue):
    """Test distributing work when there are no workers."""
    worker_queue.register_documents(["/path/to/doc1.md"])
    result = worker_queue.distribute_work()
    assert result == {"status": "error", "message": "No workers available"}
    # No HTTP requests should be made
    assert not mock_requests.post.called


@patch('app.api.worker_queue.requests')
def test_distribute_work(mock_requests, worker_queue):
    """Test distributing work to workers."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "topics": ["Topic1", "Topic2"]}
    mock_requests.post.return_value = mock_response
    
    # Register documents and workers
    worker_queue.register_documents(["/path/to/doc1.md", "/path/to/doc2.md"])
    worker_queue.register_worker({"id": "worker1", "url": "http://localhost:5555"})
    
    # Distribute work
    result = worker_queue.distribute_work()
    
    # Verify HTTP requests
    assert mock_requests.post.call_count == 2
    assert mock_requests.post.call_args[0][0].startswith("http://")
    assert mock_requests.post.call_args[1]["json"]["filepath"] in ["/path/to/doc1.md", "/path/to/doc2.md"]
    
    # Verify result
    assert result["status"] == "completed"
    assert result["processed"] == 2
    assert result["errors"] == 0