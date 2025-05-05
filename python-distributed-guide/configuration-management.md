# Configuration Management

## Do:

✅ **Use environment variables for configuration**

```python
import os

# Good: Reading configuration from environment variables
database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/mydb')
debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'
log_level = os.environ.get('LOG_LEVEL', 'INFO')
```

✅ **Use Kubernetes ConfigMaps and Secrets**

Kubernetes provides two resource types specifically designed for configuration:

1. **ConfigMaps** - For non-sensitive configuration data
2. **Secrets** - For sensitive information like passwords and API keys

### How Kubernetes propagates environment variables:

In a Kubernetes deployment file, you can specify environment variables that will be available to your container:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  template:
    spec:
      containers:
      - name: myapp
        image: myapp:latest
        env:
        - name: DATABASE_URL
          value: "postgresql://dbuser:password@postgres-service:5432/mydb"
        - name: LOG_LEVEL
          value: "INFO"
        # Using values from ConfigMaps
        - name: REDIS_HOST
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: redis.host
        # Using values from Secrets
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: api-key
```

### Using ConfigMaps:

ConfigMaps can be created and used in multiple ways:

1. **Creating a ConfigMap:**
```bash
# From literal values
kubectl create configmap app-config \
  --from-literal=redis.host=redis-service \
  --from-literal=redis.port=6379

# From a file
kubectl create configmap app-config --from-file=config.json
```

2. **Using ConfigMaps as environment variables:**
```python
# ConfigMap values are automatically available as environment variables
redis_host = os.environ.get('REDIS_HOST')
```

3. **Mounting ConfigMaps as volumes:**
```python
# ConfigMap can be mounted as a volume or exposed as environment variables
# Reading from mounted ConfigMap
with open('/config/app-config.json', 'r') as f:
    config = json.load(f)

# Reading from mounted Secret
with open('/secrets/api-key', 'r') as f:
    api_key = f.read().strip()
```

The Kubernetes volume mount for the above would look like:
```yaml
volumes:
- name: config-volume
  configMap:
    name: app-config
containers:
- name: app
  volumeMounts:
  - name: config-volume
    mountPath: /config
```

✅ **Support multiple configuration sources with appropriate overrides**

```python
import configparser
import os

def load_config():
    config = configparser.ConfigParser()
    
    # Load defaults
    config.read('defaults.ini')
    
    # Override with environment-specific config if it exists
    env = os.environ.get('ENVIRONMENT', 'development')
    config.read(f'{env}.ini')
    
    # Override with environment variables
    for section in config.sections():
        for key in config[section]:
            env_var = f"{section.upper()}_{key.upper()}"
            if env_var in os.environ:
                config[section][key] = os.environ[env_var]
    
    return config
```

## Don't:

❌ **Don't hardcode configuration values**

```python
# Bad: Hardcoded configuration
DATABASE_URL = "postgresql://user:password@db.example.com/mydb"
API_KEY = "1234567890abcdef"
```

❌ **Don't store secrets in code or configuration files**

```python
# Bad: Secrets in config file
config = {
    "database": {
        "user": "admin",
        "password": "super_secret_password",  # Don't do this!
        "host": "db.example.com"
    }
}
```

❌ **Don't reload configuration files frequently without caching**

```python
# Bad: Reading config file on every request
@app.route('/api/data')
def get_data():
    # This reads the config file on every request!
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    return fetch_data_using_config(config)
```