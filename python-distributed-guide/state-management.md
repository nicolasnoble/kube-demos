# State Management

## Do:

✅ **Design stateless services whenever possible**

Statelessness means that each request to a service is processed independently, without relying on any stored information from previous requests. This makes services more reliable, scalable, and easier to manage in distributed environments.

Key benefits of stateless design:
- **Horizontal scalability**: New instances can be added without any special configuration
- **Resilience**: If an instance fails, any other instance can handle subsequent requests
- **Load balancing**: Requests can be routed to any available instance
- **Simplified deployment**: No need to worry about state migration during updates

✅ **Design idempotent APIs**

Idempotence means that making the same request multiple times has the same effect as making it once. This property is crucial in distributed systems where retries are common due to network issues or failures.

```python
# Good: Idempotent API that can be safely retried
@app.route('/orders/<order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    order = get_order(order_id)
    
    # Idempotent - returns same result regardless of how many times it's called
    if order.status != 'cancelled':
        order.status = 'cancelled'
        order.save()
    
    return jsonify({'status': 'cancelled', 'order_id': order_id})
```

✅ **Design stateless services whenever possible**

```python
# Good: Stateless service that doesn't store any data between requests
@app.route('/add', methods=['POST'])
def add_numbers():
    data = request.get_json()
    a = data.get('a', 0)
    b = data.get('b', 0)
    return jsonify({'result': a + b})
```

✅ **Use external databases or caches for state that must be shared**

In distributed systems, when state needs to be shared across multiple service instances, using an external data store is essential. [Redis](https://redis.io/) is an excellent choice for this purpose - it's an in-memory data structure store that can be used as a database, cache, message broker, and more. Its atomic operations make it particularly well-suited for counters, rate limiting, and other shared state scenarios.

```python
# Good: Using Redis for shared state
import redis

redis_client = redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'), 
                          port=int(os.environ.get('REDIS_PORT', 6379)))

@app.route('/increment', methods=['POST'])
def increment_counter():
    counter_name = request.get_json().get('counter', 'default')
    new_value = redis_client.incr(counter_name)
    return jsonify({'counter': counter_name, 'value': new_value})
```

✅ **Use local caching with TTL for frequently accessed data**

In distributed systems, properly implemented caching can significantly improve performance by reducing the need to repeatedly fetch the same data from external sources. Time-to-live (TTL) caching ensures data freshness by automatically expiring cached entries after a specified period, balancing performance with data accuracy.

```python
from functools import lru_cache
from datetime import datetime, timedelta

# Cache with time expiration
cache = {}
CACHE_TTL = timedelta(minutes=5)

def get_with_cache(key, data_fetcher):
    now = datetime.now()
    
    # Check if in cache and not expired
    if key in cache and now - cache[key]['timestamp'] < CACHE_TTL:
        return cache[key]['data']
    
    # Fetch fresh data
    data = data_fetcher()
    
    # Update cache
    cache[key] = {
        'data': data,
        'timestamp': now
    }
    
    return data
```

## Don't:

❌ **Don't use global variables to store mutable state**

```python
# Bad: Using global variable for state
request_count = 0  # Global state will not be shared across instances

@app.route('/counter')
def counter():
    global request_count
    request_count += 1
    return jsonify({'count': request_count})  # Will return different values on different pods
```

### Understanding Kubernetes Pods and Replicas

In Kubernetes, a **pod** is the smallest deployable unit that can be created and managed. A pod encapsulates one or more containers (such as your Python application), storage resources, and a unique network IP.

When you deploy your application to Kubernetes, it typically creates multiple replicas of your pod for:
- **High Availability**: If one pod fails, others continue serving requests
- **Scalability**: Handles increased load by distributing requests across pods
- **Zero-downtime deployments**: New pods can be created before old ones are terminated

This replication has important implications for state management:
- Each pod has its own memory space
- Global variables, in-memory caches, and local state exist independently in each pod
- A user request might be routed to any available pod
- Subsequent requests from the same user might be handled by different pods
- **Even with replicas set to 1**, Kubernetes may still migrate your pod to a different node during maintenance events, node failures, or cluster scaling, causing any in-memory state to be lost

> **Important:** Using `replicas: 1` does not guarantee your application will maintain its in-memory state throughout its lifecycle. Kubernetes may need to reschedule your pod to a different node during node maintenance, hardware failures, or resource constraints, causing all in-memory state to be lost.

❌ **Don't assume in-memory caches will be shared across service instances**

```python
# Bad: Assuming in-memory cache is shared across instances
cache = {}  # This cache is only local to this instance

@app.route('/data/<id>')
def get_data(id):
    if id in cache:
        return jsonify(cache[id])  # May miss cache hits if request goes to different instance
    
    data = fetch_data_from_db(id)
    cache[id] = data  # Only cached in this instance
    return jsonify(data)
```

❌ **Don't store session state directly in your application without proper synchronization**

```python
# Bad: Storing user sessions in local memory
sessions = {}  # Local to this instance

@app.route('/login', methods=['POST'])
def login():
    user_id = authenticate(request.json)
    if user_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {'user_id': user_id, 'logged_in_at': datetime.now()}
        return jsonify({'session_id': session_id})
    return jsonify({'error': 'Authentication failed'}), 401
```