# Communication Patterns

## Do:

✅ **Use RESTful APIs for synchronous request-response interactions**

[REST (Representational State Transfer)](https://en.wikipedia.org/wiki/REST) is an architectural style for designing networked applications. RESTful services use standard HTTP methods (GET, POST, PUT, DELETE) to perform CRUD operations on resources identified by URLs. This approach enables stateless, cacheable communication between distributed services.

**Server-side implementation using Flask:**
```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/items', methods=['GET'])
def get_items():
    # Return a list of items
    return jsonify({"items": ["item1", "item2", "item3"]})

@app.route('/api/items/<item_id>', methods=['GET'])
def get_item(item_id):
    # Return a specific item
    return jsonify({"id": item_id, "name": f"Item {item_id}"})

@app.route('/api/items', methods=['POST'])
def create_item():
    # Create a new item from the request data
    new_item = request.json
    # ... save the item ...
    return jsonify({"status": "created", "item": new_item}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**Client-side implementation:**
```python
import requests

def call_service(service_url, payload):
    try:
        response = requests.post(
            f"http://{service_url}/api/item",
            json=payload,
            timeout=5  # Always include timeouts
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # Handle errors appropriately
        logging.error(f"Service call failed: {e}")
        raise ServiceCallException(f"Failed to call {service_url}: {str(e)}")
```

✅ **Implement retry logic with exponential backoff**

Automatic retries can improve resilience, but should primarily be used for idempotent operations (operations that produce the same result regardless of how many times they're executed). GET requests are typically idempotent, while POST operations may not be. Be careful when implementing retries for non-idempotent operations, as they can create duplicate records or unexpected side effects.

```python
import time
import random
import logging

def call_with_retry(func, max_retries=3, base_delay=1, max_delay=10):
    """
    Retry pattern for remote service calls in distributed systems.
    
    Args:
        func: Function that makes the remote API/service call
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay before first retry (seconds)
        max_delay: Maximum delay between retries (seconds)
    """
    retries = 0
    while True:
        try:
            # func() represents a remote service call that might fail
            # due to network issues, service unavailability, etc.
            return func()
        except Exception as e:
            retries += 1
            if retries > max_retries:
                raise
            
            # Calculate delay with exponential backoff and jitter
            delay = min(base_delay * (2 ** (retries - 1)) + random.uniform(0, 1), max_delay)
            logging.warning(f"Retry attempt {retries} after {delay:.2f}s due to: {e}")
            time.sleep(delay)
```

> **Note on Distributed Systems Consistency**: Implementing retry logic can help with transient failures, but it's challenging to guarantee strict consistency in distributed systems, especially during network partitions or partial failures. Consider using distributed transactions, sagas, or event sourcing patterns for operations requiring strong consistency guarantees across multiple services.

✅ **Use message queues for asynchronous processing**

Message queues are essential for building resilient, loosely-coupled distributed systems. [RabbitMQ](https://www.rabbitmq.com/) is a popular message broker that implements the Advanced Message Queuing Protocol (AMQP). It enables asynchronous processing by allowing services to communicate without requiring immediate responses, improving system resilience and scalability.

```python
import pika

def publish_message(queue_name, message):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=os.environ.get('RABBITMQ_HOST', 'localhost'))
    )
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)  # Durable queue survives restarts
    channel.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  # Make message persistent
        )
    )
    connection.close()
```

✅ **Implement circuit breakers to prevent cascading failures**

Circuit breakers are a crucial resilience pattern in distributed systems, inspired by electrical circuit breakers. [Hystrix](https://github.com/Netflix/Hystrix) popularized this pattern in microservices. Circuit breakers monitor for failures and prevent repeated calls to failing services, providing time for recovery and avoiding system-wide cascading failures.

```python
import time
from functools import wraps

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.open_since = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.open_since > self.recovery_timeout:
                    self.state = "HALF-OPEN"
                else:
                    raise CircuitBreakerOpenException("Circuit breaker is open")
            
            try:
                result = func(*args, **kwargs)
                if self.state == "HALF-OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold or self.state == "HALF-OPEN":
                    self.state = "OPEN"
                    self.open_since = time.time()
                raise e
        
        return wrapper
```

✅ **Use asyncio for efficient parallel requests**

When your application needs to make multiple API calls to different services, using Python's asyncio library can significantly improve performance by enabling non-blocking I/O operations. This is especially useful in distributed systems where waiting for multiple remote service responses can create bottlenecks.

```python
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any

async def fetch_data(session: aiohttp.ClientSession, url: str, timeout: int = 5) -> Dict[str, Any]:
    """Asynchronously fetch data from a service endpoint."""
    try:
        async with session.get(url, timeout=timeout) as response:
            response.raise_for_status()
            return await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logging.error(f"Failed to fetch data from {url}: {str(e)}")
        raise

async def fetch_multiple_services(endpoints: List[str]) -> List[Dict[str, Any]]:
    """Fetch data from multiple service endpoints in parallel."""
    async with aiohttp.ClientSession() as session:
        # Create a list of coroutines to run concurrently
        tasks = [fetch_data(session, url) for url in endpoints]
        
        # Wait for all requests to complete, even if some fail
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results, handling any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"Request to {endpoints[i]} failed: {str(result)}")
                processed_results.append({"error": str(result), "endpoint": endpoints[i]})
            else:
                processed_results.append(result)
        
        return processed_results

# Example usage
def get_all_service_data():
    services = [
        "http://user-service/api/users",
        "http://product-service/api/products",
        "http://order-service/api/orders"
    ]
    
    # Create an event loop and run the async function
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(fetch_multiple_services(services))
    return results
```

For applications that are already fully async (like FastAPI-based services), you can integrate async calls more naturally:

```python
from fastapi import FastAPI, HTTPException
import aiohttp

app = FastAPI()

@app.get("/aggregated-data")
async def get_aggregated_data():
    """Endpoint that aggregates data from multiple backend services."""
    services = [
        "http://service-a/api/data",
        "http://service-b/api/data",
        "http://service-c/api/data"
    ]
    
    try:
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_data(session, url) for url in services]
            results = await asyncio.gather(*tasks)
            
            # Process and combine the results
            return {
                "service_a_data": results[0],
                "service_b_data": results[1],
                "service_c_data": results[2],
                "aggregated_at": datetime.now().isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to aggregate data: {str(e)}")
```

Benefits of using asyncio for parallel requests:
- **Improved performance**: Make multiple requests concurrently without blocking
- **Better resource utilization**: Avoid idle waiting time while waiting for responses
- **Reduced latency**: Overall response time is close to the slowest single request instead of the sum of all requests
- **Graceful error handling**: Individual request failures don't block other requests
- **Configurable timeouts**: Each request can have custom timeout settings

✅ **Use service discovery through Kubernetes DNS**

Kubernetes provides a built-in DNS service that allows pods to discover and communicate with each other using consistent DNS names, eliminating the need for hardcoded IPs or manual service discovery.

**How Kubernetes DNS works:**

Kubernetes automatically assigns DNS names to services in the following format:
```
<service-name>.<namespace>.svc.cluster.local
```

- **service-name**: The name of the Kubernetes service
- **namespace**: The Kubernetes namespace where the service is deployed (defaults to "default")
- **svc.cluster.local**: The cluster domain suffix

For services in the same namespace, you can simply use `<service-name>` as the hostname.

**Python client example:**
```python
import requests

def call_service(service_name, endpoint, payload, namespace="default"):
    """Call a service using Kubernetes DNS for service discovery.
    
    Args:
        service_name: Kubernetes service name
        endpoint: API endpoint path
        payload: Request data
        namespace: Kubernetes namespace where service is deployed
    """
    # For services in the same namespace, just the service name works
    service_url = service_name
    
    # For services in different namespaces, use the fully qualified domain name
    if namespace != "default":
        service_url = f"{service_name}.{namespace}.svc.cluster.local"
    
    try:
        response = requests.post(
            f"http://{service_url}/{endpoint.lstrip('/')}",
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Service call failed: {e}")
        raise ServiceCallException(f"Failed to call {service_name}: {str(e)}")
```

**Headless services** allow direct DNS lookup for individual pod IPs using:
```
<pod-name>.<service-name>.<namespace>.svc.cluster.local
```

This DNS-based service discovery eliminates hardcoded IPs and enables automatic load balancing, improved resilience, and simplified service communication.

## Don't:

❌ **Don't use fixed IPs or hostnames without service discovery**

```python
# Bad: Hardcoded service URLs
def get_user_data(user_id):
    # Hardcoded URL will fail if service moves or scales
    response = requests.get(f"http://10.0.1.5:8080/api/users/{user_id}")
    return response.json()
```

❌ **Don't make synchronous calls without timeouts**

```python
# Bad: No timeout on request
def fetch_data_no_timeout():
    # This could hang indefinitely if the service is unresponsive
    response = requests.get("http://api-service/data")
    return response.json()
```

❌ **Don't create tight coupling between services**

Tight coupling occurs when services have strong dependencies on each other, making them difficult to modify, test, and deploy independently. In a tightly coupled system, changes to one service often require changes to other services, leading to cascading failures and deployment challenges.

**Drawbacks of tight coupling:**
- **Reduced resilience**: Failures in one service directly impact dependent services
- **Limited scalability**: Services can't scale independently based on their own resource needs
- **Deployment complexity**: Services must be deployed in a specific order or together
- **Testing difficulties**: Components can't be tested in isolation
- **Poor maintainability**: Changes to one service may require changes to multiple services
- **Technology lock-in**: Difficulty adopting new technologies for individual services

```python
# Bad: Tightly coupled services
class UserService:
    def create_user(self, user_data):
        # Create user
        user = self.user_repository.save(user_data)
        
        # Directly calling other services creates tight coupling
        billing_service.create_account(user.id)
        email_service.send_welcome_email(user.email)
        
        return user
```

**Better approach - loose coupling:**
```python
# Good: Loosely coupled using events/messaging
class UserService:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.user_repository = UserRepository()
    
    def create_user(self, user_data):
        # Create user
        user = self.user_repository.save(user_data)
        
        # Publish event instead of direct service calls
        self.event_bus.publish("user.created", {
            "user_id": user.id,
            "email": user.email,
            "timestamp": datetime.now().isoformat()
        })
        
        return user

# Services independently subscribe to events they care about
def setup_billing_service(event_bus):
    def handle_user_created(event):
        billing_service.create_account(event["user_id"])
    
    event_bus.subscribe("user.created", handle_user_created)

def setup_notification_service(event_bus):
    def handle_user_created(event):
        email_service.send_welcome_email(event["email"])
    
    event_bus.subscribe("user.created", handle_user_created)
```
