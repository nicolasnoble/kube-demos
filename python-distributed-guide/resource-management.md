# Resource Management

## Do:

✅ **Close resources explicitly**

```python
# Good: Using context managers to ensure resources are closed
with open('file.txt', 'r') as f:
    data = f.read()

# For database connections
with db_engine.connect() as connection:
    result = connection.execute(query)
```

✅ **Set appropriate timeouts for all I/O operations**

```python
import socket

# Configure socket timeout
socket.setdefaulttimeout(10)  # 10 seconds

# Configure request timeout
response = requests.get(url, timeout=(3.05, 27))  # (connect timeout, read timeout)
```

✅ **Use connection pooling**

```python
import psycopg2
from psycopg2 import pool

# Create a connection pool
connection_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    user="user",
    password="password",
    host="db.example.com",
    port="5432",
    database="mydb"
)

def execute_query(query, params=None):
    conn = connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    finally:
        # Always return the connection to the pool
        connection_pool.putconn(conn)
```

### Resource Management (Kubernetes API Integration)

This example showcases proper resource management when working with the Kubernetes API. When creating dynamic resources like containers or pods, proper cleanup is essential to prevent resource leaks. The [Kubernetes Python client](https://github.com/kubernetes-client/python) allows programmatic interaction with Kubernetes clusters and demonstrates the importance of proper resource lifecycle management in distributed systems.

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

## Don't:

❌ **Don't create unbounded resources**

```python
# Bad: Creating new connection for every request
@app.route('/query')
def run_query():
    # Creates a new connection each time
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM data")
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(result)
```

❌ **Don't leave resources open**

```python
# Bad: Resources not properly closed
def read_file_data(filename):
    f = open(filename, 'r')  # File handle is never closed
    data = f.read()
    return data
```

❌ **Don't cache connections indefinitely**

```python
# Bad: Creating "permanent" connections
# Module-level client that's never refreshed
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

def get_cache_data(key):
    # Using the stale connection - might be disconnected
    return redis_client.get(key)
```