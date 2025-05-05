# Examples from This Repository

This repository provides practical examples of distributed systems principles:

## Stateless Services (Adder Example)

This example demonstrates a stateless API design - a foundational pattern in distributed systems. Stateless services don't store client-specific data between requests, making them horizontally scalable and resilient. Each request contains all the information needed to complete it, enabling any instance of the service to handle any request without coordination.

```python
# From adder-example/app/api/adder_service.py
@app.route('/add', methods=['POST'])
def add_numbers():
    data = request.get_json()
    
    # Validate input
    if not data or 'a' not in data or 'b' not in data:
        return jsonify({'error': 'Missing required parameters: a, b'}), 400
    
    try:
        a = float(data['a'])
        b = float(data['b'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Parameters must be numeric'}), 400
    
    # Stateless operation - no data stored between requests
    result = add(a, b)
    
    return jsonify({'result': result})
```

## Message-Based Communication (Document Analytics)

This example demonstrates publish-subscribe messaging using [ZeroMQ](https://zeromq.org/), a high-performance asynchronous messaging library. The pub-sub pattern is ideal for broadcasting messages to multiple consumers without needing to know who receives them, allowing for loose coupling between components. ZeroMQ handles the network communication details, making it easy to implement complex messaging patterns.

```python
# Document Processor broadcasts content by topic
def broadcast_content(topic, content):
    socket = zmq_context.socket(zmq.PUB)
    socket.connect(f"tcp://{BROADCASTER_HOST}:{BROADCASTER_PORT}")
    # Allow time for connection to establish
    time.sleep(0.1)
    
    # Topic-based message sending
    socket.send_multipart([
        topic.encode('utf-8'),  # Topic name as first frame
        json.dumps(content).encode('utf-8')  # Content as second frame
    ])
    socket.close()

# Topic Aggregator subscribes to specific topics
def subscribe_to_topic(topic):
    socket = zmq_context.socket(zmq.SUB)
    socket.connect(f"tcp://{BROADCASTER_HOST}:{BROADCASTER_PORT}")
    
    # Subscribe only to relevant topic
    socket.setsockopt(zmq.SUBSCRIBE, topic.encode('utf-8'))
    
    return socket
```

## Resource Management (Kubernetes API Integration)

The Document Analytics example shows proper resource cleanup:

```python
# Dynamic resource creation and cleanup
def create_workers(count):
    worker_pods = []
    try:
        for i in range(count):
            pod = create_worker_pod(f"doc-processor-{i}")
            worker_pods.append(pod)
        return worker_pods
    except Exception as e:
        # Clean up any created pods if there's an error
        for pod in worker_pods:
            try:
                delete_pod(pod.metadata.name)
            except Exception:
                logging.exception(f"Failed to delete pod {pod.metadata.name} during cleanup")
        raise e
```