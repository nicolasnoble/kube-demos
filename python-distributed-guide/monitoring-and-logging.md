# Monitoring and Logging

## Do:

✅ **Implement structured logging**

Structured logging is essential in distributed systems for effective monitoring and troubleshooting. Unlike traditional text-based logs, structured logs (typically in JSON format) can be easily parsed, indexed, and analyzed by log management systems like [ELK Stack](https://www.elastic.co/elastic-stack/) or [Grafana Loki](https://grafana.com/oss/loki/). This approach enables powerful querying and visualization capabilities across distributed services.

```python
import logging
import json

class JsonFormatter(logging.Formatter):
    def __init__(self):
        super().__init__()
    
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if hasattr(record, 'request_id'):
            log_record["request_id"] = record.request_id
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record)

# Set up logger with the JSON formatter
logger = logging.getLogger("app")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage
logger.info("Processing request", extra={"request_id": request_id})
```

✅ **Add correlation IDs for distributed tracing**

Distributed tracing is essential for understanding request flow across microservices. [OpenTelemetry](https://opentelemetry.io/) and [Jaeger](https://www.jaegertracing.io/) are popular open-source tracing systems that help visualize service interactions. Correlation IDs (also called trace IDs) allow you to track a single request as it passes through multiple services, making it possible to identify bottlenecks and troubleshoot issues.

```python
import uuid
from flask import Flask, request, g

app = Flask(__name__)

@app.before_request
def add_request_id():
    # Get request ID from header or generate a new one
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    g.request_id = request_id

@app.after_request
def add_request_id_header(response):
    # Add request ID to response headers
    response.headers.add('X-Request-ID', g.request_id)
    return response

def log_with_context(message, level="info"):
    # Include request ID in logs
    getattr(logger, level)(message, extra={"request_id": g.request_id})
```

✅ **Expose health and metrics endpoints**

Observability is crucial in distributed systems. [Prometheus](https://prometheus.io/) is a popular monitoring system and time series database that collects metrics from monitored targets. Exposing metrics endpoints allows for real-time monitoring of service health, performance, and business metrics, enabling proactive identification of issues before they affect users.

```python
from prometheus_client import Counter, Histogram, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# Prometheus metrics
request_counter = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'status'])
request_latency = Histogram('http_request_duration_seconds', 'HTTP Request Latency', ['method', 'endpoint'])

@app.route('/metrics')
def metrics():
    return make_wsgi_app()

@app.before_request
def start_timer():
    g.start_time = time.time()

@app.after_request
def record_metrics(response):
    request_latency.labels(
        method=request.method, 
        endpoint=request.path
    ).observe(time.time() - g.start_time)
    
    request_counter.labels(
        method=request.method, 
        endpoint=request.path,
        status=response.status_code
    ).inc()
    
    return response
```

✅ **Implement Kubernetes health checks for container lifecycle management**

Kubernetes relies on health checking mechanisms to determine if a pod is functioning properly or needs to be restarted. These probes are critical for maintaining high availability in distributed applications. Kubernetes supports three types of health checks:

1. **Liveness Probes**: Determine if a container is running. If the liveness probe fails, Kubernetes will restart the container.
2. **Readiness Probes**: Determine if a container is ready to accept traffic. If the readiness probe fails, the container will be removed from service load balancers.
3. **Startup Probes**: Used to determine when an application has started. Startup probes are useful for containers that require a long time to start.

Here's how to implement health checks in a Flask application:

```python
from flask import Flask, jsonify

app = Flask(__name__)

# Simple health check endpoints
@app.route('/health/live')
def liveness():
    # Check critical components that indicate if the app is "alive"
    # Return 200 if functioning, non-200 if it needs to be restarted
    return jsonify({"status": "alive"}), 200

@app.route('/health/ready')
def readiness():
    # Check if the app can accept traffic (e.g., database connections are working)
    db_available = check_database_connection()
    dependencies_available = check_dependent_services()
    
    if db_available and dependencies_available:
        return jsonify({"status": "ready"}), 200
    else:
        # Return 503 if the service is temporarily unavailable
        return jsonify({
            "status": "not ready",
            "database": db_available,
            "dependencies": dependencies_available
        }), 503
```

These health check endpoints can then be configured in your Kubernetes deployments:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-python-app
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: python-app
        image: myapp:latest
        livenessProbe:
          httpGet:
            path: /health/live
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
```

By properly implementing these health checks:
- Kubernetes can automatically restart containers that have crashed or become unresponsive
- Services experiencing temporary issues won't receive traffic until they're ready
- New deployments can be safely rolled out, ensuring traffic is only sent to containers ready to handle it
- The overall resilience of your distributed system is significantly improved

Remember that health checks should be lightweight and fast, as they're called frequently. They should verify essential dependencies but avoid performing complex operations that might overload your application.

## Don't:

❌ **Don't log sensitive information**

```python
# Bad: Logging sensitive data
@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    
    # Don't log passwords!
    logging.info(f"Login attempt: username={username}, password={password}")
    
    # Authenticate user
    if authenticate(username, password):
        return jsonify({"status": "success"})
    return jsonify({"status": "failed"}), 401
```

❌ **Don't use print statements for logging in production code**

```python
# Bad: Using print instead of logging
def process_order(order):
    print(f"Processing order {order.id}")  # Will go to stdout without proper formatting
    
    if order.is_valid():
        print(f"Order {order.id} is valid")
        # Process the order
    else:
        print(f"Order {order.id} is invalid")  # No log level, difficult to filter
```

❌ **Don't log without context**

```python
# Bad: Logs without context
def process_data(data):
    logging.info("Processing data")  # What data? Which request?
    
    if not validate(data):
        logging.error("Validation failed")  # No details about what failed
        return False
    
    result = perform_processing(data)
    logging.info("Processing complete")  # No information about the outcome
    return result
```