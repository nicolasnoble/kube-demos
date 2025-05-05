# Resilience Patterns

## Do:

✅ **Implement graceful degradation**

```python
def get_user_recommendations(user_id):
    try:
        # Try to get personalized recommendations
        return recommendation_service.get_personalized(user_id)
    except ServiceUnavailableError:
        try:
            # Fall back to category-based recommendations
            return recommendation_service.get_by_category(user_id)
        except ServiceUnavailableError:
            # Last resort: return default recommendations
            return get_default_recommendations()
```

✅ **Use health checks**

```python
@app.route('/health')
def health_check():
    # Check dependencies
    health_status = {
        "status": "healthy",
        "details": {
            "database": check_database_connection(),
            "cache": check_cache_connection(),
            "dependencies": {}
        }
    }
    
    # Check dependent services
    for service_name, service_url in DEPENDENT_SERVICES.items():
        health_status["details"]["dependencies"][service_name] = check_service_health(service_url)
    
    # If any critical dependency is unhealthy, report as unhealthy
    if not all([
        health_status["details"]["database"],
        health_status["details"]["cache"]
    ]):
        health_status["status"] = "unhealthy"
        return jsonify(health_status), 503
    
    return jsonify(health_status)
```

✅ **Implement backpressure mechanisms**

```python
import asyncio
from asyncio import Semaphore

class RateLimiter:
    def __init__(self, max_concurrent=10):
        self.semaphore = Semaphore(max_concurrent)
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.semaphore.release()

# Usage
rate_limiter = RateLimiter(max_concurrent=10)

async def process_request(request_data):
    async with rate_limiter:
        # Process request with controlled concurrency
        result = await perform_work(request_data)
        return result
```

## Don't:

❌ **Don't assume network calls will always succeed**

```python
# Bad: No error handling for network calls
def get_user_data(user_id):
    # This will crash if the request fails
    response = requests.get(f"http://user-service/api/users/{user_id}")
    return response.json()
```

❌ **Don't implement retries without backoff**

```python
# Bad: Retry without backoff
def send_with_retry(data, max_retries=3):
    for i in range(max_retries):
        try:
            return requests.post("http://service/api", json=data)
        except requests.RequestException:
            # Retrying immediately can overload the target service
            continue
    raise Exception("Failed after max retries")
```

❌ **Don't ignore specific exceptions by catching all exceptions**

```python
# Bad: Catching all exceptions
def process_data(data):
    try:
        result = some_complex_operation(data)
        return result
    except Exception:  # Too broad, catches programming errors too
        return None
```