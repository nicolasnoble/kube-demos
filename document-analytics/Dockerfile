FROM python:3.9-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port for the API
EXPOSE 8080

# Command to run when container starts
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app.app:app"]