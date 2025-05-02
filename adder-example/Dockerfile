FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .
COPY adder_lib/ ./adder_lib/

# Expose port for API
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]