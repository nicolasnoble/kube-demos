# Security Considerations

## Do:

✅ **Validate all input**

```python
from pydantic import BaseModel, validator, EmailStr

class UserInput(BaseModel):
    name: str
    email: EmailStr
    age: int
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name must not be empty')
        return v
    
    @validator('age')
    def age_must_be_positive(cls, v):
        if v < 0:
            raise ValueError('Age must be positive')
        return v

@app.route('/api/users', methods=['POST'])
def create_user():
    try:
        # Validate input against model
        user_data = UserInput.parse_obj(request.json)
        # Process valid data
        return jsonify({"status": "success"})
    except ValidationError as e:
        return jsonify({"status": "error", "errors": e.errors()}), 400
```

✅ **Implement proper authentication and authorization**

```python
from functools import wraps
from flask import request, jsonify, g
import jwt

SECRET_KEY = os.environ.get('JWT_SECRET_KEY')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            # Remove Bearer prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            # Decode token
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            g.user_id = data['user_id']
            g.roles = data.get('roles', [])
        except jwt.PyJWTError:
            return jsonify({'message': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    
    return decorated

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.get('roles') or role not in g.roles:
                return jsonify({'message': 'Permission denied'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/api/admin/users', methods=['GET'])
@token_required
@role_required('admin')
def get_all_users():
    # Only accessible by users with admin role
    users = get_users_from_db()
    return jsonify(users)
```

✅ **Use secure connections for all service communication**

```python
import requests
import ssl

def call_secure_service(endpoint, data):
    # Always use HTTPS for external services
    response = requests.post(
        f"https://{SERVICE_HOST}/api/{endpoint}",
        json=data,
        verify=True,  # Verify SSL certificate
        timeout=5
    )
    return response.json()
```

## Don't:

❌ **Don't hardcode secrets**

```python
# Bad: Hardcoded secrets
API_KEY = "1234567890abcdef"  # Never do this!

def call_external_api(data):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    return requests.post("https://api.example.com/v1/data", headers=headers, json=data)
```

❌ **Don't trust client-side data without validation**

```python
# Bad: Trusting client input without validation
@app.route('/api/users/<user_id>/update', methods=['POST'])
def update_user(user_id):
    # Accepting all input without validation
    user_data = request.json
    update_user_in_db(user_id, user_data)
    return jsonify({"status": "success"})
```

❌ **Don't expose sensitive endpoints without proper authentication**

```python
# Bad: Sensitive endpoint without authentication
@app.route('/api/reset-all-data', methods=['POST'])
def reset_all_data():
    # This dangerous endpoint has no authentication!
    clear_database()
    return jsonify({"status": "Database reset successful"})
```