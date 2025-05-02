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
    worker = {"id": "worker1", "address": "tcp://localhost:5555"}
    worker_queue.register_worker(worker)
    assert worker in worker_queue.workers


@patch('app.api.worker_queue.zmq.Context')
def test_distribute_work_no_documents(mock_context, worker_queue):
    """Test distributing work when there are no documents."""
    result = worker_queue.distribute_work()
    assert result == {"status": "completed", "processed": 0}
    assert not mock_context.called


@patch('app.api.worker_queue.zmq.Context')
def test_distribute_work_no_workers(mock_context, worker_queue):
    """Test distributing work when there are no workers."""
    worker_queue.register_documents(["/path/to/doc1.md"])
    result = worker_queue.distribute_work()
    assert result == {"status": "error", "message": "No workers available"}
    assert not mock_context.called


@patch('app.api.worker_queue.zmq.Context')
def test_distribute_work(mock_context, worker_queue):
    """Test distributing work to workers."""
    # Setup mock socket
    mock_socket = MagicMock()
    mock_context.return_value.socket.return_value = mock_socket
    mock_socket.recv_json.return_value = {"status": "success"}
    
    # Register documents and workers
    worker_queue.register_documents(["/path/to/doc1.md", "/path/to/doc2.md"])
    worker_queue.register_worker({"id": "worker1", "address": "tcp://localhost:5555"})
    
    # Distribute work
    result = worker_queue.distribute_work()
    
    # Verify socket connections and communications
    assert mock_context.return_value.socket.called
    assert mock_socket.connect.called
    assert mock_socket.send_json.call_count == 2
    assert result["status"] == "completed"
    assert result["processed"] == 2